"""DLQ consumer (A8). Trigger: the parse, jd and score dead-letter queues.

Contract (sqs_messages.md): the original message body is unchanged; stage comes from the DLQ source ARN
(parse-dlq -> PARSE, jd-dlq -> JD_PARSE, score-dlq -> SCORE); s3_key / job_id come from the body.
Any message that arrives here exhausted its retries => one failed_jobs row (TRANSIENT_EXHAUSTED).
Never raises for a bad message: a DLQ consumer that fails would hide the very failure it records.
"""
import json
import logging

import config
from aws_io import get_deps
from errors import TRANSIENT_EXHAUSTED, UNKNOWN
from records import candidate_id_for, failed_job_item
from s3_events import iter_s3_objects, job_id_from_key

log = logging.getLogger()
log.setLevel(logging.INFO)

_STAGES = (("score", "SCORE"), ("jd", "JD_PARSE"), ("parse", "PARSE"))


def stage_from_arn(arn: str) -> str:
    name = (arn or "").rsplit(":", 1)[-1].lower()
    return next((stage for needle, stage in _STAGES if needle in name), "UNKNOWN")


def describe(record: dict):
    """-> (job_id, s3_key, candidate_id) as far as the message body tells us."""
    for _bucket, key in iter_s3_objects(record.get("body", "")):
        for prefix in ("resumes", "jd"):
            job_id = job_id_from_key(key, prefix)
            if job_id:
                return job_id, key, (candidate_id_for(job_id, key) if prefix == "resumes" else None)
    try:
        body = json.loads(record.get("body", ""))
        if isinstance(body, dict) and body.get("job_id"):  # a score-queue message
            return body["job_id"], None, body.get("candidate_id")
    except (TypeError, ValueError):
        pass
    return None, None, None


def process_event(event: dict, deps) -> int:
    written = 0
    for record in event.get("Records", []):
        stage = stage_from_arn(record.get("eventSourceARN", ""))
        try:
            job_id, s3_key, candidate_id = describe(record)
            if not s3_key and job_id and candidate_id:  # score message: take the file from the candidate row
                s3_key = (deps.store.get_candidate(job_id, candidate_id) or {}).get("source_key")
            deps.store.put_failed_job(failed_job_item(
                job_id=job_id, stage=stage, s3_key=s3_key, candidate_id=candidate_id,
                error_type=TRANSIENT_EXHAUSTED if job_id else UNKNOWN,
                error_message="Message moved to the dead-letter queue after repeated failures",
                attempts=config.MAX_RECEIVE_COUNT, message_id=record.get("messageId")))
            if stage == "PARSE" and job_id and candidate_id and s3_key:
                deps.store.set_candidate_status(job_id, candidate_id, "FAILED", s3_key)
            elif stage == "JD_PARSE" and job_id:
                deps.store.update_job(job_id, {"status": "FAILED"})
            written += 1
            log.warning("dlq stage=%s job=%s", stage, job_id)
        except Exception as err:  # keep going; the message stays in the DLQ for manual inspection
            log.error("could not record dlq message type=%s", type(err).__name__)
    return written


def handler(event, context=None):
    process_event(event, get_deps())
