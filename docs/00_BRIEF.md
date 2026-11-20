# 00 — Project Brief

## What we are building
An automated recruitment pipeline. A recruiter creates a job, uploads a JD and a batch of resumes. The system extracts text, runs Amazon Comprehend to pull out entities and skills, scores every candidate against the JD, and shows a ranked, explainable shortlist. Recruiter shortlists/rejects with one click; shortlisting emails the candidate via SES. Shortlist exports as CSV.

## Why it matters (the pitch)
Replaces hours of manual CV screening with an automated, auditable workflow. Every score is explainable (matched/missing skills, title similarity, years counted) and every decision is logged (who, when).

## Users
Recruiters only (Cognito-authenticated). Candidates never log in; they only receive an email.

## In scope
1. Job creation + JD upload (file or pasted text).
2. Batch resume upload (PDF/DOCX) via pre-signed S3 URLs.
3. Text extraction (Textract for PDF/images, python-docx for DOCX).
4. Comprehend: standard entities (PERSON, ORGANIZATION, DATE) + custom entity recogniser (SKILL, JOB_TITLE) + deterministic taxonomy normalisation.
5. DynamoDB records: jobs, candidates, failed_jobs.
6. Scoring: skills 50 / title 30 / experience 20; threshold flag; stored with breakdown.
7. SQS queues for parse + score, DLQs, DLQ consumer writing failed_jobs.
8. Dashboard: jobs list, candidates per job sorted by score, skill tags, shortlist/reject, failed jobs view, CSV download.
9. SES email on shortlist.
10. Cognito auth on every API route.
11. Monitoring: DLQ alarm, Lambda error alarm, budget alarm.

## Explicitly OUT of scope (do not build, do not suggest mid-project)
Candidate login/portal, multi-tenant orgs, calendar integration, resume-vs-resume dedup, Bedrock/LLM scoring, Step Functions, Terraform, mobile app, i18n, non-English resumes, payments. These are "enhancement ideas" only (see docs/04_SCORING_LOGIC.md).

## Deliverables (what the evaluator sees)
1. End-to-end demo (video): upload -> Textract -> Comprehend -> score -> dashboard -> shortlist email -> CSV.
2. Sample Comprehend entity output for 3 resume types (digital PDF, two-column DOCX, scanned PDF).
3. Recruiter dashboard with candidate-job matches + extracted skill tags.
4. Written explanation of NLP matching logic + 3 enhancement ideas.
5. Repo with deployment instructions, architecture diagram, cost sheet.

## What "production deployment" means here
- Everything created by `sam deploy` (no click-ops), stack `rs-prod` in us-east-1.
- Dashboard served from CloudFront over HTTPS; API behind API Gateway with Cognito authorizer; unauthenticated call returns 401.
- Data encrypted at rest (S3 SSE, DynamoDB SSE), S3 public access blocked, least-privilege IAM per Lambda, no wildcard `*` resources except where AWS requires it (Textract/Comprehend actions).
- Retries + DLQs configured; failures visible in the dashboard (failed_jobs) and via a CloudWatch alarm.
- Smoke test (`make smoke STAGE=prod`) passes against the live stack.
- Logs retained 14 days; no PII in logs.

## Known traps in the original spec (decisions already made — see DECISIONS.md)
- Comprehend's built-in TITLE entity is for creative works (books/films), NOT job titles. Job titles come from the custom recogniser + taxonomy.
- Textract does not read DOCX. DOCX is parsed with python-docx.
- Multi-page PDFs need Textract's async API (start job + poll), not the single-call API.
- A custom Comprehend recogniser is trained, then needs an endpoint (billed hourly) for real-time use. We make it optional-by-config with a deterministic fallback so the pipeline never depends on it.
- SES starts in sandbox: it can only email verified addresses. Request production access on day 1 and use verified demo addresses.
