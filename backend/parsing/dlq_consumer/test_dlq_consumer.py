"""Moto-backed DLQ consumer tests."""
import json

import boto3
from moto import mock_aws
import pytest

from backend.parsing.dlq_consumer.app import lambda_handler

JOB = "a1b2c3d4e5f6"
CANDIDATE = "0123456789abcdef"


@pytest.fixture
def tables(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("FAILED_TABLE", "rs-dev-failed-jobs")
    monkeypatch.setenv("CANDIDATES_TABLE", "rs-dev-candidates")
    with mock_aws():
        ddb = boto3.resource("dynamodb", region_name="us-east-1")
        failed = ddb.create_table(
            TableName="rs-dev-failed-jobs",
            KeySchema=[{"AttributeName": "failed_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "failed_id", "AttributeType": "S"}],
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
        candidates.put_item(Item={
            "job_id": JOB, "candidate_id": CANDIDATE,
            "source_key": f"resumes/{JOB}/resume.pdf", "status": "PARSED",
        })
        yield failed, candidates


def record(stage, body, message_id="message-1"):
    queue = {"PARSE": "parse-dlq", "JD_PARSE": "jd-dlq", "SCORE": "score-dlq"}[stage]
    return {
        "messageId": message_id,
        "eventSourceARN": f"arn:aws:sqs:us-east-1:123456789012:rs-dev-{queue}",
        "attributes": {"ApproximateReceiveCount": "3"},
        "body": body,
    }


def test_parse_dlq_writes_failed_job_record(tables):
    failed, _ = tables
    body = json.dumps({"Records": [{
        "s3": {"bucket": {"name": "uploads"}, "object": {"key": f"resumes/{JOB}/resume.pdf"}},
    }]})
    result = lambda_handler({"Records": [record("PARSE", body)]}, None)
    assert result == {"batchItemFailures": []}
    item = failed.scan()["Items"][0]
    assert item["stage"] == "PARSE"
    assert item["job_id"] == JOB
    assert item["s3_key"] == f"resumes/{JOB}/resume.pdf"
    assert item["error_type"] == "TRANSIENT_EXHAUSTED"
    assert item["attempts"] == 3


def test_score_dlq_resolves_candidate_source_key(tables):
    failed, _ = tables
    body = json.dumps({"job_id": JOB, "candidate_id": CANDIDATE, "reason": "CANDIDATE_PARSED"})
    lambda_handler({"Records": [record("SCORE", body, "score-message")]}, None)
    item = failed.scan()["Items"][0]
    assert item["stage"] == "SCORE"
    assert item["s3_key"] == f"resumes/{JOB}/resume.pdf"


def test_duplicate_dlq_delivery_is_idempotent(tables):
    failed, _ = tables
    body = json.dumps({"Records": [{
        "s3": {"bucket": {"name": "uploads"}, "object": {"key": f"resumes/{JOB}/resume.pdf"}},
    }]})
    event = {"Records": [record("PARSE", body, "same-message")]}
    lambda_handler(event, None)
    lambda_handler(event, None)
    assert len(failed.scan()["Items"]) == 1


def test_unknown_queue_is_recorded_as_unknown(tables):
    failed, _ = tables
    result = lambda_handler({"Records": [{
        "messageId": "unknown-message",
        "eventSourceARN": "arn:aws:sqs:us-east-1:123456789012:unexpected",
        "body": "{}",
    }]}, None)
    assert result == {"batchItemFailures": []}
    item = failed.scan()["Items"][0]
    assert item["stage"] == "UNKNOWN"
    assert item["error_type"] == "UNKNOWN"
