# STATE — live project baseline (evidence-based)

Last updated: 2026-11-24 — Phase A Step 10 audit
Integration branch: `feat/INT-full-pipeline-integration`
Integration PR: [#6 — complete backend pipeline](https://github.com/amit-cloudops-ai/resume-screener-pipeline/pull/6) (draft, not merged)
Phase A working branch: `feat/phase-a-steps-1-3`
Phase A PR: [#8 — Phase A repository work](https://github.com/amit-cloudops-ai/resume-screener-pipeline/pull/8) (draft, base `feat/INT-full-pipeline-integration`, not merged)
Submission target: 2026-11-25
AWS deployment: NOT PERFORMED; explicit deployment approval remains required.

## Status definitions
- `VERIFIED`: implementation exists on the relevant working branch and the named CI checks passed.
- `DONE-UNVERIFIED`: implementation exists, but a required runtime, account or deployment proof is absent.
- `DOING`: implementation or verification is still in progress.
- `TODO`: not implemented.
- A passing local/Moto test is not live AWS proof.

## Task board

| ID | Owner | Task | Status | Evidence / remaining gate |
|---|---|---|---|---|
| P1 | Amit | Repository, ownership rules and CI | VERIFIED | PR #6 CI runs `make verify`; direct edits stay on feature branch; main unchanged. |
| P2 | Amit | SAM infrastructure | VERIFIED | CI run 45332343952 passed SAM lint validation and build on implementation commit f755f86bca29eeafb68083e47451c5943d69ecbc. Live CloudFormation change-set review remains. |
| P3 | Amit | Cognito recruiter setup | DONE-UNVERIFIED | User pool, client and group are defined in SAM; no deployed pool/user evidence. |
| P4 | Amit | API Gateway + Cognito authorizer | DONE-UNVERIFIED | REST API and default Cognito authorizer are defined; no live 401/200 proof. |
| P5 | Amit | SES identity and production access | TODO | SES sender verification and production-access approval not evidenced. |
| P6 | Amit | Frontend shell + mocks | VERIFIED | React/Vite/TypeScript, Cognito SRP (including temporary-password challenge), raw ID-token API client, local mock mode and approved Editorial Hiring Desk visual system implemented. Step 7 frontend CI verification passed; see run 45344840009 below. |
| P7 | Amit | Recruiter frontend pages | VERIFIED | Editorial Hiring Desk recruiter workflows implemented against the frozen API routes. GitHub Actions run 45344840009 passed all three jobs: make verify + golden evaluation, frontend TypeScript/production build, SAM lint/build. |
| P8 | Amit | CloudFront deployment | DONE-UNVERIFIED | Distribution/OAC/bucket policy are defined in SAM; no live URL or browser proof. |
| P9 | Amit | Alarms / budget | DONE-UNVERIFIED | Alarm and budget resources are defined; no deployed alarm/notification proof. |
| P10 | Amit | Live E2E smoke script | VERIFIED | Guarded live smoke script for DoD B1–B5, offline tests and documentation pass CI run 45342184687. Dry-run by default; actual AWS execution remains a post-deployment gate. |
| P11 | Amit | Backend integration | VERIFIED | Moto acceptance on CI run 45331272201: one JD + ten resumes -> nine SCORED candidates + one FAILED candidate; candidate and failed-job records validate against frozen schemas. |
| P12 | Amit | Demo, architecture diagram and cost sheet | DOING | Step 9 architecture source/render, cost model and guarded frontend publish workflow are committed; demo video and teammate clean-clone deployment rehearsal remain as release-acceptance tasks. |
| P13 | Amit | Phase A Step 10 final repository audit | VERIFIED | See docs/PHASE_A_STEP10_FINAL_AUDIT.md; CSV pagination defect fixed with regression test, frontend publishing workflow added, contracts/SAM/frontend reviewed. Final audit CI run 45346661338 passed 3/3 jobs on head c8d7a2d. |
| A1 | Teammate A | Skills taxonomy | VERIFIED | `backend/parsing/skills_taxonomy.json`; 160 canonical skills, 231 canonical/alias terms, no collisions; taxonomy test passes. |
| A2 | Teammate A | Golden set (12 resumes) | VERIFIED | 12 synthetic resumes committed as source text and reproducibly materialized as 4 digital PDFs, 4 two-column DOCX and 4 raster-only scanned PDFs; 3 labelled JDs and `expected.json`; CI validates generated files. |
| A3 | Teammate A | PDF/DOCX/TXT extraction | VERIFIED | Textract async polling/pagination and DOCX paragraphs/tables implemented; mocked/unit tests pass. Golden generator validates digital PDF, image-only scanned PDF and two-column DOCX. TXT is enabled for JD only; live Textract remains unverified. |
| A4 | Teammate A | Comprehend standard/custom entity extraction | VERIFIED | Standard/custom endpoint calls and UTF-8-safe 4.8 KB chunking implemented. Text is chunked at sentence boundaries up to 4,500 characters where possible. Live endpoint/service behaviour unverified. |
| A5 | Teammate A | Candidate/JD field derivation | VERIFIED | Name/email/employer/title/skills/experience derivation and overlap-union tests implemented; custom `JOB_TITLE` only (standard Comprehend `TITLE` ignored); `N+ years` fallback; 40-year implementation cap. Golden deterministic metrics pass. |
| A6 | Teammate A | Resume parse Lambda | VERIFIED | SQS partial-batch handling, deterministic candidate IDs, permanent failure records, parsed S3 artifact and score-queue producer implemented. |
| A7 | Teammate A | JD-parse Lambda | VERIFIED | Required skills/title/years, zero-skill failure, job state update and JD_READY fan-out implemented. |
| A8 | Teammate A | DLQ consumer Lambda | VERIFIED | Stage mapping, source-key resolution, idempotent failed-job persistence implemented. |
| A9 | Teammate A | Custom recognizer model/endpoint | TODO | Optional feature remains disabled; no training dataset or endpoint ARN. |
| A10 | Teammate A | Three reviewed sample outputs | VERIFIED | Three reviewed synthetic examples committed under `docs/samples/`; automated tests enforce provenance and match parser output to golden labels. Actual Textract/Comprehend captures remain blocked on approved AWS deployment. |
| B1 | Teammate B | Scoring library + tests | VERIFIED | Deterministic 50/30/20 scorer, edge cases, title seniority, thresholds and schema fields covered. |
| B2 | Teammate B | Score Lambda | VERIFIED | SQS/DynamoDB handler accepts DynamoDB `Decimal` numeric values, duplicate idempotency and RESCORE behaviour covered. |
| B3 | Teammate B | Jobs API + uploads | VERIFIED | Create/list/get, JD text/file, presigned resume URLs, validation, Cognito subject and CORS covered. Parser checks actual object size because presigned PUT itself does not impose a size range. |
| B4 | Teammate B | Candidates API | VERIFIED | Query, counts, decision filter, score-desc ordering and detail lookup covered. |
| B5 | Teammate B | Decision API + SES | VERIFIED | SCORED-only conditional decisions, interview validation, one-time SES invitation and email status covered with SES isolated in tests. |
| B6 | Teammate B | CSV export | VERIFIED | Exact header order, shortlist filtering, ranking and CSV output covered. |
| B7 | Teammate B | Failed-jobs API + retry | VERIFIED | GSI/scan listing, PARSE/JD_PARSE/SCORE retry routing, conditional state transition and frozen SQS payload reconstruction covered. |
| B8 | Teammate B | Written NLP explanation | VERIFIED | `docs/08_NLP_AND_SCORING.md` explains extraction, taxonomy, experience, scoring and limitations. |
| B9 | Teammate B | Contract tests | VERIFIED | Frozen schema/route tests plus API handler tests and integrated persisted-record validation. |

## Phase A — Steps 1–3 completion

**Status: VERIFIED on `feat/phase-a-steps-1-3`.** This work was repository-only. No AWS account inventory, AWS console/API operation, CloudFormation change set, deployment or resource creation was performed.

- Step 1 — backend and SAM static audit completed. Corrected the standard Comprehend TITLE misuse, DynamoDB Decimal scoring validation, experience fallback/cap, sentence-boundary chunking and stale infrastructure status documentation. Audit record: `docs/PHASE_A_AUDIT.md`.
- Step 2 — 12-resume synthetic golden dataset completed: 4 digital PDF, 4 two-column DOCX, 4 raster-only scanned PDF; 3 labelled JDs; expected field labels and expected top candidate. Binary documents are reproducibly generated by `make golden-generate` from committed source text. CI validated all formats.
- Step 3 — deterministic accuracy evaluation completed. Report: `docs/PHASE_A_ACCURACY.md`. Skill precision 100% (77 TP, 0 FP), recall 100% (77 TP, 0 FN), email 12/12, experience within ±1 year 12/12, top-1 ranking 3/3.

**Important limitation:** Golden-set entity fixtures for PERSON, ORGANIZATION and JOB_TITLE are deterministic mocks. These metrics do not represent live Textract OCR or Comprehend model accuracy. Live service sample outputs and service accuracy remain AWS-phase tasks.

## Phase A — Steps 4–5 repository work

**Status: IMPLEMENTED; CI verification passed on commit `f749e5db0e622f33803f233aa9f6c3507627480a` (run 45339630424). The sample-provenance regression test and all repository checks passed on final Step 4–5 head `2ef935be4d26334764a99e7ca1f797bef89c9bd6` (CI run 45339829162).** No AWS access, deployment, stack operation or live service invocation was performed.

- Step 4 — three reviewed synthetic examples are committed in `docs/samples/`: digital PDF (R01), two-column DOCX (R05), and image-only scanned PDF (R09). Each separates standard entities, optional custom entities, expected extracted text and parser-derived output. All carry `SYNTHETIC_MOCK` / `SYNTHETIC_EXPECTED_TEXT` labels. No Comprehend confidence scores or Textract Blocks are fabricated. Actual `AWS_CAPTURED` evidence remains a post-approval dev-deployment gate.
- Step 5 — frontend technical foundation is committed under `frontend/`: React 19, Vite, TypeScript, Cognito User Pool SRP sign-in module, session ID-token retrieval, API client sending the raw ID token (no Bearer prefix), runtime environment configuration and local mock mode. The shell is intentionally neutral; D16 requires visual direction approval before the dashboard design begins.
- No API/OpenAPI/JSON/SQS contracts or SAM resources were changed.
- Frontend typecheck and Vite production build passed GitHub Actions. Frontend has not been proven against a deployed Cognito pool or live API; mock mode is not authentication evidence.

## Phase A — Step 8 implementation

**Status: VERIFIED for repository implementation and CI (run 45342184687, exact head `89091acab94d8840f1247de3faad48cc1d8d48b6`). Live AWS execution intentionally NOT performed.**

- Replaced the P10 placeholder with a guarded deployment smoke script covering DoD B1–B5.
- Uses the synthetic golden documents: 4 digital PDFs, 3 DOCX, 2 scanned PDFs and one deliberately corrupt DOCX.
- Checks authenticated API access, creates a scoped smoke job, uploads ten files, waits for nine SCORED + one FAILED, checks required scored-candidate fields, and verifies an OPEN failed-jobs record for the corrupt file.
- Re-uploads one identical S3 key and verifies candidate count remains ten.
- Sends a missing-object S3-notification-shaped event to the parse queue and waits for retry/DLQ consumer persistence. The configured 900-second queue visibility means this check can take up to 35 minutes.
- Verifies score-descending candidate order.
- Safe by default: dry-run makes no AWS/API calls. Live execution requires --execute and a recruiter SMOKE_ID_TOKEN; production additionally requires --allow-prod.
- The live run creates test records/objects and does not clean them up, shortlist candidates or send SES email. It does not deploy infrastructure.
- Offline smoke-script tests are included in make verify; make smoke generates golden files before its default dry-run.

No live AWS evidence is claimed. Step 8's live acceptance run remains a later deployment gate after explicit approval.

## CI evidence

- Latest full Phase A audit CI run [45346661338](https://github.com/amit-cloudops-ai/resume-screener-pipeline/actions/runs/45346661338) passed on head `c8d7a2d16602e9f65c27136abc625c880672bafe` (3/3 jobs).
- `make verify`: **160 tests passed**; repository integrity, frozen contracts, generated golden document formats and CSV pagination regression passed. 601 warnings were emitted, all recorded as Botocore `datetime.utcnow()` deprecation warnings.
- `make golden-evaluate`: passed; 100% skill precision/recall (77 TP, 0 FP, 0 FN), 12/12 email, 12/12 experience within ±1 year and 3/3 top-1 ranking across three JDs. Evaluation is deterministic and uses synthetic mock entity fixtures, not live Textract/Comprehend. See `docs/PHASE_A_ACCURACY.md`.
- `sam validate --lint --template-file infra/template.yaml`: passed.
- `sam build --template-file infra/template.yaml`: passed; all nine Lambda CodeUri packages built.
- Final Step 4–5 CI run [45339829162](https://github.com/amit-cloudops-ai/resume-screener-pipeline/actions/runs/45339829162) passed on commit `2ef935be4d26334764a99e7ca1f797bef89c9bd6`: `make verify` (including sample-provenance tests), `make golden-evaluate`, frontend typecheck/build, SAM lint validation and SAM build.
- The local integration acceptance processed ten synthetic resume files and one JD. Nine candidates reached SCORED, one corrupt DOCX became FAILED, and persisted candidate/failed-job items passed their JSON schemas.
- The original backend integration run `45332343952` remains historical evidence; Phase A's latest full verification is run `45337062084`.

## Architecture and contract controls

- No OpenAPI, candidate/job/failed-job JSON schema or SQS message contract was changed.
- SQS body remains raw S3 notification JSON for parse/JD queues and `{job_id,candidate_id,reason}` for score queue.
- Candidate ID remains first 16 hex characters of SHA-256 over `job_id + "/" + s3_key`.
- API proxy responses use the configured CloudFront `CORS_ORIGIN`; DynamoDB Decimal values are serialized as JSON numbers.
- Permanent input failures are recorded in failed-jobs and acknowledged. Transient errors return partial-batch failures for retry.
- Logs contain request/message identifiers only; resume text and candidate PII are not logged.
- Parser uses Textract ClientRequestToken to reuse the same asynchronous job across retries and polls within Lambda execution limits.
- Upload object size is checked with S3 HeadObject before extraction; files larger than 5 MiB are rejected.
- Retry API supports PARSE, JD_PARSE and SCORE. Unsupported/unknown stages are returned as not automatically retryable.
- The optional custom Comprehend recognizer remains disabled unless a deployment supplies its endpoint ARN.

## Remaining release blockers

1. Phase A code and static infrastructure checks are green on the Phase A working branch. Keep PR #8 draft and unmerged until reviewed; the integration PR #6 remains its base workstream.
2. Step 7 recruiter frontend is VERIFIED by CI run 45344597945. Step 8 offline smoke automation is VERIFIED; live AWS smoke remains a post-deployment acceptance gate.
3. Golden-set deterministic accuracy is benchmarked and passed. Actual AWS-generated Comprehend samples and live OCR/model accuracy remain outstanding.
4. SES sender verification/production access is not confirmed.
5. No AWS account inventory has been performed; do not assume there are no existing resources.
6. No CloudFormation change set has been created or reviewed. Static SAM validation/build does not prove deployment-time resource graph or live IAM behaviour.
7. No AWS stack is deployed; Cognito, S3 notifications, Textract, Comprehend, SES, alarms and DLQ recovery have not been exercised in AWS.

## Deployment facts

- Region: `us-east-1` (architecture decision).
- Stack names: `rs-dev` and `rs-prod` (architecture decision).
- AWS account ID: NOT RECORDED.
- API URLs / CloudFront URLs: NOT RECORDED.
- Cognito pool/client IDs: NOT RECORDED.
- SES sender: NOT VERIFIED.
- Custom recognizer ARN: disabled by default; live state NOT VERIFIED.
- AWS deployment: NOT PERFORMED.

## Next sequence

1. Step 6: **COMPLETE** — Amit approved A — Editorial Hiring Desk on 24 November 2026; D16 and the approval record are updated.
2. Step 7: **VERIFIED** — complete recruiter dashboard implementation; CI run 45344840009 passed 3/3 jobs.
3. Step 8: **VERIFIED for repository implementation and offline CI** — live execution remains a post-deployment acceptance gate.
4. Step 9: **IMPLEMENTED** — architecture source, rendered SVG, cost worksheet and evidence note committed.
5. Step 10: VERIFIED — full repository release-readiness audit completed; findings fixed and documented in docs/PHASE_A_STEP10_FINAL_AUDIT.md.
6. Phase B begins with AWS account preflight and dev deployment only after Amit explicitly approves. Review the CloudFormation change set before execution and publish the frontend with make deploy-frontend STAGE=dev.
7. Validate live AWS integrations, resolve development findings, define data-retention policy, verify alarms/SES and complete the live smoke run.
8. Complete teammate clean-clone rehearsal and demo evidence; deploy rs-prod only after separate explicit production approval and successful development acceptance.

## Phase A — Step 6 approval

**Status: COMPLETE.** On 24 November 2026, Amit explicitly approved **A — Editorial Hiring Desk**. D16 is updated in docs/DECISIONS.md and the complete rationale/approval record is in docs/PHASE_A_STEP6_DESIGN_REVIEW.md. The selected system uses warm off-white surfaces, forest-green actions, Newsreader editorial headings and IBM Plex Sans UI/data typography.

## Phase A — Step 7 recruiter dashboard

**Status: VERIFIED — GitHub Actions run 45344840009 passed all three jobs.** The frontend contains the complete recruiter-facing workflow against the existing API routes: create/list jobs, submit a JD as text or PDF/DOCX/TXT, request presigned resume uploads, upload up to 50 PDF/DOCX files with per-file progress, search/filter/rank candidates, inspect profile and weighted score breakdown, shortlist with interview details, reject with confirmation, export shortlist CSV, and inspect/retry supported failed-job stages. No OpenAPI, JSON schema, SQS message or SAM resource was changed. DoD D1–D6 are checked for the implemented recruiter workflows. Local mock mode uses synthetic records and makes no AWS requests. The live Cognito/API integration remains unverified until an approved deployment.


## Phase A — Step 10 final repository audit

**Status: VERIFIED for repository readiness; Phase B development preflight is the next stage after explicit approval.** Final CI run [45346661338](https://github.com/amit-cloudops-ai/resume-screener-pipeline/actions/runs/45346661338) passed all three jobs on head `c8d7a2d16602e9f65c27136abc625c880672bafe`. The full audit, findings, corrections and evidence boundary are recorded in [docs/PHASE_A_STEP10_FINAL_AUDIT.md](PHASE_A_STEP10_FINAL_AUDIT.md).

- Fixed the shortlist CSV pagination query by removing an invalid partition-key FilterExpression and adding a two-page regression test.
- Added scripts/deploy_frontend.sh and make deploy-frontend; the workflow reads stack outputs, requires a completed stack, builds with mock mode disabled, syncs the dedicated stage frontend bucket and invalidates CloudFront. Production publish requires ALLOW_PROD=1.
- CI validates the deployment script with bash -n.
- Reviewed the API/data/SQS contracts, frontend/auth/API client, backend handlers, SAM resource graph/IAM, smoke runner, architecture and cost documentation.
- GitHub branch protection is currently disabled on main and the feature branch. Enable required PR/CI checks before merging the release candidate.
- Candidate/JD retention needs a production policy: S3 lifecycle expires resumes/ and parsed/ after 30 days, while JD objects and DynamoDB candidate/job records currently have no equivalent expiry.
- No AWS access, account inventory, CloudFormation change set, deployment, or live integration test was performed. Those are Phase B/production acceptance gates, not completed Phase A evidence.

## Phase A — Step 9 architecture and cost

**Status: IMPLEMENTED — repository documentation committed.** Artefacts: docs/architecture.mmd (editable source), docs/architecture.svg (rendered vector diagram), docs/COST.md (workload model and cost worksheet), and docs/PHASE_A_STEP9_ARCHITECTURE_AND_COST.md (completion/evidence note). The cost worksheet models OCR + standard Comprehend processing for 100, 500 and 2,000 resumes/month and separately highlights the cost of an always-on custom Comprehend endpoint. It does not claim an account-specific monthly bill. Re-price with AWS Pricing Calculator during Phase B preflight.

## Phase A — Step 8 boundary reaffirmed

Step 8 smoke automation remains VERIFIED for repository implementation and offline CI only. The live smoke run has not been performed. It creates a job, uploads synthetic documents and leaves test records/objects in the target stage; it must be run only after explicit deployment approval and with a planned cleanup window.
