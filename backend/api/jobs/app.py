"""Jobs and upload API for the resume screener.

The parser enforces the 5 MiB object limit after upload using S3 object metadata;
a presigned PUT URL alone cannot impose a content-length range.
"""
from __future__ import annotations

import json
from decimal import Decimal
import logging
import os
import re
import secrets
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import unquote

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_MAX_FILES = 50
_ALLOWED = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
_ALLOWED_JD = {**_ALLOWED, ".txt": "text/plain"}
_JOB_ID = re.compile(r"^[0-9a-f]{12}$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _json_default(value):
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    raise TypeError(f"unsupported JSON value: {type(value).__name__}")


def _reply(status: int, payload: Any, content_type: str = "application/json") -> dict:
    headers = {
        "Content-Type": content_type,
        "Access-Control-Allow-Origin": os.getenv("CORS_ORIGIN", ""),
        "Vary": "Origin",
    }
    body = payload if content_type == "text/csv" else json.dumps(payload, default=_json_default)
    return {"statusCode": status, "headers": headers, "body": body}


def _error(status: int, message: str) -> dict:
    return _reply(status, {"error": message})


def _claims(event: dict) -> dict:
    return (
        event.get("requestContext", {})
        .get("authorizer", {})
        .get("claims", {})
        or {}
    )


def _body(event: dict) -> dict:
    raw = event.get("body")
    if not isinstance(raw, str):
        raise ValueError("request body must be JSON")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("request body must be valid JSON") from exc
    if not isinstance(value, dict):
        raise ValueError("request body must be a JSON object")
    return value


def _resources():
    region = os.getenv("AWS_REGION", "us-east-1")
    ddb = boto3.resource("dynamodb", region_name=region)
    return (
        ddb.Table(os.environ["JOBS_TABLE"]),
        boto3.client("s3", region_name=region),
        boto3.client("ssm", region_name=region),
    )


def _threshold(body: dict, ssm) -> float:
    value = body.get("threshold")
    if value is None:
        try:
            value = float(ssm.get_parameter(
                Name=f"/rs/{os.getenv('STAGE', 'dev')}/threshold-default"
            )["Parameter"]["Value"])
        except ClientError:
            value = 60
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 100:
        raise ValueError("threshold must be a number between 0 and 100")
    return float(value)


def _safe_filename(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("file_name must be a non-empty string")
    name = PurePosixPath(unquote(value.strip())).name
    if name in {"", ".", ".."} or "/" in name or chr(92) in name:
        raise ValueError("file_name is invalid")
    if len(name) > 180:
        raise ValueError("file_name must be at most 180 characters")
    return name


def _presign(s3, bucket: str, key: str, content_type: str) -> str:
    return s3.generate_presigned_url(
        "put_object",
        Params={"Bucket": bucket, "Key": key, "ContentType": content_type},
        ExpiresIn=900,
    )


def _list_jobs(table) -> dict:
    response = table.scan()
    jobs = response.get("Items", [])
    while response.get("LastEvaluatedKey"):
        response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
        jobs.extend(response.get("Items", []))
    jobs.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return _reply(200, {"jobs": jobs})


def _create_job(event: dict, table, s3, ssm) -> dict:
    body = _body(event)
    title = body.get("title")
    if not isinstance(title, str) or not title.strip() or len(title.strip()) > 200:
        raise ValueError("title must be between 1 and 200 characters")
    threshold = _threshold(body, ssm)
    claims = _claims(event)
    created_by = claims.get("sub")
    if not isinstance(created_by, str) or not created_by:
        return _error(401, "authenticated recruiter identity is missing")

    job_id = secrets.token_hex(6)
    created_at = _now()
    job = {
        "job_id": job_id,
        "title": title.strip(),
        "status": "CREATED",
        "threshold": Decimal(str(threshold)),
        "required_skills": [],
        "jd_titles": [],
        "required_years": None,
        "parser_version": os.getenv("PARSER_VERSION", "1.0.0"),
        "created_by": created_by,
        "created_at": created_at,
        "jd_parsed_at": None,
        "jd_s3_key": None,
    }
    bucket = os.environ["UPLOADS_BUCKET"]
    jd_upload = None

    description = body.get("description_text")
    file_name = body.get("jd_file_name")
    if description is not None and file_name is not None:
        raise ValueError("provide description_text or jd_file_name, not both")
    if description is not None:
        if not isinstance(description, str) or not description.strip():
            raise ValueError("description_text must be a non-empty string")
        key = f"jd/{job_id}/description.txt"
        job["jd_s3_key"] = key
        job["status"] = "JD_UPLOADED"
    elif file_name is not None:
        name = _safe_filename(file_name)
        extension = PurePosixPath(name).suffix.lower()
        content_type = _ALLOWED_JD.get(extension)
        if content_type is None:
            raise ValueError("JD file must be PDF, DOCX or TXT")
        key = f"jd/{job_id}/{name}"
        jd_upload = {"file_name": name, "url": _presign(s3, bucket, key, content_type), "s3_key": key}
        job["jd_s3_key"] = key
        job["status"] = "JD_UPLOADED"

    table.put_item(Item=job, ConditionExpression="attribute_not_exists(job_id)")
    if description is not None:
        try:
            s3.put_object(
                Bucket=bucket, Key=job["jd_s3_key"],
                Body=description.encode("utf-8"), ContentType="text/plain",
            )
        except Exception:
            logger.exception("JD text upload failed for job_id=%s", job_id)
            table.update_item(
                Key={"job_id": job_id},
                UpdateExpression="SET #status = :failed",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={":failed": "FAILED"},
            )
            return _error(500, "could not store job description")
    payload = {"job": job}
    if jd_upload:
        payload["jd_upload"] = jd_upload
    return _reply(201, payload)


def _get_job(event: dict, table) -> dict:
    job_id = event.get("pathParameters", {}).get("job_id")
    if not isinstance(job_id, str) or not _JOB_ID.fullmatch(job_id):
        return _error(400, "job_id is invalid")
    item = table.get_item(Key={"job_id": job_id}, ConsistentRead=True).get("Item")
    return _reply(200, item) if item else _error(404, "job not found")


def _uploads(event: dict, table, s3) -> dict:
    job_id = event.get("pathParameters", {}).get("job_id")
    if not isinstance(job_id, str) or not _JOB_ID.fullmatch(job_id):
        return _error(400, "job_id is invalid")
    if table.get_item(Key={"job_id": job_id}, ConsistentRead=True).get("Item") is None:
        return _error(404, "job not found")
    body = _body(event)
    files = body.get("files")
    if not isinstance(files, list) or not 1 <= len(files) <= _MAX_FILES:
        raise ValueError("files must contain between 1 and 50 entries")
    bucket = os.environ["UPLOADS_BUCKET"]
    seen = set()
    uploads = []
    for entry in files:
        if not isinstance(entry, dict):
            raise ValueError("each file entry must be an object")
        name = _safe_filename(entry.get("file_name"))
        content_type = entry.get("content_type")
        expected = _ALLOWED.get(PurePosixPath(name).suffix.lower())
        if expected is None or content_type != expected:
            raise ValueError(f"{name}: only PDF and DOCX with matching content_type are allowed")
        if name.casefold() in seen:
            raise ValueError("duplicate file names are not allowed in one upload request")
        seen.add(name.casefold())
        key = f"resumes/{job_id}/{name}"
        uploads.append({"file_name": name, "url": _presign(s3, bucket, key, content_type), "s3_key": key})
    return _reply(200, {"uploads": uploads})


def lambda_handler(event, context):
    """Dispatch API Gateway proxy requests; log request IDs only, never payloads."""
    event = event if isinstance(event, dict) else {}
    method = event.get("httpMethod", "")
    path = event.get("resource", "")
    request_id = getattr(context, "aws_request_id", "unknown")
    logger.info("jobs API request_id=%s method=%s resource=%s", request_id, method, path)
    try:
        table, s3, ssm = _resources()
        if method == "GET" and path == "/jobs":
            return _list_jobs(table)
        if method == "POST" and path == "/jobs":
            return _create_job(event, table, s3, ssm)
        if method == "GET" and path == "/jobs/{job_id}":
            return _get_job(event, table)
        if method == "POST" and path == "/jobs/{job_id}/uploads":
            return _uploads(event, table, s3)
        return _error(404, "route not found")
    except ValueError as exc:
        return _error(400, str(exc))
    except ClientError:
        logger.exception("jobs API AWS operation failed request_id=%s", request_id)
        return _error(500, "internal service error")
    except Exception:
        logger.exception("jobs API unexpected failure request_id=%s", request_id)
        return _error(500, "internal service error")
