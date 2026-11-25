"""Repository-side validation for the reviewed synthetic extraction examples."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = {
    "R01": "deterministic-digital-pdf.json",
    "R05": "deterministic-two-column-docx.json",
    "R09": "deterministic-scanned-pdf.json",
}


def test_reviewed_samples_are_explicitly_synthetic_and_match_golden_labels():
    expected = json.loads((ROOT / "fixtures/golden/expected.json").read_text(encoding="utf-8"))
    by_id = {item["id"]: item for item in expected["resumes"]}
    assert set(SAMPLES) <= set(by_id)

    for resume_id, filename in SAMPLES.items():
        sample = json.loads((ROOT / "docs/samples" / filename).read_text(encoding="utf-8"))
        assert sample["evidence_class"] == "SYNTHETIC_MOCK"
        assert sample["source_fixture"]["resume_id"] == resume_id
        assert sample["parser_output"] == {
            key: by_id[resume_id][key]
            for key in ("name", "email", "skills", "employers", "titles", "experience_years")
        }
        assert sample["extraction_engine"] == "deterministic-taxonomy-regex-date-v1"
        assert "comprehend" not in sample


def test_scanned_sample_does_not_claim_live_textract_output():
    sample = json.loads((ROOT / "docs/samples/deterministic-scanned-pdf.json").read_text(encoding="utf-8"))
    assert sample["textract"]["evidence_class"] == "SYNTHETIC_EXPECTED_TEXT"
    assert "not Textract Blocks" in sample["textract"]["note"]
