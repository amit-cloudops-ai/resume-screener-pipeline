# AI Resume Screener & Talent Acquisition Pipeline

An AWS-native resume screening workflow. Recruiters create a job, upload a job description and resumes, and receive ranked candidates with explainable skill, title and experience scores. The backend uses Textract, Comprehend, deterministic Python scoring, DynamoDB, S3, SQS, Cognito, API Gateway, CloudFront and SES.

## Current status — 24 November 2026

**Backend integration implemented; release gates remain.**

The integrated backend and SAM updates are in [draft PR #6](https://github.com/amit-cloudops-ai/resume-screener-pipeline/pull/6). The branch is separate from `main`; no code has been merged and no AWS resources have been deployed by this work.

- **B1/B2:** deterministic scoring library, SQS scoring Lambda, DynamoDB Decimal conversion and idempotency.
- **B3–B9:** jobs/uploads, candidate list/detail, recruiter decisions and SES, CSV export, failed-job listing/retry, NLP explanation and contract tests.
- **Part A:** PDF Textract extraction, DOCX/TXT parsing, Comprehend standard/custom entity support, taxonomy normalization, field derivation, JD parsing and DLQ persistence.
- **Integration:** local Moto acceptance scenario exercises one JD and ten resumes, yielding nine scored candidates and one permanent parse failure.
- **Infrastructure:** SAM validation/lint and build pass on the recorded CI run.

CI run `45332343952` passed on implementation commit `f755f86bca29eeafb68083e47451c5943d69ecbc`: `make verify` passed with 138 tests, SAM lint validation passed, and SAM build passed. Subsequent README/status-only commits are also checked by CI.

**Not yet complete:** recruiter frontend, live AWS deployment, Cognito 401/200 proof, S3-to-SQS live delivery, live Textract/Comprehend/SES tests, production sender verification, operational alarm proof and live E2E smoke. The local integration test is not a substitute for those deployed checks.

See [`docs/STATE.md`](docs/STATE.md) for the evidence-based status and remaining release gates.

## Start here

| Role | Read |
|---|---|
| Teammates | [`docs/TEAMMATE_QUICKSTART.md`](docs/TEAMMATE_QUICKSTART.md) |
| Engineering setup | [`docs/SETUP_CHECKLIST.md`](docs/SETUP_CHECKLIST.md) |
| AI coding assistant | [`AGENTS.md`](AGENTS.md), then [`docs/prompts/SESSION_STARTER.md`](docs/prompts/SESSION_STARTER.md) |
| Infrastructure | [`infra/README.md`](infra/README.md) |

## Repository map

| Path | Purpose |
|---|---|
| `docs/00_BRIEF.md` | Product scope and deliverables |
| `docs/01_ARCHITECTURE.md` | Locked architecture and event flow |
| `docs/02_DEFINITION_OF_DONE.md` | Acceptance criteria |
| `docs/03_WORK_SPLIT.md` | Ownership boundaries |
| `docs/04_SCORING_LOGIC.md` | Scoring specification |
| `docs/08_NLP_AND_SCORING.md` | Extraction and ranking explanation |
| `docs/STATE.md` | Current implementation and verification status |
| `contracts/` | Frozen OpenAPI, JSON schemas and SQS contracts |
| `fixtures/` | Sample job, candidate and failure records |
| `backend/parsing/` | Shared extraction, taxonomy, resume/JD/DLQ Lambdas |
| `backend/scoring/` | Deterministic scorer and SQS scoring Lambda |
| `backend/api/` | Recruiter API Lambdas |
| `backend/integration/` | Local end-to-end integration acceptance |
| `infra/` | AWS SAM template and deployment configuration |
| `frontend/` | Recruiter dashboard (not yet implemented) |
| `tests/` | Contract and repository-level tests |

## Verification commands

Run from the repository root with Python 3.12, AWS SAM CLI and cfn-lint installed:

```bash
make verify
make sam-validate
make sam-build
```

CI runs repository tests and SAM validation/build. A successful SAM build is not a live CloudFormation deployment or runtime proof.

## Architecture at a glance

Recruiter browser → CloudFront/S3 dashboard → Cognito-authenticated API Gateway → API Lambdas → DynamoDB/S3/SES.

JD and resume objects trigger SQS queues. The parsing workers use Textract asynchronous text detection for PDFs and python-docx for DOCX, then Comprehend and deterministic taxonomy normalization. Parsed candidates are written to DynamoDB and an audit artifact in S3. The JD parser extracts required skills, titles and minimum experience. The scoring worker calculates:

`score = round(100 × (0.50 × skills + 0.30 × title + 0.20 × experience), 1)`

Failures are recorded in the failed-jobs table; exhausted transient messages are captured by DLQ consumers. Recruiters can inspect and retry supported failure stages.

The authoritative resource names, SQS body formats, failure policy and security constraints are in [`docs/01_ARCHITECTURE.md`](docs/01_ARCHITECTURE.md) and [`contracts/`](contracts/).

## AWS deployment controls

Region: `us-east-1`. Stack names: `rs-dev` and `rs-prod`.

Development deployment (only after repository review and explicit approval):

```bash
make deploy-dev ALARM_EMAIL=you@example.com
```

Production deployment requires a verified SES sender and an alarm email:

```bash
make deploy-prod ALARM_EMAIL=you@example.com SES_SENDER=verified-sender@example.com
```

The optional Comprehend custom recognizer is disabled by default. To enable it, pass `CUSTOM_RECOGNIZER_ARN=<endpoint-arn>` during deployment. Redeployment is required to update the Lambda environment.

**Cost and safety:** the AWS Budget is an alert, not a spending cap. Review the CloudFormation change set before execution. Keep [`docs/RESOURCES.md`](docs/RESOURCES.md) current for manually created resources and follow its teardown procedure after the demo.
