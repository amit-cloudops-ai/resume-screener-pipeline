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


def s3_body(key):
    return json.dumps({"Records": [{
        "s3": {"bucket": {"name": "uploads"}, "object": {"key": key}},
    }]})


def test_parse_dlq_writes_failed_job_record(tables):
    failed, _ = tables
    result = lambda_handler({"Records": [record("PARSE", s3_body(f"resumes/{JOB}/resume.pdf"))]}, None)
    assert result == {"batchItemFailures": []}
    item = failed.scan()["Items"][0]
    assert item["stage"] == "PARSE"
    assert item["job_id"] == JOB
    assert item["s3_key"] == f"resumes/{JOB}/resume.pdf"
    assert item["error_type"] == "TRANSIENT_EXHAUSTED"
    assert item["attempts"] == 3


def test_jd_parse_dlq_writes_job_identity(tables):
    failed, _ = tables
    result = lambda_handler({"Records": [record("JD_PARSE", s3_body(f"jd/{JOB}/description.txt"))]}, None)
    assert result == {"batchItemFailures": []}
    item = failed.scan()["Items"][0]
    assert item["stage"] == "JD_PARSE"
    assert item["job_id"] == JOB
    assert item["s3_key"] == f"jd/{JOB}/description.txt"


def test_score_dlq_resolves_candidate_source_key(tables):
    failed, _ = tables
    body = json.dumps({"job_id": JOB, "candidate_id": CANDIDATE, "reason": "CANDIDATE_PARSED"})
    lambda_handler({"Records": [record("SCORE", body, "score-message")]}, None)
    item = failed.scan()["Items"][0]
    assert item["stage"] == "SCORE"
    assert item["s3_key"] == f"resumes/{JOB}/resume.pdf"


def test_event_source_arn_casing_variant_is_supported(tables):
    failed, _ = tables
    event_record = record("PARSE", s3_body(f"resumes/{JOB}/resume.pdf"))
    event_record["eventSourceArn"] = event_record.pop("eventSourceARN")
    result = lambda_handler({"Records": [event_record]}, None)
    assert result == {"batchItemFailures": []}
    assert failed.scan()["Items"][0]["stage"] == "PARSE"


def test_malformed_s3_notification_is_recorded_with_diagnostic(tables):
    failed, _ = tables
    result = lambda_handler({"Records": [record("PARSE", "{not-json", "bad-s3")]}, None)
    assert result == {"batchItemFailures": []}
    item = failed.scan()["Items"][0]
    assert item["stage"] == "UNKNOWN"
    assert item["error_type"] == "UNKNOWN"
    assert "invalid_s3_notification" in item["error_message"]


def test_wrong_s3_key_prefix_is_not_misclassified_as_parse_failure(tables):
    failed, _ = tables
    result = lambda_handler({"Records": [record("JD_PARSE", s3_body(f"resumes/{JOB}/resume.pdf"), "wrong-prefix")]}, None)
    assert result == {"batchItemFailures": []}
    item = failed.scan()["Items"][0]
    assert item["stage"] == "UNKNOWN"
    assert "expected jd/" in item["error_message"]


def test_malformed_score_payload_is_recorded_with_diagnostic(tables):
    failed, _ = tables
    result = lambda_handler({"Records": [record("SCORE", "[]", "bad-score")]}, None)
    assert result == {"batchItemFailures": []}
    item = failed.scan()["Items"][0]
    assert item["stage"] == "UNKNOWN"
    assert "invalid_score_payload" in item["error_message"]


def test_missing_source_arn_is_recorded_with_diagnostic(tables):
    failed, _ = tables
    result = lambda_handler({"Records": [{
        "messageId": "missing-source",
        "body": "{}",
        "attributes": {"ApproximateReceiveCount": "4"},
    }]}, None)
    assert result == {"batchItemFailures": []}
    item = failed.scan()["Items"][0]
    assert item["stage"] == "UNKNOWN"
    assert "unrecognized_source_queue" in item["error_message"]


def test_unrecognized_queue_is_recorded_as_unknown(tables):
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
    assert "unrecognized_source_queue" in item["error_message"]


def test_duplicate_dlq_delivery_is_idempotent(tables):
    failed, _ = tables
    event = {"Records": [record("PARSE", s3_body(f"resumes/{JOB}/resume.pdf"), "same-message")]}
    lambda_handler(event, None)
    lambda_handler(event, None)
    assert len(failed.scan()["Items"]) == 1
