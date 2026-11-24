"""Candidate list/detail API (B4)."""
from __future__ import annotations

import json
import logging
import os
import re
from collections import Counter
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)
_ID = re.compile(r"^[0-9a-f]{12}$")
_CANDIDATE_ID = re.compile(r"^[0-9a-f]{16}$")
_DECISIONS = {"PENDING", "SHORTLISTED", "REJECTED"}


def _reply(status: int, payload: Any) -> dict:
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": os.getenv("CORS_ORIGIN", ""),
            "Vary": "Origin",
        },
        "body": json.dumps(payload, default=str),
    }


def _error(status: int, message: str) -> dict:
    return _reply(status, {"error": message})


def _table():
    return boto3.resource(
        "dynamodb", region_name=os.getenv("AWS_REGION", "us-east-1")
    ).Table(os.environ["CANDIDATES_TABLE"])


def _query_all(table, job_id: str) -> list[dict]:
    response = table.query(
        KeyConditionExpression=Key("job_id").eq(job_id)
    )
    items = response.get("Items", [])
    while response.get("LastEvaluatedKey"):
        response = table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key("job_id").eq(job_id),
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        items.extend(response.get("Items", []))
    return items


def lambda_handler(event, context):
    event = event if isinstance(event, dict) else {}
    method = event.get("httpMethod", "")
    resource = event.get("resource", "")
    path = event.get("pathParameters") or {}
    job_id = path.get("job_id")
    candidate_id = path.get("candidate_id")
    request_id = getattr(context, "aws_request_id", "unknown")
    logger.info("candidates API request_id=%s method=%s resource=%s", request_id, method, resource)

    if not isinstance(job_id, str) or not _ID.fullmatch(job_id):
        return _error(400, "job_id is invalid")
    table = _table()
    try:
        if method == "GET" and resource == "/jobs/{job_id}/candidates":
            decision = (event.get("queryStringParameters") or {}).get("decision")
            if decision is not None and decision not in _DECISIONS:
                return _error(400, "decision filter is invalid")
            items = _query_all(table, job_id)
            counts = dict(Counter(item.get("decision", "PENDING") for item in items))
            if decision:
                items = [item for item in items if item.get("decision", "PENDING") == decision]
            items.sort(
                key=lambda item: (
                    item.get("score") is None,
                    -(float(item.get("score") or 0)),
                    item.get("created_at", ""),
                    item.get("candidate_id", ""),
                )
            )
            return _reply(200, {"candidates": items, "counts": counts})

        if method == "GET" and resource == "/jobs/{job_id}/candidates/{candidate_id}":
            if not isinstance(candidate_id, str) or not _CANDIDATE_ID.fullmatch(candidate_id):
                return _error(400, "candidate_id is invalid")
            item = table.get_item(
                Key={"job_id": job_id, "candidate_id": candidate_id},
                ConsistentRead=True,
            ).get("Item")
            return _reply(200, item) if item else _error(404, "candidate not found")
        return _error(404, "route not found")
    except ClientError:
        logger.exception("candidates API AWS operation failed request_id=%s", request_id)
        return _error(500, "internal service error")
    except Exception:
        logger.exception("candidates API unexpected failure request_id=%s", request_id)
        return _error(500, "internal service error")
