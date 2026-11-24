"""Moto-backed CSV export tests."""
import csv
import io

import boto3
import pytest
from moto import mock_aws

from backend.api.export.app import lambda_handler

JOB = "a1b2c3d4e5f6"


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
        table.put_item(Item={
            "job_id": JOB, "candidate_id": "0000000000000001",
            "decision": "SHORTLISTED", "score": 91.5, "name": "Asha",
            "email": "asha@example.test", "skills": ["aws"],
            "score_breakdown": {"skills": {"matched": ["aws", "docker"], "missing": ["terraform"]}},
            "titles": ["cloud engineer"], "experience_years": 4,
            "email_status": "SENT",
        })
        table.put_item(Item={
            "job_id": JOB, "candidate_id": "0000000000000002",
            "decision": "REJECTED", "score": 99, "name": "Not shortlisted",
        })
        table.put_item(Item={
            "job_id": JOB, "candidate_id": "0000000000000003",
            "decision": "SHORTLISTED", "score": 82, "name": "Bala",
            "email_status": "NO_EMAIL",
        })
        yield table


def test_export_has_exact_columns_and_only_shortlisted_candidates(table):
    response = lambda_handler({
        "httpMethod": "GET",
        "resource": "/jobs/{job_id}/shortlist.csv",
        "pathParameters": {"job_id": JOB},
    }, None)
    assert response["statusCode"] == 200
    assert response["headers"]["Content-Type"].startswith("text/csv")
    rows = list(csv.DictReader(io.StringIO(response["body"])))
    assert list(rows[0]) == [
        "rank", "name", "email", "score", "skills_matched", "skills_missing",
        "titles", "experience_years", "decision", "email_status",
    ]
    assert [row["name"] for row in rows] == ["Asha", "Bala"]
    assert rows[0]["skills_matched"] == "aws; docker"
    assert rows[0]["skills_missing"] == "terraform"
    assert rows[0]["rank"] == "1"


def test_invalid_job_id_returns_400(table):
    response = lambda_handler({
        "httpMethod": "GET", "pathParameters": {"job_id": "bad"}
    }, None)
    assert response["statusCode"] == 400
