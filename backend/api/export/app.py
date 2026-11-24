"""CSV export Lambda for a job's shortlisted candidates."""

import csv
import io
import json
import os
import re
from decimal import Decimal, InvalidOperation

import boto3
from boto3.dynamodb.conditions import Key


CSV_COLUMNS = (
    "rank",
    "name",
    "email",
    "score",
    "skills_matched",
    "skills_missing",
    "titles",
    "experience_years",
    "decision",
    "email_status",
)


def _error(status_code, error):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"error": error}),
    }


def _list_cell(value):
    """Join string lists with semicolons, keeping commas readable in CSV."""
    if not isinstance(value, (list, tuple)):
        return ""
    return "; ".join(str(item) for item in value if item is not None)


def _candidate_row(candidate, rank):
    breakdown = candidate.get("score_breakdown") or {}
    skills = breakdown.get("skills") or {}
    return {
        "rank": rank,
        "name": candidate.get("name") or "",
        "email": candidate.get("email") or "",
        "score": candidate.get("score") if candidate.get("score") is not None else "",
        "skills_matched": _list_cell(skills.get("matched", [])),
        "skills_missing": _list_cell(skills.get("missing", [])),
        "titles": _list_cell(candidate.get("titles", [])),
        "experience_years": (
            candidate.get("experience_years")
            if candidate.get("experience_years") is not None
            else ""
        ),
        "decision": candidate.get("decision", ""),
        "email_status": candidate.get("email_status", ""),
    }


def _score_sort_key(candidate):
    score = candidate.get("score")
    if isinstance(score, bool) or not isinstance(score, (Decimal, int, float)):
        return (1, Decimal(0), candidate.get("candidate_id", ""))
    try:
        numeric_score = Decimal(str(score))
    except (InvalidOperation, ValueError):
        return (1, Decimal(0), candidate.get("candidate_id", ""))
    if not numeric_score.is_finite():
        return (1, Decimal(0), candidate.get("candidate_id", ""))
    return (0, -numeric_score, candidate.get("candidate_id", ""))


def _query_candidates(table, job_id):
    items = []
    query = {"KeyConditionExpression": Key("job_id").eq(job_id)}
    while True:
        response = table.query(**query)
        items.extend(response.get("Items", []))
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            return items
        query["ExclusiveStartKey"] = last_key


def handler(event, context):
    path_parameters = (event or {}).get("pathParameters") or {}
    job_id = path_parameters.get("job_id")
    if not isinstance(job_id, str) or not job_id.strip():
        return _error(400, "Missing required path parameter: job_id")
    if not re.fullmatch(r"[0-9a-f]{12}", job_id):
        return _error(400, "Invalid path parameter: job_id")

    try:
        table_name = os.environ["CANDIDATES_TABLE"]
        table = boto3.resource("dynamodb").Table(table_name)
        candidates = _query_candidates(table, job_id)
    except Exception:
        # Do not include SDK exception text; it may contain request or item data.
        return _error(500, "Internal server error")

    shortlisted = [c for c in candidates if c.get("decision") == "SHORTLISTED"]
    shortlisted.sort(key=_score_sort_key)

    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for rank, candidate in enumerate(shortlisted, start=1):
        writer.writerow(_candidate_row(candidate, rank))

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "text/csv; charset=utf-8",
            "Content-Disposition": f'attachment; filename="{job_id}-shortlist.csv"',
        },
        "body": "\ufeff" + output.getvalue(),
    }
