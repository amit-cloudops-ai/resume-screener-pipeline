import copy
import json
import pathlib
from decimal import Decimal

import pytest
from jsonschema import Draft7Validator

from app import candidate_id_for, handler

ROOT = pathlib.Path(__file__).resolve().parents[3]
SCHEMA = json.loads((ROOT / "contracts/failed_job.schema.json").read_text())
FIXTURE = json.loads((ROOT / "fixtures/failed_jobs/failed_corrupt.json").read_text())
ERROR_SCHEMA = {
    "type": "object", "required": ["error"],
    "properties": {"error": {"type": "string"}, "detail": {"type": "string"}},
}


def payload(response):
    return json.loads(response["body"])


class FakeTable:
    def __init__(self, items=None, pages=None, conditional_error=False, read_error=None, update_error=None):
        self.items = {x["failed_id"]: copy.deepcopy(x) for x in ([FIXTURE] if items is None else items)}
        self.pages = list(pages or [])
        self.conditional_error = conditional_error
        self.read_error = read_error
        self.update_error = update_error
        self.calls = []

    def scan(self, **kwargs):
        self.calls.append(("scan", kwargs))
        if self.read_error:
            raise self.read_error
        return self.pages.pop(0) if self.pages else {"Items": list(self.items.values())}

    def query(self, **kwargs):
        self.calls.append(("query", kwargs))
        if self.read_error:
            raise self.read_error
        return self.pages.pop(0) if self.pages else {"Items": list(self.items.values())}

    def get_item(self, **kwargs):
        if self.read_error:
            raise self.read_error
        return {"Item": copy.deepcopy(self.items[kwargs["Key"]["failed_id"]])} if kwargs["Key"]["failed_id"] in self.items else {}

    def update_item(self, **kwargs):
        if self.conditional_error:
            raise ConditionalFailure()
        if self.update_error:
            raise self.update_error
        item = self.items[kwargs["Key"]["failed_id"]]
        item["status"] = "RETRIED"
        item["message_id"] = kwargs["ExpressionAttributeValues"][":message_id"]
        return {"Attributes": copy.deepcopy(item)}


class ConditionalFailure(Exception):
    response = {"Error": {"Code": "ConditionalCheckFailedException"}}


class FakeSqs:
    def __init__(self, fail_send=False, url_error=None):
        self.fail_send = fail_send
        self.url_error = url_error
        self.urls = []
        self.sent = []

    def get_queue_url(self, **kwargs):
        if self.url_error:
            raise self.url_error
        self.urls.append(kwargs["QueueName"])
        return {"QueueUrl": "https://sqs.test/" + kwargs["QueueName"]}

    def send_message(self, **kwargs):
        if self.fail_send:
            raise RuntimeError("send failed")
        self.sent.append(kwargs)
        return {"MessageId": "message-123"}


def invoke_get(table, query=None):
    return handler({"httpMethod": "GET", "queryStringParameters": query}, None, table=table, sqs=FakeSqs())


def test_get_without_job_id_scans_and_returns_exact_wrapper():
    table = FakeTable()
    result = invoke_get(table)
    assert result["statusCode"] == 200
    assert set(payload(result)) == {"failed_jobs"}
    assert payload(result)["failed_jobs"] == [FIXTURE]
    assert table.calls[0][0] == "scan"
    Draft7Validator(SCHEMA).validate(payload(result)["failed_jobs"][0])


def test_get_with_job_id_queries_documented_gsi():
    table = FakeTable()
    result = invoke_get(table, {"job_id": FIXTURE["job_id"]})
    assert result["statusCode"] == 200
    assert table.calls[0][0] == "query"
    assert table.calls[0][1]["IndexName"] == "job_id-created_at"


def test_get_empty_results():
    assert payload(invoke_get(FakeTable(items=[]))) == {"failed_jobs": []}


def test_get_rejects_explicit_empty_job_id_without_scanning():
    table = FakeTable()
    response = invoke_get(table, {"job_id": ""})
    assert response["statusCode"] == 400
    assert payload(response) == {"error": "job_id must be a non-empty string"}
    assert not table.calls


def test_get_converts_dynamodb_decimal_to_schema_integer():
    item = copy.deepcopy(FIXTURE)
    item["attempts"] = Decimal("3")
    result = payload(invoke_get(FakeTable([item])))
    assert result["failed_jobs"][0]["attempts"] == 3
    assert isinstance(result["failed_jobs"][0]["attempts"], int)
    Draft7Validator(SCHEMA).validate(result["failed_jobs"][0])


@pytest.mark.parametrize("query", [None, {"job_id": "job-1"}])
def test_get_consumes_dynamodb_pages(query):
    first = copy.deepcopy(FIXTURE)
    second = copy.deepcopy(FIXTURE)
    second["failed_id"] = "f-0002"
    table = FakeTable(items=[], pages=[{"Items": [first], "LastEvaluatedKey": {"failed_id": "f-0001"}}, {"Items": [second]}])
    result = invoke_get(table, query)
    assert [x["failed_id"] for x in payload(result)["failed_jobs"]] == ["f-0001", "f-0002"]
    assert len(table.calls) == 2
    assert table.calls[1][1]["ExclusiveStartKey"] == {"failed_id": "f-0001"}


@pytest.mark.parametrize("stage,queue", [
    ("JD_PARSE", "jd-queue"), ("PARSE", "parse-queue"),
    ("TEXT_EXTRACT", "parse-queue"), ("COMPREHEND", "parse-queue"),
    ("SCORE", "score-queue"),
])
def test_retry_uses_stage_queue_and_exact_message_contract(stage, queue):
    item = copy.deepcopy(FIXTURE)
    item["stage"] = stage
    if stage == "JD_PARSE":
        item["s3_key"] = "jd/a1b2c3d4e5f6/role.pdf"
    table, sqs = FakeTable([item]), FakeSqs()
    response = handler(
        {"httpMethod": "POST", "pathParameters": {"failed_id": item["failed_id"]}}, None,
        table=table, sqs=sqs,
        environ={"UPLOADS_BUCKET": "uploads-test", "STAGE": "dev"},
    )
    assert response["statusCode"] == 202
    returned = payload(response)
    Draft7Validator(SCHEMA).validate(returned)
    assert returned["status"] == "RETRIED"
    assert returned["message_id"] == "message-123"
    assert sqs.urls == [f"rs-dev-{queue}"]
    assert len(sqs.sent) == 1
    sent_body = json.loads(sqs.sent[0]["MessageBody"])
    if stage == "SCORE":
        expected_id = candidate_id_for(item["job_id"], item["s3_key"])
        assert sqs.sent[0]["MessageBody"] == json.dumps(
            {"job_id": item["job_id"], "candidate_id": expected_id, "reason": "RESCORE"},
            separators=(",", ":"),
        )
    else:
        assert set(sent_body) == {"Records"}
        record = sent_body["Records"][0]
        assert set(record) == {"s3"}
        assert record["s3"]["bucket"] == {"name": "uploads-test"}
        assert record["s3"]["object"]["key"] == item["s3_key"]
        assert set(record["s3"]["object"]) == {"key"}
        assert sqs.sent[0]["QueueUrl"].endswith(queue)


@pytest.mark.parametrize("stage,key,encoded", [
    ("JD_PARSE", "jd/job-1/role résumé + #?.pdf", "jd/job-1/role+r%C3%A9sum%C3%A9+%2B+%23%3F.pdf"),
    ("PARSE", "resumes/job-1/candidate résumé + #?.pdf", "resumes/job-1/candidate+r%C3%A9sum%C3%A9+%2B+%23%3F.pdf"),
])
def test_jd_and_parse_retry_use_exact_contract_s3_payload(stage, key, encoded):
    item = copy.deepcopy(FIXTURE)
    item.update(stage=stage, s3_key=key)
    sqs = FakeSqs()
    response = handler({"httpMethod": "POST", "pathParameters": {"failed_id": item["failed_id"]}}, None,
                       table=FakeTable([item]), sqs=sqs,
                       environ={"UPLOADS_BUCKET": "uploads-test", "STAGE": "dev"})
    assert response["statusCode"] == 202
    assert sqs.sent[0]["MessageBody"] == json.dumps({
        "Records": [{"s3": {"bucket": {"name": "uploads-test"}, "object": {"key": encoded}}}],
    }, separators=(",", ":"))


def test_score_candidate_id_uses_d13():
    assert candidate_id_for("a1b2c3d4e5f6", "resumes/a1b2c3d4e5f6/broken.pdf") == "25d5391508c49774"


def test_missing_failed_id_returns_openapi_error_shape():
    response = handler({"httpMethod": "POST", "pathParameters": {"failed_id": "missing"}}, None,
                       table=FakeTable(items=[]), sqs=FakeSqs())
    assert response["statusCode"] == 404
    assert not list(Draft7Validator(ERROR_SCHEMA).iter_errors(payload(response)))


def test_unknown_stage_returns_400_without_sending():
    item = copy.deepcopy(FIXTURE)
    item["stage"] = "UNKNOWN"
    sqs = FakeSqs()
    response = handler({"httpMethod": "POST", "pathParameters": {"failed_id": item["failed_id"]}}, None,
                       table=FakeTable([item]), sqs=sqs)
    assert response["statusCode"] == 400
    assert not sqs.sent
    assert not list(Draft7Validator(ERROR_SCHEMA).iter_errors(payload(response)))


def test_unsupported_stage_returns_400_without_sending():
    item = copy.deepcopy(FIXTURE)
    item["stage"] = "NEW_STAGE"
    sqs = FakeSqs()
    response = handler({"httpMethod": "POST", "pathParameters": {"failed_id": item["failed_id"]}}, None,
                       table=FakeTable([item]), sqs=sqs)
    assert response["statusCode"] == 400
    assert not sqs.sent


@pytest.mark.parametrize("status", ["RETRIED", "RESOLVED"])
def test_non_open_job_returns_409_without_sending(status):
    item = copy.deepcopy(FIXTURE)
    item["status"] = status
    sqs = FakeSqs()
    response = handler({"httpMethod": "POST", "pathParameters": {"failed_id": item["failed_id"]}}, None,
                       table=FakeTable([item]), sqs=sqs)
    assert response["statusCode"] == 409
    assert not sqs.sent
    assert not list(Draft7Validator(ERROR_SCHEMA).iter_errors(payload(response)))


def test_sqs_failure_leaves_open_status():
    table, sqs = FakeTable(), FakeSqs(fail_send=True)
    response = handler({"httpMethod": "POST", "pathParameters": {"failed_id": FIXTURE["failed_id"]}}, None,
                       table=table, sqs=sqs,
                       environ={"UPLOADS_BUCKET": "uploads-test", "STAGE": "dev"})
    assert response["statusCode"] == 500
    assert payload(response) == {"error": "Internal server error"}
    assert table.items[FIXTURE["failed_id"]]["status"] == "OPEN"


def test_conditional_update_failure_returns_409_after_message_send():
    table, sqs = FakeTable(conditional_error=True), FakeSqs()
    response = handler({"httpMethod": "POST", "pathParameters": {"failed_id": FIXTURE["failed_id"]}}, None,
                       table=table, sqs=sqs,
                       environ={"UPLOADS_BUCKET": "uploads-test", "STAGE": "dev"})
    assert response["statusCode"] == 409
    assert len(sqs.sent) == 1
    assert table.items[FIXTURE["failed_id"]]["status"] == "OPEN"


@pytest.mark.parametrize("stage,key", [
    ("JD_PARSE", "resumes/job-1/file.pdf"),
    ("PARSE", "jd/job-1/file.pdf"),
    ("TEXT_EXTRACT", "jd/job-1/file.pdf"),
    ("COMPREHEND", "jd/job-1/file.pdf"),
])
def test_retry_rejects_s3_prefix_that_does_not_match_stage(stage, key):
    item = copy.deepcopy(FIXTURE)
    item.update(stage=stage, s3_key=key)
    sqs = FakeSqs()
    response = handler({"httpMethod": "POST", "pathParameters": {"failed_id": item["failed_id"]}}, None,
                       table=FakeTable([item]), sqs=sqs,
                       environ={"UPLOADS_BUCKET": "uploads-test", "STAGE": "dev"})
    assert response["statusCode"] == 400
    assert not sqs.sent


def test_retry_rejects_malformed_record_without_leaking_details():
    item = copy.deepcopy(FIXTURE)
    item["stage"] = []
    sqs = FakeSqs()
    response = handler({"httpMethod": "POST", "pathParameters": {"failed_id": item["failed_id"]}}, None,
                       table=FakeTable([item]), sqs=sqs,
                       environ={"UPLOADS_BUCKET": "uploads-test", "STAGE": "dev"})
    assert response["statusCode"] == 500
    assert payload(response) == {"error": "Internal server error"}
    assert not sqs.sent


@pytest.mark.parametrize("environ", [
    {"UPLOADS_BUCKET": "uploads-test"},
    {"STAGE": "dev"},
])
def test_retry_requires_stage_and_bucket_configuration(environ):
    response = handler({"httpMethod": "POST", "pathParameters": {"failed_id": FIXTURE["failed_id"]}}, None,
                       table=FakeTable(), sqs=FakeSqs(), environ=environ)
    assert response["statusCode"] == 500
    assert payload(response) == {"error": "Internal server error"}


def test_retry_handles_queue_url_lookup_failure_generically():
    response = handler({"httpMethod": "POST", "pathParameters": {"failed_id": FIXTURE["failed_id"]}}, None,
                       table=FakeTable(), sqs=FakeSqs(url_error=RuntimeError("private details")),
                       environ={"UPLOADS_BUCKET": "uploads-test", "STAGE": "dev"})
    assert response["statusCode"] == 500
    assert payload(response) == {"error": "Internal server error"}


def test_retry_handles_dynamodb_read_failure_generically():
    response = handler({"httpMethod": "POST", "pathParameters": {"failed_id": FIXTURE["failed_id"]}}, None,
                       table=FakeTable(read_error=RuntimeError("private details")), sqs=FakeSqs(),
                       environ={"UPLOADS_BUCKET": "uploads-test", "STAGE": "dev"})
    assert response["statusCode"] == 500
    assert payload(response) == {"error": "Internal server error"}


def test_get_handles_dynamodb_read_failure_generically():
    response = invoke_get(FakeTable(read_error=RuntimeError("private details")))
    assert response["statusCode"] == 500
    assert payload(response) == {"error": "Internal server error"}


def test_retry_handles_dynamodb_update_failure_after_send_and_can_duplicate():
    table, sqs = FakeTable(update_error=RuntimeError("write response lost")), FakeSqs()
    event = {"httpMethod": "POST", "pathParameters": {"failed_id": FIXTURE["failed_id"]}}
    config = {"UPLOADS_BUCKET": "uploads-test", "STAGE": "dev"}

    first = handler(event, None, table=table, sqs=sqs, environ=config)
    assert first["statusCode"] == 500
    assert payload(first) == {"error": "Internal server error"}
    assert table.items[FIXTURE["failed_id"]]["status"] == "OPEN"
    assert len(sqs.sent) == 1

    # The failed status write leaves OPEN, so a later request can send again.
    table.update_error = None
    second = handler(event, None, table=table, sqs=sqs, environ=config)
    assert second["statusCode"] == 202
    assert len(sqs.sent) == 2


def test_sqs_send_failure_returns_generic_error_and_leaves_open():
    table, sqs = FakeTable(), FakeSqs(fail_send=True)
    response = handler({"httpMethod": "POST", "pathParameters": {"failed_id": FIXTURE["failed_id"]}}, None,
                       table=table, sqs=sqs,
                       environ={"UPLOADS_BUCKET": "uploads-test", "STAGE": "dev"})
    assert response["statusCode"] == 500
    assert payload(response) == {"error": "Internal server error"}
    assert table.items[FIXTURE["failed_id"]]["status"] == "OPEN"
