"""A10 + A3/A4 evidence: run the REAL pipeline stages (Textract, Comprehend) on files already in S3 and save
the raw Comprehend output + the parsed record, for docs/samples/.

  aws s3 cp fixtures/golden/resumes/ s3://BUCKET/golden/ --recursive
  python backend/parsing/tools/sample_run.py --bucket BUCKET --keys golden/g01.pdf golden/g02.docx golden/g03.pdf

g01 = digital PDF, g02 = two-column DOCX, g03 = scanned PDF (the three resume types the brief asks for).
Needs AWS credentials (us-east-1). Set COMPREHEND_ENDPOINT_ARN to include the custom recogniser.
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import boto3  # noqa: E402

import comprehend_client as cc  # noqa: E402
import config  # noqa: E402
import extract  # noqa: E402
import fields  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bucket", required=True)
    ap.add_argument("--keys", nargs="+", required=True)
    ap.add_argument("--out", default="docs/samples")
    a = ap.parse_args()
    s3, textract, comprehend = boto3.client("s3"), boto3.client("textract"), boto3.client("comprehend")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for key in a.keys:
        text = extract.extract_text(a.bucket, key, s3=s3, textract=textract)
        raw = cc.detect_entities(text, comprehend, config.comprehend_endpoint_arn())
        parsed = fields.parse_resume(text, cc.merge_entities(raw), date.today())
        stem = Path(key).stem
        (out / f"{stem}.comprehend.json").write_text(json.dumps(raw, indent=2), encoding="utf-8")
        (out / f"{stem}.parsed.json").write_text(json.dumps(parsed, indent=2), encoding="utf-8")
        print(f"{key}: {len(text)} chars, {len(raw['standard'])} standard + {len(raw['custom'])} custom entities -> {out}/{stem}.*.json")


if __name__ == "__main__":
    main()
