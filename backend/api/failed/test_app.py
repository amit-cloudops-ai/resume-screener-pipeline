"""Moto-backed failed-job list and retry tests."""
import json

import boto3
import pytest
from moto import mock_aws

from backend.api.failed.app import lambda_handler

JOB = "a1b2c3d4e5f6"
CANDIDATE = "0123456789abcdef"


@pytest.fixture
def resources(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("FAILED_TABLE", "rs-dev-failed-jobs")
    monkeypatch.setenv("CANDIDATES_TABLE", "rs-dev-candidates")
    monkeypatch.setenv("PARSE_QUEUE_URL", "https://sqs.us-east-1.amazonaws.com/123/parse")
    monkeypatch.setenv("JD_QUEUE_URL", "https://sqs.us-east-1.amazonaws.com/123/jd")
    monkeypatch.setenv("SCORE_QUEUE_URL", "https://sqs.us-east-1.amazonaws.com/123/score")
    monkeypatch.setenv("UPLOADS_BUCKET", "rs-dev-uploads-test")
    monkeypatch.setenv("CORS_ORIGIN", "https://dashboard.example.test")
    with mock_aws():
        ddb = boto3.resource("dynamodb", region_name="us-east-1")
        failed = ddb.create_table(
            TableName="rs-dev-failed-jobs",
            KeySchema=[{"AttributeName": "failed_id", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "failed_id", "AttributeType": "S"},
                {"AttributeName": "job_id", "AttributeType": "S"},
                {"AttributeName": "created_at", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[{
                "IndexName": "job_id-created_at",
                "KeySchema": [
                    {"AttributeName": "job_id", "KeyType": "HASH"},
                    {"AttributeName": "created_at", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            }],
            BillingMode="PAY_PER_REQUEST",
        )
        candidates = ddb.create_table(
            TableName="rs-dev-candidates",
            KeySchema=[
                {"AttributeName": "job_id", "KeyType": "HASH"},
                {"AttributeName": "candidate_id", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "job_id", "AttributeType": "S"},
                {"AttributeName": "candidate_id", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        sqs = boto3.client("sqs", region_name="us-east-1")
        queue_urls = {
            "PARSE_QUEUE_URL": sqs.create_queue(QueueName="parse")["QueueUrl"],
            "JD_QUEUE_URL": sqs.create_queue(QueueName="jd")["QueueUrl"],
            "SCORE_QUEUE_URL": sqs.create_queue(QueueName="score")["QueueUrl"],
        }
        for key, value in queue_urls.items():
            monkeypatch.setenv(key, value)
        failed.put_item(Item={
            "failed_id": "fail-1", "job_id": JOB, "stage": "PARSE",
            "s3_key": f"resumes/{JOB}/resume.pdf", "error_type": "TRANSIENT_EXHAUSTED",
            "error_message": "retry exhausted", "attempts": 3,
            "message_id": "message-1", "status": "OPEN", "created_at": "2026-11-24T00:00:00Z",
        })
        failed.put_item(Item={
            "failed_id": "fail-2", "job_id": JOB, "stage": "SCORE",
            "s3_key": f"resumes/{JOB}/resume.pdf", "error_type": "TRANSIENT_EXHAUSTED",
            "error_message": "score retry exhausted", "attempts": 5,
            "message_id": "message-2", "status": "OPEN", "created_at": "2026-11-24T00:01:00Z",
        })
        candidates.put_item(Item={
            "job_id": JOB, "candidate_id": CANDIDATE,
            "source_key": f"resumes/{JOB}/resume.pdf", "status": "SCORED",
        })
        yield failed, candidates, sqs, queue_urls


def event(method, resource, path=None, query=None):
    return {
        "httpMethod": method, "resource": resource,
        "pathParameters": path or {}, "queryStringParameters": query,
    }


def body(response):
    return json.loads(response["body"])


def test_list_failed_jobs_and_filter_by_job(resources):
    response = lambda_handler(event("GET", "/failed-jobs"), None)
    assert response["statusCode"] == 200
    assert len(body(response)["failed_jobs"]) == 2
    filtered = lambda_handler(event("GET", "/failed-jobs", query={"job_id": JOB}), None)
    assert len(body(filtered)["failed_jobs"]) == 2


def test_retry_parse_reconstructs_s3_event(resources):
    failed, _, sqs, urls = resources
    response = lambda_handler(
        event("POST", "/failed-jobs/{failed_id}/retry", {"failed_id": "fail-1"}), None
    )
    assert response["statusCode"] == 202
    item = body(response)
    assert item["status"] == "RETRIED"
    assert item["attempts"] == 4
    message = json.loads(sqs.receive_message(QueueUrl=urls["PARSE_QUEUE_URL"])["Messages"][0]["Body"])
    assert message["Records"][0]["s3"]["bucket"]["name"] == "rs-dev-uploads-test"
    assert message["Records"][0]["s3"]["object"]["key"] == f"resumes/{JOB}/resume.pdf"


def test_retry_score_reconstructs_frozen_score_message(resources):
    _, _, sqs, urls = resources
    response = lambda_handler(
        event("POST", "/failed-jobs/{failed_id}/retry", {"failed_id": "fail-2"}), None
    )
    assert response["statusCode"] == 202
    message = json.loads(sqs.receive_message(QueueUrl=urls["SCORE_QUEUE_URL"])["Messages"][0]["Body"])
    assert message == {"job_id": JOB, "candidate_id": CANDIDATE, "reason": "RESCORE"}


def test_missing_and_already_retried_failed_job(resources):
    failed, _, _, _ = resources
    missing = lambda_handler(
        event("POST", "/failed-jobs/{failed_id}/retry", {"failed_id": "absent"}), None
    )
    assert missing["statusCode"] == 404
    failed.update_item(
        Key={"failed_id": "fail-1"},
        UpdateExpression="SET #s = :retried",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":retried": "RETRIED"},
    )
    duplicate = lambda_handler(
        event("POST", "/failed-jobs/{failed_id}/retry", {"failed_id": "fail-1"}), None
    )
    assert duplicate["statusCode"] == 409


def test_unknown_stage_is_not_retried(resources):
    failed, _, _, _ = resources
    failed.put_item(Item={
        "failed_id": "fail-unknown", "job_id": JOB, "stage": "UNKNOWN",
        "s3_key": "unknown", "error_type": "UNKNOWN", "error_message": "unknown",
        "attempts": 1, "status": "OPEN", "created_at": "2026-11-24T00:02:00Z",
    })
    response = lambda_handler(
        event("POST", "/failed-jobs/{failed_id}/retry", {"failed_id": "fail-unknown"}), None
    )
    assert response["statusCode"] == 409
