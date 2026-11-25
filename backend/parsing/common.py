"""Shared parsing primitives for the resume and job-description pipelines."""
from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from urllib.parse import unquote_plus

from docx import Document

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10,
    "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}
DATE_RANGE_RE = re.compile(
    r"\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t|tember)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)\s+(19\d{2}|20\d{2})\s*(?:-|–|—|to)\s*"
    r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t|tember)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?|Present|Current)?\s*(19\d{2}|20\d{2})?",
    re.I,
)
YEAR_RANGE_RE = re.compile(r"\b(19\d{2}|20\d{2})\s*(?:-|–|—|to)\s*(Present|Current|19\d{2}|20\d{2})\b", re.I)
YEARS_PLUS_RE = re.compile(r"\b(\d+(?:\.\d+)?)\s*\+\s*(?:years|year|yrs|yr)\b", re.I)


class PermanentDocumentError(Exception):
    def __init__(self, error_type: str, message: str):
        super().__init__(message)
        self.error_type = error_type


class TransientProcessingError(Exception):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def candidate_id_for(job_id: str, s3_key: str) -> str:
    return hashlib.sha256(f"{job_id}/{s3_key}".encode("utf-8")).hexdigest()[:16]


def parse_s3_notification(body: str) -> tuple[str, str]:
    try:
        event = json.loads(body)
    except (TypeError, json.JSONDecodeError) as exc:
        raise PermanentDocumentError("CORRUPT_FILE", "Invalid S3 notification JSON") from exc
    records = event.get("Records") if isinstance(event, dict) else None
    if not isinstance(records, list) or not records or not isinstance(records[0], dict):
        raise PermanentDocumentError("CORRUPT_FILE", "S3 notification has no Records entry")
    data = records[0].get("s3") or {}
    bucket = (data.get("bucket") or {}).get("name")
    key = (data.get("object") or {}).get("key")
    if not isinstance(bucket, str) or not isinstance(key, str):
        raise PermanentDocumentError("CORRUPT_FILE", "S3 notification is missing bucket or key")
    return bucket, unquote_plus(key)


def split_utf8(text: str, limit: int = 4800) -> list[str]:
    """Split on UTF-8 codepoint boundaries without changing the source text."""
    chunks, current, used = [], [], 0
    for char in text:
        size = len(char.encode("utf-8"))
        if size > limit:
            raise ValueError("Text chunk limit is smaller than one UTF-8 codepoint")
        if used + size > limit:
            chunks.append("".join(current))
            current, used = [], 0
        current.append(char)
        used += size
    if current:
        chunks.append("".join(current))
    return chunks or [""]



def _docx_text(data: bytes) -> str:
    try:
        document = Document(BytesIO(data))
    except Exception as exc:
        raise PermanentDocumentError("CORRUPT_FILE", "DOCX document could not be opened") from exc
    parts = [p.text.strip() for p in document.paragraphs if p.text.strip()]
    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                parts.append(" | ".join(cells))
    result = "\n".join(parts).strip()
    if not result:
        raise PermanentDocumentError("EMPTY_TEXT", "Document contains no extractable text")
    return result


def _pdf_text(bucket: str, key: str, textract, job_id: str, context=None) -> str:
    # ClientRequestToken makes retries idempotent: the same object returns the same Textract JobId.
    token = hashlib.sha256(f"{job_id}/{key}".encode("utf-8")).hexdigest()
    try:
        started = textract.start_document_text_detection(
            DocumentLocation={"S3Object": {"Bucket": bucket, "Name": key}},
            ClientRequestToken=token,
        )
        job = started["JobId"]
        deadline = time.monotonic() + 90
        if context and hasattr(context, "get_remaining_time_in_millis"):
            deadline = time.monotonic() + max(5, (context.get_remaining_time_in_millis() - 10000) / 1000)
        delay, status = 1.0, "IN_PROGRESS"
        while time.monotonic() < deadline:
            response = textract.get_document_text_detection(JobId=job, MaxResults=1000)
            status = response.get("JobStatus", "IN_PROGRESS")
            if status != "IN_PROGRESS":
                break
            time.sleep(delay)
            delay = min(delay * 1.6, 5.0)
        if status == "IN_PROGRESS":
            raise TransientProcessingError("Textract job exceeded this Lambda execution window")
        if status != "SUCCEEDED":
            raise PermanentDocumentError("CORRUPT_FILE", "Textract could not read this PDF")
        lines, token = [], None
        while True:
            args = {"JobId": job, "MaxResults": 1000}
            if token:
                args["NextToken"] = token
            page = textract.get_document_text_detection(**args)
            lines.extend(
                block["Text"] for block in page.get("Blocks", [])
                if block.get("BlockType") == "LINE" and isinstance(block.get("Text"), str)
            )
            token = page.get("NextToken")
            if not token:
                break
        result = "\n".join(lines).strip()
        if not result:
            raise PermanentDocumentError("EMPTY_TEXT", "PDF contains no extractable text")
        return result
    except (PermanentDocumentError, TransientProcessingError):
        raise
    except Exception as exc:
        raise TransientProcessingError("Textract request failed") from exc


def extract_document_text(bucket: str, key: str, s3, textract, job_id: str, context=None, allow_txt=False) -> str:
    extension = Path(key).suffix.lower()
    allowed = {".pdf", ".docx"} | ({".txt"} if allow_txt else set())
    if extension not in allowed:
        raise PermanentDocumentError("UNSUPPORTED_TYPE", "Unsupported document type")
    try:
        size = int(s3.head_object(Bucket=bucket, Key=key).get("ContentLength", 0))
    except Exception as exc:
        raise TransientProcessingError("Could not inspect uploaded object") from exc
    if size > MAX_UPLOAD_BYTES:
        raise PermanentDocumentError("UNSUPPORTED_TYPE", "Uploaded file exceeds 5 MiB")
    if extension == ".pdf":
        return _pdf_text(bucket, key, textract, job_id, context)
    try:
        data = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
    except Exception as exc:
        raise TransientProcessingError("Could not download uploaded object") from exc
    if extension == ".docx":
        return _docx_text(data)
    try:
        text = data.decode("utf-8-sig").strip()
    except UnicodeDecodeError as exc:
        raise PermanentDocumentError("CORRUPT_FILE", "JD text file is not valid UTF-8") from exc
    if not text:
        raise PermanentDocumentError("EMPTY_TEXT", "Document contains no extractable text")
    return text



def _taxonomy() -> dict:
    path = Path(__file__).with_name("skills_taxonomy.json")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError("skills_taxonomy.json is missing or invalid") from exc
    aliases = {}
    for canonical, terms in data.items():
        aliases[canonical.casefold()] = canonical.casefold()
        for term in terms:
            aliases[term.casefold()] = canonical.casefold()
    return aliases


def normalise_skills(text: str, entities: dict | None = None) -> list[str]:
    """Extract canonical skills from the controlled taxonomy, longest aliases first."""
    aliases, found, lowered = _taxonomy(), set(), text.casefold()
    for alias, canonical in sorted(aliases.items(), key=lambda item: (-len(item[0]), item[0])):
        pattern = r"(?<![a-z0-9+#.])" + re.escape(alias) + r"(?![a-z0-9+#.])"
        if re.search(pattern, lowered):
            found.add(canonical)
    return sorted(found)


def experience_years(text: str):
    intervals = []
    now = datetime.now(timezone.utc)
    for match in DATE_RANGE_RE.finditer(text):
        start_year = int(match.group(2))
        start = start_year * 12 + MONTHS[match.group(1).casefold()[:3]] - 1
        end_month_text, end_year_text = match.group(3), match.group(4)
        if not end_month_text:
            continue
        if end_month_text.casefold() in {"present", "current"}:
            end = now.year * 12 + now.month - 1
        else:
            end_year = int(end_year_text) if end_year_text else start_year
            end = end_year * 12 + MONTHS[end_month_text.casefold()[:3]] - 1
        if end >= start:
            intervals.append((start, end))

    # Year-only ranges are common in resumes; count full calendar years.
    for match in YEAR_RANGE_RE.finditer(text):
        start_year = int(match.group(1))
        end_text = match.group(2)
        start = start_year * 12
        end = (
            now.year * 12 + now.month - 1
            if end_text.casefold() in {"present", "current"}
            else int(end_text) * 12 + 11
        )
        if end >= start:
            intervals.append((start, end))

    if not intervals:
        # Resume summaries often state total experience without dated roles.
        # Use this fallback only when no explicit employment intervals were found.
        fallback = YEARS_PLUS_RE.search(text)
        if fallback:
            return round(min(float(fallback.group(1)), 40), 1)
        return None
    intervals.sort()
    total, left, right = 0, intervals[0][0], intervals[0][1]
    for start, end in intervals[1:]:
        if start <= right + 1:
            right = max(right, end)
        else:
            total += right - left + 1
            left, right = start, end
    total += right - left + 1
    return round(min(total / 12, 40), 1)


JOB_TITLE_RE = re.compile(
    r"\b(?:senior|sr\.?|junior|jr\.?|lead|principal|staff|associate|mid[- ]level)?\s*"
    r"(?:devops|platform|cloud|site reliability|sre|software|backend|back-end|"
    r"frontend|front-end|full[- ]stack|data|ml|machine learning|security|network|"
    r"systems|infrastructure|qa|test|database|application)\s+"
    r"(?:engineer|developer|architect|administrator|analyst|scientist|consultant|"
    r"specialist|manager)\b", re.I
)
PERSON_LINE_RE = re.compile(r"(?m)^\s*([A-Z][A-Za-z'’-]+(?:\s+[A-Z][A-Za-z'’-]+){1,3})\s*$")
EMPLOYER_RE = re.compile(r"(?im)^\s*(?:at|company|employer)\s*:?\s*([A-Z][A-Za-z0-9&.,' -]{1,60})\s*$")


def derive_fields(text: str, entities: dict | None = None) -> dict:
    """Deterministic extraction; missing evidence remains null/empty."""
    email = EMAIL_RE.search(text)
    titles = sorted({m.group(0).strip().casefold() for m in JOB_TITLE_RE.finditer(text)})
    people = [m.group(1).strip() for m in PERSON_LINE_RE.finditer(text)]
    people = [p for p in people if p.casefold() not in {
        "professional summary", "work experience", "technical skills",
        "education details", "career objective", "personal information",
    }]
    employers = sorted({m.group(1).strip(" .,-") for m in EMPLOYER_RE.finditer(text)})
    return {
        "name": people[0] if people else None,
        "email": email.group(0).casefold() if email else None,
        "skills": normalise_skills(text),
        "employers": employers,
        "titles": titles,
        "experience_years": experience_years(text),
    }
