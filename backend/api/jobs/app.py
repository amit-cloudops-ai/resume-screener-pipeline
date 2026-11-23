"""Jobs and upload URL API Lambda (task B3)."""
from __future__ import annotations

import json
import math
import os
import re
import secrets
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import boto3


_JOB_ID = re.compile(r"^[0-9a-f]{12}$")
_SAFE_FILENAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._-]{0,127}$")
_MAX_UPLOADS = 50
_MAX_UPLOAD_BYTES = 5 * 1024 * 1024
_RESUME_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
_JD_TYPES = {**_RESUME_TYPES, ".txt": "text/plain"}


class RequestError(Exception):
    """An expected client or resource error with an HTTP status."""

    def __init__(self, status: int, code: str, detail: str):
        super().__init__(detail)
        self.status = status
        self.code = code
        self.detail = detail


def _response(status: int, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(payload, default=_json_default, separators=(",", ":")),
    }


def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _native(value: Any) -> Any:
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, dict):
        return {key: _native(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_native(item) for item in value]
    return value


def _dynamodb_value(value: Any) -> Any:
    if isinstance(value, bool) or value is None or isinstance(value, (str, int, Decimal)):
        return value
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {key: _dynamodb_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_dynamodb_value(item) for item in value]
    return value


def _jobs_table():
    dynamodb = boto3.resource("dynamodb", region_name=os.getenv("AWS_REGION", "us-east-1"))
    return dynamodb.Table(os.environ["JOBS_TABLE"])


def _s3_client():
    return boto3.client("s3", region_name=os.getenv("AWS_REGION", "us-east-1"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _error(status: int, code: str, detail: str) -> dict[str, Any]:
    return _response(status, {"error": code, "detail": detail})


def _body(event: dict[str, Any]) -> dict[str, Any]:
    raw = event.get("body")
    if not isinstance(raw, str):
        raise RequestError(400, "invalid_request", "Request body must be a JSON object.")
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise RequestError(400, "invalid_request", "Request body must be valid JSON.") from exc
    if not isinstance(parsed, dict):
        raise RequestError(400, "invalid_request", "Request body must be a JSON object.")
    return parsed


def _principal(event: dict[str, Any]) -> str:
    """Read the authenticated Cognito subject supplied by the API Gateway authorizer."""
    context = event.get("requestContext") or {}
    authorizer = context.get("authorizer") or {}
    claims = authorizer.get("claims") or {}
    subject = claims.get("sub") if isinstance(claims, dict) else None
    if not isinstance(subject, str) or not subject.strip():
        raise RequestError(401, "unauthorized", "Authenticated recruiter identity is missing.")
    return subject


def _threshold(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RequestError(400, "invalid_request", "threshold must be a number from 0 to 100.")
    number = float(value)
    if not math.isfinite(number) or not 0 <= number <= 100:
        raise RequestError(400, "invalid_request", "threshold must be a number from 0 to 100.")
    return number


def _default_threshold() -> float:
    stage = os.environ["STAGE"]
    response = boto3.client("ssm", region_name=os.getenv("AWS_REGION", "us-east-1")).get_parameter(
        Name=f"/rs/{stage}/threshold-default"
    )
    raw = response["Parameter"]["Value"]
    try:
        number = float(raw)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("configured threshold-default is not numeric") from exc
    if not math.isfinite(number) or not 0 <= number <= 100:
        raise RuntimeError("configured threshold-default is outside 0 to 100")
    return number


def _safe_filename(value: Any, allowed_types: dict[str, str]) -> tuple[str, str]:
    if not isinstance(value, str):
        raise RequestError(400, "invalid_request", "file_name must be a safe filename.")
    filename = value.strip()
    if not filename or not _SAFE_FILENAME.fullmatch(filename) or filename in {".", ".."}:
        raise RequestError(400, "invalid_request", "file_name must be a safe filename without path separators.")
    extension = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    content_type = allowed_types.get(extension)
    if content_type is None:
        allowed = ", ".join(sorted(allowed_types))
        raise RequestError(400, "invalid_request", f"Unsupported file extension; allowed: {allowed}.")
    return filename, content_type


def _upload_url(bucket: str, key: str, content_type: str) -> str:
    return _s3_client().generate_presigned_url(
        "put_object",
        Params={"Bucket": bucket, "Key": key, "ContentType": content_type},
        HttpMethod="PUT",
    )


def _create_job(event: dict[str, Any]) -> dict[str, Any]:
    data = _body(event)
    principal = _principal(event)
    title = data.get("title")
    if not isinstance(title, str) or not title.strip() or len(title.strip()) > 200:
        raise RequestError(400, "invalid_request", "title must contain 1 to 200 characters.")
    threshold = _threshold(data["threshold"]) if "threshold" in data else _default_threshold()

    has_description = "description_text" in data
    description = data.get("description_text")
    if has_description:
        if not isinstance(description, str):
            raise RequestError(400, "invalid_request", "description_text must be text.")
        if len(description.encode("utf-8")) > _MAX_UPLOAD_BYTES:
            raise RequestError(400, "invalid_request", "description_text exceeds the 5 MB JD limit.")
        filename = "description.txt"
        content_type = "text/plain"
    else:
        requested_name = data.get("jd_file_name", "job-description.pdf")
        filename, content_type = _safe_filename(requested_name, _JD_TYPES)

    job_id = secrets.token_hex(6)
    key = f"jd/{job_id}/{filename}"
    has_text = has_description
    job = {
        "job_id": job_id,
        "title": title.strip(),
        "status": "JD_UPLOADED" if has_text else "CREATED",
        "threshold": threshold,
        "jd_s3_key": key,
        "required_skills": [],
        "jd_titles": [],
        "required_years": None,
        "parser_version": os.environ["PARSER_VERSION"],
        "created_by": principal,
        "created_at": _now(),
        "jd_parsed_at": None,
    }

    bucket = os.environ["UPLOADS_BUCKET"]
    jd_upload = None if has_text else {
        "file_name": filename,
        "url": _upload_url(bucket, key, content_type),
        "s3_key": key,
    }

    # A conditional write prevents an extremely unlikely generated ID collision
    # from replacing an existing job.
    _jobs_table().put_item(
        Item=_dynamodb_value(job),
        ConditionExpression="attribute_not_exists(job_id)",
    )

    if has_text:
        try:
            _s3_client().put_object(
                Bucket=bucket,
                Key=key,
                Body=description.encode("utf-8"),
                ContentType=content_type,
            )
        except Exception:
            # Do not leave a job looking uploaded when its S3 write failed.
            _jobs_table().update_item(
                Key={"job_id": job_id},
                UpdateExpression="SET #status = :failed",
                ConditionExpression="#status = :uploaded",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={":failed": "FAILED", ":uploaded": "JD_UPLOADED"},
            )
            raise

    payload = {"job": _native(job)}
    if jd_upload is not None:
        payload["jd_upload"] = jd_upload
    return _response(201, payload)


def _list_jobs() -> dict[str, Any]:
    table = _jobs_table()
    items: list[dict[str, Any]] = []
    scan_args: dict[str, Any] = {}
    while True:
        page = table.scan(**scan_args)
        items.extend(page.get("Items", []))
        last_key = page.get("LastEvaluatedKey")
        if not last_key:
            break
        scan_args["ExclusiveStartKey"] = last_key
    items.sort(key=lambda item: (item.get("created_at", ""), item.get("job_id", "")), reverse=True)
    return _response(200, {"jobs": _native(items)})


def _get_job(job_id: Any) -> dict[str, Any]:
    if not isinstance(job_id, str) or not _JOB_ID.fullmatch(job_id):
        raise RequestError(404, "not_found", "Job was not found.")
    response = _jobs_table().get_item(Key={"job_id": job_id}, ConsistentRead=True)
    item = response.get("Item")
    if item is None:
        raise RequestError(404, "not_found", "Job was not found.")
    return _response(200, _native(item))


def _resume_uploads(job_id: Any, event: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(job_id, str) or not _JOB_ID.fullmatch(job_id):
        raise RequestError(404, "not_found", "Job was not found.")
    if _jobs_table().get_item(Key={"job_id": job_id}, ConsistentRead=True).get("Item") is None:
        raise RequestError(404, "not_found", "Job was not found.")

    data = _body(event)
    files = data.get("files")
    if not isinstance(files, list):
        raise RequestError(400, "invalid_request", "files must be a list.")
    if len(files) > _MAX_UPLOADS:
        raise RequestError(400, "invalid_request", "At most 50 files may be uploaded at once.")

    bucket = os.environ["UPLOADS_BUCKET"]
    uploads = []
    seen_names: set[str] = set()
    for entry in files:
        if not isinstance(entry, dict):
            raise RequestError(400, "invalid_request", "Each file must include file_name and content_type.")
        filename, expected_type = _safe_filename(entry.get("file_name"), _RESUME_TYPES)
        supplied_type = entry.get("content_type")
        if not isinstance(supplied_type, str) or supplied_type.strip().lower() != expected_type:
            raise RequestError(400, "invalid_request", f"content_type does not match {filename}'s extension.")
        canonical_name = filename.casefold()
        if canonical_name in seen_names:
            raise RequestError(400, "invalid_request", "Duplicate filenames are not allowed in one upload request.")
        seen_names.add(canonical_name)
        key = f"resumes/{job_id}/{filename}"
        uploads.append({"file_name": filename, "url": _upload_url(bucket, key, expected_type), "s3_key": key})

    # These pre-signed PUT URLs do not constrain object length. Teammate A's
    # parsing pipeline must check S3 object metadata (ContentLength) against the
    # 5 MB limit before document processing.
    return _response(200, {"uploads": uploads})


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Dispatch API Gateway REST proxy events for the four B3 routes."""
    if not isinstance(event, dict):
        return _error(400, "invalid_request", "Request event must be an object.")
    method = event.get("httpMethod")
    resource = event.get("resource")
    params = event.get("pathParameters") or {}
    try:
        if resource == "/jobs" and method == "GET":
            return _list_jobs()
        if resource == "/jobs" and method == "POST":
            return _create_job(event)
        if resource == "/jobs/{job_id}" and method == "GET":
            return _get_job(params.get("job_id"))
        if resource == "/jobs/{job_id}/uploads" and method == "POST":
            return _resume_uploads(params.get("job_id"), event)
        return _error(404, "not_found", "Route was not found.")
    except RequestError as exc:
        return _error(exc.status, exc.code, exc.detail)
    except Exception:
        # Keep request bodies, JD text, and AWS exception payloads out of logs and responses.
        return _error(500, "internal_error", "The request could not be completed.")
