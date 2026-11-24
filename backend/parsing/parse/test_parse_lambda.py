"""Moto-backed resume parsing Lambda tests."""
import json
from io import BytesIO
from urllib.parse import quote_plus

import boto3
from docx import Document
import pytest
from moto import mock_aws

from backend.parsing.parse.app import lambda_handler
from backend.parsing.common import candidate_id_for

JOB = "a1b2c3d4e5f6"
BUCKET = "rs-dev-uploads-test"


class FakeComprehend:
    def detect_entities(self, **kwargs):
        text = kwargs["Text"]
        entities = []
        if "Priya Sharma" in text:
            entities.append({"Type": "PERSON", "Text": "Priya Sharma"})
        if "Acme Systems" in text:
            entities.append({"Type": "ORGANIZATION", "Text": "Acme Systems"})
        return {"Entities": entities}


def docx_bytes():
    doc = Document()
    doc.add_paragraph("Priya Sharma")
    doc.add_paragraph("Email: priya@example.test")
    doc.add_paragraph("Platform Engineer at Acme Systems")
    doc.add_paragraph("Skills: AWS, Docker, Kubernetes, Python")
    doc.add_paragraph("Jan 2020 - Dec 2022")
    output = BytesIO()
    doc.save(output)
    return output.getvalue()


@pytest.fixture
def aws(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("UPLOADS_BUCKET", BUCKET)
    monkeypatch.setenv("CANDIDATES_TABLE", "rs-dev-candidates")
    monkeypatch.setenv("FAILED_TABLE", "rs-dev-failed-jobs")
    monkeypatch.setenv("PARSER_VERSION", "1.0.0")
    monkeypatch.setenv("CUSTOM_RECOGNIZER_ARN", "DISABLED")
    with mock_aws():
        ddb = boto3.resource("dynamodb", region_name="us-east-1")
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
        yield candidates, failed, s3, sqs, queue_url


def s3_event(key):
    return json.dumps({
        "Records": [{
            "eventSource": "aws:s3",
            "eventName": "ObjectCreated:Put",
            "s3": {"bucket": {"name": BUCKET}, "object": {"key": quote_plus(key, safe="/")}},
        }]
    })


def invoke(key, message_id="msg-1"):
    return lambda_handler({
        "Records": [{"messageId": message_id, "body": s3_event(key)}]
    }, None)


def test_docx_is_parsed_and_score_message_is_enqueued(aws):
    candidates, _, s3, sqs, queue_url = aws
    key = f"resumes/{JOB}/priya.docx"
    s3.put_object(Bucket=BUCKET, Key=key, Body=docx_bytes())
    result = invoke(key)
    assert result == {"batchItemFailures": []}
    candidate_id = candidate_id_for(JOB, key)
    item = candidates.get_item(Key={"job_id": JOB, "candidate_id": candidate_id})["Item"]
    assert item["status"] == "PARSED"
    assert item["name"] == "Priya Sharma"
    assert item["email"] == "priya@example.test"
    assert item["skills"] == ["aws", "docker", "kubernetes", "python"]
    assert item["employers"] == ["Acme Systems"]
    assert item["experience_years"] == 3
    assert item["parsed_s3_key"] == f"parsed/{JOB}/{candidate_id}.json"
    message = json.loads(sqs.receive_message(QueueUrl=queue_url)["Messages"][0]["Body"])
    assert message == {"job_id": JOB, "candidate_id": candidate_id, "reason": "CANDIDATE_PARSED"}


def test_duplicate_parsed_event_republishes_score_message_without_rewriting_candidate(aws):
    candidates, _, s3, sqs, queue_url = aws
    key = f"resumes/{JOB}/priya.docx"
    s3.put_object(Bucket=BUCKET, Key=key, Body=docx_bytes())
    invoke(key, "first")
    candidate_id = candidate_id_for(JOB, key)
    candidates.update_item(
        Key={"job_id": JOB, "candidate_id": candidate_id},
        UpdateExpression="SET decision = :decision, #status = :scored",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={":decision": "SHORTLISTED", ":scored": "SCORED"},
    )
    invoke(key, "duplicate")
    item = candidates.get_item(Key={"job_id": JOB, "candidate_id": candidate_id})["Item"]
    assert item["status"] == "SCORED"
    assert item["decision"] == "SHORTLISTED"
    assert len(sqs.receive_message(QueueUrl=queue_url)["Messages"]) == 1


def test_oversized_resume_is_recorded_as_permanent_failure(aws):
    candidates, failed, s3, _, _ = aws
    key = f"resumes/{JOB}/large.pdf"
    s3.put_object(Bucket=BUCKET, Key=key, Body=b"x" * (5 * 1024 * 1024 + 1))
    result = invoke(key)
    assert result == {"batchItemFailures": []}
    candidate_id = candidate_id_for(JOB, key)
    item = candidates.get_item(Key={"job_id": JOB, "candidate_id": candidate_id})["Item"]
    assert item["status"] == "FAILED"
    records = failed.scan()["Items"]
    assert len(records) == 1
    assert records[0]["error_type"] == "UNSUPPORTED_TYPE"
    assert records[0]["status"] == "OPEN"


def test_transient_comprehend_failure_returns_partial_batch_failure(aws, monkeypatch):
    _, _, s3, _, _ = aws
    key = f"resumes/{JOB}/priya.docx"
    s3.put_object(Bucket=BUCKET, Key=key, Body=docx_bytes())

    class BrokenComprehend:
        def detect_entities(self, **kwargs):
            raise RuntimeError("throttled")

    original_client = boto3.client
    def client(service, *args, **kwargs):
        if service == "comprehend":
            return BrokenComprehend()
        return original_client(service, *args, **kwargs)
    monkeypatch.setattr(boto3, "client", client)
    result = invoke(key, "transient-message")
    assert result == {"batchItemFailures": [{"itemIdentifier": "transient-message"}]}
