"""Validates what Part A writes against the frozen schemas in contracts/ (brief section 9).

Skips (visibly) only when contracts/ is missing, so the check is never silently green. If a test here fails, change
records.py / the handlers to match the contract. Never loosen the schema.
"""
import json
import re
from pathlib import Path

import pytest

import records

_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "contracts").is_dir()), None)
CONTRACTS = _ROOT / "contracts" if _ROOT else None
KEY = "resumes/a1b2c3d4e5f6/asha verma.pdf"
JOB = "a1b2c3d4e5f6"
CID = records.candidate_id_for(JOB, KEY)
FIELDS = {"name": "Asha Verma", "email": "asha@example.com", "skills": ["aws"], "employers": ["Acme"],
          "titles": ["devops engineer"], "experience_years": 3.2}


def schema(name):
    path = CONTRACTS / name if CONTRACTS else None
    if not path or not path.exists():
        pytest.skip(f"contracts/{name} not found in this checkout")
    return json.loads(path.read_text())


def validate(item, name):
    jsonschema = pytest.importorskip("jsonschema")
    jsonschema.validate(json.loads(json.dumps(item, default=float)), schema(name))


def row(**attrs):  # what DynamoDB holds after Store.upsert_candidate: attrs + the defaults it adds
    return {"job_id": JOB, "candidate_id": CID, "decision": "PENDING", "decision_history": [], "created_at": records.now_iso(), **attrs}


def test_parsed_candidate_row_matches_candidate_schema():
    validate(row(**records.parsed_candidate_attrs(FIELDS, "parsed/x.json", KEY)), "candidate.schema.json")


def test_parsed_candidate_with_unknown_fields_still_matches():
    unknown = {"name": None, "email": None, "skills": [], "employers": [], "titles": [], "experience_years": 0.0}
    validate(row(**records.parsed_candidate_attrs(unknown, "parsed/x.json", KEY)), "candidate.schema.json")


@pytest.mark.parametrize("status", ["PARSING", "FAILED"])
def test_status_only_candidate_rows_still_have_the_required_fields(status):
    validate(row(status=status, **records.candidate_base(KEY)), "candidate.schema.json")


@pytest.mark.parametrize("stage", ["JD_PARSE", "TEXT_EXTRACT", "COMPREHEND", "PARSE", "SCORE", "UNKNOWN"])
@pytest.mark.parametrize("s3_key,message_id", [(KEY, "m1"), ("", None), (None, "m2")])
def test_failed_job_rows_match_failed_job_schema(stage, s3_key, message_id):
    validate(records.failed_job_item(job_id=JOB, stage=stage, s3_key=s3_key, error_type="CORRUPT_FILE", error_message="x",
                                     attempts=1, message_id=message_id), "failed_job.schema.json")


def test_failed_job_with_unknown_job_id_still_validates():
    validate(records.failed_job_item(job_id=None, stage="UNKNOWN", s3_key=None, error_type="UNKNOWN", error_message="x", attempts=3),
             "failed_job.schema.json")


def test_score_message_reasons_are_the_ones_in_sqs_messages_md():
    text = (CONTRACTS / "sqs_messages.md").read_text() if CONTRACTS and (CONTRACTS / "sqs_messages.md").exists() else pytest.skip("no sqs_messages.md")
    allowed = set(re.search(r"`reason` in: ([A-Z_ |]+)\.", text).group(1).replace(" ", "").split("|"))
    assert {"CANDIDATE_PARSED", "JD_READY"} <= allowed
    src = (Path(__file__).resolve().parents[1])
    used = set(re.findall(r'send_score\([^)]*"([A-Z_]+)"\)', (src / "parse_handler.py").read_text() + (src / "jd_handler.py").read_text()))
    assert used and used <= allowed


def test_job_fields_part_a_writes_are_valid_per_property_in_job_schema():
    jsonschema = pytest.importorskip("jsonschema")
    props = schema("job.schema.json")["properties"]  # skips if the file is missing
    mine = {"required_skills": ["aws"], "jd_titles": ["devops engineer"], "required_years": 3, "status": "JD_PARSED"}
    for key, value in mine.items():
        assert key in props, f"job.schema.json has no property {key!r}"
        jsonschema.validate(value, props[key])
    jsonschema.validate("FAILED", props["status"])
