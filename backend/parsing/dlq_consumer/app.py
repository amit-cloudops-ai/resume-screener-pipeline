"""DLQ consumer: record exhausted parse/JD/score messages for recruiter retry.

Classification is deliberately diagnostic: malformed events are recorded as
UNKNOWN with a safe reason in error_message, while logs retain queue provenance
without logging message bodies or candidate/resume data.
"""
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

_STAGE_BY_QUEUE_NAME = {
    f"rs-{stage}-parse-dlq": "PARSE"
    for stage in ("dev", "prod")
}
_STAGE_BY_QUEUE_NAME.update({
    f"rs-{stage}-jd-dlq": "JD_PARSE"
    for stage in ("dev", "prod")
})
_STAGE_BY_QUEUE_NAME.update({
    f"rs-{stage}-score-dlq": "SCORE"
    for stage in ("dev", "prod")
})


def _clients():
    ddb = boto3.resource("dynamodb", region_name=os.getenv("AWS_REGION", "us-east-1"))
    return (
        ddb.Table(os.environ["FAILED_TABLE"]),
        ddb.Table(os.environ["CANDIDATES_TABLE"]),
    )


def _source_arn(record: dict) -> str:
    """Read the AWS SQS event field, tolerating the documented casing variant."""
    value = record.get("eventSourceARN") or record.get("eventSourceArn") or ""
    return value if isinstance(value, str) else ""


def _classify_source(source_arn: str) -> str | None:
    """Classify only known project DLQ queue names; never infer from message data."""
    if not source_arn:
        return None
    queue_name = source_arn.rsplit(":", 1)[-1]
    return _STAGE_BY_QUEUE_NAME.get(queue_name)


def _s3_identity(body: str, expected_prefix: str) -> tuple[str, str]:
    """Extract and validate the job-scoped S3 key used by parse/JD retry."""
    _, s3_key = parse_s3_notification(body)
    parts = s3_key.split("/", 2)
    if len(parts) != 3 or parts[0] != expected_prefix or not parts[1] or not parts[2]:
        raise ValueError(f"S3 object key must match {expected_prefix}/<job_id>/<filename>")
    return parts[1], s3_key


def _record(record, failed_table, candidates_table):
    body = record.get("body", "")
    source_arn = _source_arn(record)
    message_id = record.get("messageId")
    attributes = record.get("attributes") or {}
    attempts = int(attributes.get("ApproximateReceiveCount", "1"))

    stage = _classify_source(source_arn)
    job_id, s3_key = "unknown", "unknown"
    diagnostic = None

    if stage in {"PARSE", "JD_PARSE"}:
        expected_prefix = "resumes" if stage == "PARSE" else "jd"
        try:
            job_id, s3_key = _s3_identity(body, expected_prefix)
        except Exception as exc:
            diagnostic = f"invalid_s3_notification: {type(exc).__name__}: {exc}"
            stage = "UNKNOWN"
    elif stage == "SCORE":
        try:
            message = json.loads(body)
            if not isinstance(message, dict):
                raise ValueError("score payload must be a JSON object")
            job_value = message.get("job_id")
            candidate_id = message.get("candidate_id")
            if not isinstance(job_value, str) or not job_value:
                raise ValueError("score payload is missing a valid job_id")
            if not isinstance(candidate_id, str) or not candidate_id:
                raise ValueError("score payload is missing a valid candidate_id")
            job_id = job_value
            candidate = candidates_table.get_item(
                Key={"job_id": job_id, "candidate_id": candidate_id},
                ConsistentRead=True,
            ).get("Item")
            if candidate:
                s3_key = candidate.get("source_key", "unknown")
            else:
                s3_key = f"score/{job_id}/{candidate_id}"
        except (TypeError, json.JSONDecodeError, ValueError) as exc:
            diagnostic = f"invalid_score_payload: {type(exc).__name__}: {exc}"
            stage = "UNKNOWN"
    else:
        diagnostic = "unrecognized_source_queue: eventSourceARN/eventSourceArn did not identify a project DLQ"
        stage = "UNKNOWN"

    if stage == "UNKNOWN":
        logger.warning(
            "DLQ classification unresolved message_id=%s source_arn=%s reason=%s",
            message_id or "unknown",
            source_arn or "missing",
            diagnostic or "unknown_classification_failure",
        )
    else:
        logger.info(
            "DLQ message classified message_id=%s stage=%s source_arn=%s",
            message_id or "unknown",
            stage,
            source_arn,
        )

    failed_id = hashlib.sha256(
        f"{source_arn}/{message_id or body}".encode("utf-8")
    ).hexdigest()[:32]
    item = {
        "failed_id": failed_id,
        "job_id": str(job_id),
        "stage": stage,
        "s3_key": str(s3_key),
        "error_type": "TRANSIENT_EXHAUSTED" if stage != "UNKNOWN" else "UNKNOWN",
        "error_message": (
            "Message exhausted its SQS receive attempts and reached a dead-letter queue."
            if stage != "UNKNOWN"
            else (diagnostic or "DLQ message could not be classified; inspect diagnostic logs.")
        )[:1000],
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
