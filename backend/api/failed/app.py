"""Failed-job listing and retry API handlers."""

from __future__ import annotations

import hashlib
import json
import os
from decimal import Decimal
from urllib.parse import quote_plus

import boto3
from boto3.dynamodb.conditions import Key

FAILED_JOB_REQUIRED = {
    "failed_id", "job_id", "stage", "s3_key", "error_type",
    "error_message", "status", "created_at",
}
FAILED_JOB_FIELDS = FAILED_JOB_REQUIRED | {"attempts", "message_id"}
STAGES = {"JD_PARSE", "TEXT_EXTRACT", "COMPREHEND", "PARSE", "SCORE", "UNKNOWN"}
ERROR_TYPES = {
    "UNSUPPORTED_TYPE", "CORRUPT_FILE", "EMPTY_TEXT", "JD_NO_SKILLS",
    "TRANSIENT_EXHAUSTED", "UNKNOWN",
}
QUEUE_NAMES = {
    "JD_PARSE": "jd-queue",
    "TEXT_EXTRACT": "parse-queue",
    "COMPREHEND": "parse-queue",
    "PARSE": "parse-queue",
    "SCORE": "score-queue",
}
GSI_NAME = "job_id-created_at"


class InvalidFailedJob(ValueError):
    """A stored row cannot be returned under the frozen failed-job schema."""


def _response(status: int, payload: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(payload, separators=(",", ":")),
    }


def _error(status: int, message: str, detail: str | None = None) -> dict:
    payload = {"error": message}
    if detail is not None:
        payload["detail"] = detail
    return _response(status, payload)


def _validate_failed_job(item: dict) -> None:
    try:
        if not isinstance(item, dict) or set(item) - FAILED_JOB_FIELDS:
            raise InvalidFailedJob("invalid")
        if FAILED_JOB_REQUIRED - set(item):
            raise InvalidFailedJob("invalid")
        if not all(isinstance(item[k], str) for k in FAILED_JOB_REQUIRED):
            raise InvalidFailedJob("invalid")
        if item["stage"] not in STAGES or item["error_type"] not in ERROR_TYPES:
            raise InvalidFailedJob("invalid")
        if item["status"] not in {"OPEN", "RETRIED", "RESOLVED"}:
            raise InvalidFailedJob("invalid")
        if len(item["error_message"]) > 1000:
            raise InvalidFailedJob("invalid")
        if "attempts" in item:
            attempts = item["attempts"]
            if isinstance(attempts, bool) or not isinstance(attempts, (int, Decimal)):
                raise InvalidFailedJob("invalid")
            if isinstance(attempts, Decimal) and (not attempts.is_finite() or attempts != attempts.to_integral_value()):
                raise InvalidFailedJob("invalid")
            if attempts < 0:
                raise InvalidFailedJob("invalid")
        if "message_id" in item and item["message_id"] is not None and not isinstance(item["message_id"], str):
            raise InvalidFailedJob("invalid")
    except InvalidFailedJob:
        raise
    except Exception as exc:
        # Weird DynamoDB values (for example unhashable enum values) are data
        # errors, not reasons to expose Python exceptions from the API.
        raise InvalidFailedJob("invalid") from exc


def _json_failed_job(item: dict) -> dict:
    """Validate and convert DynamoDB Decimal integer values to JSON integers."""
    _validate_failed_job(item)
    normalized = dict(item)
    if isinstance(normalized.get("attempts"), Decimal):
        normalized["attempts"] = int(normalized["attempts"])
    return normalized


def _all_pages(operation, **kwargs):
    items = []
    request = dict(kwargs)
    while True:
        page = operation(**request)
        items.extend(page.get("Items", []))
        key = page.get("LastEvaluatedKey")
        if not key:
            return items
        request["ExclusiveStartKey"] = key


def list_failed_jobs(table, job_id: str | None) -> list[dict]:
    if job_id:
        items = _all_pages(
            table.query,
            IndexName=GSI_NAME,
            KeyConditionExpression=Key("job_id").eq(job_id),
        )
    else:
        items = _all_pages(table.scan)
    return [_json_failed_job(item) for item in items]


def candidate_id_for(job_id: str, s3_key: str) -> str:
    return hashlib.sha256(f"{job_id}/{s3_key}".encode("utf-8")).hexdigest()[:16]


def s3_event_message(bucket: str, key: str) -> str:
    event = {
        "Records": [{
            "s3": {
                "bucket": {"name": bucket},
                "object": {"key": quote_plus(key, safe="/")},
            },
        }]
    }
    return json.dumps(event, separators=(",", ":"))


def _get_queue_url(sqs, queue_name: str, stage: str, score_queue_url: str | None) -> str:
    # SCORE_QUEUE_URL is the only queue URL explicitly listed in the architecture
    # environment contract. The other queues use the fixed architecture names.
    if queue_name == "score-queue":
        if score_queue_url:
            return score_queue_url
    response = sqs.get_queue_url(QueueName=f"rs-{stage}-{queue_name}")
    queue_url = response.get("QueueUrl")
    if not isinstance(queue_url, str) or not queue_url:
        raise RuntimeError("Queue URL is unavailable")
    return queue_url


def _is_conditional_failure(exc: Exception) -> bool:
    return getattr(exc, "response", {}).get("Error", {}).get("Code") == "ConditionalCheckFailedException"


def retry_failed_job(
    table, sqs, failed_id: str, *, bucket: str | None, stage: str,
    score_queue_url: str | None = None,
) -> dict:
    found = table.get_item(Key={"failed_id": failed_id}, ConsistentRead=True).get("Item")
    if not found:
        return _error(404, "Failed job not found")

    # Return the requested unsupported-stage response without trying to route
    # any unrecognized stage. Other malformed row data is handled generically.
    if isinstance(found, dict) and isinstance(found.get("stage"), str):
        if found["stage"] == "UNKNOWN" or found["stage"] not in QUEUE_NAMES:
            return _error(400, "Unsupported failed-job stage")
    found = _json_failed_job(found)
    if found["status"] != "OPEN":
        return _error(409, "Failed job is not open for retry")

    queue_name = QUEUE_NAMES.get(found["stage"])
    if not queue_name:
        return _error(400, "Unsupported failed-job stage")
    if found["stage"] == "JD_PARSE" and not found["s3_key"].startswith("jd/"):
        return _error(400, "S3 key does not match failed-job stage")
    if found["stage"] in {"PARSE", "TEXT_EXTRACT", "COMPREHEND"} and not found["s3_key"].startswith("resumes/"):
        return _error(400, "S3 key does not match failed-job stage")
    if stage not in {"dev", "prod"}:
        raise RuntimeError("Stage configuration is unavailable")
    if queue_name != "score-queue" and (not isinstance(bucket, str) or not bucket):
        raise RuntimeError("Bucket configuration is unavailable")
    if queue_name == "score-queue" and score_queue_url is not None and not score_queue_url:
        raise RuntimeError("Score queue configuration is unavailable")
    if queue_name == "score-queue":
        message = {
            "job_id": found["job_id"],
            "candidate_id": candidate_id_for(found["job_id"], found["s3_key"]),
            "reason": "RESCORE",
        }
        body = json.dumps(message, separators=(",", ":"))
    else:
        body = s3_event_message(bucket, found["s3_key"])

    queue_url = _get_queue_url(sqs, queue_name, stage, score_queue_url)
    sent = sqs.send_message(QueueUrl=queue_url, MessageBody=body)
    message_id = sent.get("MessageId")
    if not isinstance(message_id, str) or not message_id:
        raise RuntimeError("SQS response did not contain a message ID")
    try:
        updated = table.update_item(
            Key={"failed_id": failed_id},
            UpdateExpression="SET #status = :retried, message_id = :message_id",
            ConditionExpression="#status = :open",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":open": "OPEN", ":retried": "RETRIED", ":message_id": message_id,
            },
            ReturnValues="ALL_NEW",
        ).get("Attributes", {**found, "status": "RETRIED", "message_id": message_id})
    except Exception as exc:
        if _is_conditional_failure(exc):
            return _error(409, "Failed job is not open for retry")
        raise
    updated = _json_failed_job(updated)
    return _response(202, updated)


def handler(event, context, *, table=None, sqs=None, environ=None):
    """API Gateway proxy handler. Optional clients make the handler testable."""
    env = os.environ if environ is None else environ
    table_name = env.get("FAILED_TABLE")
    if table is None:
        if not table_name:
            return _error(500, "Internal server error")
        table = boto3.resource("dynamodb").Table(table_name)
    if sqs is None:
        sqs = boto3.client("sqs")

    method = event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get("method")
    path = event.get("pathParameters") or {}
    if method == "GET":
        query = event.get("queryStringParameters") or {}
        if "job_id" in query and (not isinstance(query["job_id"], str) or not query["job_id"]):
            return _error(400, "job_id must be a non-empty string")
        try:
            jobs = list_failed_jobs(table, query.get("job_id"))
        except InvalidFailedJob:
            return _error(500, "Internal server error")
        except Exception:
            return _error(500, "Internal server error")
        return _response(200, {"failed_jobs": jobs})
    if method == "POST" and path.get("failed_id"):
        try:
            return retry_failed_job(
                table, sqs, path["failed_id"], bucket=env.get("UPLOADS_BUCKET"),
                stage=env.get("STAGE"), score_queue_url=env.get("SCORE_QUEUE_URL"),
            )
        except Exception:
            return _error(500, "Internal server error")
    return _error(404, "Not found")
