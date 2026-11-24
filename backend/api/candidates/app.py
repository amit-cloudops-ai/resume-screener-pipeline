"""Candidates API Lambda (task B4)."""
from __future__ import annotations

import json
import os
import re
from decimal import Decimal
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key


_JOB_ID = re.compile(r"^[0-9a-f]{12}$")
_CANDIDATE_ID = re.compile(r"^[0-9a-f]{16}$")
_DECISIONS = ("PENDING", "SHORTLISTED", "REJECTED")


def _candidate_table():
    dynamodb = boto3.resource("dynamodb", region_name=os.getenv("AWS_REGION", "us-east-1"))
    return dynamodb.Table(os.environ["CANDIDATES_TABLE"])


def _native(value: Any) -> Any:
    """Convert DynamoDB Decimal values recursively into JSON numbers."""
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, dict):
        return {key: _native(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_native(item) for item in value]
    return value


def _response(status: int, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(payload, separators=(",", ":")),
    }


def _error(status: int, code: str, detail: str) -> dict[str, Any]:
    return _response(status, {"error": code, "detail": detail})


def _query_all_candidates(job_id: str) -> list[dict[str, Any]]:
    table = _candidate_table()
    items: list[dict[str, Any]] = []
    query_args: dict[str, Any] = {
        "KeyConditionExpression": Key("job_id").eq(job_id),
        "ConsistentRead": True,
    }
    while True:
        page = table.query(**query_args)
        items.extend(page.get("Items", []))
        last_key = page.get("LastEvaluatedKey")
        if not last_key:
            break
        query_args["ExclusiveStartKey"] = last_key
    return items


def _list_candidates(job_id: Any, event: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(job_id, str) or not _JOB_ID.fullmatch(job_id):
        return _error(400, "invalid_request", "job_id must be 12 lowercase hexadecimal characters.")

    query_params = event.get("queryStringParameters")
    if query_params is not None and not isinstance(query_params, dict):
        return _error(400, "invalid_request", "queryStringParameters must be an object.")
    decision_filter = query_params.get("decision") if query_params else None
    if decision_filter is not None and not isinstance(decision_filter, str):
        return _error(400, "invalid_request", "decision must be a string.")

    candidates = _query_all_candidates(job_id)
    # Query returns partition-key rows in candidate_id order. Python's stable sort
    # preserves that deterministic order for candidates with equal scores.
    candidates.sort(
        key=lambda candidate: (
            candidate.get("score") is not None,
            float(candidate["score"]) if candidate.get("score") is not None else 0.0,
        ),
        reverse=True,
    )

    counts = {"total": len(candidates), **{decision: 0 for decision in _DECISIONS}}
    for candidate in candidates:
        decision = candidate.get("decision")
        if decision in counts and decision != "total":
            counts[decision] += 1

    if decision_filter is not None:
        candidates = [candidate for candidate in candidates if candidate.get("decision") == decision_filter]

    return _response(200, {"candidates": _native(candidates), "counts": counts})


def _get_candidate(job_id: Any, candidate_id: Any) -> dict[str, Any]:
    if not isinstance(job_id, str) or not _JOB_ID.fullmatch(job_id):
        return _error(400, "invalid_request", "job_id must be 12 lowercase hexadecimal characters.")
    if not isinstance(candidate_id, str) or not _CANDIDATE_ID.fullmatch(candidate_id):
        return _error(400, "invalid_request", "candidate_id must be 16 lowercase hexadecimal characters.")

    response = _candidate_table().get_item(
        Key={"job_id": job_id, "candidate_id": candidate_id},
        ConsistentRead=True,
    )
    candidate = response.get("Item")
    if candidate is None:
        return _error(404, "not_found", "Candidate was not found.")
    return _response(200, _native(candidate))


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Dispatch API Gateway REST proxy events for the B4 candidates routes."""
    if not isinstance(event, dict):
        return _error(400, "invalid_request", "Request event must be an object.")
    resource = event.get("resource")
    method = event.get("httpMethod")
    params = event.get("pathParameters") or {}
    if not isinstance(params, dict):
        return _error(400, "invalid_request", "pathParameters must be an object.")

    if resource == "/jobs/{job_id}/candidates" and method == "GET":
        return _list_candidates(params.get("job_id"), event)
    if resource == "/jobs/{job_id}/candidates/{candidate_id}" and method == "GET":
        return _get_candidate(params.get("job_id"), params.get("candidate_id"))
    return _error(404, "not_found", "Route was not found.")
