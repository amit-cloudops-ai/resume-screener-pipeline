"""Moto-backed contract tests for the B3 jobs/upload API."""
import json
import os

import boto3
import pytest
from moto import mock_aws

from backend.api.jobs.app import lambda_handler

JOB_TABLE = "rs-dev-jobs"
BUCKET = "rs-dev-uploads-test"


@pytest.fixture
def aws_resources(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("STAGE", "dev")
    monkeypatch.setenv("JOBS_TABLE", JOB_TABLE)
    monkeypatch.setenv("UPLOADS_BUCKET", BUCKET)
    monkeypatch.setenv("CORS_ORIGIN", "https://dashboard.example.test")
    with mock_aws():
        ddb = boto3.resource("dynamodb", region_name="us-east-1")
        ddb.create_table(
            TableName=JOB_TABLE,
            KeySchema=[{"AttributeName": "job_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "job_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket=BUCKET)
        yield


def event(method, resource, body=None, path=None):
    return {
        "httpMethod": method,
        "resource": resource,
        "pathParameters": path or {},
        "body": json.dumps(body) if body is not None else None,
        "requestContext": {"authorizer": {"claims": {"sub": "recruiter-sub-123"}}},
    }


def payload(response):
    return json.loads(response["body"])


def test_create_job_returns_contract_fields_and_cors(aws_resources):
    response = lambda_handler(
        event("POST", "/jobs", {"title": "Platform Engineer", "threshold": 72}),
        None,
    )
    body = payload(response)
    assert response["statusCode"] == 201
    assert response["headers"]["Access-Control-Allow-Origin"] == "https://dashboard.example.test"
    job = body["job"]
    assert len(job["job_id"]) == 12
    assert job["status"] == "CREATED"
    assert job["threshold"] == 72.0
    assert job["created_by"] == "recruiter-sub-123"
    assert job["required_skills"] == []
    assert job["jd_s3_key"] is None


def test_create_job_uploads_text_description_to_jd_prefix(aws_resources):
    response = lambda_handler(
        event("POST", "/jobs", {"title": "SRE", "description_text": "Python and AWS required"}),
        None,
    )
    body = payload(response)
    assert response["statusCode"] == 201
    job = body["job"]
    assert job["status"] == "JD_UPLOADED"
    assert job["jd_s3_key"] == f"jd/{job['job_id']}/description.txt"
    obj = boto3.client("s3", region_name="us-east-1").get_object(
        Bucket=BUCKET, Key=job["jd_s3_key"]
    )
    assert obj["Body"].read().decode() == "Python and AWS required"


def test_create_job_returns_presigned_jd_upload(aws_resources):
    response = lambda_handler(
        event("POST", "/jobs", {"title": "Analyst", "jd_file_name": "role.pdf"}),
        None,
    )
    body = payload(response)
    assert response["statusCode"] == 201
    assert body["jd_upload"]["s3_key"].endswith("/role.pdf")
    assert body["jd_upload"]["url"].startswith("https://")


@pytest.mark.parametrize("body", [
    {"title": ""},
    {"title": "x", "threshold": -1},
    {"title": "x", "threshold": 101},
    {"title": "x", "threshold": True},
    {"title": "x", "description_text": "JD", "jd_file_name": "role.pdf"},
])
def test_invalid_job_payload_returns_400(aws_resources, body):
    response = lambda_handler(event("POST", "/jobs", body), None)
    assert response["statusCode"] == 400
    assert "error" in payload(response)


def test_create_job_requires_cognito_subject(aws_resources):
    request = event("POST", "/jobs", {"title": "Engineer"})
    request["requestContext"]["authorizer"]["claims"] = {}
    response = lambda_handler(request, None)
    assert response["statusCode"] == 401


def test_list_and_get_job(aws_resources):
    created = payload(lambda_handler(
        event("POST", "/jobs", {"title": "Engineer"}), None
    ))["job"]
    listed = lambda_handler(event("GET", "/jobs"), None)
    assert payload(listed)["jobs"][0]["job_id"] == created["job_id"]
    fetched = lambda_handler(
        event("GET", "/jobs/{job_id}", path={"job_id": created["job_id"]}), None
    )
    assert payload(fetched)["job_id"] == created["job_id"]


def test_get_missing_job_returns_404(aws_resources):
    response = lambda_handler(
        event("GET", "/jobs/{job_id}", path={"job_id": "a1b2c3d4e5f6"}), None
    )
    assert response["statusCode"] == 404


def test_upload_urls_are_limited_to_pdf_docx_and_50(aws_resources):
    created = payload(lambda_handler(
        event("POST", "/jobs", {"title": "Engineer"}), None
    ))["job"]
    request = event(
        "POST", "/jobs/{job_id}/uploads",
        {"files": [
            {"file_name": "resume.pdf", "content_type": "application/pdf"},
            {"file_name": "resume.docx", "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
        ]},
        {"job_id": created["job_id"]},
    )
    response = lambda_handler(request, None)
    uploads = payload(response)["uploads"]
    assert response["statusCode"] == 200
    assert len(uploads) == 2
    assert uploads[0]["s3_key"] == f"resumes/{created['job_id']}/resume.pdf"
    assert all(item["url"].startswith("https://") for item in uploads)


def test_upload_urls_reject_unsupported_extension_and_duplicates(aws_resources):
    created = payload(lambda_handler(
        event("POST", "/jobs", {"title": "Engineer"}), None
    ))["job"]
    bad = event(
        "POST", "/jobs/{job_id}/uploads",
        {"files": [{"file_name": "resume.txt", "content_type": "text/plain"}]},
        {"job_id": created["job_id"]},
    )
    assert lambda_handler(bad, None)["statusCode"] == 400
    duplicate = event(
        "POST", "/jobs/{job_id}/uploads",
        {"files": [
            {"file_name": "Resume.pdf", "content_type": "application/pdf"},
            {"file_name": "resume.pdf", "content_type": "application/pdf"},
        ]},
        {"job_id": created["job_id"]},
    )
    assert lambda_handler(duplicate, None)["statusCode"] == 400


def test_upload_urls_reject_missing_job_and_more_than_50_files(aws_resources):
    missing = event(
        "POST", "/jobs/{job_id}/uploads", {"files": [{"file_name": "a.pdf", "content_type": "application/pdf"}]},
        {"job_id": "a1b2c3d4e5f6"},
    )
    assert lambda_handler(missing, None)["statusCode"] == 404
    created = payload(lambda_handler(
        event("POST", "/jobs", {"title": "Engineer"}), None
    ))["job"]
    files = [{"file_name": f"{i}.pdf", "content_type": "application/pdf"} for i in range(51)]
    too_many = event("POST", "/jobs/{job_id}/uploads", {"files": files}, {"job_id": created["job_id"]})
    assert lambda_handler(too_many, None)["statusCode"] == 400
