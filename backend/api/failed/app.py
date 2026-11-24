"""Failed-job listing and stage-aware retry API (B7)."""
from __future__ import annotations

import json
from decimal import Decimal
import logging
import os
import os
from datetime import datetime, timezone
from urllib.parse import quote

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _json_default(value):
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    raise TypeError(f"unsupported JSON value: {type(value).__name__}")


def _reply(status: int, payload) -> dict:
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": os.getenv("CORS_ORIGIN", ""),
            "Vary": "Origin",
        },
        "body": json.dumps(payload, default=_json_default),
    }


def _error(status: int, message: str) -> dict:
    return _reply(status, {"error": message})


def _clients():
    region = os.getenv("AWS_REGION", "us-east-1")
    ddb = boto3.resource("dynamodb", region_name=region)
    return (
        ddb.Table(os.environ["FAILED_TABLE"]),
        ddb.Table(os.environ["CANDIDATES_TABLE"]),
        boto3.client("sqs", region_name=region),
    )


def _query_candidates(table, job_id):
    response = table.query(KeyConditionExpression=Key("job_id").eq(job_id))
    items = response.get("Items", [])
    while response.get("LastEvaluatedKey"):
        response = table.query(
            KeyConditionExpression=Key("job_id").eq(job_id),
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        items.extend(response.get("Items", []))
    return items


def _list_failed(table, job_id=None):
    if job_id:
        response = table.query(
            IndexName="job_id-created_at",
            KeyConditionExpression=Key("job_id").eq(job_id),
            ScanIndexForward=False,
        )
        items = response.get("Items", [])
        while response.get("LastEvaluatedKey"):
            response = table.query(
                IndexName="job_id-created_at",
                KeyConditionExpression=Key("job_id").eq(job_id),
                ScanIndexForward=False,
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            items.extend(response.get("Items", []))
    else:
        response = table.scan()
        items = response.get("Items", [])
        while response.get("LastEvaluatedKey"):
            response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
            items.extend(response.get("Items", []))
    items.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return _reply(200, {"failed_jobs": items})


def _s3_event(bucket: str, key: str) -> str:
    return json.dumps({
        "Records": [{
            "eventSource": "aws:s3",
            "eventName": "ObjectCreated:Put",
            "s3": {
                "bucket": {"name": bucket},
                "object": {"key": quote(key, safe="/"), "size": 0},
            },
        }]
    })


def _retry(failed_table, candidates_table, sqs, failed_id):
    item = failed_table.get_item(Key={"failed_id": failed_id}, ConsistentRead=True).get("Item")
    if item is None:
        return _error(404, "failed job not found")
    if item.get("status") != "OPEN":
        return _error(409, "failed job is not open for retry")

    stage = item.get("stage")
    queue_url = {
        "PARSE": os.environ["PARSE_QUEUE_URL"],
        "TEXT_EXTRACT": os.environ["PARSE_QUEUE_URL"],
        "COMPREHEND": os.environ["PARSE_QUEUE_URL"],
        "JD_PARSE": os.environ["JD_QUEUE_URL"],
    }.get(stage)
    message_body = None

    if queue_url:
        message_body = _s3_event(os.environ["UPLOADS_BUCKET"], item["s3_key"])
    elif stage == "SCORE":
        candidates = _query_candidates(candidates_table, item["job_id"])
        candidate = next(
            (row for row in candidates if row.get("source_key") == item.get("s3_key")),
            None,
        )
        if candidate is None:
            return _error(409, "candidate for score retry could not be resolved")
        queue_url = os.environ["SCORE_QUEUE_URL"]
        message_body = json.dumps({
            "job_id": item["job_id"],
            "candidate_id": candidate["candidate_id"],
            "reason": "RESCORE",
        })
    else:
        return _error(409, f"stage {stage!r} cannot be retried automatically")

    try:
        updated = failed_table.update_item(
            Key={"failed_id": failed_id},
            UpdateExpression="SET #status = :retried, attempts = if_not_exists(attempts, :zero) + :one",
            ConditionExpression="#status = :open",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":retried": "RETRIED", ":open": "OPEN", ":zero": 0, ":one": 1,
            },
            ReturnValues="ALL_NEW",
        )["Attributes"]
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            return _error(409, "failed job was already retried")
        raise

    try:
        sqs.send_message(QueueUrl=queue_url, MessageBody=message_body)
    except Exception:
        # Restore OPEN so the recruiter can retry after the queue outage is fixed.
        failed_table.update_item(
            Key={"failed_id": failed_id},
            UpdateExpression="SET #status = :open, attempts = attempts - :one",
            ConditionExpression="#status = :retried AND attempts >= :one",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":open": "OPEN", ":retried": "RETRIED", ":one": 1},
        )
        raise
    return _reply(202, updated)


def lambda_handler(event, context):
    event = event if isinstance(event, dict) else {}
    request_id = getattr(context, "aws_request_id", "unknown")
    logger.info("failed jobs API request_id=%s method=%s", request_id, event.get("httpMethod"))
    try:
        failed_table, candidates_table, sqs = _clients()
        method, resource = event.get("httpMethod"), event.get("resource")
        if method == "GET" and resource == "/failed-jobs":
            query = event.get("queryStringParameters") or {}
            return _list_failed(failed_table, query.get("job_id"))
        if method == "POST" and resource == "/failed-jobs/{failed_id}/retry":
            failed_id = (event.get("pathParameters") or {}).get("failed_id")
            if not isinstance(failed_id, str) or not failed_id:
                return _error(400, "failed_id is invalid")
            return _retry(failed_table, candidates_table, sqs, failed_id)
        return _error(404, "route not found")
    except ClientError:
        logger.exception("failed jobs API AWS operation failed request_id=%s", request_id)
        return _error(500, "internal service error")
    except Exception:
        logger.exception("failed jobs API unexpected failure request_id=%s", request_id)
        return _error(500, "internal service error")
