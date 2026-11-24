# STATE — live project baseline (evidence-based)

Last updated: 2026-11-24
Integration branch: `feat/INT-full-pipeline-integration`
Integration PR: [#6 — complete backend pipeline](https://github.com/amit-cloudops-ai/resume-screener-pipeline/pull/6) (draft, not merged)
Phase A working branch: `feat/phase-a-steps-1-3`
Phase A PR: [#8 — Phase A steps 1–3](https://github.com/amit-cloudops-ai/resume-screener-pipeline/pull/8) (draft, base `feat/INT-full-pipeline-integration`, not merged)
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
| P6 | Amit | Frontend shell + mocks | TODO | `frontend/` still contains only its scaffold/readme. |
| P7 | Amit | Recruiter frontend pages | TODO | Not implemented. |
| P8 | Amit | CloudFront deployment | DONE-UNVERIFIED | Distribution/OAC/bucket policy are defined in SAM; no live URL or browser proof. |
| P9 | Amit | Alarms / budget | DONE-UNVERIFIED | Alarm and budget resources are defined; no deployed alarm/notification proof. |
| P10 | Amit | Live E2E smoke script | TODO | Existing live smoke script remains a placeholder; local integration acceptance exists separately. |
| P11 | Amit | Backend integration | VERIFIED | Moto acceptance on CI run 45331272201: one JD + ten resumes -> nine SCORED candidates + one FAILED candidate; candidate and failed-job records validate against frozen schemas. |
| P12 | Amit | Demo, architecture diagram and cost sheet | TODO | Not evidenced as complete. |
| A1 | Teammate A | Skills taxonomy | VERIFIED | `backend/parsing/skills_taxonomy.json`; 160 canonical skills, 231 canonical/alias terms, no collisions; taxonomy test passes. |
| A2 | Teammate A | Golden set (12 resumes) | TODO | 12 synthetic resumes committed as source text and reproducibly materialized as 4 digital PDFs, 4 two-column DOCX and 4 raster-only scanned PDFs; 3 labelled JDs and `expected.json`; CI validates generated files. |
| A3 | Teammate A | PDF/DOCX/TXT extraction | VERIFIED | Textract async polling/pagination and DOCX paragraphs/tables implemented; mocked/unit tests pass. Golden generator validates digital PDF, image-only scanned PDF and two-column DOCX. TXT is enabled for JD only; live Textract remains unverified. |
| A4 | Teammate A | Comprehend standard/custom entity extraction | VERIFIED | Standard/custom endpoint calls and UTF-8-safe 4.8 KB chunking implemented. Text is chunked at sentence boundaries up to 4,500 characters where possible. Live endpoint/service behaviour unverified. |
| A5 | Teammate A | Candidate/JD field derivation | VERIFIED | Name/email/employer/title/skills/experience derivation and overlap-union tests implemented; custom `JOB_TITLE` only (standard Comprehend `TITLE` ignored); `N+ years` fallback; 40-year implementation cap. Golden deterministic metrics pass. |
| A6 | Teammate A | Resume parse Lambda | VERIFIED | SQS partial-batch handling, deterministic candidate IDs, permanent failure records, parsed S3 artifact and score-queue producer implemented. |
| A7 | Teammate A | JD-parse Lambda | VERIFIED | Required skills/title/years, zero-skill failure, job state update and JD_READY fan-out implemented. |
| A8 | Teammate A | DLQ consumer Lambda | VERIFIED | Stage mapping, source-key resolution, idempotent failed-job persistence implemented. |
| A9 | Teammate A | Custom recognizer model/endpoint | TODO | Optional feature remains disabled; no training dataset or endpoint ARN. |
| A10 | Teammate A | Three reviewed sample outputs | TODO | Automated test artifacts exist, but reviewed sample deliverables are not recorded. |
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

## CI evidence

- Phase A CI run [45337062084](https://github.com/amit-cloudops-ai/resume-screener-pipeline/actions/runs/45337062084) passed on PR #8 merge commit `99462daee207a6cd10a6319c1a270d0753ad07f2`, containing Phase A branch head `904f4ab6972032cd86687e02deb4699a8df0f37c`.
- `make verify`: 153 tests passed; repository integrity, frozen contracts and generated golden document formats passed. 601 warnings were emitted, all recorded as Botocore `datetime.utcnow()` deprecation warnings.
- `make golden-evaluate`: passed; 100% skill precision/recall, 12/12 email, 12/12 experience within ±1 year and 3/3 top-1 ranking. See `docs/PHASE_A_ACCURACY.md`.
- `sam validate --lint --template-file infra/template.yaml`: passed.
- `sam build --template-file infra/template.yaml`: passed; all nine Lambda CodeUri packages built.
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

1. Code and static infrastructure checks are green on the current integration head. Keep PR #6 draft until review and the remaining release gates are addressed.
2. Recruiter frontend and the live E2E smoke workflow remain unimplemented.
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

1. Continue Phase A with Step 4 — reviewed extraction sample deliverables and service-mock boundary documentation.
2. Complete Step 5–9: frontend foundation/design, recruiter dashboard, live smoke implementation, architecture/cost documentation.
3. Complete Step 10 repository release-readiness audit and verify the exact final Phase A branch head.
4. Only after the full Phase A gate passes, request explicit approval for AWS account preflight and `rs-dev` deployment.
5. Validate live AWS integrations, resolve development findings and freeze a production release candidate.
6. Deploy `rs-prod` only after explicit production approval and successful development acceptance.
