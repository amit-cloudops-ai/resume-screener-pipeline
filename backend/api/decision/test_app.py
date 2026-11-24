import json
from decimal import Decimal
from types import SimpleNamespace

import pytest

from backend.api.decision import app


JOB_ID = "a1b2c3d4e5f6"
CANDIDATE_ID = "0123456789abcdef"


class ConditionalCheckFailedException(Exception):
    pass


class FakeTable:
    def __init__(self, candidate):
        self.candidate = candidate
        self.updates = []
        self.fail_email_status_update = False
        self.before_decision_update = None
        self.after_decision_update = None
        self.before_email_status_update = None

    def update_item(self, **kwargs):
        self.updates.append(kwargs)
        values = kwargs["ExpressionAttributeValues"]
        if ":previous_decision" in values:
            if self.before_decision_update:
                self.before_decision_update(self.candidate)
                self.before_decision_update = None
            if (not self.candidate or self.candidate.get("status") != values[":scored"]
                    or self.candidate.get("decision") != values[":previous_decision"]):
                raise ConditionalCheckFailedException()
            self.candidate["decision"] = values[":decision"]
            self.candidate.setdefault("decision_history", []).extend(values[":history"])
            if self.after_decision_update:
                self.after_decision_update(self.candidate)
                self.after_decision_update = None
        else:
            if self.before_email_status_update:
                self.before_email_status_update(self.candidate)
                self.before_email_status_update = None
            if self.fail_email_status_update:
                raise RuntimeError("database unavailable")
            if (not self.candidate or self.candidate.get("status") != values[":scored"]
                    or self.candidate.get("decision") != values[":decision"]
                    or self.candidate.get("decision_history") != values[":history_snapshot"]):
                raise ConditionalCheckFailedException()
            self.candidate["email_status"] = values[":email_status"]
        return {"Attributes": dict(self.candidate)}

    def get_item(self, **kwargs):
        return {"Item": dict(self.candidate)} if self.candidate else {}


class FakeSes:
    def __init__(self, error=None):
        self.error = error
        self.calls = []
        self.before_send = None

    def send_email(self, **kwargs):
        self.calls.append(kwargs)
        if self.before_send:
            self.before_send()
            self.before_send = None
        if self.error:
            raise self.error
        return {"MessageId": "msg-1"}


@pytest.fixture
def setup(monkeypatch):
    candidate = {
        "job_id": JOB_ID,
        "candidate_id": CANDIDATE_ID,
        "status": "SCORED",
        "decision": "PENDING",
        "decision_history": [],
        "email": "person@example.com",
        "name": "Taylor Example",
        "email_status": "NOT_SENT",
    }
    table, ses = FakeTable(candidate), FakeSes()
    monkeypatch.setattr(app, "_clients", lambda: (table, ses))
    monkeypatch.setenv("SES_SENDER", "recruiter@example.com")
    return candidate, table, ses


def event(body):
    return {
        "body": json.dumps(body),
        "pathParameters": {"job_id": JOB_ID, "candidate_id": CANDIDATE_ID},
        "requestContext": {"authorizer": {"claims": {"email": "recruiter@example.com"}}},
    }


def response(result):
    return result["statusCode"], json.loads(result["body"])


@pytest.mark.parametrize("body", [None, "not-json", [], {}, {"action": "other"}, {"action": "shortlist"},
                                  {"action": "shortlist", "interview": {"date_time": "tomorrow"}},
                                  {"action": "shortlist", "interview": {"date_time": "tomorrow", "location_or_link": " "}},
                                  {"action": "shortlist", "interview": {"date_time": "tomorrow", "location_or_link": "Zoom", "notes": 3}}])
def test_invalid_requests_return_400_without_writes(setup, body):
    _, table, ses = setup
    result = app.lambda_handler(event(body), SimpleNamespace(aws_request_id="req"))
    assert response(result)[0] == 400
    assert table.updates == []
    assert ses.calls == []


def test_missing_path_parameters_return_400(setup):
    _, table, _ = setup
    request = event({"action": "reject"})
    request["pathParameters"] = {}
    assert response(app.lambda_handler(request, None))[0] == 400
    assert table.updates == []


def test_reject_persists_decision_history_and_does_not_send_email(setup):
    _, table, ses = setup
    status, result = response(app.lambda_handler(event({"action": "reject"}), None))
    assert status == 200
    assert result["decision"] == "REJECTED"
    assert result["email_status"] == "NOT_SENT"
    assert result["decision_history"][0]["action"] == "reject"
    assert result["decision_history"][0]["by"] == "recruiter@example.com"
    assert result["decision_history"][0]["at"].endswith("Z")
    assert len(table.updates) == 2
    assert "#status = :scored AND #decision = :previous_decision" == table.updates[0]["ConditionExpression"]
    assert table.updates[0]["ExpressionAttributeValues"][":previous_decision"] == "PENDING"
    assert ses.calls == []


def test_existing_decision_can_be_changed_and_history_is_preserved(setup):
    candidate, table, _ = setup
    candidate["decision"] = "SHORTLISTED"
    candidate["decision_history"] = [{"action": "shortlist", "by": "first", "at": "t1"}]
    status, result = response(app.lambda_handler(event({"action": "reject"}), None))
    assert status == 200
    assert result["decision"] == "REJECTED"
    assert [entry["action"] for entry in result["decision_history"]] == ["shortlist", "reject"]
    assert table.updates[0]["ExpressionAttributeValues"][":previous_decision"] == "SHORTLISTED"


def test_shortlist_sends_interview_details_and_persists_sent_status(setup):
    _, table, ses = setup
    body = {"action": "shortlist", "interview": {"date_time": "2026-11-25 10:00 UTC", "location_or_link": "https://meet.example", "notes": "Bring portfolio"}}
    status, result = response(app.lambda_handler(event(body), None))
    assert status == 200
    assert result["decision"] == "SHORTLISTED"
    assert result["email_status"] == "SENT"
    assert len(table.updates) == 2
    assert len(ses.calls) == 1
    email_text = ses.calls[0]["Message"]["Body"]["Text"]["Data"]
    assert "2026-11-25 10:00 UTC" in email_text
    assert "https://meet.example" in email_text
    assert "Bring portfolio" in email_text
    assert table.candidate["decision_history"][0]["action"] == "shortlist"
    assert table.updates[1]["ExpressionAttributeValues"][":history_snapshot"] == result["decision_history"]


def test_shortlist_without_candidate_email_records_no_email(setup):
    candidate, _, ses = setup
    candidate["email"] = None
    status, result = response(app.lambda_handler(event({"action": "shortlist", "interview": {"date_time": "tomorrow", "location_or_link": "Office"}}), None))
    assert status == 200
    assert result["email_status"] == "NO_EMAIL"
    assert ses.calls == []


def test_ses_failure_is_recorded_as_failed(setup):
    _, _, ses = setup
    ses.error = RuntimeError("SES unavailable")
    status, result = response(app.lambda_handler(event({"action": "shortlist", "interview": {"date_time": "tomorrow", "location_or_link": "Office"}}), None))
    assert status == 200
    assert result["decision"] == "SHORTLISTED"
    assert result["email_status"] == "FAILED"


def test_competing_decision_update_returns_409_and_preserves_winner(setup):
    candidate, table, ses = setup

    def competing_decision(row):
        row["decision"] = "REJECTED"
        row["decision_history"].append({"action": "reject", "by": "other", "at": "t2"})

    table.before_decision_update = competing_decision
    status, result = response(app.lambda_handler(event({"action": "reject"}), None))
    assert status == 409
    assert result["error"] == "decision_conflict"
    assert candidate["decision"] == "REJECTED"
    assert len(candidate["decision_history"]) == 1
    assert ses.calls == []


def test_email_status_cannot_overwrite_a_newer_decision(setup):
    candidate, table, ses = setup

    def newer_decision():
        candidate["decision"] = "REJECTED"
        candidate["decision_history"].append({"action": "reject", "by": "other", "at": "t2"})
        candidate["email_status"] = "NOT_SENT"

    ses.before_send = newer_decision
    status, result = response(app.lambda_handler(event({"action": "shortlist", "interview": {"date_time": "tomorrow", "location_or_link": "Office"}}), None))
    assert status == 409
    assert result["error"] == "decision_conflict"
    assert candidate["decision"] == "REJECTED"
    assert candidate["email_status"] == "NOT_SENT"
    assert len(candidate["decision_history"]) == 2
    assert len(ses.calls) == 1


def test_shortlist_without_email_and_reject_never_send_email(setup):
    candidate, _, ses = setup
    candidate["email"] = None
    shortlist = {"action": "shortlist", "interview": {"date_time": "tomorrow", "location_or_link": "Office"}}
    assert response(app.lambda_handler(event(shortlist), None))[1]["email_status"] == "NO_EMAIL"
    assert ses.calls == []


def test_email_status_write_failure_keeps_decision_and_reports_correct_message(setup):
    _, table, _ = setup
    table.fail_email_status_update = True
    status, result = response(app.lambda_handler(event({"action": "reject"}), None))
    assert status == 500
    assert result["detail"] == "Decision was saved, but email status could not be updated"
    assert table.candidate["decision"] == "REJECTED"
    assert len(table.candidate["decision_history"]) == 1


def test_missing_candidate_returns_404(setup):
    _, table, _ = setup
    table.candidate = None
    status, result = response(app.lambda_handler(event({"action": "reject"}), None))
    assert status == 404
    assert result["error"] == "not_found"


def test_unscored_candidate_returns_409_without_decision_write(setup):
    candidate, table, ses = setup
    candidate["status"] = "PARSED"
    status, result = response(app.lambda_handler(event({"action": "reject"}), None))
    assert status == 409
    assert result["error"] == "candidate_not_scored"
    assert table.updates == []
    assert ses.calls == []


def test_history_uses_cognito_sub_when_email_claim_is_missing(setup):
    _, table, _ = setup
    request = event({"action": "reject"})
    request["requestContext"]["authorizer"]["claims"] = {"sub": "recruiter-sub"}
    status, result = response(app.lambda_handler(request, None))
    assert status == 200
    assert result["decision_history"][0]["by"] == "recruiter-sub"
    assert table.updates[0]["ReturnValues"] == "ALL_NEW"


def test_decimal_values_in_dynamodb_response_are_json_serializable():
    result = app._response(200, {"score": Decimal("91.5"), "count": Decimal("2")})
    assert json.loads(result["body"]) == {"score": 91.5, "count": 2}
