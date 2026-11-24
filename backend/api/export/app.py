"""Shortlisted-candidate CSV export (B6)."""
from __future__ import annotations

import csv
import json
import io
import logging
import os
import re

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)
_JOB_ID = re.compile(r"^[0-9a-f]{12}$")
_COLUMNS = [
    "rank", "name", "email", "score", "skills_matched", "skills_missing",
    "titles", "experience_years", "decision", "email_status",
]

def _safe_text(value) -> str:
    """Neutralize spreadsheet formula prefixes in untrusted resume-derived text."""
    text = "" if value is None else str(value)
    if text.lstrip(" \t\r\n").startswith(("=", "+", "-", "@")):
        return "'" + text
    return text




def _error(status: int, message: str) -> dict:
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": os.getenv("CORS_ORIGIN", ""),
            "Vary": "Origin",
        },
        "body": json.dumps({"error": message}),
    }


def lambda_handler(event, context):
    event = event if isinstance(event, dict) else {}
    request_id = getattr(context, "aws_request_id", "unknown")
    logger.info("CSV export request_id=%s", request_id)
    job_id = (event.get("pathParameters") or {}).get("job_id")
    if not isinstance(job_id, str) or not _JOB_ID.fullmatch(job_id):
        return _error(400, "job_id is invalid")
    try:
        table = boto3.resource(
            "dynamodb", region_name=os.getenv("AWS_REGION", "us-east-1")
        ).Table(os.environ["CANDIDATES_TABLE"])
        response = table.query(
            KeyConditionExpression=Key("job_id").eq(job_id),
        )
        candidates = response.get("Items", [])
        while response.get("LastEvaluatedKey"):
            response = table.query(
                KeyConditionExpression=Key("job_id").eq(job_id),
                FilterExpression=Key("job_id").eq(job_id),
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            candidates.extend(response.get("Items", []))
        shortlisted = [item for item in candidates if item.get("decision") == "SHORTLISTED"]
        shortlisted.sort(
            key=lambda item: (
                item.get("score") is None,
                -(float(item.get("score") or 0)),
                item.get("candidate_id", ""),
            )
        )
        output = io.StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=_COLUMNS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for rank, item in enumerate(shortlisted, start=1):
            breakdown = item.get("score_breakdown") or {}
            skills = breakdown.get("skills") or {}
            writer.writerow({
                "rank": rank,
                "name": _safe_text(item.get("name")),
                "email": _safe_text(item.get("email")),
                "score": item.get("score") if item.get("score") is not None else "",
                "skills_matched": _safe_text("; ".join(skills.get("matched") or [])),
                "skills_missing": _safe_text("; ".join(skills.get("missing") or [])),
                "titles": _safe_text("; ".join(item.get("titles") or [])),
                "experience_years": item.get("experience_years") if item.get("experience_years") is not None else "",
                "decision": item.get("decision") or "",
                "email_status": item.get("email_status") or "",
            })
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "text/csv; charset=utf-8",
                "Content-Disposition": f'attachment; filename="shortlist-{job_id}.csv"',
                "Access-Control-Allow-Origin": os.getenv("CORS_ORIGIN", ""),
                "Vary": "Origin",
            },
            "body": output.getvalue(),
        }
    except ClientError:
        logger.exception("CSV export DynamoDB operation failed request_id=%s", request_id)
        return _error(500, "internal service error")
    except Exception:
        logger.exception("CSV export unexpected failure request_id=%s", request_id)
        return _error(500, "internal service error")
