"""Validate fixtures against frozen JSON schemas and validate the OpenAPI contract."""
import json
import pathlib
import sys

import yaml
from jsonschema import Draft7Validator
from openapi_spec_validator import validate as validate_openapi

ROOT = pathlib.Path(__file__).resolve().parent.parent
ERRORS = []


def check(schema_file, fixtures_glob):
    try:
        schema = json.loads((ROOT / "contracts" / schema_file).read_text())
        Draft7Validator.check_schema(schema)
    except Exception as exc:  # noqa: BLE001
        ERRORS.append(f"contracts/{schema_file}: unreadable or invalid schema: {exc}")
        return
    validator = Draft7Validator(schema)
    files = sorted((ROOT / "fixtures").glob(fixtures_glob))
    if not files:
        ERRORS.append(f"no fixtures found for {fixtures_glob}")
    for f in files:
        try:
            payload = json.loads(f.read_text())
        except json.JSONDecodeError as exc:
            ERRORS.append(f"{f.relative_to(ROOT)}: invalid JSON: {exc}")
            continue
        for e in validator.iter_errors(payload):
            ERRORS.append(f"{f.relative_to(ROOT)}: {e.message}")


check("job.schema.json", "jobs/*.json")
check("candidate.schema.json", "candidates/*.json")
check("failed_job.schema.json", "failed_jobs/*.json")

api = ROOT / "contracts" / "openapi.yaml"
try:
    spec = yaml.safe_load(api.read_text()) or {}
except Exception as exc:  # noqa: BLE001
    spec = {}
    ERRORS.append(f"openapi.yaml unreadable: {exc}")
try:
    validate_openapi(spec, base_uri=api.as_uri())
except Exception as exc:  # noqa: BLE001
    ERRORS.append(f"openapi.yaml invalid (or a referenced schema is broken): {exc}")

REQUIRED = [
    "/jobs", "/jobs/{job_id}", "/jobs/{job_id}/uploads", "/jobs/{job_id}/candidates",
    "/jobs/{job_id}/candidates/{candidate_id}", "/jobs/{job_id}/candidates/{candidate_id}/decision",
    "/jobs/{job_id}/shortlist.csv", "/failed-jobs", "/failed-jobs/{failed_id}/retry",
]
for path in REQUIRED:
    if path not in spec.get("paths", {}):
        ERRORS.append(f"openapi missing path {path}")

if ERRORS:
    print("CONTRACT CHECK FAILED")
    for e in ERRORS:
        print(" -", e)
    sys.exit(1)
print("contracts OK")
