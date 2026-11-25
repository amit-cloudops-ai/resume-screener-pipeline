"""Parse Lambda (A6). Trigger: SQS parse-queue (S3 events for resumes/{job_id}/...).

file -> text -> entities -> fields -> raw Comprehend JSON to S3 (audit) -> candidate row PARSED -> score message.
Logs IDs and error types only: never resume text, file names or personal data.
"""
import json
import logging

import comprehend_client as cc
import extract
import fields
from aws_io import get_deps
from botocore.exceptions import ClientError
from errors import PermanentError, TransientError, classify_client_error
from records import candidate_id_for, failed_job_item, parsed_candidate_attrs
from s3_events import iter_s3_objects, job_id_from_key

log = logging.getLogger()
log.setLevel(logging.INFO)

PREFIX = "resumes"


def _stage(name: str, fn):
    """Run one pipeline step; a permanent error is tagged with the failed_job.schema.json stage it came from."""
    try:
        return fn()
    except PermanentError as err:
        err.stage = err.stage or name
        raise


def process_resume(bucket: str, key: str, deps, today=None, sleep=None, clock=None) -> str:
    job_id = job_id_from_key(key, PREFIX)
    candidate_id = candidate_id_for(job_id, key)
    extra = {k: v for k, v in (("sleep", sleep), ("clock", clock)) if v}

    deps.store.set_candidate_status(job_id, candidate_id, "PARSING", key)
    text = _stage("TEXT_EXTRACT", lambda: extract.extract_text(bucket, key, s3=deps.s3, textract=deps.textract, **extra))
    raw = _stage("COMPREHEND", lambda: cc.detect_entities(text, deps.comprehend, deps.endpoint_arn))
    parsed = fields.parse_resume(text, cc.merge_entities(raw), today)

    parsed_key = f"parsed/{job_id}/{candidate_id}.json"
    try:
        deps.s3.put_object(Bucket=bucket, Key=parsed_key, ContentType="application/json",
                           Body=json.dumps({"comprehend": raw, "parsed": parsed}).encode("utf-8"))
    except ClientError as exc:
        raise classify_client_error(exc)

    deps.store.upsert_candidate(job_id, candidate_id, parsed_candidate_attrs(parsed, parsed_key, key))
    deps.send_score(job_id, candidate_id, "CANDIDATE_PARSED")
    log.info("parsed job=%s candidate=%s", job_id, candidate_id)
    return candidate_id


def _record_permanent_failure(key: str, err: PermanentError, deps, message_id=None) -> None:
    job_id = job_id_from_key(key, PREFIX)
    candidate_id = candidate_id_for(job_id, key)
    deps.store.put_failed_job(failed_job_item(
        job_id=job_id, stage=err.stage or "PARSE", s3_key=key, error_type=err.error_type,
        error_message=err.message, attempts=1, message_id=message_id))
    deps.store.set_candidate_status(job_id, candidate_id, "FAILED", key)
    log.warning("permanent failure job=%s candidate=%s type=%s", job_id, candidate_id, err.error_type)


def process_event(event: dict, deps, today=None, **kw) -> None:
    transient = 0
    for record in event.get("Records", []):
        for bucket, key in iter_s3_objects(record.get("body", "")):
            job_id = job_id_from_key(key, PREFIX)
            if not job_id:
                log.info("ignored an object outside resumes/<12-hex job id>/")
                continue  # not a resume object: acknowledge and ignore
            try:
                process_resume(bucket, key, deps, today, **kw)
            except PermanentError as err:
                _record_permanent_failure(key, err, deps, record.get("messageId"))  # retrying would not help: acknowledge
            except Exception as err:  # transient or unexpected: let SQS retry (writes are idempotent)
                transient += 1
                log.error("transient failure job=%s candidate=%s type=%s", job_id, candidate_id_for(job_id, key), type(err).__name__)
    if transient:
        raise TransientError(f"{transient} object(s) failed and will be retried")


def handler(event, context=None):
    process_event(event, get_deps())
