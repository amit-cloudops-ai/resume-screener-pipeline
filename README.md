# AI Resume Screener & Talent Acquisition Pipeline

An AWS-native, auditable resume screening workflow. Recruiters create a job, upload a job description and resumes, and receive a ranked shortlist with explainable skill, title and experience scores. The target architecture uses Amazon Textract, Amazon Comprehend, deterministic Python scoring, DynamoDB, S3, SQS, Cognito, API Gateway, CloudFront and SES.

## Current project status — 24 November 2026

**Infrastructure scaffold: SAM lint and build passing. Application: not end-to-end complete. AWS: not deployed or live-verified.**

- P2 SAM infrastructure and Lambda stubs are under review in [PR #5](https://github.com/amit-cloudops-ai/resume-screener-pipeline/pull/5).
- CI run 45328825772 passed `make verify`, `sam validate --lint` and `sam build` on the recorded PR head. The SAM build currently packages scaffold handlers; it does not prove live AWS behaviour.
- B1/B2/B3 implementation work exists in separate open PRs and is not yet integrated into the P2 branch.
- Parsing, Candidates/Decision/Export/Failed APIs, recruiter frontend and E2E workflow remain incomplete or stubbed.
- No `rs-dev` or `rs-prod` deployment, Cognito 401/200 test, S3-to-SQS event test, Textract/Comprehend run, SES delivery or full E2E pass is evidenced.

The evidence-based task board and next gates are in [`docs/STATE.md`](docs/STATE.md). Do not deploy to AWS until the remaining implementation, contract, integration and security gates pass.

## Where to start

| Role | Read first |
|---|---|
| Teammate | [`docs/TEAMMATE_QUICKSTART.md`](docs/TEAMMATE_QUICKSTART.md) |
| Amit — setup/deployment | [`docs/SETUP_CHECKLIST.md`](docs/SETUP_CHECKLIST.md), [`infra/README.md`](infra/README.md) |
| AI coding assistant | [`AGENTS.md`](AGENTS.md), then [`docs/prompts/SESSION_STARTER.md`](docs/prompts/SESSION_STARTER.md) |

## Repository map

| Path | Purpose |
|---|---|
| `docs/00_BRIEF.md` | Product scope, deliverables and production definition |
| `docs/01_ARCHITECTURE.md` | Locked architecture, resources, event flow and AWS constraints |
| `docs/02_DEFINITION_OF_DONE.md` | Acceptance criteria and evidence required to finish |
| `docs/03_WORK_SPLIT.md` | Ownership boundaries and task IDs |
| `docs/04_SCORING_LOGIC.md` | Extraction and deterministic scoring specification |
| `docs/05_TIMELINE.md` | Delivery gates and deadline |
| `docs/STATE.md` | Current evidence-based implementation status |
| `docs/DECISIONS.md` | Approved architecture and contract decisions |
| `docs/RESOURCES.md` | AWS resource ledger and teardown procedure |
| `docs/RISKS.md` | Delivery, cost and integration risks |
| `contracts/` | Frozen OpenAPI, JSON schemas and SQS message contracts |
| `fixtures/` | Sample jobs, candidates and failure records |
| `infra/` | AWS SAM infrastructure |
| `backend/` | Parsing, scoring and API Lambda handlers |
| `frontend/` | Recruiter dashboard |
| `tests/` | Contract, unit and E2E tests |

## Repository checks

Run from the repository root with Python 3.12, AWS SAM CLI and cfn-lint installed:

```bash
make verify       # repository integrity, contract validation and unit tests
make sam-validate # SAM + cfn-lint validation
make sam-build    # package every Lambda CodeUri locally
```

CI runs all three gates on pull requests. A passing SAM validation/build does not replace a CloudFormation change-set review or live integration tests.

## AWS deployment controls

Region: `us-east-1`. Stack names: `rs-dev` and `rs-prod`.

Development deployment (only after the repository gates pass):

```bash
make deploy-dev ALARM_EMAIL=you@example.com
```

Production deployment requires an alarm email and a verified SES sender:

```bash
make deploy-prod ALARM_EMAIL=you@example.com SES_SENDER=verified-sender@example.com
```

Optional Comprehend custom entity recognition is disabled by default. To enable it, pass `CUSTOM_RECOGNIZER_ARN=<endpoint-arn>` when deploying. The stack parameter is copied into Lambda environment variables and mirrored to SSM; changing SSM alone does not update running Lambda environments.

**Cost and safety:** the AWS Budget is an alert, not a spending cap. Do not create a Comprehend real-time endpoint unless it is required for the approved demo window. Review the CloudFormation change set before confirming deployment. Keep [`docs/RESOURCES.md`](docs/RESOURCES.md) current for manually created resources and follow its teardown order after submission.

## Architecture at a glance

Recruiter browser → CloudFront/S3 dashboard → Cognito-authenticated API Gateway → API Lambdas → DynamoDB/S3/SES.

JD and resume objects in the uploads bucket trigger SQS queues. Parsing Lambdas use Textract for PDFs and python-docx for DOCX, then Comprehend and taxonomy normalization. Parsed candidates enter DynamoDB and the score queue. The scoring Lambda calculates the deterministic 50% skills / 30% title / 20% experience score. Parse, JD-parse and score failures flow through DLQs into the failed-jobs table for recruiter visibility and retry.

See [`docs/01_ARCHITECTURE.md`](docs/01_ARCHITECTURE.md) for the authoritative resource names, queue contracts, IAM constraints and failure policy.
