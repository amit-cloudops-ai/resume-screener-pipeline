"""Moto-backed JD parser tests."""
import json

import boto3
import pytest
from moto import mock_aws

from backend.parsing.jd_parse.app import lambda_handler

JOB = "a1b2c3d4e5f6"
BUCKET = "rs-dev-uploads-test"


@pytest.fixture
def resources(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("UPLOADS_BUCKET", BUCKET)
    monkeypatch.setenv("JOBS_TABLE", "rs-dev-jobs")
    monkeypatch.setenv("CANDIDATES_TABLE", "rs-dev-candidates")
    monkeypatch.setenv("FAILED_TABLE", "rs-dev-failed-jobs")
    monkeypatch.setenv("SCORE_QUEUE_URL", "placeholder")
    with mock_aws():
        ddb = boto3.resource("dynamodb", region_name="us-east-1")
        jobs = ddb.create_table(
            TableName="rs-dev-jobs",
            KeySchema=[{"AttributeName": "job_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "job_id", "AttributeType": "S"}],
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
        failed = ddb.create_table(
            TableName="rs-dev-failed-jobs",
            KeySchema=[{"AttributeName": "failed_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "failed_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket=BUCKET)
        sqs = boto3.client("sqs", region_name="us-east-1")
        queue_url = sqs.create_queue(QueueName="score")["QueueUrl"]
        monkeypatch.setenv("SCORE_QUEUE_URL", queue_url)
        jobs.put_item(Item={
            "job_id": JOB, "title": "DevOps Engineer", "status": "JD_UPLOADED",
            "threshold": 60, "created_by": "recruiter", "created_at": "2026-11-24T00:00:00Z",
        })
        candidates.put_item(Item={
            "job_id": JOB, "candidate_id": "0000000000000001", "status": "PARSED",
            "source_key": f"resumes/{JOB}/a.docx",
        })
        candidates.put_item(Item={
            "job_id": JOB, "candidate_id": "0000000000000002", "status": "UPLOADED",
            "source_key": f"resumes/{JOB}/b.docx",
        })
        yield jobs, candidates, failed, s3, sqs, queue_url


def notification(key):
    return json.dumps({"Records": [{
        "s3": {"bucket": {"name": BUCKET}, "object": {"key": key}},
    }]})


def invoke(key, message_id="jd-msg"):
    return lambda_handler({
        "Records": [{"messageId": message_id, "body": notification(key)}]
    }, None)


def test_jd_parse_updates_job_and_sends_ready_only_for_parsed_candidates(resources):
    jobs, _, _, s3, sqs, queue_url = resources
    key = f"jd/{JOB}/role.txt"
    s3.put_object(
        Bucket=BUCKET, Key=key,
        Body=b"DevOps Engineer requires AWS, Docker, Kubernetes and Terraform. 3+ years experience.",
        ContentType="text/plain",
    )
    result = invoke(key)
    assert result == {"batchItemFailures": []}
    job = jobs.get_item(Key={"job_id": JOB})["Item"]
    assert job["status"] == "JD_PARSED"
    assert job["required_skills"] == ["aws", "docker", "kubernetes", "terraform"]
    assert job["jd_titles"] == ["devops engineer"]
    assert job["required_years"] == 3
    messages = sqs.receive_message(QueueUrl=queue_url)["Messages"]
    assert len(messages) == 1
    assert json.loads(messages[0]["Body"]) == {
        "job_id": JOB, "candidate_id": "0000000000000001", "reason": "JD_READY"
    }


def test_jd_without_required_skills_is_failed_and_recorded(resources):
    jobs, _, failed, s3, _, _ = resources
    key = f"jd/{JOB}/vague.txt"
    s3.put_object(Bucket=BUCKET, Key=key, Body=b"An exciting opportunity with a great team.")
    assert invoke(key) == {"batchItemFailures": []}
    assert jobs.get_item(Key={"job_id": JOB})["Item"]["status"] == "FAILED"
    item = failed.scan()["Items"][0]
    assert item["stage"] == "JD_PARSE"
    assert item["error_type"] == "JD_NO_SKILLS"
    assert item["status"] == "OPEN"


def test_jd_parse_duplicate_is_idempotent(resources):
    jobs, _, _, s3, sqs, queue_url = resources
    key = f"jd/{JOB}/role.txt"
    s3.put_object(Bucket=BUCKET, Key=key, Body=b"DevOps Engineer requires AWS and Docker.")
    invoke(key, "first")
    first = jobs.get_item(Key={"job_id": JOB})["Item"]["jd_parsed_at"]
    invoke(key, "duplicate")
    second = jobs.get_item(Key={"job_id": JOB})["Item"]["jd_parsed_at"]
    assert first == second
    assert len(sqs.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=10)["Messages"]) == 2


def test_missing_job_does_not_create_malformed_job_record(resources):
    jobs, _, failed, s3, _, _ = resources
    jobs.delete_item(Key={"job_id": JOB})
    key = f"jd/{JOB}/orphan.txt"
    s3.put_object(Bucket=BUCKET, Key=key, Body=b"AWS and Docker")
    assert invoke(key) == {"batchItemFailures": []}
    assert jobs.get_item(Key={"job_id": JOB}).get("Item") is None
    item = failed.scan()["Items"][0]
    assert item["error_type"] == "UNKNOWN"
    assert item["stage"] == "JD_PARSE"
