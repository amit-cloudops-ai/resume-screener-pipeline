"""Recruiter decision and shortlist email API (B5)."""
from __future__ import annotations

import json
from decimal import Decimal
import logging
import os
from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _json_default(value):
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    raise TypeError(f"unsupported JSON value: {type(value).__name__}")


def _reply(status: int, payload: Any) -> dict:
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


def _body(event: dict) -> dict:
    raw = event.get("body")
    if not isinstance(raw, str):
        raise ValueError("request body must be JSON")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("request body must be valid JSON") from exc
    if not isinstance(data, dict):
        raise ValueError("request body must be a JSON object")
    return data


def _tables():
    region = os.getenv("AWS_REGION", "us-east-1")
    table = boto3.resource("dynamodb", region_name=region).Table(os.environ["CANDIDATES_TABLE"])
    ses = boto3.client("ses", region_name=region)
    return table, ses


def lambda_handler(event, context):
    event = event if isinstance(event, dict) else {}
    request_id = getattr(context, "aws_request_id", "unknown")
    logger.info("decision API request_id=%s", request_id)
    path = event.get("pathParameters") or {}
    job_id, candidate_id = path.get("job_id"), path.get("candidate_id")
    if not isinstance(job_id, str) or len(job_id) != 12 or any(c not in "0123456789abcdef" for c in job_id):
        return _error(400, "job_id is invalid")
    if not isinstance(candidate_id, str) or len(candidate_id) != 16 or any(c not in "0123456789abcdef" for c in candidate_id):
        return _error(400, "candidate_id is invalid")

    try:
        data = _body(event)
        action = data.get("action")
        if action not in {"shortlist", "reject"}:
            raise ValueError("action must be shortlist or reject")
        interview = data.get("interview")
        if action == "shortlist":
            if not isinstance(interview, dict):
                raise ValueError("interview details are required to shortlist")
            for field in ("date_time", "location_or_link"):
                if not isinstance(interview.get(field), str) or not interview[field].strip():
                    raise ValueError(f"interview.{field} is required")
            if "notes" in interview and not isinstance(interview["notes"], str):
                raise ValueError("interview.notes must be a string")

        claims = (
            event.get("requestContext", {})
            .get("authorizer", {})
            .get("claims", {})
            or {}
        )
        actor = claims.get("sub")
        if not isinstance(actor, str) or not actor:
            return _error(401, "authenticated recruiter identity is missing")

        table, ses = _tables()
        key = {"job_id": job_id, "candidate_id": candidate_id}
        candidate = table.get_item(Key=key, ConsistentRead=True).get("Item")
        if candidate is None:
            return _error(404, "candidate not found")
        if candidate.get("status") != "SCORED":
            return _error(409, "candidate must be SCORED before a decision")

        now = _now()
        decision = "SHORTLISTED" if action == "shortlist" else "REJECTED"
        history = {"action": action, "by": actor, "at": now}
        try:
            updated = table.update_item(
                Key=key,
                UpdateExpression=(
                    "SET decision = :decision, "
                    "decision_history = list_append(if_not_exists(decision_history, :empty), :history)"
                ),
                ConditionExpression="#status = :scored AND decision = :pending",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={
                    ":decision": decision,
                    ":empty": [],
                    ":history": [history],
                    ":scored": "SCORED",
                    ":pending": "PENDING",
                },
                ReturnValues="ALL_NEW",
            )["Attributes"]
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                return _error(409, "candidate already has a recruiter decision or is not scored")
            raise

        if action == "shortlist":
            email = candidate.get("email")
            sender = os.getenv("SES_SENDER", "DISABLED")
            if not isinstance(email, str) or not email.strip():
                email_status = "NO_EMAIL"
            elif not sender or sender == "DISABLED":
                email_status = "FAILED"
            else:
                notes = interview.get("notes", "").strip()
                body_lines = [
                    f"Hello {candidate.get('name') or 'Candidate'},",
                    "",
                    "You have been shortlisted for an interview.",
                    f"Date and time: {interview['date_time'].strip()}",
                    f"Location or meeting link: {interview['location_or_link'].strip()}",
                ]
                if notes:
                    body_lines.extend(["", f"Additional information: {notes}"])
                body_lines.extend(["", "Regards,", "Recruitment Team"])
                try:
                    ses.send_email(
                        Source=sender,
                        Destination={"ToAddresses": [email]},
                        Message={
                            "Subject": {"Data": "Interview invitation"},
                            "Body": {"Text": {"Data": "\n".join(body_lines)}},
                        },
                    )
                    email_status = "SENT"
                except Exception:
                    logger.exception("shortlist email failed request_id=%s", request_id)
                    email_status = "FAILED"
            updated = table.update_item(
                Key=key,
                UpdateExpression="SET email_status = :email_status",
                ExpressionAttributeValues={":email_status": email_status},
                ReturnValues="ALL_NEW",
            )["Attributes"]

        return _reply(200, updated)
    except ValueError as exc:
        return _error(400, str(exc))
    except ClientError:
        logger.exception("decision API AWS operation failed request_id=%s", request_id)
        return _error(500, "internal service error")
    except Exception:
        logger.exception("decision API unexpected failure request_id=%s", request_id)
        return _error(500, "internal service error")
