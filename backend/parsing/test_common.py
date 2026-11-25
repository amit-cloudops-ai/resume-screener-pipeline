"""Unit tests for shared Part A extraction and NLP helpers."""
import json
from io import BytesIO

from docx import Document

from backend.parsing.common import (
    PermanentDocumentError,
    candidate_id_for,
    derive_fields,
    experience_years,
    parse_s3_notification,
    split_utf8,
)


def test_s3_notification_decodes_object_key():
    body = json.dumps({"Records": [{"s3": {"bucket": {"name": "uploads"}, "object": {"key": "resumes%2Fjob%2FJohn+Resume.pdf"}}}]})
    assert parse_s3_notification(body) == ("uploads", "resumes/job/John Resume.pdf")


def test_s3_notification_rejects_invalid_shape():
    try:
        parse_s3_notification('{"Records":[]}')
    except PermanentDocumentError as exc:
        assert exc.error_type == "CORRUPT_FILE"
    else:
        raise AssertionError("expected permanent document error")


def test_candidate_id_is_deterministic_and_16_hex():
    first = candidate_id_for("a1b2c3d4e5f6", "resumes/a1b2c3d4e5f6/a.pdf")
    assert first == candidate_id_for("a1b2c3d4e5f6", "resumes/a1b2c3d4e5f6/a.pdf")
    assert len(first) == 16
    assert all(char in "0123456789abcdef" for char in first)


def test_taxonomy_finds_aliases_and_canonical_skills():
    fields = derive_fields(
        "Built k8s platforms on AWS, Docker, Terraform and Python.",
        {"standard": [], "custom": []},
    )
    assert fields["skills"] == ["aws", "docker", "kubernetes", "python", "terraform"]


def test_entities_derive_name_email_employers_and_titles():
    fields = derive_fields(
        "Priya Sharma\nContact: PRIYA@example.com.\\nPlatform Engineer\\nCompany: Acme Systems\\nJan 2020 - Dec 2022",
        {
            "standard": [],
            "custom": [],
        },
    )
    assert fields["name"] == "Priya Sharma"
    assert fields["email"] == "priya@example.com"
    assert fields["employers"] == ["Acme Systems"]
    assert fields["titles"] == ["platform engineer"]
    assert fields["experience_years"] == 3.0


def test_experience_unions_overlapping_periods():
    assert experience_years("Jan 2020 - Dec 2021\nJan 2021 - Dec 2022") == 3.0


def test_experience_unknown_is_null():
    assert experience_years("Worked at Acme Systems for several years") is None


def test_docx_paragraph_and_table_content_is_preserved():
    from backend.parsing.common import _docx_text
    document = Document()
    document.add_paragraph("Platform Engineer")
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "AWS"
    table.cell(0, 1).text = "Kubernetes"
    output = BytesIO()
    document.save(output)
    text = _docx_text(output.getvalue())
    assert "Platform Engineer" in text
    assert "AWS | Kubernetes" in text


def test_pdf_textract_async_job_polls_and_reads_all_pages(monkeypatch):
    from backend.parsing.common import _pdf_text

    class FakeTextract:
        def __init__(self):
            self.polls = 0
            self.tokens = []

        def start_document_text_detection(self, **kwargs):
            self.start_args = kwargs
            return {"JobId": "textract-job-1"}

        def get_document_text_detection(self, **kwargs):
            self.tokens.append(kwargs.get("NextToken"))
            if self.polls == 0:
                self.polls += 1
                return {"JobStatus": "IN_PROGRESS"}
            if self.polls == 1:
                self.polls += 1
                return {"JobStatus": "SUCCEEDED"}
            if kwargs.get("NextToken") == "page-2":
                return {"JobStatus": "SUCCEEDED", "Blocks": [
                    {"BlockType": "LINE", "Text": "Second page"},
                ]}
            return {
                "JobStatus": "SUCCEEDED",
                "Blocks": [{"BlockType": "LINE", "Text": "First page"}],
                "NextToken": "page-2",
            }

    monkeypatch.setattr("backend.parsing.common.time.sleep", lambda _: None)
    textract = FakeTextract()
    assert _pdf_text("uploads", "resumes/job/resume.pdf", textract, "job") == "First page\nSecond page"
    assert len(textract.start_args["ClientRequestToken"]) == 64
    assert textract.tokens == [None, None, None, "page-2"]


def test_experience_supports_year_only_ranges():
    assert experience_years("Experience: 2018 - 2020") == 3.0


def test_year_only_ranges_are_unioned_without_double_counting():
    assert experience_years("2018 - 2020\n2019 - 2021") == 4.0
