import io

import pytest

pytest.importorskip("docx", reason="python-docx not installed")
from docx import Document  # noqa: E402

import extract
from errors import CORRUPT_FILE, EMPTY_TEXT, UNSUPPORTED_TYPE, PermanentError, TransientError
from fakes import FakeTextract


def run(key="resumes/j/a.pdf", textract=None, s3=None, **kw):
    return extract.extract_text("b", key, s3=s3, textract=textract or FakeTextract(), sleep=lambda s: None, **kw)


def test_pdf_goes_through_textract_and_joins_pages():
    t = FakeTextract(pages=[["Page one", "line"], ["Page two"]])
    assert run(textract=t) == "Page one\nline\nPage two"


def test_pdf_polls_until_finished():
    t = FakeTextract(statuses=["IN_PROGRESS", "IN_PROGRESS"])
    assert run(textract=t) == "Hello world" and t.calls == 3


def test_pdf_poll_cap_is_transient():
    clock = iter(range(0, 1000, 60))  # jumps 60 s per call
    t = FakeTextract(statuses=["IN_PROGRESS"] * 10)
    with pytest.raises(TransientError):
        extract.extract_text("b", "resumes/j/a.pdf", s3=None, textract=t, sleep=lambda s: None, clock=lambda: next(clock))


def test_failed_textract_job_is_permanent_corrupt():
    with pytest.raises(PermanentError) as e:
        run(textract=FakeTextract(fail=True))
    assert e.value.error_type == CORRUPT_FILE


@pytest.mark.parametrize("code,expected", [("UnsupportedDocumentException", UNSUPPORTED_TYPE), ("BadDocumentException", CORRUPT_FILE)])
def test_textract_permanent_codes(code, expected):
    with pytest.raises(PermanentError) as e:
        run(textract=FakeTextract(start_error=code))
    assert e.value.error_type == expected


@pytest.mark.parametrize("code", ["ThrottlingException", "ProvisionedThroughputExceededException", "InternalServerError"])
def test_textract_throttling_is_transient(code):
    with pytest.raises(TransientError):
        run(textract=FakeTextract(start_error=code))


def test_unsupported_extension_is_permanent():
    with pytest.raises(PermanentError) as e:
        run(key="resumes/j/a.exe")
    assert e.value.error_type == UNSUPPORTED_TYPE
    with pytest.raises(PermanentError):
        run(key="resumes/j/a.txt")  # .txt is allowed for JDs only


def test_empty_pdf_text_is_permanent():
    with pytest.raises(PermanentError) as e:
        run(textract=FakeTextract(pages=[[""]]))
    assert e.value.error_type == EMPTY_TEXT


def _docx_bytes(build):
    doc = Document()
    build(doc)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


class S3Stub:
    def __init__(self, data):
        self.data = data

    def get_object(self, Bucket, Key):
        return {"Body": io.BytesIO(self.data)}


def test_docx_reads_paragraphs_and_two_column_tables_in_order():
    def build(doc):
        doc.add_paragraph("Header line")
        table = doc.add_table(rows=1, cols=2)
        table.cell(0, 0).text = "LEFT column skills"
        table.cell(0, 1).text = "RIGHT column experience"
        doc.add_paragraph("Footer line")

    text = run(key="resumes/j/a.docx", s3=S3Stub(_docx_bytes(build)))
    assert text.index("Header") < text.index("LEFT") < text.index("RIGHT") < text.index("Footer")


def test_docx_merged_cells_not_repeated():
    def build(doc):
        t = doc.add_table(rows=1, cols=2)
        t.cell(0, 0).merge(t.cell(0, 1)).text = "merged once"

    assert run(key="resumes/j/a.docx", s3=S3Stub(_docx_bytes(build))).count("merged once") == 1


def test_corrupt_docx_is_permanent():
    with pytest.raises(PermanentError) as e:
        run(key="resumes/j/a.docx", s3=S3Stub(b"this is not a zip"))
    assert e.value.error_type == CORRUPT_FILE


def test_txt_allowed_for_jd():
    out = extract.extract_text("b", "jd/j/jd.txt", s3=S3Stub(b"Need python\n\n\n\nand aws"), textract=None, allowed=extract.JD_TYPES)
    assert out == "Need python\n\nand aws"
