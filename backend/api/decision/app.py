import json
import logging
import os
from datetime import datetime, timezone
from decimal import Decimal

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _json_default(value):
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _response(status_code, payload):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(payload, default=_json_default),
    }


def _clients():
    import boto3

    return (
        boto3.resource("dynamodb").Table(os.environ["CANDIDATES_TABLE"]),
        boto3.client("ses"),
    )


def _parse_request(event):
    raw_body = event.get("body")
    try:
        body = json.loads(raw_body) if isinstance(raw_body, str) else raw_body
    except (TypeError, json.JSONDecodeError):
        return None, "Request body must be valid JSON"
    if not isinstance(body, dict):
        return None, "Request body must be a JSON object"
    action = body.get("action")
    if action not in ("shortlist", "reject"):
        return None, "action must be 'shortlist' or 'reject'"

    interview = body.get("interview")
    if action == "shortlist":
        if not isinstance(interview, dict):
            return None, "interview details are required to shortlist"
        for field in ("date_time", "location_or_link"):
            if not isinstance(interview.get(field), str) or not interview[field].strip():
                return None, f"interview.{field} is required"
        if "notes" in interview and not isinstance(interview["notes"], str):
            return None, "interview.notes must be a string"

    return {"action": action, "interview": interview}, None


def _recruiter(event):
    authorizer = event.get("requestContext", {}).get("authorizer", {})
    claims = authorizer.get("claims", {})
    return claims.get("email") or claims.get("cognito:username") or claims.get("sub") or "unknown"


def _email_message(candidate, interview, sender):
    greeting = candidate.get("name") or "there"
    details = [
        f"Date and time: {interview['date_time']}",
        f"Location or link: {interview['location_or_link']}",
    ]
    if interview.get("notes"):
        details.append(f"Notes: {interview['notes']}")
    body = f"Hello {greeting},\n\nWe would like to invite you to an interview.\n\n" + "\n".join(details)
    return {
        "Source": sender,
        "Destination": {"ToAddresses": [candidate["email"]]},
        "Message": {
            "Subject": {"Data": "Interview invitation"},
            "Body": {"Text": {"Data": body}},
        },
    }


def _is_conditional_failure(exc):
    return exc.__class__.__name__ == "ConditionalCheckFailedException"


def lambda_handler(event, context):
    logger.info("decision API request_id=%s", getattr(context, "aws_request_id", "unknown"))
    parsed, error = _parse_request(event)
    if error:
        return _response(400, {"error": "invalid_request", "detail": error})

    path = event.get("pathParameters") or {}
    job_id, candidate_id = path.get("job_id"), path.get("candidate_id")
    if not job_id or not candidate_id:
        return _response(400, {"error": "invalid_request", "detail": "job_id and candidate_id are required"})

    table, ses = _clients()
    key = {"job_id": job_id, "candidate_id": candidate_id}
    current = table.get_item(Key=key, ConsistentRead=True).get("Item")
    if not current:
        return _response(404, {"error": "not_found", "detail": "Candidate not found"})
    if current.get("status") != "SCORED":
        return _response(409, {"error": "candidate_not_scored", "detail": "Candidate must be SCORED before a decision"})

    action = parsed["action"]
    decision = "SHORTLISTED" if action == "shortlist" else "REJECTED"
    previous_decision = current["decision"]
    email_status = "NOT_SENT" if action == "reject" else None
    history = {
        "action": action,
        "by": _recruiter(event),
        "at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }

    try:
        result = table.update_item(
            Key=key,
            UpdateExpression="SET #decision = :decision, decision_history = list_append(if_not_exists(decision_history, :empty), :history)",
            ConditionExpression="#status = :scored AND #decision = :previous_decision",
            ExpressionAttributeNames={"#decision": "decision", "#status": "status"},
            ExpressionAttributeValues={
                ":decision": decision,
                ":previous_decision": previous_decision,
                ":scored": "SCORED",
                ":empty": [],
                ":history": [history],
            },
            ReturnValues="ALL_NEW",
        )
        candidate = result["Attributes"]
    except Exception as exc:
        if _is_conditional_failure(exc):
            return _response(409, {"error": "decision_conflict", "detail": "Another decision was saved first; refresh the candidate and retry"})
        logger.exception("decision persistence failed request_id=%s", getattr(context, "aws_request_id", "unknown"))
        return _response(500, {"error": "internal_error", "detail": "Unable to save decision"})

    if action == "shortlist":
        email = candidate.get("email")
        if not email:
            email_status = "NO_EMAIL"
        else:
            try:
                ses.send_email(**_email_message(candidate, parsed["interview"], os.environ["SES_SENDER"] ))
                email_status = "SENT"
            except Exception:
                logger.exception("shortlist email failed request_id=%s", getattr(context, "aws_request_id", "unknown"))
                email_status = "FAILED"

    try:
        updated = table.update_item(
            Key=key,
            UpdateExpression="SET email_status = :email_status",
            ConditionExpression="#status = :scored AND #decision = :decision AND #history = :history_snapshot",
            ExpressionAttributeNames={"#status": "status", "#decision": "decision", "#history": "decision_history"},
            ExpressionAttributeValues={
                ":scored": "SCORED",
                ":decision": decision,
                ":history_snapshot": candidate["decision_history"],
                ":email_status": email_status,
            },
            ReturnValues="ALL_NEW",
        )
        candidate = updated["Attributes"]
    except Exception as exc:
        if _is_conditional_failure(exc):
            return _response(409, {"error": "decision_conflict", "detail": "Decision was saved, but another decision changed it before email status could be updated"})
        logger.exception("email status persistence failed request_id=%s", getattr(context, "aws_request_id", "unknown"))
        return _response(500, {"error": "internal_error", "detail": "Decision was saved, but email status could not be updated"})

    return _response(200, candidate)
