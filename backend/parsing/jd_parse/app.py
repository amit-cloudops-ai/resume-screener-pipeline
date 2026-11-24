"""SQS job-description parser and score-queue fan-out (A7)."""
from __future__ import annotations

import hashlib
import json
from decimal import Decimal
import logging
import os
import re

import boto3
from boto3.dynamodb.conditions import Key

try:
    from ..common import (
        PermanentDocumentError, TransientProcessingError, comprehend_entities,
        derive_fields, extract_document_text, parse_s3_notification, utc_now,
    )
except ImportError:
    from common import (
        PermanentDocumentError, TransientProcessingError, comprehend_entities,
        derive_fields, extract_document_text, parse_s3_notification, utc_now,
    )

logger = logging.getLogger()
logger.setLevel(logging.INFO)
REQUIRED_YEARS_RE = re.compile(r"\b(\d+(?:\.\d+)?)\s*\+?\s*(?:years|year|yrs|yr)\b", re.I)


def _clients():
    region = os.getenv("AWS_REGION", "us-east-1")
    ddb = boto3.resource("dynamodb", region_name=region)
    return (
        boto3.client("s3", region_name=region),
        boto3.client("textract", region_name=region),
        boto3.client("comprehend", region_name=region),
        boto3.client("sqs", region_name=region),
        ddb.Table(os.environ["JOBS_TABLE"]),
        ddb.Table(os.environ["CANDIDATES_TABLE"]),
        ddb.Table(os.environ["FAILED_TABLE"]),
    )


def _record_failure(failed, jobs, job_id, key, message_id, error):
    now = utc_now()
    failed_id = hashlib.sha256(
        f"JD_PARSE/{job_id}/{key}/{error.error_type}".encode("utf-8")
    ).hexdigest()[:32]
    failed.put_item(Item={
        "failed_id": failed_id,
        "job_id": job_id,
        "stage": "JD_PARSE",
        "s3_key": key,
        "error_type": error.error_type,
        "error_message": str(error)[:1000],
        "attempts": 0,
        "message_id": message_id,
        "status": "OPEN",
        "created_at": now,
    })
    # Update an existing job only; UpdateItem on a missing key would create a
    # malformed partial job record that violates the frozen job schema.
    if jobs.get_item(Key={"job_id": job_id}, ConsistentRead=True).get("Item"):
        jobs.update_item(
            Key={"job_id": job_id},
            UpdateExpression="SET #status = :failed",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":failed": "FAILED"},
        )


def _required_years(text):
    matches = [float(match.group(1)) for match in REQUIRED_YEARS_RE.finditer(text)]
    return min(matches) if matches else None


def _send_ready(candidates, sqs, queue_url, job_id):
    response = candidates.query(KeyConditionExpression=Key("job_id").eq(job_id))
    items = response.get("Items", [])
    while response.get("LastEvaluatedKey"):
        response = candidates.query(
            KeyConditionExpression=Key("job_id").eq(job_id),
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        items.extend(response.get("Items", []))
    for candidate in items:
        if candidate.get("status") in {"PARSED", "SCORED"}:
            sqs.send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps({
                    "job_id": job_id,
                    "candidate_id": candidate["candidate_id"],
                    "reason": "JD_READY",
                }),
            )


def _process(body, message_id, clients, context):
    s3, textract, comprehend, sqs, jobs, candidates, failed = clients
    bucket, key = parse_s3_notification(body)
    parts = key.split("/", 2)
    if len(parts) != 3 or parts[0] != "jd" or not parts[1]:
        raise PermanentDocumentError("UNSUPPORTED_TYPE", "JD object key is outside jd/{job_id}/{file_name}")
    job_id = parts[1]
    if bucket != os.environ["UPLOADS_BUCKET"]:
        raise PermanentDocumentError("UNSUPPORTED_TYPE", "JD object is in an unexpected bucket")
    job = jobs.get_item(Key={"job_id": job_id}, ConsistentRead=True).get("Item")
    if job is None:
        raise PermanentDocumentError("UNKNOWN", "Job record does not exist")
    if job.get("status") == "JD_PARSED":
        _send_ready(candidates, sqs, os.environ["SCORE_QUEUE_URL"], job_id)
        return

    text = extract_document_text(
        bucket, key, s3, textract, job_id, context, allow_txt=True
    )
    entities = comprehend_entities(
        text, comprehend, os.getenv("CUSTOM_RECOGNIZER_ARN", "DISABLED")
    )
    fields = derive_fields(text, entities)
    required_skills = fields["skills"]
    if not required_skills:
        error = PermanentDocumentError(
            "JD_NO_SKILLS", "No required skills could be identified in the job description"
        )
        _record_failure(failed, jobs, job_id, key, message_id, error)
        return

    titles = fields["titles"] or ([job["title"].strip().casefold()] if job.get("title") else [])
    parsed_key = f"parsed/{job_id}/jd.json"
    # Persist the audit artifact before marking the job ready. If this write
    # fails, SQS retries while the job remains JD_UPLOADED.
    s3.put_object(
        Bucket=bucket,
        Key=parsed_key,
        Body=json.dumps({"entities": entities, "fields": fields}, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
    )
    required_years = _required_years(text)
    jobs.update_item(
        Key={"job_id": job_id},
        UpdateExpression=(
            "SET #status = :parsed, required_skills = :skills, jd_titles = :titles, "
            "required_years = :years, parser_version = :version, jd_parsed_at = :parsed_at, jd_s3_key = :key"
        ),
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":parsed": "JD_PARSED",
            ":skills": required_skills,
            ":titles": titles,
            ":years": Decimal(str(required_years)) if required_years is not None else None,
            ":version": os.getenv("PARSER_VERSION", "1.0.0"),
            ":parsed_at": utc_now(),
            ":key": key,
        },
    )
    _send_ready(candidates, sqs, os.environ["SCORE_QUEUE_URL"], job_id)


def lambda_handler(event, context):
    records = event.get("Records", []) if isinstance(event, dict) else []
    if not isinstance(records, list):
        raise ValueError("SQS event Records must be a list")
    clients = _clients()
    failures = []
    for record in records:
        message_id = record.get("messageId", "unknown") if isinstance(record, dict) else "unknown"
        try:
            if not isinstance(record, dict) or not isinstance(record.get("body"), str):
                raise PermanentDocumentError("CORRUPT_FILE", "SQS record body is missing")
            _process(record["body"], message_id, clients, context)
        except PermanentDocumentError as exc:
            try:
                _, key = parse_s3_notification(record["body"])
                job_id = key.split("/", 2)[1]
                _record_failure(clients[6], clients[4], job_id, key, message_id, exc)
            except Exception:
                logger.exception("permanent JD failure could not be recorded message_id=%s", message_id)
                failures.append({"itemIdentifier": message_id})
        except Exception:
            logger.exception("transient JD processing failure message_id=%s", message_id)
            failures.append({"itemIdentifier": message_id})
    return {"batchItemFailures": failures}
