"""DLQ consumer: record exhausted parse/JD/score messages for recruiter retry."""
from __future__ import annotations

import hashlib
import json
import logging
import os

import boto3

try:
    from ..common import parse_s3_notification, utc_now
except ImportError:
    from common import parse_s3_notification, utc_now

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _clients():
    ddb = boto3.resource("dynamodb", region_name=os.getenv("AWS_REGION", "us-east-1"))
    return (
        ddb.Table(os.environ["FAILED_TABLE"]),
        ddb.Table(os.environ["CANDIDATES_TABLE"]),
    )


def _record(record, failed_table, candidates_table):
    body = record.get("body", "")
    source_arn = record.get("eventSourceARN", "")
    message_id = record.get("messageId")
    attributes = record.get("attributes") or {}
    attempts = int(attributes.get("ApproximateReceiveCount", "1"))
    if source_arn.endswith("parse-dlq"):
        stage = "PARSE"
    elif source_arn.endswith("jd-dlq"):
        stage = "JD_PARSE"
    elif source_arn.endswith("score-dlq"):
        stage = "SCORE"
    else:
        stage = "UNKNOWN"

    job_id, s3_key = "unknown", "unknown"
    try:
        message = json.loads(body)
    except (TypeError, json.JSONDecodeError):
        message = None

    if stage in {"PARSE", "JD_PARSE"}:
        try:
            _, s3_key = parse_s3_notification(body)
            parts = s3_key.split("/", 2)
            job_id = parts[1] if len(parts) == 3 else "unknown"
        except Exception:
            stage = "UNKNOWN"
    elif stage == "SCORE" and isinstance(message, dict):
        job_id = message.get("job_id", "unknown")
        candidate_id = message.get("candidate_id")
        if isinstance(job_id, str) and isinstance(candidate_id, str):
            candidate = candidates_table.get_item(
                Key={"job_id": job_id, "candidate_id": candidate_id},
                ConsistentRead=True,
            ).get("Item")
            if candidate:
                s3_key = candidate.get("source_key", "unknown")
            else:
                s3_key = f"score/{job_id}/{candidate_id}"
        else:
            stage = "UNKNOWN"
    else:
        stage = "UNKNOWN"

    failed_id = hashlib.sha256(
        f"{source_arn}/{message_id or body}".encode("utf-8")
    ).hexdigest()[:32]
    item = {
        "failed_id": failed_id,
        "job_id": str(job_id),
        "stage": stage,
        "s3_key": str(s3_key),
        "error_type": "TRANSIENT_EXHAUSTED" if stage != "UNKNOWN" else "UNKNOWN",
        "error_message": "Message exhausted its SQS receive attempts and reached a dead-letter queue.",
        "attempts": attempts,
        "message_id": message_id if isinstance(message_id, str) else None,
        "status": "OPEN",
        "created_at": utc_now(),
    }
    try:
        failed_table.put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(failed_id)",
        )
    except Exception as exc:
        # Duplicate DLQ deliveries are harmless; all other persistence errors retry.
        code = getattr(exc, "response", {}).get("Error", {}).get("Code")
        if code != "ConditionalCheckFailedException":
            raise


def lambda_handler(event, context):
    records = event.get("Records", []) if isinstance(event, dict) else []
    if not isinstance(records, list):
        raise ValueError("SQS event Records must be a list")
    failed_table, candidates_table = _clients()
    failures = []
    for record in records:
        message_id = record.get("messageId", "unknown") if isinstance(record, dict) else "unknown"
        try:
            if not isinstance(record, dict):
                raise ValueError("invalid SQS record")
            _record(record, failed_table, candidates_table)
        except Exception:
            logger.exception("DLQ persistence failed message_id=%s", message_id)
            failures.append({"itemIdentifier": message_id})
    return {"batchItemFailures": failures}
