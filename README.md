# AI Resume Screener & Talent Acquisition Pipeline

Automated, auditable resume screening on AWS. Recruiters upload a job description and a batch of resumes (PDF/DOCX); Amazon Textract and Amazon Comprehend (managed NLP + a custom entity recogniser) extract entities and skills; a deterministic, explainable scoring model ranks candidates; the recruiter shortlists in a dashboard, which emails the candidate via SES and exports CSV.

**Status:** foundation only (docs, frozen contracts, fixtures, CI). Infrastructure, backend and frontend are not built yet. Live status: [`docs/STATE.md`](docs/STATE.md).

## Where to start
| You are | Read |
|---|---|
| A teammate | [`docs/TEAMMATE_QUICKSTART.md`](docs/TEAMMATE_QUICKSTART.md) |
| Amit (setup) | [`docs/SETUP_CHECKLIST.md`](docs/SETUP_CHECKLIST.md) |
| An AI assistant | [`AGENTS.md`](AGENTS.md) first, then paste [`docs/prompts/SESSION_STARTER.md`](docs/prompts/SESSION_STARTER.md) |

## Repo map
| Path | Purpose |
|---|---|
| `docs/00_BRIEF.md` | What we build, scope, deliverables, what "production" means |
| `docs/01_ARCHITECTURE.md` | Locked architecture, resource names, AWS gotchas |
| `docs/02_DEFINITION_OF_DONE.md` | The finish line (evidence-based checklist) |
| `docs/03_WORK_SPLIT.md` | Three parts, task IDs, ownership |
| `docs/04_SCORING_LOGIC.md` | Extraction + scoring spec |
| `docs/05_TIMELINE.md` | Dates and gates (submit 25 Nov 2026) |
| `docs/STATE.md`, `DECISIONS.md`, `RISKS.md`, `RESOURCES.md` | Live status, locked decisions, risks, AWS resource ledger + teardown |
| `contracts/` | Frozen OpenAPI 3.1, JSON schemas, SQS messages |
| `fixtures/` | Sample jobs/candidates/failures (and later golden resumes) |
| `infra/` `backend/` `frontend/` `tests/` | Implementation areas |

## Commands
```bash
make verify        # repo check + contract validation + tests (must be green before every commit)
make deploy-dev    # sam build + deploy stack rs-dev  (needs infra/template.yaml, task P2)
make deploy-prod   # stack rs-prod
make smoke STAGE=prod
```

## Architecture in one paragraph
S3 (`jd/`, `resumes/` prefixes) -> SQS -> Lambda: Textract (PDF) / python-docx (DOCX) -> Comprehend -> DynamoDB -> score queue -> scoring Lambda -> DynamoDB. API Gateway (Cognito authorizer) + Lambdas serve a React dashboard hosted on S3 + CloudFront. DLQs + a failed_jobs table capture failures; SES emails shortlisted candidates. Region us-east-1, IaC with AWS SAM (stacks `rs-dev`, `rs-prod`).

## Teardown
Everything created by hand is logged in [`docs/RESOURCES.md`](docs/RESOURCES.md), with the exact delete order. All resources are tagged `Project=resume-screener`.
