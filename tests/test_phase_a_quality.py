"""Phase A quality regression tests for parser requirements discovered in the release audit."""
import json
from decimal import Decimal
from pathlib import Path

from backend.parsing.common import derive_fields, experience_years, split_comprehend_text
from backend.scoring.scoring import score_candidate


ROOT = Path(__file__).resolve().parents[1]


def test_taxonomy_meets_work_split_minimum_and_has_no_alias_collisions():
    taxonomy = json.loads(
        (ROOT / "backend" / "parsing" / "skills_taxonomy.json").read_text(encoding="utf-8")
    )
    assert len(taxonomy) >= 150
    aliases = {}
    for canonical, terms in taxonomy.items():
        for term in [canonical, *terms]:
            key = term.casefold()
            assert key not in aliases or aliases[key] == canonical
            aliases[key] = canonical


def test_standard_comprehend_title_is_not_treated_as_a_job_title():
    fields = derive_fields(
        "Ada Example\nada@example.com\nWorked at Example Systems",
        {
            "standard": [
                {"Type": "PERSON", "Text": "Ada Example"},
                {"Type": "ORGANIZATION", "Text": "Example Systems"},
                {"Type": "TITLE", "Text": "The Art of Cloud Computing"},
            ],
            "custom": [],
        },
    )
    assert fields["titles"] == []
    assert fields["name"] == "Ada Example"
    assert fields["employers"] == ["Example Systems"]


def test_custom_job_title_is_retained():
    fields = derive_fields(
        "Ada Example\nada@example.com",
        {
            "standard": [{"Type": "PERSON", "Text": "Ada Example"}],
            "custom": [{"Type": "JOB_TITLE", "Text": "Senior Cloud Engineer"}],
        },
    )
    assert fields["titles"] == ["senior cloud engineer"]


def test_experience_uses_n_plus_fallback_when_dates_are_absent():
    assert experience_years("Summary: 7+ years of cloud engineering experience") == 7.0


def test_experience_fallback_is_capped_at_40_years():
    assert experience_years("Summary: 55+ years of engineering experience") == 40


def test_explicit_date_ranges_take_precedence_over_n_plus_fallback():
    text = "Summary: 12+ years experience. Engineer, Jan 2018 - Dec 2020."
    assert experience_years(text) == 3.0


def test_experience_union_does_not_double_count_overlapping_roles():
    text = "Jan 2018 - Dec 2020\nJan 2020 - Dec 2022"
    assert experience_years(text) == 5.0


def test_experience_date_union_obeys_40_year_cap():
    text = "Jan 1970 - Dec 2025"
    assert experience_years(text) == 40


def test_scoring_accepts_dynamodb_decimal_values():
    result = score_candidate(
        {
            "skills": ["python", "docker"],
            "titles": ["senior devops engineer"],
            "experience_years": Decimal("6"),
        },
        {
            "required_skills": ["python", "docker"],
            "jd_titles": ["senior devops engineer"],
            "required_years": Decimal("6"),
            "threshold": Decimal("60"),
        },
    )
    assert result["score"] == 100.0
    assert result["above_threshold"] is True


def test_scoring_still_rejects_boolean_numeric_values():
    try:
        score_candidate(
            {"skills": ["python"], "experience_years": True},
            {"required_skills": ["python"], "required_years": 1},
        )
    except ValueError as exc:
        assert "experience_years" in str(exc)
    else:
        raise AssertionError("boolean must not be accepted as a numeric experience value")


def test_comprehend_chunking_prefers_sentence_boundaries_and_respects_limits():
    first = "A" * 2000 + "."
    second = "B" * 2000 + "."
    third = "C" * 2000 + "."
    chunks = split_comprehend_text(f"{first} {second} {third}")
    assert chunks == [first + " " + second, third]
    assert all(len(chunk) <= 4500 for chunk in chunks)
    assert all(len(chunk.encode("utf-8")) <= 4800 for chunk in chunks)


def test_comprehend_chunking_never_splits_utf8_codepoints():
    text = ("Résumé ingénieur. " * 400)
    chunks = split_comprehend_text(text)
    assert "".join(chunks).replace(" ", "") == text.strip().replace(" ", "")
    assert all(len(chunk.encode("utf-8")) <= 4800 for chunk in chunks)
