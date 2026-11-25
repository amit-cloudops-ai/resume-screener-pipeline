"""Text extraction (A3). PDF -> Textract async (start + poll, 100 s cap). DOCX -> python-docx. TXT -> decode.

Anything else is a permanent UNSUPPORTED_TYPE error. No AWS clients are created here; they are passed in.
"""
import io
import time
import zipfile
from pathlib import PurePosixPath

from botocore.exceptions import ClientError

import config
from errors import CORRUPT_FILE, EMPTY_TEXT, UNSUPPORTED_TYPE, PermanentError, TransientError, classify_client_error

RESUME_TYPES = {".pdf", ".docx"}
JD_TYPES = {".pdf", ".docx", ".txt"}


def extension(key: str) -> str:
    return PurePosixPath(key).suffix.lower()


def _tidy(text: str) -> str:
    text = text.replace("\u00a0", " ").replace("\r\n", "\n").replace("\r", "\n")
    lines = [ln.rstrip() for ln in text.split("\n")]
    out, blank = [], 0
    for ln in lines:
        blank = blank + 1 if not ln.strip() else 0
        if blank <= 1:
            out.append(ln)
    return "\n".join(out).strip()


def _download(s3, bucket: str, key: str) -> bytes:
    try:
        return s3.get_object(Bucket=bucket, Key=key)["Body"].read()
    except ClientError as exc:
        raise classify_client_error(exc)


def docx_text(data: bytes) -> str:
    """Read body paragraphs AND table cells in document order (two-column resumes are usually tables)."""
    from docx import Document
    from docx.oxml.ns import qn
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    try:
        doc = Document(io.BytesIO(data))
    except (zipfile.BadZipFile, KeyError, ValueError, Exception) as exc:  # corrupt / not a real docx
        raise PermanentError(CORRUPT_FILE, f"Could not open DOCX ({type(exc).__name__})")

    def walk(element, parent):
        for child in element.iterchildren():
            if child.tag == qn("w:p"):
                yield Paragraph(child, parent).text
            elif child.tag == qn("w:tbl"):
                for row in Table(child, parent).rows:
                    seen = []
                    for cell in row.cells:
                        if any(cell._tc is s for s in seen):  # merged cells repeat
                            continue
                        seen.append(cell._tc)
                        yield from walk(cell._tc, cell)

    return "\n".join(walk(doc.element.body, doc))


def _textract_pdf(bucket: str, key: str, textract, sleep, clock) -> str:
    try:
        job_id = textract.start_document_text_detection(
            DocumentLocation={"S3Object": {"Bucket": bucket, "Name": key}}
        )["JobId"]
    except ClientError as exc:
        raise classify_client_error(exc)

    started, lines, token = clock(), [], None
    while True:
        kwargs = {"JobId": job_id}
        if token:
            kwargs["NextToken"] = token
        try:
            resp = textract.get_document_text_detection(**kwargs)
        except ClientError as exc:
            raise classify_client_error(exc)
        status = resp.get("JobStatus")
        if status == "IN_PROGRESS":
            if clock() - started > config.TEXTRACT_POLL_CAP_SECONDS:
                raise TransientError("Textract job did not finish within the time cap")
            sleep(config.TEXTRACT_POLL_INTERVAL_SECONDS)
            continue
        if status == "FAILED":
            raise PermanentError(CORRUPT_FILE, "Textract could not read the document")
        lines += [b["Text"] for b in resp.get("Blocks", []) if b.get("BlockType") == "LINE"]
        token = resp.get("NextToken")
        if not token:
            return "\n".join(lines)


def extract_text(bucket, key, *, s3, textract, allowed=RESUME_TYPES, sleep=time.sleep, clock=time.monotonic) -> str:
    ext = extension(key)
    if ext not in allowed:
        raise PermanentError(UNSUPPORTED_TYPE, f"File type '{ext or 'none'}' is not supported")
    if ext == ".pdf":
        text = _textract_pdf(bucket, key, textract, sleep, clock)
    elif ext == ".docx":
        text = docx_text(_download(s3, bucket, key))
    else:
        text = _download(s3, bucket, key).decode("utf-8", errors="replace")
    text = _tidy(text)
    if not text:
        raise PermanentError(EMPTY_TEXT, "No readable text found in the file")
    return text
