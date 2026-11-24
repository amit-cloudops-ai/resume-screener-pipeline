"""End-to-end local integration: resume/JD parsing -> score queue -> scoring."""
import json
from decimal import Decimal
from io import BytesIO
from urllib.parse import quote_plus

import boto3
from docx import Document
from jsonschema import Draft7Validator
import pytest
from moto import mock_aws

from backend.parsing.parse.app import lambda_handler as parse_resume
from backend.parsing.jd_parse.app import lambda_handler as parse_jd
from backend.scoring.handler import lambda_handler as score_batch, _to_native

JOB = "a1b2c3d4e5f6"
BUCKET = "rs-dev-uploads-test"


class FakeComprehend:
    def detect_entities(self, **kwargs):
        return {"Entities": []}


def make_docx():
    doc = Document()
    doc.add_paragraph("Asha Candidate")
    doc.add_paragraph("asha@example.test")
    doc.add_paragraph("Skills: AWS, Docker")
    doc.add_paragraph("Jan 2020 - Dec 2022")
    out = BytesIO()
    doc.save(out)
    return out.getvalue()


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("STAGE", "dev")
    monkeypatch.setenv("UPLOADS_BUCKET", BUCKET)
    monkeypatch.setenv("JOBS_TABLE", "rs-dev-jobs")
    monkeypatch.setenv("CANDIDATES_TABLE", "rs-dev-candidates")
    monkeypatch.setenv("FAILED_TABLE", "rs-dev-failed-jobs")
    monkeypatch.setenv("SCORE_QUEUE_URL", "placeholder")
    monkeypatch.setenv("PARSER_VERSION", "1.0.0")
    monkeypatch.setenv("SCORER_VERSION", "1.0.0")
    monkeypatch.setenv("CUSTOM_RECOGNIZER_ARN", "DISABLED")
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
        original_client = boto3.client

        def client(service, *args, **kwargs):
            if service == "comprehend":
                return FakeComprehend()
            return original_client(service, *args, **kwargs)

        monkeypatch.setattr(boto3, "client", client)
        jobs.put_item(Item={
            "job_id": JOB,
            "title": "DevOps Engineer",
            "status": "JD_UPLOADED",
            "threshold": Decimal("60"),
            "jd_s3_key": f"jd/{JOB}/role.txt",
            "required_skills": [],
            "jd_titles": [],
            "required_years": None,
            "parser_version": "1.0.0",
            "created_by": "recruiter-sub",
            "created_at": "2026-11-24T00:00:00Z",
            "jd_parsed_at": None,
        })
        yield jobs, candidates, failed, s3, sqs, queue_url


def notification(key):
    return json.dumps({"Records": [{
        "s3": {"bucket": {"name": BUCKET}, "object": {"key": quote_plus(key, safe="/")}},
    }]})


def test_resume_and_jd_flow_produces_schema_valid_scored_candidate(env):
    jobs, candidates, failed, s3, sqs, queue_url = env
    resume_key = f"resumes/{JOB}/asha.docx"
    jd_key = f"jd/{JOB}/role.txt"
    s3.put_object(Bucket=BUCKET, Key=resume_key, Body=make_docx())
    s3.put_object(
        Bucket=BUCKET, Key=jd_key,
        Body=b"DevOps Engineer requires AWS and Docker. Minimum 2 years experience.",
        ContentType="text/plain",
    )

    # S3 -> parse queue -> resume parser
    parse_resume({"Records": [{
        "messageId": "resume-event",
        "body": notification(resume_key),
    }]}, None)

    # S3 -> JD queue -> JD parser; this also emits JD_READY for parsed candidates.
    parse_jd({"Records": [{
        "messageId": "jd-event",
        "body": notification(jd_key),
    }]}, None)

    queued = sqs.receive_message(
        QueueUrl=queue_url, MaxNumberOfMessages=10
    ).get("Messages", [])
    assert len(queued) == 2
    for message in queued:
        score_batch({"Records": [{"body": message["Body"]}]}, None)

    candidate_id = __import__("hashlib").sha256(
        f"{JOB}/{resume_key}".encode("utf-8")
    ).hexdigest()[:16]
    candidate = candidates.get_item(
        Key={"job_id": JOB, "candidate_id": candidate_id},
        ConsistentRead=True,
    )["Item"]
    job = jobs.get_item(Key={"job_id": JOB}, ConsistentRead=True)["Item"]

    assert job["status"] == "JD_PARSED"
    assert job["required_skills"] == ["aws", "docker"]
    assert candidate["status"] == "SCORED"
    assert candidate["skills"] == ["aws", "docker"]
    assert candidate["score"] == Decimal("70.0")
    assert candidate["above_threshold"] is True
    assert candidate["score_breakdown"]["skills"]["matched"] == ["aws", "docker"]
    assert not failed.scan()["Items"]

    schema = json.loads(
        __import__("pathlib").Path("contracts/candidate.schema.json").read_text()
    )
    assert not list(Draft7Validator(schema).iter_errors(_to_native(candidate)))
