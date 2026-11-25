"""Builds the DynamoDB items Part A writes. Field names and values follow contracts/*.schema.json (FROZEN).

If a contract changes, change it HERE (single place) and run tests/test_contracts.py, which validates these
builders and the rows the handlers really write against the real schemas. Never loosen a schema.
"""
import hashlib
from datetime import datetime, timezone
from decimal import Decimal

import config


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def candidate_id_for(job_id: str, s3_key: str) -> str:
    """Brief section 6: first 16 hex chars of SHA-256 of job_id + '/' + s3_key (schema: ^[0-9a-f]{16}$)."""
    return hashlib.sha256(f"{job_id}/{s3_key}".encode("utf-8")).hexdigest()[:16]


def to_dynamo(value):
    """boto3's DynamoDB resource rejects float; convert recursively."""
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: to_dynamo(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_dynamo(v) for v in value]
    return value


def candidate_base(source_key: str) -> dict:
    """candidate.schema.json requires source_key and file_name on every candidate row."""
    return {"source_key": source_key, "file_name": source_key.rsplit("/", 1)[-1]}


def parsed_candidate_attrs(fields: dict, parsed_s3_key: str, source_key: str) -> dict:
    """Attributes Part A sets when a resume reaches PARSED (score, decision and email fields belong to Part B / the recruiter)."""
    return {
        **candidate_base(source_key),
        "status": "PARSED",
        "name": fields["name"],
        "email": fields["email"],
        "skills": fields["skills"],
        "employers": fields["employers"],
        "titles": fields["titles"],
        "experience_years": fields["experience_years"],
        "parsed_s3_key": parsed_s3_key,
        "parser_version": config.PARSER_VERSION,
    }


def failed_id_for(stage: str, ident: str) -> str:
    """Deterministic: the same failure of the same file is one row, however many times it is delivered or re-uploaded."""
    return hashlib.sha256(f"{stage}/{ident}".encode("utf-8")).hexdigest()[:16]


def failed_job_item(*, job_id, stage, s3_key, error_type, error_message, attempts, message_id=None, candidate_id=None) -> dict:
    """failed_job.schema.json (additionalProperties false). error_message must NEVER contain resume text or personal data.
    candidate_id is only used to build a stable failed_id when there is no s3_key (it is not stored)."""
    ident = s3_key or candidate_id or message_id or job_id or ""
    return {
        "failed_id": failed_id_for(stage, ident),
        "job_id": job_id or "unknown",
        "stage": stage,
        "s3_key": s3_key or "",
        "error_type": error_type,
        "error_message": (error_message or "")[:300],
        "attempts": attempts,
        "message_id": message_id,
        "status": "OPEN",
        "created_at": now_iso(),
    }
