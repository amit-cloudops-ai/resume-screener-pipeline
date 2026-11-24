"""Tests for the B1 deterministic scoring library."""
import copy
import json
from pathlib import Path

import pytest

from backend.scoring.scoring import score_candidate, SCORER_VERSION

ROOT = Path(__file__).resolve().parents[2]


def load_fixture(path):
    with (ROOT / path).open(encoding="utf-8") as handle:
        return json.load(handle)


@pytest.fixture
def job():
    return load_fixture("fixtures/jobs/job_devops.json")


@pytest.fixture
def strong():
    return load_fixture("fixtures/candidates/cand_strong.json")


@pytest.fixture
def partial():
    return load_fixture("fixtures/candidates/cand_partial.json")


@pytest.fixture
def sparse():
    return load_fixture("fixtures/candidates/cand_sparse.json")


def test_strong_candidate_scores_100(strong, job):
    result = score_candidate(strong, job)
    assert result["score"] == 100.0
    assert result["above_threshold"] is True
    assert result["score_breakdown"]["title"]["best_pair"] == [
        "devops engineer", "devops engineer"
    ]


def test_partial_candidate_scores_44_8(partial, job):
    assert score_candidate(partial, job)["score"] == 44.8


def test_sparse_candidate_scores_zero(sparse, job):
    result = score_candidate(sparse, job)
    assert result["score"] == 0.0
    assert result["score_breakdown"]["title"]["best_pair"] is None


def test_breakdown_matches_candidate_contract(strong, job):
    breakdown = score_candidate(strong, job)["score_breakdown"]
    assert set(breakdown) == {"skills", "title", "experience", "scorer_version"}
    assert set(breakdown["skills"]) == {"score", "weight", "matched", "missing"}
    assert set(breakdown["title"]) == {"score", "weight", "best_pair"}
    assert set(breakdown["experience"]) == {
        "score", "weight", "years_counted", "required_years"
    }
    assert breakdown["scorer_version"] == SCORER_VERSION


def test_input_dictionaries_are_not_mutated(strong, job):
    before_candidate, before_job = copy.deepcopy(strong), copy.deepcopy(job)
    score_candidate(strong, job)
    assert strong == before_candidate
    assert job == before_job


def test_skill_matching_is_case_insensitive_and_sorted(job):
    result = score_candidate({"skills": ["Docker", "AWS", "aws"]}, job)
    assert result["score_breakdown"]["skills"]["matched"] == ["aws", "docker"]


def test_duplicate_required_skills_are_counted_once(job):
    result = score_candidate(
        {"skills": ["aws"]},
        {**job, "required_skills": ["aws", "aws", "docker"]},
    )
    assert result["score_breakdown"]["skills"]["score"] == 0.5


def test_missing_optional_fields_are_handled(job):
    result = score_candidate({}, job)
    assert result["score_breakdown"]["skills"]["matched"] == []
    assert result["score_breakdown"]["title"]["best_pair"] is None


def test_no_required_skills_raises(job):
    with pytest.raises(ValueError, match="required_skills"):
        score_candidate({}, {**job, "required_skills": []})


@pytest.mark.parametrize("bad", [None, "aws", 3, {"aws": True}, ["aws", 4]])
def test_invalid_candidate_skills_raise(job, bad):
    with pytest.raises(ValueError):
        score_candidate({"skills": bad}, job)


@pytest.mark.parametrize("bad", [None, "engineer", 3])
def test_invalid_titles_raise(job, bad):
    with pytest.raises(ValueError):
        score_candidate({"titles": bad}, job)


@pytest.mark.parametrize("years, expected", [
    (None, 0.0), (0, 0.0), (1.5, 0.5), (3, 1.0), (8, 1.0)
])
def test_experience_ratio(job, years, expected):
    result = score_candidate({"experience_years": years}, job)
    assert result["score_breakdown"]["experience"]["score"] == expected


@pytest.mark.parametrize("required", [None, 0])
def test_zero_or_null_required_experience_scores_full(required, job):
    result = score_candidate(
        {"experience_years": None}, {**job, "required_years": required}
    )
    assert result["score_breakdown"]["experience"]["score"] == 1.0


@pytest.mark.parametrize("bad", ["two", True, -1, float("inf"), float("nan")])
def test_invalid_experience_values_raise(job, bad):
    with pytest.raises(ValueError):
        score_candidate({"experience_years": bad}, job)


def test_sde_alias_matches_software_engineer(job):
    result = score_candidate(
        {"titles": ["SDE"]},
        {**job, "jd_titles": ["software engineer"]},
    )
    assert result["score_breakdown"]["title"]["score"] == 1.0


def test_software_developer_alias(job):
    result = score_candidate(
        {"titles": ["software developer"]},
        {**job, "jd_titles": ["software engineer"]},
    )
    assert result["score_breakdown"]["title"]["score"] == 1.0


def test_dev_ops_alias(job):
    result = score_candidate(
        {"titles": ["dev ops engineer"]},
        {**job, "jd_titles": ["devops engineer"]},
    )
    assert result["score_breakdown"]["title"]["score"] == 1.0


@pytest.mark.parametrize("candidate_title, expected", [
    ("senior devops engineer", 1.0),
    ("mid devops engineer", 0.85),
    ("junior devops engineer", 0.5),
    ("intern devops engineer", 0.5),
])
def test_seniority_levels(candidate_title, expected, job):
    result = score_candidate(
        {"titles": [candidate_title]},
        {**job, "jd_titles": ["senior devops engineer"]},
    )
    assert result["score_breakdown"]["title"]["score"] == expected


def test_best_title_pair_is_selected(job):
    result = score_candidate(
        {"titles": ["data analyst", "devops engineer"]},
        {**job, "jd_titles": ["software engineer", "devops engineer"]},
    )
    assert result["score_breakdown"]["title"]["best_pair"] == [
        "devops engineer", "devops engineer"
    ]


def test_job_title_is_fallback_when_jd_titles_empty(job):
    result = score_candidate(
        {"titles": ["devops engineer"]},
        {**job, "jd_titles": []},
    )
    assert result["score_breakdown"]["title"]["score"] == 1.0


def test_threshold_is_inclusive(strong, job):
    assert score_candidate(strong, {**job, "threshold": 100})["above_threshold"] is True


@pytest.mark.parametrize("threshold", [-1, 101, "60", True, float("inf")])
def test_invalid_threshold_raises(job, threshold):
    with pytest.raises(ValueError):
        score_candidate({}, {**job, "threshold": threshold})


@pytest.mark.parametrize("candidate, job_value", [
    (None, {}),
    ([], {}),
    ({}, None),
    ({}, []),
])
def test_non_object_arguments_raise(candidate, job_value):
    with pytest.raises(ValueError):
        score_candidate(candidate, job_value)


def test_result_contains_expected_top_level_fields(strong, job):
    assert set(score_candidate(strong, job)) == {
        "score", "above_threshold", "score_breakdown"
    }


def test_component_scores_are_rounded_to_three_decimals(partial, job):
    breakdown = score_candidate(partial, job)["score_breakdown"]
    for component in ("skills", "title", "experience"):
        value = breakdown[component]["score"]
        assert value == round(value, 3)


def test_weights_are_exact(strong, job):
    breakdown = score_candidate(strong, job)["score_breakdown"]
    assert breakdown["skills"]["weight"] == 0.5
    assert breakdown["title"]["weight"] == 0.3
    assert breakdown["experience"]["weight"] == 0.2
