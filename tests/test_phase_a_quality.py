"""Phase A quality regression tests for parser requirements discovered in the release audit."""
import json
from decimal import Decimal
from docx import Document
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


def _golden_data():
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "fixtures" / "golden"
    expected = json.loads((root / "expected.json").read_text(encoding="utf-8"))
    jobs = json.loads((root / "job_descriptions.json").read_text(encoding="utf-8"))
    return root, expected, jobs


def test_golden_dataset_contains_twelve_resumes_and_three_jds():
    root, expected, jobs = _golden_data()
    resumes = expected["resumes"]
    assert len(resumes) == 12
    assert len(jobs["jobs"]) == 3
    assert sum(row["format"] == "digital_pdf" for row in resumes) == 4
    assert sum(row["format"] == "two_column_docx" for row in resumes) == 4
    assert sum(row["format"] == "scanned_pdf" for row in resumes) == 4
    for row in resumes:
        assert (root / "source" / f"{row['id'].lower()}.txt").is_file()
        assert row["email"].endswith("@example.com")
        asset = root / "resumes" / row["file_name"]
        assert asset.is_file()
        data = asset.read_bytes()
        if row["format"] in {"digital_pdf", "scanned_pdf"}:
            assert data.startswith(b"%PDF-")
        if row["format"] == "digital_pdf":
            assert b"/Subtype /Image" not in data
        if row["format"] == "scanned_pdf":
            assert b"/Subtype /Image" in data
            page_stream = data.split(b"stream\\n", 1)[1].split(b"\\nendstream", 1)[0]
            assert b"BT" not in page_stream and b" Tj" not in page_stream
        if row["format"] == "two_column_docx":
            document = Document(asset)
            assert document.tables
            assert len(document.tables[0].columns) == 2


def test_golden_deterministic_field_accuracy_meets_definition_of_done():
    from backend.parsing.common import derive_fields

    root, expected, _ = _golden_data()
    true_positive = false_positive = false_negative = 0
    email_correct = experience_within_tolerance = 0

    for row in expected["resumes"]:
        text = (root / "source" / f"{row['id'].lower()}.txt").read_text(encoding="utf-8")
        actual = derive_fields(text, row["mock_entities"])
        wanted, found = set(row["skills"]), set(actual["skills"])
        true_positive += len(wanted & found)
        false_positive += len(found - wanted)
        false_negative += len(wanted - found)
        email_correct += actual["email"] == row["email"]
        years = actual["experience_years"]
        experience_within_tolerance += (
            years is not None and abs(years - row["experience_years"]) <= 1
        )

    precision = true_positive / (true_positive + false_positive)
    recall = true_positive / (true_positive + false_negative)
    assert precision >= 0.85
    assert recall >= 0.85
    assert email_correct >= 11
    assert experience_within_tolerance >= 10


def test_golden_job_rankings_match_human_labelled_top_candidate():
    from backend.scoring.scoring import score_candidate
    from backend.parsing.common import derive_fields

    root, expected, jobs = _golden_data()
    derived = {}
    for row in expected["resumes"]:
        text = (root / "source" / f"{row['id'].lower()}.txt").read_text(encoding="utf-8")
        fields = derive_fields(text, row["mock_entities"])
        derived[row["id"]] = fields

    for job in jobs["jobs"]:
        scored = []
        for row in expected["resumes"]:
            result = score_candidate(
                derived[row["id"]],
                {
                    "required_skills": job["required_skills"],
                    "jd_titles": job["jd_titles"],
                    "required_years": job["required_years"],
                    "threshold": 60,
                },
            )
            scored.append((result["score"], row["id"]))
        scored.sort(key=lambda item: (-item[0], item[1]))
        assert scored[0][1] == job["expected_top_candidate"], (job["id"], scored)
