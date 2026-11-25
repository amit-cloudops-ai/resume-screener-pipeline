"""Moto-backed decision API tests; SES is isolated behind a fake client."""
import json

import boto3
import pytest
from moto import mock_aws

from backend.api.decision.app import lambda_handler

JOB = "a1b2c3d4e5f6"
CANDIDATE = "0123456789abcdef"


class FakeSes:
    def __init__(self):
        self.sent = []

    def send_email(self, **kwargs):
        self.sent.append(kwargs)
        return {"MessageId": "fake-message-id"}


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("CANDIDATES_TABLE", "rs-dev-candidates")
    monkeypatch.setenv("CORS_ORIGIN", "https://dashboard.example.test")
    monkeypatch.setenv("SES_SENDER", "recruiting@example.test")
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
            "job_id": JOB, "candidate_id": CANDIDATE, "status": "SCORED",
            "score": 90, "decision": "PENDING", "name": "Candidate One",
            "email": "candidate@example.test", "email_status": "NOT_SENT",
            "created_at": "2026-11-24T00:00:00Z",
        })
        fake_ses = FakeSes()
        original_client = boto3.client

        def client(service, *args, **kwargs):
            if service == "ses":
                return fake_ses
            return original_client(service, *args, **kwargs)

        monkeypatch.setattr(boto3, "client", client)
        yield table, fake_ses


def request(action, interview=None):
    body = {"action": action}
    if interview is not None:
        body["interview"] = interview
    return {
        "httpMethod": "POST",
        "resource": "/jobs/{job_id}/candidates/{candidate_id}/decision",
        "pathParameters": {"job_id": JOB, "candidate_id": CANDIDATE},
        "body": json.dumps(body),
        "requestContext": {"authorizer": {"claims": {"sub": "recruiter-sub"}}},
    }


def decode(response):
    return json.loads(response["body"])


def test_reject_records_decision_and_actor(setup):
    table, ses = setup
    response = lambda_handler(request("reject"), None)
    item = decode(response)
    assert response["statusCode"] == 200
    assert item["decision"] == "REJECTED"
    assert item["decision_history"][0]["by"] == "recruiter-sub"
    assert item["decision_history"][0]["action"] == "reject"
    assert ses.sent == []


def test_shortlist_sends_interview_email_and_updates_status(setup):
    table, ses = setup
    response = lambda_handler(request("shortlist", {
        "date_time": "2026-12-01 10:00 IST",
        "location_or_link": "https://meet.example.test/room",
        "notes": "Bring portfolio",
    }), None)
    item = decode(response)
    assert response["statusCode"] == 200
    assert item["decision"] == "SHORTLISTED"
    assert item["email_status"] == "SENT"
    assert len(ses.sent) == 1
    assert ses.sent[0]["Destination"]["ToAddresses"] == ["candidate@example.test"]


def test_shortlist_without_email_marks_no_email(setup):
    table, ses = setup
    table.update_item(
        Key={"job_id": JOB, "candidate_id": CANDIDATE},
        UpdateExpression="REMOVE email",
    )
    response = lambda_handler(request("shortlist", {
        "date_time": "2026-12-01 10:00 IST",
        "location_or_link": "Online",
    }), None)
    assert decode(response)["email_status"] == "NO_EMAIL"
    assert ses.sent == []


def test_shortlist_requires_interview_details(setup):
    response = lambda_handler(request("shortlist", {"date_time": "Tomorrow"}), None)
    assert response["statusCode"] == 400


def test_candidate_must_be_scored(setup):
    table, _ = setup
    table.update_item(
        Key={"job_id": JOB, "candidate_id": CANDIDATE},
        UpdateExpression="SET #s = :status",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":status": "PARSED"},
    )
    response = lambda_handler(request("reject"), None)
    assert response["statusCode"] == 409


def test_duplicate_decision_is_rejected_without_second_email(setup):
    _, ses = setup
    interview = {"date_time": "2026-12-01 10:00 IST", "location_or_link": "Online"}
    assert lambda_handler(request("shortlist", interview), None)["statusCode"] == 200
    second = lambda_handler(request("shortlist", interview), None)
    assert second["statusCode"] == 409
    assert len(ses.sent) == 1


def test_invalid_action_returns_400(setup):
    response = lambda_handler(request("maybe"), None)
    assert response["statusCode"] == 400
