import copy
import json
import pathlib

import pytest
from jsonschema import Draft7Validator

ROOT = pathlib.Path(__file__).resolve().parents[2]


def load(rel):
    return json.loads((ROOT / rel).read_text())


def errors(schema_rel, payload):
    return list(Draft7Validator(load(schema_rel)).iter_errors(payload))


def test_valid_candidate_fixtures_pass():
    for f in (ROOT / "fixtures/candidates").glob("*.json"):
        assert not errors("contracts/candidate.schema.json", json.loads(f.read_text())), f.name


@pytest.mark.parametrize("mutate", [
    lambda c: c.update(score=150),
    lambda c: c.update(status="DONE"),
    lambda c: c.update(candidate_id="xyz"),
    lambda c: c.update(unknown_field=1),
    lambda c: c.pop("decision"),
    lambda c: c.update(experience_years=-1),
])
def test_bad_candidates_are_rejected(mutate):
    c = copy.deepcopy(load("fixtures/candidates/cand_strong.json"))
    mutate(c)
    assert errors("contracts/candidate.schema.json", c)


def test_scored_candidate_with_breakdown_is_valid():
    c = copy.deepcopy(load("fixtures/candidates/cand_strong.json"))
    c.update(status="SCORED", score=91.5, above_threshold=True, scored_at="2026-11-19T09:10:00Z",
             score_breakdown={
                 "skills": {"score": 1.0, "weight": 0.5, "matched": ["aws"], "missing": []},
                 "title": {"score": 1.0, "weight": 0.3, "best_pair": ["devops engineer", "devops engineer"]},
                 "experience": {"score": 1.0, "weight": 0.2, "years_counted": 6.5, "required_years": 3},
                 "scorer_version": "1.0.0"})
    assert not errors("contracts/candidate.schema.json", c)


def test_job_and_failed_job_reject_bad_enums():
    j = load("fixtures/jobs/job_devops.json"); j["status"] = "WHATEVER"
    assert errors("contracts/job.schema.json", j)
    f = load("fixtures/failed_jobs/failed_corrupt.json"); f["stage"] = "NOPE"
    assert errors("contracts/failed_job.schema.json", f)
    f = load("fixtures/failed_jobs/failed_corrupt.json"); f["error_type"] = "JD_NO_SKILLS"
    assert not errors("contracts/failed_job.schema.json", f)
