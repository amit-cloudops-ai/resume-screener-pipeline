"""SQS resume parser: S3 -> Textract/DOCX -> deterministic NLP -> DynamoDB -> score queue."""
from __future__ import annotations

import json
from decimal import Decimal
import logging
import os
import re
from pathlib import PurePosixPath

import boto3

try:
    from ..common import (
        PermanentDocumentError, TransientProcessingError, candidate_id_for,
        derive_fields, extract_document_text,
        parse_s3_notification, utc_now,
    )
except ImportError:  # SAM packages backend/parsing as the Lambda import root.
    from common import (
        PermanentDocumentError, TransientProcessingError, candidate_id_for,
        derive_fields, extract_document_text,
        parse_s3_notification, utc_now,
    )

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _clients():
    region = os.getenv("AWS_REGION", "us-east-1")
    return (
        boto3.client("s3", region_name=region),
        boto3.client("textract", region_name=region),
        boto3.client("sqs", region_name=region),
        boto3.resource("dynamodb", region_name=region).Table(os.environ["CANDIDATES_TABLE"]),
        boto3.resource("dynamodb", region_name=region).Table(os.environ["FAILED_TABLE"]),
    )


def _failure(failed_table, candidate_table, job_id, key, message_id, error):
    now = utc_now()
    if not isinstance(job_id, str) or not re.fullmatch(r"[0-9a-f]{12}", job_id):
        failed_id = __import__("hashlib").sha256(
            f"UNKNOWN/{key}/{error.error_type}".encode("utf-8")
        ).hexdigest()[:32]
        failed_table.put_item(Item={
            "failed_id": failed_id,
            "job_id": "unknown",
            "stage": "UNKNOWN",
            "s3_key": key,
            "error_type": "UNKNOWN",
            "error_message": "Resume notification contains an invalid job identifier.",
            "attempts": 0,
            "message_id": message_id,
            "status": "OPEN",
            "created_at": now,
        })
        return
    candidate_id = candidate_id_for(job_id, key)
    existing = candidate_table.get_item(
        Key={"job_id": job_id, "candidate_id": candidate_id}
    ).get("Item") or {}
    failed_id = __import__("hashlib").sha256(
        f"PARSE/{job_id}/{key}/{error.error_type}".encode("utf-8")
    ).hexdigest()[:32]
    failed_table.put_item(Item={
        "failed_id": failed_id,
        "job_id": job_id,
        "stage": "PARSE",
        "s3_key": key,
        "error_type": error.error_type,
        "error_message": str(error)[:1000],
        "attempts": 0,
        "message_id": message_id,
        "status": "OPEN",
        "created_at": now,
    })
    item = {
        "job_id": job_id,
        "candidate_id": candidate_id,
        "status": "FAILED",
        "source_key": key,
        "file_name": PurePosixPath(key).name,
        "name": None,
        "email": None,
        "skills": [],
        "employers": [],
        "titles": [],
        "experience_years": None,
        "parsed_s3_key": None,
        "parser_version": os.getenv("PARSER_VERSION", "1.0.0"),
        "score": None,
        "above_threshold": None,
        "score_breakdown": None,
        "scored_at": None,
        "decision": existing.get("decision", "PENDING"),
        "decision_history": existing.get("decision_history", []),
        "email_status": existing.get("email_status", "NOT_SENT"),
        "created_at": existing.get("created_at", now),
    }
    candidate_table.put_item(Item=item)


def _process(body, message_id, clients, context):
    s3, textract, sqs, candidates, failed = clients
    bucket, key = parse_s3_notification(body)
    parts = key.split("/", 2)
    if len(parts) != 3 or parts[0] != "resumes" or not parts[1]:
        raise PermanentDocumentError("UNSUPPORTED_TYPE", "Resume object key is outside resumes/{job_id}/{file_name}")
    job_id = parts[1]
    if not re.fullmatch(r"[0-9a-f]{12}", job_id):
        raise PermanentDocumentError("UNKNOWN", "Resume key contains an invalid job identifier")
    if bucket != os.environ["UPLOADS_BUCKET"]:
        raise PermanentDocumentError("UNSUPPORTED_TYPE", "Resume object is in an unexpected bucket")
    candidate_id = candidate_id_for(job_id, key)
    existing = candidates.get_item(
        Key={"job_id": job_id, "candidate_id": candidate_id},
        ConsistentRead=True,
    ).get("Item")
    if existing and existing.get("status") == "SCORED":
        return
    if existing and existing.get("status") == "PARSED":
        sqs.send_message(
            QueueUrl=os.environ["SCORE_QUEUE_URL"],
            MessageBody=json.dumps({
                "job_id": job_id, "candidate_id": candidate_id,
                "reason": "CANDIDATE_PARSED",
            }),
        )
        return
    if not existing or existing.get("status") != "PARSING":
        now = existing.get("created_at", utc_now()) if existing else utc_now()
        candidates.put_item(Item={
            "job_id": job_id,
            "candidate_id": candidate_id,
            "status": "PARSING",
            "source_key": key,
            "file_name": PurePosixPath(key).name,
            "name": None,
            "email": None,
            "skills": [],
            "employers": [],
            "titles": [],
            "experience_years": None,
            "parsed_s3_key": None,
            "parser_version": os.getenv("PARSER_VERSION", "1.0.0"),
            "score": None,
            "above_threshold": None,
            "score_breakdown": None,
            "scored_at": None,
            "decision": existing.get("decision", "PENDING") if existing else "PENDING",
            "decision_history": existing.get("decision_history", []) if existing else [],
            "email_status": existing.get("email_status", "NOT_SENT") if existing else "NOT_SENT",
            "created_at": now,
        })
        existing = candidates.get_item(
            Key={"job_id": job_id, "candidate_id": candidate_id},
            ConsistentRead=True,
        ).get("Item")

    text = extract_document_text(bucket, key, s3, textract, job_id, context)
    fields = derive_fields(text)
    extraction_audit = {"engine": "deterministic-taxonomy-v1", "fields": fields}
    candidate_fields = dict(fields)
    if candidate_fields["experience_years"] is not None:
        candidate_fields["experience_years"] = Decimal(str(candidate_fields["experience_years"]))
    now = existing.get("created_at", utc_now()) if existing else utc_now()
    item = {
        "job_id": job_id,
        "candidate_id": candidate_id,
        "status": "PARSED",
        "source_key": key,
        "file_name": PurePosixPath(key).name,
        **candidate_fields,
        "parsed_s3_key": f"parsed/{job_id}/{candidate_id}.json",
        "parser_version": os.getenv("PARSER_VERSION", "1.0.0"),
        "score": None,
        "above_threshold": None,
        "score_breakdown": None,
        "scored_at": None,
        "decision": existing.get("decision", "PENDING") if existing else "PENDING",
        "decision_history": existing.get("decision_history", []) if existing else [],
        "email_status": existing.get("email_status", "NOT_SENT") if existing else "NOT_SENT",
        "created_at": now,
    }
    s3.put_object(
        Bucket=bucket,
        Key=item["parsed_s3_key"],
        Body=json.dumps(extraction_audit, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
    )
    candidates.put_item(Item=item)
    sqs.send_message(
        QueueUrl=os.environ["SCORE_QUEUE_URL"],
        MessageBody=json.dumps({
            "job_id": job_id, "candidate_id": candidate_id,
            "reason": "CANDIDATE_PARSED",
        }),
    )


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
                bucket, key = parse_s3_notification(record["body"])
                job_id = key.split("/", 2)[1]
                _failure(clients[5], clients[4], job_id, key, message_id, exc)
            except Exception:
                logger.exception("permanent resume failure could not be recorded message_id=%s", message_id)
                failures.append({"itemIdentifier": message_id})
        except Exception:
            logger.exception("transient resume processing failure message_id=%s", message_id)
            failures.append({"itemIdentifier": message_id})
    return {"batchItemFailures": failures}
