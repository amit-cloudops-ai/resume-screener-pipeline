#!/usr/bin/env python3
"""Live E2E acceptance test for DoD B1-B5. Dry-run unless --execute is passed."""
from __future__ import annotations
import argparse, json, os, sys, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path
import boto3

ROOT = Path(__file__).resolve().parents[2]
GOLDEN = ROOT / "fixtures" / "golden" / "resumes"
RESUME_IDS = ("R01", "R02", "R03", "R04", "R05", "R06", "R07", "R09", "R10")
JD_TEXT = """Platform Engineer
Required skills: aws, docker, kubernetes, terraform, linux, python, git.
Experience: 3+ years.
Responsibilities: Build reliable cloud infrastructure and CI/CD automation.
"""

class SmokeFailure(RuntimeError):
    pass

def request(url, token, method="GET", payload=None, content=None, content_type=None):
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = token
    data = content
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode()
    if content_type:
        headers["Content-Type"] = content_type
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read().decode("utf-8", "replace")
            if response.headers.get_content_type() == "application/json":
                raw = json.loads(raw) if raw else {}
            return response.status, raw
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            pass
        return exc.code, raw

def wait_candidates(api, token, job_id, timeout=300):
    deadline = time.monotonic() + timeout
    latest = []
    while time.monotonic() < deadline:
        status, body = request(f"{api}/jobs/{job_id}/candidates", token)
        if status != 200:
            raise SmokeFailure(f"Candidate API HTTP {status}: {body}")
        latest = body.get("candidates", [])
        scored = sum(x.get("status") == "SCORED" for x in latest)
        failed = sum(x.get("status") == "FAILED" for x in latest)
        if len(latest) == 10 and scored == 9 and failed == 1:
            return latest
        time.sleep(5)
    raise SmokeFailure(f"Expected 9 SCORED + 1 FAILED within {timeout}s; got {len(latest)} records.")

def wait_failed_record(api, token, job_id, source_key, timeout=300):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status, body = request(f"{api}/failed-jobs?job_id={urllib.parse.quote(job_id)}", token)
        if status != 200:
            raise SmokeFailure(f"Failed-jobs API HTTP {status}: {body}")
        for row in body.get("failed_jobs", []):
            if row.get("s3_key") == source_key and row.get("status") == "OPEN":
                return row
        time.sleep(5)
    raise SmokeFailure(f"No OPEN failed_jobs record for {source_key!r}.")

def upload(url, path, content_type):
    req = urllib.request.Request(url, data=path.read_bytes(), method="PUT",
                                 headers={"Content-Type": content_type})
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            if response.status not in (200, 204):
                raise SmokeFailure(f"Upload {path.name}: HTTP {response.status}")
    except urllib.error.HTTPError as exc:
        raise SmokeFailure(f"Upload {path.name}: HTTP {exc.code}") from exc

def run(args):
    token = os.getenv("SMOKE_ID_TOKEN", "").strip()
    if not token:
        raise SmokeFailure("Set SMOKE_ID_TOKEN to a valid recruiter Cognito ID token.")
    if args.stage == "prod" and not args.allow_prod:
        raise SmokeFailure("Production requires both --execute and --allow-prod.")
    session = boto3.Session(region_name=args.region)
    cfn, sqs = session.client("cloudformation"), session.client("sqs")
    stack = cfn.describe_stacks(StackName=f"rs-{args.stage}")["Stacks"][0]
    outputs = {x["OutputKey"]: x["OutputValue"] for x in stack.get("Outputs", [])}
    api, bucket = outputs.get("ApiUrl", "").rstrip("/"), outputs.get("UploadsBucketName")
    if not api or not bucket:
        raise SmokeFailure("Stack must expose ApiUrl and UploadsBucketName.")
    status, body = request(f"{api}/jobs", token)
    if status != 200:
        raise SmokeFailure(f"Authenticated GET /jobs expected 200, got {status}: {body}")
    status, body = request(f"{api}/jobs", token, "POST",
        {"title": f"Phase A smoke {int(time.time())}", "threshold": 60, "description_text": JD_TEXT})
    if status != 201 or "job" not in body:
        raise SmokeFailure(f"Job creation expected 201, got {status}: {body}")
    job_id = body["job"]["job_id"]
    expected = json.loads((ROOT / "fixtures/golden/expected.json").read_text())
    rows = {x["id"]: x for x in expected["resumes"]}
    selected = [rows[x] for x in RESUME_IDS]
    entries = [{"file_name": x["file_name"], "content_type":
        "application/pdf" if x["file_name"].endswith(".pdf") else
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"} for x in selected]
    entries.append({"file_name": "smoke-corrupt.docx",
                    "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"})
    status, body = request(f"{api}/jobs/{job_id}/uploads", token, "POST", {"files": entries})
    if status != 200 or len(body.get("uploads", [])) != 10:
        raise SmokeFailure(f"Expected 10 presigned URLs, got HTTP {status}: {body}")
    urls = {x["file_name"]: x["url"] for x in body["uploads"]}
    for row in selected:
        path = GOLDEN / row["file_name"]
        ctype = "application/pdf" if path.suffix == ".pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        upload(urls[row["file_name"]], path, ctype)
    corrupt = ROOT / "tests/e2e/corrupt-resume.docx"
    corrupt.write_bytes(b"deliberately invalid DOCX package")
    upload(urls["smoke-corrupt.docx"], corrupt,
           "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    candidates = wait_candidates(api, token, job_id)
    bad = next((x for x in candidates if x.get("file_name") == "smoke-corrupt.docx"), None)
    if not bad or bad.get("status") != "FAILED":
        raise SmokeFailure("Corrupt DOCX did not produce a FAILED candidate.")
    wait_failed_record(api, token, job_id, bad["source_key"])

    # B3: re-upload same S3 object; deterministic candidate identity must prevent duplicates.
    first = selected[0]
    first_path = GOLDEN / first["file_name"]
    upload(urls[first["file_name"]], first_path, "application/pdf" if first_path.suffix == ".pdf" else
           "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    time.sleep(15)
    status, body = request(f"{api}/jobs/{job_id}/candidates", token)
    if status != 200 or len(body.get("candidates", [])) != 10:
        raise SmokeFailure("Duplicate upload created an extra candidate or candidate API failed.")

    # B4: send an S3-event-shaped missing-object message; deployed retry/DLQ consumer must persist it.
    queue = sqs.get_queue_url(QueueName=f"rs-{args.stage}-parse-queue")["QueueUrl"]
    missing_key = f"resumes/{job_id}/smoke-missing-object.pdf"
    event = {"Records": [{"eventSource": "aws:s3", "eventName": "ObjectCreated:Put",
        "s3": {"bucket": {"name": bucket}, "object": {
            "key": urllib.parse.quote(missing_key, safe="/"), "size": 0}}}]}
    sqs.send_message(QueueUrl=queue, MessageBody=json.dumps(event))
    wait_failed_record(api, token, job_id, missing_key)

    # B5: score ordering is descending.
    status, body = request(f"{api}/jobs/{job_id}/candidates", token)
    if status != 200:
        raise SmokeFailure(f"Final candidates API HTTP {status}: {body}")
    scores = [x["score"] for x in body.get("candidates", []) if x.get("score") is not None]
    if scores != sorted(scores, reverse=True):
        raise SmokeFailure("Candidate list is not sorted by descending score.")
    print(json.dumps({"stage": args.stage, "job_id": job_id, "candidate_count": len(body["candidates"]),
        "scored": sum(x.get("status") == "SCORED" for x in body["candidates"]),
        "failed": sum(x.get("status") == "FAILED" for x in body["candidates"]),
        "corrupt_input": "verified", "duplicate_upload": "verified",
        "missing_object_dlq": "verified", "score_order": "verified"}, indent=2))
    return 0

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("dev", "prod"), default="dev")
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--execute", action="store_true", help="perform live API/AWS operations")
    parser.add_argument("--allow-prod", action="store_true", help="extra explicit opt-in for production")
    args = parser.parse_args()
    if not args.execute:
        print("DRY RUN: no AWS/API calls. Live mode creates a job and 10 synthetic uploads, "
              "exercises SQS/DLQ, and leaves test data in the target stage.")
        return 0
    try:
        return run(args)
    except Exception as exc:
        print(f"SMOKE TEST FAILED: {exc}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
