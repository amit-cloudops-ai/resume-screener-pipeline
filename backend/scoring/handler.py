"""SQS-triggered scoring Lambda for Part B (task B2)."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import boto3

from scoring import score_candidate


_ALLOWED_REASONS = {"CANDIDATE_PARSED", "JD_READY", "RESCORE"}


def _to_native(value: Any) -> Any:
    """Convert DynamoDB Decimal values into numbers accepted by scoring.py."""
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, dict):
        return {key: _to_native(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_native(item) for item in value]
    return value


def _to_dynamodb(value: Any) -> Any:
    """Convert Python floats into Decimal values accepted by boto3 DynamoDB."""
    if isinstance(value, bool) or value is None or isinstance(value, (str, int)):
        return value
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {key: _to_dynamodb(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_dynamodb(item) for item in value]
    return value


def _tables():
    """Create table resources lazily so imports and unit tests need no AWS access."""
    dynamodb = boto3.resource("dynamodb", region_name=os.getenv("AWS_REGION", "us-east-1"))
    jobs_table_name = os.environ["JOBS_TABLE"]
    candidates_table_name = os.environ["CANDIDATES_TABLE"]
    return dynamodb.Table(jobs_table_name), dynamodb.Table(candidates_table_name)


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _process_message(body: str, jobs_table, candidates_table) -> None:
    try:
        message = json.loads(body)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("score message body must be valid JSON") from exc

    if not isinstance(message, dict):
        raise ValueError("score message body must be a JSON object")

    job_id = message.get("job_id")
    candidate_id = message.get("candidate_id")
    reason = message.get("reason")

    if not isinstance(job_id, str) or not isinstance(candidate_id, str):
        raise ValueError("score message requires string job_id and candidate_id")
    if reason not in _ALLOWED_REASONS:
        raise ValueError(f"unsupported score message reason: {reason!r}")

    job_response = jobs_table.get_item(Key={"job_id": job_id}, ConsistentRead=True)
    candidate_response = candidates_table.get_item(
        Key={"job_id": job_id, "candidate_id": candidate_id},
        ConsistentRead=True,
    )
    job = job_response.get("Item")
    candidate = candidate_response.get("Item")

    if job is None:
        raise LookupError(f"job not found: {job_id}")
    if candidate is None:
        raise LookupError(f"candidate not found: {candidate_id}")

    # A JD_READY message can arrive before the JD parser has finished. Raising
    # makes SQS retry it; the queue's redrive policy eventually routes exhaustion
    # to the score DLQ.
    if job.get("status") != "JD_PARSED":
        raise RuntimeError(f"job {job_id} is not JD_PARSED")

    if candidate.get("status") not in {"PARSED", "SCORED"}:
        raise RuntimeError(
            f"candidate {candidate_id} is not ready for scoring "
            f"(status={candidate.get('status')!r})"
        )

    candidate_values = _to_native(candidate)
    result = score_candidate(candidate_values, _to_native(job))
    score_fields = {
        "score": result["score"],
        "score_breakdown": result["score_breakdown"],
        "above_threshold": result["above_threshold"],
    }

    # Duplicate deliveries should not change scored_at when the calculated
    # result is identical. RESCORE intentionally refreshes the timestamp.
    # boto3 reads DynamoDB numbers as Decimal; compare normalized values so
    # equivalent values such as Decimal("0.3") and 0.3 remain idempotent.
    same_result = all(candidate_values.get(key) == value for key, value in score_fields.items())
    if candidate.get("status") == "SCORED" and same_result and reason != "RESCORE":
        return

    candidates_table.update_item(
        Key={"job_id": job_id, "candidate_id": candidate_id},
        UpdateExpression=(
            "SET #score = :score, score_breakdown = :breakdown, "
            "above_threshold = :above, #status = :scored, scored_at = :scored_at"
        ),
        ConditionExpression="#status = :parsed OR #status = :scored",
        ExpressionAttributeNames={"#score": "score", "#status": "status"},
        ExpressionAttributeValues={
            ":score": _to_dynamodb(result["score"]),
            ":breakdown": _to_dynamodb(result["score_breakdown"]),
            ":above": result["above_threshold"],
            ":scored": "SCORED",
            ":parsed": "PARSED",
            ":scored_at": _timestamp(),
        },
    )


def lambda_handler(event, context):
    """Process an SQS batch; an exception retries the batch per queue policy."""
    records = event.get("Records", []) if isinstance(event, dict) else []
    if not isinstance(records, list):
        raise ValueError("SQS event Records must be a list")

    jobs_table, candidates_table = _tables()
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("body"), str):
            raise ValueError("each SQS record must contain a string body")
        _process_message(record["body"], jobs_table, candidates_table)

    return {"processed": len(records)}
