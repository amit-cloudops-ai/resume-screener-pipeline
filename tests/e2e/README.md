# Live deployment smoke test — Phase A Step 8 (DoD B1–B5)

This script validates an already deployed stack. It does not deploy infrastructure and is dry-run by default.

## Acceptance checks
- B1: create one job, upload 9 valid synthetic resumes (4 digital PDFs, 3 DOCX, 2 scanned PDFs) plus one corrupt DOCX; require 9 SCORED + 1 FAILED and an OPEN failed_jobs record for the corrupt input.
- B2: require name, email (string or null), skills[], employers[], titles[], experience_years, score (0–100), score_breakdown and above_threshold on every scored candidate.
- B3: re-upload the same object and assert candidate count remains ten.
- B4: enqueue an S3-event-shaped message for a deliberately missing object; require parse-queue redrive (up to two 900-second visibility intervals) and DLQ consumer to persist an OPEN failed_jobs record. Allow up to 35 minutes for this check.
- B5: assert candidate results are sorted by descending score.

The run creates new synthetic records and objects, does not delete or modify existing jobs, and does not shortlist candidates or send SES email.

## Prerequisites
1. Deploy the target stage separately after explicit approval.
2. Run make golden-generate.
3. Set SMOKE_ID_TOKEN to a valid recruiter Cognito ID token (not access token; no Bearer prefix).
4. Configure AWS credentials in the same account/region with CloudFormation read and test-bucket/parse-queue access.
5. Confirm S3 notifications, Lambda event source mappings, SQS redrive and DLQ consumer are active.

## Safe invocation
Dry run, no credentials required:
make smoke STAGE=dev

Live development run:
SMOKE_ID_TOKEN="$ID_TOKEN" python tests/e2e/smoke.py --stage dev --region us-east-1 --execute

Production requires both --execute and --allow-prod. Do not use production as the first smoke target.

A successful CI run proves static/offline checks only. The live smoke test has not been run against AWS. Keep the generated job ID for cleanup using the documented teardown procedure.
