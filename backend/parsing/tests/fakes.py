"""Fake Textract / Comprehend clients and a moto-backed AWS environment for handler tests."""
import json

import boto3
from botocore.exceptions import ClientError

import config
from aws_io import Deps, Store


def client_error(code, op="Op"):
    return ClientError({"Error": {"Code": code, "Message": "x"}}, op)


class FakeTextract:
    def __init__(self, pages=None, statuses=None, start_error=None, fail=False):
        self.pages = pages or [["Hello world"]]
        self.statuses = list(statuses or [])  # extra IN_PROGRESS answers before success
        self.start_error, self.fail, self.calls = start_error, fail, 0

    def start_document_text_detection(self, **kw):
        if self.start_error:
            raise client_error(self.start_error)
        return {"JobId": "job-1"}

    def get_document_text_detection(self, JobId, NextToken=None):
        self.calls += 1
        if self.statuses:
            return {"JobStatus": self.statuses.pop(0)}
        if self.fail:
            return {"JobStatus": "FAILED"}
        page = int(NextToken or 0)
        resp = {"JobStatus": "SUCCEEDED", "Blocks": [{"BlockType": "LINE", "Text": t} for t in self.pages[page]]}
        if page + 1 < len(self.pages):
            resp["NextToken"] = str(page + 1)
        return resp


class FakeComprehend:
    def __init__(self, standard=None, custom=None, error=None):
        self.standard, self.custom, self.error, self.calls = standard or [], custom or [], error, []

    def detect_entities(self, **kw):
        self.calls.append(kw)
        if self.error:
            raise client_error(self.error)
        ents = self.custom if "EndpointArn" in kw else self.standard
        return {"Entities": [{"Score": 0.99, **e} for e in ents]}


def make_env(textract=None, comprehend=None):
    """Create the moto resources; call inside `with mock_aws():`."""
    ddb = boto3.resource("dynamodb")
    ddb.create_table(TableName=config.table_name("candidates"), BillingMode="PAY_PER_REQUEST",
                     KeySchema=[{"AttributeName": "job_id", "KeyType": "HASH"}, {"AttributeName": "candidate_id", "KeyType": "RANGE"}],
                     AttributeDefinitions=[{"AttributeName": "job_id", "AttributeType": "S"}, {"AttributeName": "candidate_id", "AttributeType": "S"}])
    ddb.create_table(TableName=config.table_name("jobs"), BillingMode="PAY_PER_REQUEST",
                     KeySchema=[{"AttributeName": "job_id", "KeyType": "HASH"}],
                     AttributeDefinitions=[{"AttributeName": "job_id", "AttributeType": "S"}])
    ddb.create_table(TableName=config.table_name("failed_jobs"), BillingMode="PAY_PER_REQUEST",
                     KeySchema=[{"AttributeName": "failed_id", "KeyType": "HASH"}],
                     AttributeDefinitions=[{"AttributeName": "failed_id", "AttributeType": "S"}])
    s3, sqs = boto3.client("s3"), boto3.client("sqs")
    s3.create_bucket(Bucket="rs-dev-uploads")
    sqs.create_queue(QueueName=config.score_queue_name())
    return Deps(s3=s3, textract=textract or FakeTextract(), comprehend=comprehend or FakeComprehend(),
                sqs=sqs, store=Store(ddb))


def s3_event_body(key, bucket="rs-dev-uploads"):
    return json.dumps({"Records": [{"s3": {"bucket": {"name": bucket}, "object": {"key": key}}}]})


def sqs_event(*bodies, arn="arn:aws:sqs:us-east-1:1:rs-dev-parse-queue"):
    return {"Records": [{"body": b, "messageId": f"m{i}", "eventSourceARN": arn} for i, b in enumerate(bodies)]}


def score_messages(deps):
    msgs = deps.sqs.receive_message(QueueUrl=deps.score_queue_url, MaxNumberOfMessages=10).get("Messages", [])
    return [json.loads(m["Body"]) for m in msgs]
