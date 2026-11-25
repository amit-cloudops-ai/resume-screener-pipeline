"""Runtime configuration.

Table / queue names follow contracts/*.schema.json (rs-<stage>-candidates, -jobs, -failed-jobs, -score-queue).
ASSUMPTION - CHECK AGAINST infra/template.yaml: the environment variable NAMES below are not in the contracts.
Each can override the default; if the template uses different names, change them HERE only.
"""
import os

TEXTRACT_POLL_CAP_SECONDS = 100   # brief: "start and poll, 100 s cap"
TEXTRACT_POLL_INTERVAL_SECONDS = 3
MAX_RECEIVE_COUNT = 3             # brief: "retry 3x then DLQ"
MAX_EXPERIENCE_YEARS = 40         # brief section 7 (contract allows up to 60)
PARSER_VERSION = "A-1.0"          # candidate.schema.json: parser_version


def stage() -> str:
    return os.environ.get("STAGE", "dev")


def table_name(kind: str) -> str:
    """kind: candidates | jobs | failed_jobs"""
    env = {"candidates": "CANDIDATES_TABLE", "jobs": "JOBS_TABLE", "failed_jobs": "FAILED_JOBS_TABLE"}[kind]
    return os.environ.get(env) or f"rs-{stage()}-{kind.replace('_', '-')}"


def score_queue_name() -> str:
    return f"rs-{stage()}-score-queue"


def score_queue_url_env() -> str:
    return os.environ.get("SCORE_QUEUE_URL", "")


def comprehend_endpoint_arn() -> str:
    """Empty string = custom recogniser disabled; the taxonomy matcher is the guaranteed fallback."""
    return os.environ.get("COMPREHEND_ENDPOINT_ARN", "")
