"""Moto-backed tests for B4 candidate API."""
import os

import boto3
import pytest
from moto import mock_aws

from backend.api.candidates.app import lambda_handler

JOB_ID = "a1b2c3d4e5f6"


@pytest.fixture
def table(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("CANDIDATES_TABLE", "rs-dev-candidates")
    monkeypatch.setenv("CORS_ORIGIN", "https://dashboard.example.test")
    with mock_aws():
        ddb = boto3.resource("dynamodb", region_name="us-east-1")
        table = ddb.create_table(
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
        for candidate_id, score, decision in [
            ("0000000000000001", 88.5, "SHORTLISTED"),
            ("0000000000000002", 72.0, "PENDING"),
            ("0000000000000003", None, "PENDING"),
        ]:
            table.put_item(Item={
                "job_id": JOB_ID, "candidate_id": candidate_id,
                "status": "SCORED" if score is not None else "PARSED",
                "score": score, "decision": decision, "created_at": "2026-11-24T00:00:00Z",
            })
        yield table


def event(resource, path=None, query=None):
    return {
        "httpMethod": "GET", "resource": resource,
        "pathParameters": path or {}, "queryStringParameters": query,
    }


def body(response):
    import json
    return json.loads(response["body"])


def test_list_candidates_sorted_with_unscored_last_and_counts(table):
    response = lambda_handler(event("/jobs/{job_id}/candidates", {"job_id": JOB_ID}), None)
    data = body(response)
    assert response["statusCode"] == 200
    assert [x["candidate_id"] for x in data["candidates"]] == [
        "0000000000000001", "0000000000000002", "0000000000000003"
    ]
    assert data["counts"] == {"SHORTLISTED": 1, "PENDING": 2}


def test_decision_filter_does_not_change_total_counts(table):
    response = lambda_handler(
        event("/jobs/{job_id}/candidates", {"job_id": JOB_ID}, {"decision": "SHORTLISTED"}), None
    )
    data = body(response)
    assert len(data["candidates"]) == 1
    assert data["counts"]["PENDING"] == 2


def test_invalid_decision_filter_returns_400(table):
    response = lambda_handler(
        event("/jobs/{job_id}/candidates", {"job_id": JOB_ID}, {"decision": "MAYBE"}), None
    )
    assert response["statusCode"] == 400


def test_get_candidate_returns_record(table):
    response = lambda_handler(
        event(
            "/jobs/{job_id}/candidates/{candidate_id}",
            {"job_id": JOB_ID, "candidate_id": "0000000000000001"},
        ), None
    )
    assert response["statusCode"] == 200
    assert body(response)["score"] == 88.5


def test_missing_candidate_returns_404(table):
    response = lambda_handler(
        event(
            "/jobs/{job_id}/candidates/{candidate_id}",
            {"job_id": JOB_ID, "candidate_id": "0000000000000099"},
        ), None
    )
    assert response["statusCode"] == 404


def test_invalid_identifiers_return_400(table):
    response = lambda_handler(event("/jobs/{job_id}/candidates", {"job_id": "bad"}), None)
    assert response["statusCode"] == 400
