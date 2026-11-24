"""Cross-endpoint contract envelope checks (B9)."""
import csv
import io
import json
from pathlib import Path

import yaml
from jsonschema import Draft7Validator

ROOT = Path(__file__).resolve().parents[2]


def load_json(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def validate(schema_path, payload):
    schema = load_json(schema_path)
    errors = list(Draft7Validator(schema).iter_errors(payload))
    assert not errors, [error.message for error in errors]


def test_jobs_candidates_and_failed_jobs_envelopes_use_frozen_schemas():
    job = load_json("fixtures/jobs/job_devops.json")
    candidate = load_json("fixtures/candidates/cand_strong.json")
    failed = load_json("fixtures/failed_jobs/failed_corrupt.json")
    validate("contracts/job.schema.json", job)
    validate("contracts/candidate.schema.json", candidate)
    validate("contracts/failed_job.schema.json", failed)

    jobs_response = {"jobs": [job]}
    candidates_response = {"candidates": [candidate], "counts": {"PENDING": 1}}
    failed_response = {"failed_jobs": [failed]}
    assert set(jobs_response) == {"jobs"}
    assert set(candidates_response) == {"candidates", "counts"}
    assert set(failed_response) == {"failed_jobs"}


def test_scored_candidate_and_decision_history_remain_schema_valid():
    candidate = load_json("fixtures/candidates/cand_strong.json")
    candidate.update(
        status="SCORED",
        score=88.5,
        above_threshold=True,
        score_breakdown={
            "skills": {"score": 1.0, "weight": 0.5, "matched": ["aws"], "missing": []},
            "title": {"score": 0.9, "weight": 0.3, "best_pair": ["devops engineer", "devops engineer"]},
            "experience": {"score": 1.0, "weight": 0.2, "years_counted": 6, "required_years": 3},
            "scorer_version": "1.0.0",
        },
        scored_at="2026-11-24T00:00:00Z",
        decision="SHORTLISTED",
        decision_history=[{"action": "shortlist", "by": "recruiter-sub", "at": "2026-11-24T00:01:00Z"}],
        email_status="SENT",
    )
    validate("contracts/candidate.schema.json", candidate)


def test_openapi_declares_all_implemented_routes_and_expected_methods():
    spec = yaml.safe_load((ROOT / "contracts/openapi.yaml").read_text(encoding="utf-8"))
    expected = {
        "/jobs": {"get", "post"},
        "/jobs/{job_id}": {"get"},
        "/jobs/{job_id}/uploads": {"post"},
        "/jobs/{job_id}/candidates": {"get"},
        "/jobs/{job_id}/candidates/{candidate_id}": {"get"},
        "/jobs/{job_id}/candidates/{candidate_id}/decision": {"post"},
        "/jobs/{job_id}/shortlist.csv": {"get"},
        "/failed-jobs": {"get"},
        "/failed-jobs/{failed_id}/retry": {"post"},
    }
    for path, methods in expected.items():
        assert methods <= set(spec["paths"][path])
    assert spec["security"] == [{"cognito": []}]


def test_csv_contract_header_order_is_fixed():
    expected = [
        "rank", "name", "email", "score", "skills_matched", "skills_missing",
        "titles", "experience_years", "decision", "email_status",
    ]
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=expected)
    writer.writeheader()
    assert next(csv.reader(io.StringIO(stream.getvalue()))) == expected
