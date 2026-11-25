"""Brief section 2, group C, measured offline (clean text + real DOCX, taxonomy fallback only).

The AWS run (real Textract OCR + Comprehend) is `tools/golden_eval.py --bucket ...`; this test guards against regressions.
"""
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import golden_eval as ge  # noqa: E402

pytestmark = pytest.mark.skipif(not (ge.GOLD / "labels").exists(), reason="golden fixtures not generated yet")


@pytest.fixture(scope="module")
def results():
    labels = ge.load_labels()
    parsed = ge.parse_offline(labels)
    return ge.evaluate(parsed, labels), ge.ranking(parsed), parsed, labels


def test_set_has_the_required_mix(results):
    labels = results[3]
    counts = {}
    for lab in labels.values():
        counts[lab["format"]] = counts.get(lab["format"], 0) + 1
    assert counts == {"digital_pdf": 4, "docx_two_column": 4, "scanned_pdf": 4}


def test_skill_recall_and_precision_at_least_85_percent(results):
    m = results[0]
    assert m["skill_recall"] >= 0.85 and m["skill_precision"] >= 0.85


def test_email_correct_in_at_least_11_of_12(results):
    assert results[0]["email_correct"] >= 11


def test_experience_within_one_year_in_at_least_10_of_12(results):
    assert results[0]["experience_within_1y"] >= 10


def test_correct_top_candidate_for_all_three_jds(results):
    rows = results[1]
    assert len(rows) == 3 and all(r["top_ok"] for r in rows)
    assert all(r["job_fields_ok"] for r in rows)  # JD parsing produced the expected required skills / titles / years


def test_scanned_pdfs_really_have_no_text_layer():
    pytest.importorskip("pypdf")
    from pypdf import PdfReader
    for f in (ge.GOLD / "resumes").glob("g*.pdf"):
        text = "".join(p.extract_text() or "" for p in PdfReader(f).pages).strip()
        label = ge.load_labels()[f.stem]
        assert (text == "") == (label["format"] == "scanned_pdf"), f.name


def test_smoke_set_composition():
    smoke = ge.ROOT / "fixtures/resumes"
    names = sorted(p.name for p in smoke.glob("*") if p.suffix in (".pdf", ".docx"))
    assert len(names) == 10 and "corrupt.pdf" in names and sum(n.endswith(".docx") for n in names) == 3
