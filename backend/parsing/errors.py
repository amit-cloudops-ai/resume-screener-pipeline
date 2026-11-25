"""Error types and the error policy from brief section 4.

Permanent errors  -> write a failed_jobs row, mark the candidate FAILED, acknowledge the message.
Transient errors  -> raise, so SQS retries; after the max attempts the DLQ consumer writes the row.
"""

UNSUPPORTED_TYPE = "UNSUPPORTED_TYPE"
CORRUPT_FILE = "CORRUPT_FILE"
EMPTY_TEXT = "EMPTY_TEXT"
JD_NO_SKILLS = "JD_NO_SKILLS"
TRANSIENT_EXHAUSTED = "TRANSIENT_EXHAUSTED"
UNKNOWN = "UNKNOWN"


class PermanentError(Exception):
    def __init__(self, error_type: str, message: str = ""):
        super().__init__(message or error_type)
        self.error_type = error_type
        self.message = message or error_type
        self.stage = None  # set by the handler: TEXT_EXTRACT / COMPREHEND / JD_PARSE ...


class TransientError(Exception):
    pass


# AWS error codes that mean "retrying will not help".
_PERMANENT_CODES = {
    "UnsupportedDocumentException": UNSUPPORTED_TYPE,
    "BadDocumentException": CORRUPT_FILE,
    "DocumentTooLargeException": CORRUPT_FILE,
    "InvalidS3ObjectException": CORRUPT_FILE,
    "InvalidParameterException": CORRUPT_FILE,
}


def classify_client_error(exc: Exception) -> Exception:
    """Turn a botocore ClientError into PermanentError or TransientError (never leaks message text)."""
    code = getattr(exc, "response", {}).get("Error", {}).get("Code", "") or type(exc).__name__
    if code in _PERMANENT_CODES:
        return PermanentError(_PERMANENT_CODES[code], f"AWS error: {code}")
    return TransientError(f"AWS error: {code}")
