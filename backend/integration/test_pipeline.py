"""Local end-to-end acceptance: one JD and ten resumes, nine scored, one failed."""
import json
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from urllib.parse import quote_plus

import boto3
from boto3.dynamodb.conditions import Key
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


def make_docx(index):
    doc = Document()
    doc.add_paragraph(f"Candidate {index}")
    doc.add_paragraph(f"candidate{index}@example.test")
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


def test_one_jd_ten_resumes_yield_nine_scored_and_one_failed(env):
    jobs, candidates, failed, s3, sqs, queue_url = env
    jd_key = f"jd/{JOB}/role.txt"
    s3.put_object(
        Bucket=BUCKET, Key=jd_key,
        Body=b"DevOps Engineer requires AWS and Docker. Minimum 2 years experience.",
        ContentType="text/plain",
    )

    resume_keys = []
    resume_records = []
    for index in range(1, 11):
        key = f"resumes/{JOB}/candidate-{index}.docx"
        resume_keys.append(key)
        payload = make_docx(index) if index < 10 else b"not-a-valid-docx"
        s3.put_object(Bucket=BUCKET, Key=key, Body=payload)
        resume_records.append({
            "messageId": f"resume-{index}",
            "body": notification(key),
        })

    # Process the ten resume notifications, then the JD notification.
    parse_result = parse_resume({"Records": resume_records}, None)
    assert parse_result == {"batchItemFailures": []}
    jd_result = parse_jd({"Records": [{
        "messageId": "jd-event",
        "body": notification(jd_key),
    }]}, None)
    assert jd_result == {"batchItemFailures": []}

    job = jobs.get_item(Key={"job_id": JOB}, ConsistentRead=True)["Item"]
    assert job["status"] == "JD_PARSED"
    assert job["required_skills"] == ["aws", "docker"]

    # Drain the score queue in SQS-sized batches. Duplicate CANDIDATE_PARSED and
    # JD_READY messages are intentional and must remain idempotent.
    processed_messages = 0
    while True:
        batch = sqs.receive_message(
            QueueUrl=queue_url, MaxNumberOfMessages=10
        ).get("Messages", [])
        if not batch:
            break
        for offset in range(0, len(batch), 5):
            group = batch[offset:offset + 5]
            result = score_batch({
                "Records": [
                    {"messageId": message["MessageId"], "body": message["Body"]}
                    for message in group
                ]
            }, None)
            assert result == {"processed": len(group)}
            processed_messages += len(group)
            for message in group:
                sqs.delete_message(
                    QueueUrl=queue_url,
                    ReceiptHandle=message["ReceiptHandle"],
                )

    assert processed_messages == 18
    items = candidates.query(
        KeyConditionExpression=Key("job_id").eq(JOB)
    )["Items"]
    assert len(items) == 10
    scored = [item for item in items if item["status"] == "SCORED"]
    failed_candidates = [item for item in items if item["status"] == "FAILED"]
    assert len(scored) == 9
    assert len(failed_candidates) == 1
    assert all(item["score"] == Decimal("70.0") for item in scored)
    assert all(item["above_threshold"] is True for item in scored)

    failed_items = failed.scan()["Items"]
    assert len(failed_items) == 1
    assert failed_items[0]["stage"] == "PARSE"
    assert failed_items[0]["error_type"] == "CORRUPT_FILE"
    assert failed_items[0]["status"] == "OPEN"

    candidate_schema = json.loads(Path("contracts/candidate.schema.json").read_text())
    failed_schema = json.loads(Path("contracts/failed_job.schema.json").read_text())
    for item in items:
        assert not list(Draft7Validator(candidate_schema).iter_errors(_to_native(item)))
    for item in failed_items:
        assert not list(Draft7Validator(failed_schema).iter_errors(_to_native(item)))
