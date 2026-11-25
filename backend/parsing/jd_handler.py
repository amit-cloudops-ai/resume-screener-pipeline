"""JD-parse Lambda (A7). Trigger: SQS jd-queue (S3 events for jd/{job_id}/...).

Reads the JD, stores required_skills / jd_titles / required_years on the job, sets JD_PARSED, then asks for
scoring of candidates that already exist. Zero skills found => job FAILED with JD_NO_SKILLS.
"""
import logging
import re

import extract
import fields
import taxonomy as tx
from aws_io import get_deps
from errors import JD_NO_SKILLS, PermanentError, TransientError
from records import failed_job_item
from s3_events import iter_s3_objects, job_id_from_key

log = logging.getLogger()
log.setLevel(logging.INFO)

PREFIX = "jd"
_YEARS = re.compile(r"(\d{1,2})\s*(?:\+|plus)?(?:\s*(?:-|–|to)\s*\d{1,2})?\s*(?:years?|yrs?)", re.I)


def required_years(text: str) -> int:
    """First 'N years' on a line that mentions experience (lower bound of a range). 0 = no requirement stated."""
    for line in text.splitlines():
        if "experience" in line.lower():
            m = _YEARS.search(line)
            if m:
                return int(m.group(1))
    return 0


def jd_titles(text: str, job_title: str | None) -> list[str]:
    found = []
    if job_title:
        t = fields.normalize_title(job_title)
        if t:
            found.append(t)
    for line in [ln for ln in text.splitlines() if ln.strip()][:15]:  # the role is named near the top
        found += fields.titles_in_line(line)
    return list(dict.fromkeys(found))


def process_jd(bucket: str, key: str, deps, **kw) -> None:
    job_id = job_id_from_key(key, PREFIX)
    text = extract.extract_text(bucket, key, s3=deps.s3, textract=deps.textract, allowed=extract.JD_TYPES, **kw)
    skills = fields.derive_skills(text)
    if not skills:
        raise PermanentError(JD_NO_SKILLS, "No known skills were found in the job description")
    job = deps.store.get_job(job_id) or {}
    deps.store.update_job(job_id, {
        "required_skills": skills,
        "jd_titles": jd_titles(text, job.get("title")),
        "required_years": required_years(text),
        "status": "JD_PARSED",
    })
    for candidate_id in deps.store.candidates_for_job(job_id):
        deps.send_score(job_id, candidate_id, "JD_READY")
    log.info("jd parsed job=%s skills=%d", job_id, len(skills))


def process_event(event: dict, deps, **kw) -> None:
    transient = 0
    for record in event.get("Records", []):
        for bucket, key in iter_s3_objects(record.get("body", "")):
            job_id = job_id_from_key(key, PREFIX)
            if not job_id:
                continue
            try:
                process_jd(bucket, key, deps, **kw)
            except PermanentError as err:
                deps.store.put_failed_job(failed_job_item(job_id=job_id, stage="JD_PARSE", s3_key=key, error_type=err.error_type,
                                                          error_message=err.message, attempts=1, message_id=record.get("messageId")))
                deps.store.update_job(job_id, {"status": "FAILED"})
                log.warning("jd failure job=%s type=%s", job_id, err.error_type)
            except Exception as err:
                transient += 1
                log.error("jd transient failure job=%s type=%s", job_id, type(err).__name__)
    if transient:
        raise TransientError(f"{transient} job description(s) failed and will be retried")


def handler(event, context=None):
    process_event(event, get_deps())
