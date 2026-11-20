# 03 — Work Split (3 parts, zero overlap)

Coupling between parts is ONLY through `contracts/` and `fixtures/`. No shared Python package, no shared Lambda layer, no editing each other's folders. If you stick to the contracts, the parts snap together.

| Part | Owner | Theme | Owns |
|---|---|---|---|
| **P — Platform & Product** | Amit | "Everything runs and looks right" | `infra/`, `frontend/`, `tests/e2e/`, `.github/`, `contracts/`, docs |
| **A — Understand** | Teammate A | "Turn a file into structured data" | `backend/parsing/`, `fixtures/golden/`, `fixtures/resumes/` |
| **B — Decide** | Teammate B | "Score it and expose it" | `backend/scoring/`, `backend/api/` |

Amit writes the entire SAM template with STUB handlers for every Lambda by Fri 20 Nov noon (Gate 1). Teammates never edit `template.yaml`; they request resource/env changes from Amit in the PR.

## Part A — Understand (Teammate A)
Input: S3 objects + SQS messages. Output: DynamoDB `candidates`/`jobs` rows exactly per `contracts/`.
| ID | Task | Done when |
|---|---|---|
| A1 | `backend/parsing/skills_taxonomy.json`: >=150 canonical skills with aliases (K8s=Kubernetes, AWS Lambda, CI/CD...) + job-title aliases + seniority words | loads, no duplicate aliases, test passes |
| A2 | Golden set in `fixtures/golden/`: 12 SYNTHETIC resumes (made-up people, fake emails like name@example.com; 4 digital PDF, 4 two-column DOCX, 4 scanned PDF) + `expected.json` hand-labelled (name, email, skills, employers, titles, years) + 3 JDs with a hand-ranked expected candidate order (used by DoD C4) | file exists, labels reviewed by Amit |
| A3 | Text extraction: PDF -> Textract async (start + poll, 100s cap), DOCX -> python-docx, others -> permanent error | unit tests with moto/mocks; real run on 3 PDFs |
| A4 | Comprehend module: chunk text (<= 4500 chars on sentence boundaries), DetectEntities standard (PERSON/ORGANIZATION/DATE) + custom recogniser if `CUSTOM_RECOGNIZER_ARN` set (SKILL/JOB_TITLE); merge + dedupe | unit tests + 1 real call |
| A5 | Field derivation: name (first PERSON in header), email (regex), skills (entities + taxonomy dictionary match, normalised), titles, employers, `experience_years` (union of date ranges, "Present" = today, overlaps not double counted, cap 40; fallback "N+ years" phrase) | accuracy vs golden meets DoD C1-C3 |
| A6 | `parse` Lambda: SQS handler per Architecture error policy; idempotent candidate_id; writes candidate row + `parsed/` audit JSON; enqueues score message | record validates against `candidate.schema.json` |
| A7 | `jd-parse` Lambda: extract required_skills, jd_titles, required_years -> `jobs` row status JD_PARSED; enqueue JD_READY scoring for existing candidates; zero skills found -> job FAILED + failed_jobs `JD_NO_SKILLS` | validates against `job.schema.json` |
| A8 | `dlq-consumer` Lambda: reads any DLQ message, writes `failed_jobs` row | validates against `failed_job.schema.json` |
| A9 | Custom recogniser: build training annotations (synthetic resumes), train in console, evaluate, give Amit the ARN. Stretch-with-fallback: pipeline must pass DoD without it | ARN in SSM or documented "disabled" |
| A10 | `docs/samples/`: raw Comprehend JSON + parsed record for 3 resume types | committed |

## Part B — Decide (Teammate B)
Input: DynamoDB rows from Part A (use `fixtures/candidates/` and `fixtures/jobs/` from day 1 — you do NOT wait for Part A). Output: scores + the whole HTTP API per `contracts/openapi.yaml`.
| ID | Task | Done when |
|---|---|---|
| B1 | Pure scoring library `backend/scoring/scoring.py` per `docs/04_SCORING_LOGIC.md` + exhaustive unit tests | all branches tested, no AWS imports |
| B2 | `score` Lambda: SQS handler; job not JD_PARSED -> raise (retry); writes score/breakdown/above_threshold/status SCORED; idempotent | test with moto |
| B3 | API: `POST /jobs`, `GET /jobs`, `GET /jobs/{id}`, `POST /jobs/{id}/uploads` (pre-signed PUT URLs, content-type + size limits, pasted-JD support) | responses match openapi |
| B4 | API: `GET /jobs/{id}/candidates` (sorted desc by score, unscored last), `GET .../candidates/{cid}` | match openapi |
| B5 | API: `POST .../decision` -> shortlist (SES email using interview details, NO_EMAIL if no address) / reject; append `decision_history` | email_status correct |
| B6 | API: `GET /jobs/{id}/shortlist.csv` (columns fixed in openapi) | opens in Excel |
| B7 | API: `GET /failed-jobs`, `POST /failed-jobs/{id}/retry` (re-enqueue by copying S3 object key into a new SQS message) | works on fixture |
| B8 | Final written explanation: NLP matching logic + 3 enhancements (finalise docs/04) | reviewed |
| B9 | Contract tests: every API response in tests validates against openapi/JSON schemas | `make verify` green |

## Part P — Platform & Product (Amit)
| ID | Task | Done when |
|---|---|---|
| P1 | Repo, branches, CODEOWNERS, CI | done at scaffold |
| P2 | SAM `template.yaml`: ALL resources in 01_ARCHITECTURE + stub handlers (Gate 1) | `make deploy-dev` succeeds |
| P3 | Cognito pool, client, group, 3 recruiter users; script `scripts/create_user.sh` | login returns JWT |
| P4 | API Gateway REST + Cognito authorizer, all routes wired to stub Lambdas, CORS | 401 without token, 200 with |
| P5 | SES: verify sender + demo recipients; REQUEST PRODUCTION ACCESS (today) | identity verified |
| P6 | Frontend shell + auth + mock API generated from openapi (build UI before backend exists) | runs on mocks |
| P7 | Frontend pages: jobs, upload w/ progress, candidates table + skill tags + breakdown drawer, shortlist modal, reject, failed jobs, CSV | DoD D1-D6 |
| P8 | CloudFront + S3 frontend deploy via template | HTTPS URL works |
| P9 | Alarms, SNS, budget, log retention | E1, E3 |
| P10 | `tests/e2e/smoke.py` implementing DoD B1-B5 | green on dev, then prod |
| P11 | Integration owner: merges, resolves contract questions, runs gates | gates passed |
| P12 | Demo video, architecture diagram, cost sheet, README tested | F1, F4, F5 |

## How the parts click together (the integration contract in one table)
| Producer | Artifact | Consumer | Defined in |
|---|---|---|---|
| Amit | S3 keys `jd/{job_id}/`, `resumes/{job_id}/` | A | 01_ARCHITECTURE |
| A | `candidates` row (status PARSED) | B | `contracts/candidate.schema.json` |
| A | `jobs` row JD fields | B | `contracts/job.schema.json` |
| A | SQS score message | B | `contracts/sqs_messages.md` |
| B | `score`, `score_breakdown`, `above_threshold` | Frontend | `contracts/candidate.schema.json` |
| B | HTTP API | Frontend, smoke test | `contracts/openapi.yaml` |
| A/B | `failed_jobs` row | Frontend, B7 | `contracts/failed_job.schema.json` |

## Rules for a clean merge
1. Branch `feat/<task-id>-name`, PR to `main`, Amit merges. CI must be green.
2. Records you WRITE must validate against the schema (test it). Records you READ: assume the schema, nothing more.
3. Changing a contract requires a DECISIONS.md entry signed off by all three.
