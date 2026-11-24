"""Moto-backed tests for the B2 score Lambda."""
import json
import os
from decimal import Decimal
from pathlib import Path

import boto3
import pytest
from moto import mock_aws

from backend.scoring.handler import lambda_handler

def to_dynamodb_values(value):
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {key: to_dynamodb_values(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_dynamodb_values(item) for item in value]
    return value


def from_dynamodb_values(value):
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, dict):
        return {key: from_dynamodb_values(item) for key, item in value.items()}
    if isinstance(value, list):
        return [from_dynamodb_values(item) for item in value]
    return value


ROOT = Path(__file__).resolve().parents[2]


def load_fixture(relative_path):
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


@pytest.fixture
def aws_tables(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("JOBS_TABLE", "rs-dev-jobs")
    monkeypatch.setenv("CANDIDATES_TABLE", "rs-dev-candidates")

    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        jobs = dynamodb.create_table(
            TableName="rs-dev-jobs",
            KeySchema=[{"AttributeName": "job_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "job_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        candidates = dynamodb.create_table(
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
        jobs.put_item(Item=to_dynamodb_values(load_fixture("fixtures/jobs/job_devops.json")))
        candidates.put_item(
            Item=to_dynamodb_values(load_fixture("fixtures/candidates/cand_strong.json"))
        )
        yield jobs, candidates


def sqs_event(reason="CANDIDATE_PARSED"):
    message = {
        "job_id": "a1b2c3d4e5f6",
        "candidate_id": "0123456789abcdef",
        "reason": reason,
    }
    return {"Records": [{"messageId": "message-1", "body": json.dumps(message)}]}


def test_lambda_scores_candidate_and_writes_contract_fields(aws_tables):
    _, candidates = aws_tables

    result = lambda_handler(sqs_event(), None)

    assert result == {"processed": 1}
    item = from_dynamodb_values(candidates.get_item(
        Key={"job_id": "a1b2c3d4e5f6", "candidate_id": "0123456789abcdef"}
    )["Item"])
    assert item["status"] == "SCORED"
    assert item["score"] == 100
    assert item["above_threshold"] is True
    assert item["score_breakdown"]["skills"]["weight"] == 0.5
    assert item["score_breakdown"]["title"]["weight"] == 0.3
    assert item["score_breakdown"]["experience"]["weight"] == 0.2
    assert item["scored_at"].endswith("Z")
    # Existing candidate data and recruiter decision fields are preserved.
    assert item["name"] == "Priya Sharma"
    assert item["decision"] == "PENDING"
    assert item["email_status"] == "NOT_SENT"


def test_duplicate_delivery_is_idempotent(aws_tables):
    _, candidates = aws_tables
    event = sqs_event()

    lambda_handler(event, None)
    first = candidates.get_item(
        Key={"job_id": "a1b2c3d4e5f6", "candidate_id": "0123456789abcdef"}
    )["Item"]
    lambda_handler(event, None)
    second = candidates.get_item(
        Key={"job_id": "a1b2c3d4e5f6", "candidate_id": "0123456789abcdef"}
    )["Item"]

    assert second["score"] == first["score"]
    assert second["score_breakdown"] == first["score_breakdown"]
    assert second["scored_at"] == first["scored_at"]



def test_duplicate_delivery_with_decimal_breakdown_is_idempotent(aws_tables):
    _, candidates = aws_tables
    candidates.update_item(
        Key={"job_id": "a1b2c3d4e5f6", "candidate_id": "0123456789abcdef"},
        UpdateExpression="SET skills = :skills",
        ExpressionAttributeValues={":skills": ["aws", "docker"]},
    )
    event = sqs_event()

    lambda_handler(event, None)
    first = candidates.get_item(
        Key={"job_id": "a1b2c3d4e5f6", "candidate_id": "0123456789abcdef"}
    )["Item"]
    assert isinstance(first["score_breakdown"]["skills"]["score"], Decimal)
    lambda_handler(event, None)
    second = candidates.get_item(
        Key={"job_id": "a1b2c3d4e5f6", "candidate_id": "0123456789abcdef"}
    )["Item"]

    assert second["scored_at"] == first["scored_at"]


def test_rescore_refreshes_timestamp_even_when_score_is_unchanged(aws_tables):
    _, candidates = aws_tables
    event = sqs_event("RESCORE")

    lambda_handler(event, None)
    first = candidates.get_item(
        Key={"job_id": "a1b2c3d4e5f6", "candidate_id": "0123456789abcdef"}
    )["Item"]
    lambda_handler(event, None)
    second = candidates.get_item(
        Key={"job_id": "a1b2c3d4e5f6", "candidate_id": "0123456789abcdef"}
    )["Item"]

    assert second["score"] == first["score"]
    assert second["scored_at"] >= first["scored_at"]


def test_job_not_jd_parsed_raises_for_sqs_retry(aws_tables):
    jobs, _ = aws_tables
    jobs.update_item(
        Key={"job_id": "a1b2c3d4e5f6"},
        UpdateExpression="SET #status = :status",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={":status": "JD_UPLOADED"},
    )

    with pytest.raises(RuntimeError, match="not JD_PARSED"):
        lambda_handler(sqs_event(), None)


def test_missing_candidate_raises(aws_tables):
    event = {
        "Records": [{
            "messageId": "message-2",
            "body": json.dumps({
                "job_id": "a1b2c3d4e5f6",
                "candidate_id": "aaaaaaaaaaaaaaaa",
                "reason": "CANDIDATE_PARSED",
            }),
        }]
    }
    with pytest.raises(LookupError, match="candidate not found"):
        lambda_handler(event, None)


def test_invalid_message_raises(aws_tables):
    event = {"Records": [{"messageId": "bad", "body": "{not-json"}]}
    with pytest.raises(ValueError, match="valid JSON"):
        lambda_handler(event, None)


def test_candidate_decision_is_not_overwritten(aws_tables):
    _, candidates = aws_tables
    candidates.update_item(
        Key={"job_id": "a1b2c3d4e5f6", "candidate_id": "0123456789abcdef"},
        UpdateExpression="SET decision = :decision",
        ExpressionAttributeValues={":decision": "SHORTLISTED"},
    )

    lambda_handler(sqs_event("RESCORE"), None)
    item = candidates.get_item(
        Key={"job_id": "a1b2c3d4e5f6", "candidate_id": "0123456789abcdef"}
    )["Item"]
    assert item["decision"] == "SHORTLISTED"
