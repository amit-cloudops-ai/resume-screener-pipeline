"""Focused moto tests for the B3 jobs and upload URL API."""
import json
from decimal import Decimal
from pathlib import Path

import boto3
import pytest
from jsonschema import Draft7Validator
from moto import mock_aws

from backend.api.jobs.app import lambda_handler


ROOT = Path(__file__).resolve().parents[3]
JOB_SCHEMA = json.loads((ROOT / "contracts/job.schema.json").read_text(encoding="utf-8"))
JOB_ID = "a1b2c3d4e5f6"


def event(method, resource, body=None, job_id=None, principal="recruiter-sub-001"):
    return {
        "httpMethod": method,
        "resource": resource,
        "pathParameters": {"job_id": job_id} if job_id is not None else None,
        "requestContext": {"authorizer": {"claims": {"sub": principal}}},
        "body": json.dumps(body) if body is not None else None,
    }


def payload(response):
    return json.loads(response["body"])


def assert_error(response, status):
    assert response["statusCode"] == status
    assert set(payload(response)) == {"error", "detail"}


@pytest.fixture

def aws_resources(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("STAGE", "dev")
    monkeypatch.setenv("JOBS_TABLE", "rs-dev-jobs")
    monkeypatch.setenv("UPLOADS_BUCKET", "rs-dev-uploads-test")
    monkeypatch.setenv("PARSER_VERSION", "1.0.0")
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        jobs = dynamodb.create_table(
            TableName="rs-dev-jobs",
            KeySchema=[{"AttributeName": "job_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "job_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="rs-dev-uploads-test")
        ssm = boto3.client("ssm", region_name="us-east-1")
        ssm.put_parameter(Name="/rs/dev/threshold-default", Type="String", Value="60")
        yield jobs, s3


def test_create_job_returns_schema_valid_job_and_presigned_jd_url(aws_resources, monkeypatch):
    jobs, _ = aws_resources
    monkeypatch.setattr("backend.api.jobs.app.secrets.token_hex", lambda count: JOB_ID)

    response = lambda_handler(event("POST", "/jobs", {"title": "DevOps Engineer"}), None)

    assert response["statusCode"] == 201
    result = payload(response)
    assert set(result) == {"job", "jd_upload"}
    Draft7Validator(JOB_SCHEMA).validate(result["job"])
    assert result["job"]["job_id"] == JOB_ID
    assert result["job"]["status"] == "CREATED"
    assert result["job"]["threshold"] == 60
    assert result["job"]["created_by"] == "recruiter-sub-001"
    assert result["jd_upload"]["s3_key"] == f"jd/{JOB_ID}/job-description.pdf"
    assert result["jd_upload"]["url"].startswith("https://")
    assert "Signature=" in result["jd_upload"]["url"]
    saved = jobs.get_item(Key={"job_id": JOB_ID}, ConsistentRead=True)["Item"]
    assert saved["created_by"] == "recruiter-sub-001"


def test_create_job_uses_threshold_override(aws_resources, monkeypatch):
    _, _ = aws_resources
    monkeypatch.setattr("backend.api.jobs.app.secrets.token_hex", lambda count: JOB_ID)

    result = payload(lambda_handler(
        event("POST", "/jobs", {"title": "Ops", "threshold": 72.5}), None
    ))

    assert result["job"]["threshold"] == 72.5


@pytest.mark.parametrize("body", [
    {"title": ""},
    {"title": "x" * 201},
    {"title": "Ops", "threshold": -1},
    {"title": "Ops", "threshold": 100.1},
    {"title": "Ops", "threshold": True},
])
def test_create_job_rejects_invalid_fields(aws_resources, body):
    response = lambda_handler(event("POST", "/jobs", body), None)
    assert_error(response, 400)


def test_create_job_rejects_explicit_null_description_text(aws_resources):
    response = lambda_handler(event(
        "POST", "/jobs", {"title": "Ops", "description_text": None}
    ), None)

    assert_error(response, 400)


def test_create_job_stores_empty_jd_in_s3_without_persisting_text(aws_resources, monkeypatch):
    jobs, s3 = aws_resources
    monkeypatch.setattr("backend.api.jobs.app.secrets.token_hex", lambda count: JOB_ID)

    response = lambda_handler(event(
        "POST", "/jobs", {"title": "Ops", "description_text": ""}
    ), None)

    assert response["statusCode"] == 201
    result = payload(response)
    key = result["job"]["jd_s3_key"]
    assert key == f"jd/{JOB_ID}/description.txt"
    assert s3.get_object(Bucket="rs-dev-uploads-test", Key=key)["Body"].read() == b""
    stored = jobs.get_item(Key={"job_id": JOB_ID}, ConsistentRead=True)["Item"]
    assert "description_text" not in stored


def test_create_job_uses_cognito_subject_over_client_created_by(aws_resources, monkeypatch):
    jobs, _ = aws_resources
    monkeypatch.setattr("backend.api.jobs.app.secrets.token_hex", lambda count: JOB_ID)

    response = lambda_handler(event(
        "POST", "/jobs", {"title": "Ops", "created_by": "forged-client-identity"}
    ), None)

    assert response["statusCode"] == 201
    assert payload(response)["job"]["created_by"] == "recruiter-sub-001"
    stored = jobs.get_item(Key={"job_id": JOB_ID}, ConsistentRead=True)["Item"]
    assert stored["created_by"] == "recruiter-sub-001"


def test_create_job_requires_json_body_and_authenticated_subject(aws_resources):
    bad_json = event("POST", "/jobs")
    bad_json["body"] = "{invalid"
    assert_error(lambda_handler(bad_json, None), 400)

    unauthenticated = event("POST", "/jobs", {"title": "Ops"}, principal=None)
    assert_error(lambda_handler(unauthenticated, None), 401)


def test_create_job_stores_pasted_jd_for_architecture_queue_flow(aws_resources, monkeypatch):
    jobs, s3 = aws_resources
    monkeypatch.setattr("backend.api.jobs.app.secrets.token_hex", lambda count: JOB_ID)
    text = "Experience with Python and AWS"

    response = lambda_handler(event(
        "POST", "/jobs", {"title": "Ops", "description_text": text}
    ), None)

    result = payload(response)
    assert response["statusCode"] == 201
    assert set(result) == {"job"}
    assert result["job"]["status"] == "JD_UPLOADED"
    assert result["job"]["jd_s3_key"] == f"jd/{JOB_ID}/description.txt"
    stored = s3.get_object(Bucket="rs-dev-uploads-test", Key=result["job"]["jd_s3_key"])
    assert stored["Body"].read().decode("utf-8") == text
    validator = Draft7Validator(JOB_SCHEMA, format_checker=Draft7Validator.FORMAT_CHECKER)
    validator.validate(jobs.get_item(Key={"job_id": JOB_ID})["Item"])


def test_create_job_rejects_unsafe_or_unsupported_jd_filename(aws_resources):
    response = lambda_handler(event(
        "POST", "/jobs", {"title": "Ops", "jd_file_name": "../evil.pdf"}
    ), None)
    assert_error(response, 400)
    response = lambda_handler(event(
        "POST", "/jobs", {"title": "Ops", "jd_file_name": "notes.exe"}
    ), None)
    assert_error(response, 400)


def test_create_job_rejects_pasted_jd_over_5mb(aws_resources):
    response = lambda_handler(event(
        "POST", "/jobs", {"title": "Ops", "description_text": "x" * (5 * 1024 * 1024 + 1)}
    ), None)
    assert_error(response, 400)


def test_list_jobs_returns_newest_first_and_handles_decimal_values(aws_resources):
    jobs, _ = aws_resources
    for job_id, created_at, threshold in [
        ("000000000001", "2026-11-20T10:00:00Z", Decimal("55.5")),
        ("000000000002", "2026-11-21T10:00:00Z", Decimal("75")),
    ]:
        jobs.put_item(Item={
            "job_id": job_id, "title": job_id, "status": "CREATED", "threshold": threshold,
            "created_at": created_at, "created_by": "recruiter-sub-001",
        })

    response = lambda_handler(event("GET", "/jobs"), None)

    assert response["statusCode"] == 200
    result = payload(response)
    assert [job["job_id"] for job in result["jobs"]] == ["000000000002", "000000000001"]
    assert result["jobs"][1]["threshold"] == 55.5


def test_list_jobs_items_validate_against_frozen_job_schema(aws_resources):
    jobs, _ = aws_resources
    jobs.put_item(Item={
        "job_id": JOB_ID, "title": "DevOps", "status": "CREATED", "threshold": Decimal("60"),
        "created_at": "2026-11-22T10:00:00Z", "created_by": "recruiter-sub-001",
    })

    response = lambda_handler(event("GET", "/jobs"), None)

    assert response["statusCode"] == 200
    result = payload(response)
    assert set(result) == {"jobs"}
    validator = Draft7Validator(JOB_SCHEMA, format_checker=Draft7Validator.FORMAT_CHECKER)
    assert result["jobs"]
    for job in result["jobs"]:
        validator.validate(job)


def test_get_job_returns_record_and_missing_job_is_404(aws_resources):
    jobs, _ = aws_resources
    jobs.put_item(Item={
        "job_id": JOB_ID, "title": "DevOps", "status": "CREATED", "threshold": Decimal("60"),
        "created_at": "2026-11-22T10:00:00Z", "created_by": "recruiter-sub-001",
    })

    response = lambda_handler(event("GET", "/jobs/{job_id}", job_id=JOB_ID), None)
    assert response["statusCode"] == 200
    assert payload(response)["job_id"] == JOB_ID
    assert_error(lambda_handler(event("GET", "/jobs/{job_id}", job_id="ffffffffffff"), None), 404)
    assert_error(lambda_handler(event("GET", "/jobs/{job_id}", job_id="bad-id"), None), 404)


def test_uploads_returns_resume_urls_and_architecture_keys(aws_resources):
    jobs, _ = aws_resources
    jobs.put_item(Item={
        "job_id": JOB_ID, "title": "Ops", "status": "CREATED", "threshold": 60,
        "created_at": "2026-11-22T10:00:00Z", "created_by": "recruiter-sub-001",
    })
    request = {"files": [
        {"file_name": "Priya.pdf", "content_type": "application/pdf"},
        {"file_name": "Aman.docx", "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    ]}

    response = lambda_handler(event("POST", "/jobs/{job_id}/uploads", request, JOB_ID), None)

    assert response["statusCode"] == 200
    uploads = payload(response)["uploads"]
    assert [item["s3_key"] for item in uploads] == [
        f"resumes/{JOB_ID}/Priya.pdf", f"resumes/{JOB_ID}/Aman.docx"
    ]
    assert all(item["url"].startswith("https://") and "Signature=" in item["url"] for item in uploads)


def test_uploads_accept_empty_files_array(aws_resources):
    jobs, _ = aws_resources
    jobs.put_item(Item={
        "job_id": JOB_ID, "title": "Ops", "status": "CREATED", "threshold": 60,
        "created_at": "2026-11-22T10:00:00Z", "created_by": "recruiter-sub-001",
    })

    response = lambda_handler(event(
        "POST", "/jobs/{job_id}/uploads", {"files": []}, JOB_ID
    ), None)

    assert response["statusCode"] == 200
    assert payload(response) == {"uploads": []}


@pytest.mark.parametrize("files", [
    [{"file_name": "resume.txt", "content_type": "text/plain"}],
    [{"file_name": "resume.pdf", "content_type": "text/plain"}],
    [{"file_name": "../resume.pdf", "content_type": "application/pdf"}],
    [{"file_name": "resume.pdf", "content_type": "application/pdf"}] * 2,
])
def test_uploads_reject_invalid_files(aws_resources, files):
    jobs, _ = aws_resources
    jobs.put_item(Item={
        "job_id": JOB_ID, "title": "Ops", "status": "CREATED", "threshold": 60,
        "created_at": "2026-11-22T10:00:00Z", "created_by": "recruiter-sub-001",
    })
    response = lambda_handler(event(
        "POST", "/jobs/{job_id}/uploads", {"files": files}, JOB_ID
    ), None)
    assert_error(response, 400)


def test_uploads_reject_more_than_50_files_and_missing_jobs(aws_resources):
    jobs, _ = aws_resources
    jobs.put_item(Item={
        "job_id": JOB_ID, "title": "Ops", "status": "CREATED", "threshold": 60,
        "created_at": "2026-11-22T10:00:00Z", "created_by": "recruiter-sub-001",
    })
    files = [{"file_name": f"resume-{i}.pdf", "content_type": "application/pdf"} for i in range(51)]
    assert_error(lambda_handler(event(
        "POST", "/jobs/{job_id}/uploads", {"files": files}, JOB_ID
    ), None), 400)
    assert_error(lambda_handler(event(
        "POST", "/jobs/{job_id}/uploads", {"files": [{"file_name": "r.pdf", "content_type": "application/pdf"}]},
        "ffffffffffff"
    ), None), 404)


def test_pasted_jd_s3_failure_marks_job_failed(aws_resources, monkeypatch):
    jobs, _ = aws_resources
    monkeypatch.setattr("backend.api.jobs.app.secrets.token_hex", lambda count: JOB_ID)

    class FailingS3:
        def put_object(self, **kwargs):
            raise RuntimeError("simulated S3 failure")

    monkeypatch.setattr("backend.api.jobs.app._s3_client", lambda: FailingS3())

    response = lambda_handler(event(
        "POST", "/jobs", {"title": "Ops", "description_text": "A valid JD"}
    ), None)

    assert_error(response, 500)
    saved = jobs.get_item(Key={"job_id": JOB_ID}, ConsistentRead=True)["Item"]
    assert saved["status"] == "FAILED"
