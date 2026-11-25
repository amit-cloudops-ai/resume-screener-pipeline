"""Reads S3 event notifications delivered through SQS."""
import json
import re
from urllib.parse import unquote_plus

JOB_ID = re.compile(r"^[0-9a-f]{12}$")


def iter_s3_objects(body: str):
    """Yield (bucket, key). Malformed bodies and S3 test events yield nothing (they are acknowledged)."""
    try:
        data = json.loads(body)
    except (TypeError, ValueError):
        return
    for rec in data.get("Records", []) if isinstance(data, dict) else []:
        s3 = rec.get("s3") or {}
        bucket, key = (s3.get("bucket") or {}).get("name"), (s3.get("object") or {}).get("key")
        if bucket and key:
            yield bucket, unquote_plus(key)


def job_id_from_key(key: str, prefix: str):
    """'resumes/{job_id}/file.pdf' -> job_id, or None if the key does not look like that."""
    parts = key.split("/")
    return parts[1] if len(parts) >= 3 and parts[0] == prefix and JOB_ID.match(parts[1]) else None
