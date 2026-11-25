"""Validate representative success and error response bodies against OpenAPI.

These are response-contract tests, not route-presence checks: each documented
operation/status pair is resolved from OpenAPI and its complete payload is
validated against that response's declared schema.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import yaml
from jsonschema import Draft7Validator, RefResolver

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "contracts"
OPENAPI_PATH = CONTRACTS / "openapi.yaml"


def _load_fixture(relative_path: str) -> dict:
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


def _openapi():
    spec = yaml.safe_load(OPENAPI_PATH.read_text(encoding="utf-8"))
    store = {}
    for filename in ("job.schema.json", "candidate.schema.json", "failed_job.schema.json"):
        path = CONTRACTS / filename
        store[path.as_uri()] = json.loads(path.read_text(encoding="utf-8"))
    resolver = RefResolver(
        base_uri=OPENAPI_PATH.as_uri(),
        referrer=spec,
        store=store,
    )
    return spec, resolver


def _response_schema(spec: dict, path: str, method: str, status: int):
    operation = spec["paths"][path][method.lower()]
    response = operation["responses"][str(status)]
    content = response.get("content", {})
    assert content, f"{method} {path} {status} has no documented response content"
    media_type = "text/csv" if "text/csv" in content else "application/json"
    schema = content[media_type].get("schema")
    assert schema is not None, f"{method} {path} {status} has no response schema"
    return schema, media_type


def _validate_response(spec, resolver, path, method, status, payload):
    schema, media_type = _response_schema(spec, path, method, status)
    validator = Draft7Validator(schema, resolver=resolver)
    errors = sorted(validator.iter_errors(payload), key=lambda error: list(error.path))
    assert not errors, (
        f"{method} {path} -> {status} ({media_type}) violated OpenAPI: "
        + "; ".join(error.message for error in errors)
    )


def _scored_candidate():
    candidate = _load_fixture("fixtures/candidates/cand_strong.json")
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
    return candidate


def test_every_openapi_operation_has_a_schema_valid_success_response():
    spec, resolver = _openapi()
    job = _load_fixture("fixtures/jobs/job_devops.json")
    candidate = _scored_candidate()
    failed = _load_fixture("fixtures/failed_jobs/failed_corrupt.json")
    upload = {"file_name": "resume.pdf", "url": "https://uploads.example.test/signed", "s3_key": "resumes/0123456789ab/resume.pdf"}

    # Payloads are representative Lambda proxy response bodies. Each is checked
    # against the schema selected from the actual OpenAPI operation/status pair.
    cases = [
        ("/jobs", "get", 200, {"jobs": [job]}),
        ("/jobs", "post", 201, {"job": job, "jd_upload": upload}),
        ("/jobs/{job_id}", "get", 200, job),
        ("/jobs/{job_id}/uploads", "post", 200, {"uploads": [upload]}),
        ("/jobs/{job_id}/candidates", "get", 200, {"candidates": [candidate], "counts": {"SHORTLISTED": 1}}),
        ("/jobs/{job_id}/candidates/{candidate_id}", "get", 200, candidate),
        ("/jobs/{job_id}/candidates/{candidate_id}/decision", "post", 200, candidate),
        ("/jobs/{job_id}/shortlist.csv", "get", 200, "rank,name,email,score,skills_matched,skills_missing,titles,experience_years,decision,email_status\n"),
        ("/failed-jobs", "get", 200, {"failed_jobs": [failed]}),
        ("/failed-jobs/{failed_id}/retry", "post", 202, failed),
    ]
    for path, method, status, payload in cases:
        _validate_response(spec, resolver, path, method, status, payload)


def test_every_documented_json_error_response_matches_error_schema():
    spec, resolver = _openapi()
    error = {"error": "request could not be completed"}
    for path, methods in spec["paths"].items():
        for method, operation in methods.items():
            if method not in {"get", "post", "put", "patch", "delete"}:
                continue
            for status, response in operation.get("responses", {}).items():
                content = response.get("content", {})
                if "application/json" not in content:
                    continue
                schema = content["application/json"].get("schema", {})
                if schema.get("$ref") == "#/components/schemas/Error":
                    _validate_response(spec, resolver, path, method, int(status), error)


def test_openapi_success_response_coverage_is_complete_for_all_api_routes():
    spec, _ = _openapi()
    expected = {
        ("/jobs", "get", "200"),
        ("/jobs", "post", "201"),
        ("/jobs/{job_id}", "get", "200"),
        ("/jobs/{job_id}/uploads", "post", "200"),
        ("/jobs/{job_id}/candidates", "get", "200"),
        ("/jobs/{job_id}/candidates/{candidate_id}", "get", "200"),
        ("/jobs/{job_id}/candidates/{candidate_id}/decision", "post", "200"),
        ("/jobs/{job_id}/shortlist.csv", "get", "200"),
        ("/failed-jobs", "get", "200"),
        ("/failed-jobs/{failed_id}/retry", "post", "202"),
    }
    actual = {
        (path, method, status)
        for path, methods in spec["paths"].items()
        for method, operation in methods.items()
        if method in {"get", "post", "put", "patch", "delete"}
        for status in operation.get("responses", {})
        if status.startswith("2")
    }
    assert actual == expected
