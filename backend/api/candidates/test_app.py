"""Moto-backed tests for the B4 candidates API."""
import copy
import json
from decimal import Decimal
from pathlib import Path

import boto3
import pytest
from jsonschema import Draft7Validator
from moto import mock_aws

from backend.api.candidates.app import lambda_handler


ROOT = Path(__file__).resolve().parents[3]
CANDIDATE_SCHEMA = json.loads(
    (ROOT / "contracts/candidate.schema.json").read_text(encoding="utf-8")
)
JOB_ID = "a1b2c3d4e5f6"
OTHER_JOB_ID = "b1b2c3d4e5f6"


def load_fixture(name):
    return json.loads((ROOT / f"fixtures/candidates/{name}").read_text(encoding="utf-8"))


def to_dynamodb_values(value):
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {key: to_dynamodb_values(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_dynamodb_values(item) for item in value]
    return value


def api_event(method, resource, *, job_id=None, candidate_id=None, query=None):
    path_parameters = {}
    if job_id is not None:
        path_parameters["job_id"] = job_id
    if candidate_id is not None:
        path_parameters["candidate_id"] = candidate_id
    return {
        "httpMethod": method,
        "resource": resource,
        "pathParameters": path_parameters,
        "queryStringParameters": query,
    }


def payload(response):
    return json.loads(response["body"])


def assert_error(response, status):
    assert response["statusCode"] == status
    body = payload(response)
    assert isinstance(body.get("error"), str)
    assert isinstance(body.get("detail"), str)


@pytest.fixture
def candidate_table(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("CANDIDATES_TABLE", "rs-dev-candidates")
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.create_table(
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
        yield table


def put_candidate(table, fixture_name, candidate_id, *, job_id=JOB_ID, score=None, decision="PENDING"):
    candidate = copy.deepcopy(load_fixture(fixture_name))
    candidate["job_id"] = job_id
    candidate["candidate_id"] = candidate_id
    candidate["score"] = score
    candidate["status"] = "SCORED" if score is not None else "PARSED"
    candidate["above_threshold"] = score is not None and score >= 60
    candidate["decision"] = decision
    table.put_item(Item=to_dynamodb_values(candidate))
    return candidate


def test_list_candidates_sorts_scores_unscored_last_counts_and_schema(candidate_table):
    put_candidate(candidate_table, "cand_strong.json", "0000000000000001", score=94.5,
                  decision="SHORTLISTED")
    put_candidate(candidate_table, "cand_partial.json", "0000000000000002", score=41.2)
    put_candidate(candidate_table, "cand_sparse.json", "0000000000000003", score=None,
                  decision="REJECTED")

    response = lambda_handler(api_event(
        "GET", "/jobs/{job_id}/candidates", job_id=JOB_ID
    ), None)

    assert response["statusCode"] == 200
    result = payload(response)
    assert set(result) == {"candidates", "counts"}
    assert [candidate["candidate_id"] for candidate in result["candidates"]] == [
        "0000000000000001", "0000000000000002", "0000000000000003"
    ]
    assert result["candidates"][-1]["score"] is None
    assert result["counts"] == {
        "total": 3, "PENDING": 1, "SHORTLISTED": 1, "REJECTED": 1
    }
    validator = Draft7Validator(CANDIDATE_SCHEMA)
    for candidate in result["candidates"]:
        validator.validate(candidate)


def test_list_candidates_keeps_zero_score_ahead_of_unscored(candidate_table):
    put_candidate(candidate_table, "cand_strong.json", "0000000000000001", score=0)
    put_candidate(candidate_table, "cand_sparse.json", "0000000000000002", score=None)

    result = payload(lambda_handler(api_event(
        "GET", "/jobs/{job_id}/candidates", job_id=JOB_ID
    ), None))

    assert [candidate["score"] for candidate in result["candidates"]] == [0, None]


def test_list_candidates_filters_by_decision_but_counts_all_candidates(candidate_table):
    put_candidate(candidate_table, "cand_strong.json", "0000000000000001", score=90,
                  decision="SHORTLISTED")
    put_candidate(candidate_table, "cand_partial.json", "0000000000000002", score=40,
                  decision="PENDING")
    put_candidate(candidate_table, "cand_sparse.json", "0000000000000003", score=None,
                  decision="SHORTLISTED")

    result = payload(lambda_handler(api_event(
        "GET", "/jobs/{job_id}/candidates", job_id=JOB_ID,
        query={"decision": "SHORTLISTED"},
    ), None))

    assert [candidate["candidate_id"] for candidate in result["candidates"]] == [
        "0000000000000001", "0000000000000003"
    ]
    assert result["counts"] == {
        "total": 3, "PENDING": 1, "SHORTLISTED": 2, "REJECTED": 0
    }


def test_list_candidates_paginates_dynamodb_query(candidate_table, monkeypatch):
    for index, score in enumerate((10, 30, 20), start=1):
        put_candidate(
            candidate_table, "cand_strong.json", f"000000000000000{index}", score=score
        )

    class OneItemPerPage:
        def __init__(self, table):
            self.table = table
            self.calls = []

        def query(self, **kwargs):
            self.calls.append(dict(kwargs))
            kwargs["Limit"] = 1
            return self.table.query(**kwargs)

    paged_table = OneItemPerPage(candidate_table)
    monkeypatch.setattr("backend.api.candidates.app._candidate_table", lambda: paged_table)

    result = payload(lambda_handler(api_event(
        "GET", "/jobs/{job_id}/candidates", job_id=JOB_ID
    ), None))

    assert len(paged_table.calls) == 3
    assert "ExclusiveStartKey" not in paged_table.calls[0]
    assert all("ExclusiveStartKey" in call for call in paged_table.calls[1:])
    assert [candidate["score"] for candidate in result["candidates"]] == [30, 20, 10]


def test_get_candidate_uses_both_partition_and_sort_keys(candidate_table):
    candidate_id = "0000000000000001"
    put_candidate(candidate_table, "cand_strong.json", candidate_id, job_id=OTHER_JOB_ID, score=60)
    requested = put_candidate(candidate_table, "cand_partial.json", candidate_id, score=45)

    response = lambda_handler(api_event(
        "GET", "/jobs/{job_id}/candidates/{candidate_id}",
        job_id=JOB_ID, candidate_id=candidate_id,
    ), None)

    assert response["statusCode"] == 200
    result = payload(response)
    Draft7Validator(CANDIDATE_SCHEMA).validate(result)
    assert result["job_id"] == JOB_ID
    assert result["name"] == requested["name"]
    assert result["score"] == 45


def test_get_candidate_returns_documented_404_when_missing(candidate_table):
    response = lambda_handler(api_event(
        "GET", "/jobs/{job_id}/candidates/{candidate_id}",
        job_id=JOB_ID, candidate_id="0000000000000001",
    ), None)

    assert_error(response, 404)


@pytest.mark.parametrize("event", [
    None,
    {"httpMethod": "GET", "resource": "/jobs/{job_id}/candidates", "pathParameters": []},
    api_event("GET", "/jobs/{job_id}/candidates", job_id="invalid"),
    api_event("GET", "/jobs/{job_id}/candidates", job_id=JOB_ID, query=[]),
    api_event("GET", "/jobs/{job_id}/candidates/{candidate_id}",
              job_id=JOB_ID, candidate_id="bad-id"),
])
def test_invalid_candidate_requests_return_error_shape(candidate_table, event):
    response = lambda_handler(event, None)
    assert_error(response, 400)


def test_list_candidates_for_empty_partition_returns_zero_counts(candidate_table):
    result = payload(lambda_handler(api_event(
        "GET", "/jobs/{job_id}/candidates", job_id=JOB_ID
    ), None))

    assert result == {
        "candidates": [],
        "counts": {"total": 0, "PENDING": 0, "SHORTLISTED": 0, "REJECTED": 0},
    }
