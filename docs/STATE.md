# STATE — live project baseline (evidence-based)

Last updated: 2026-11-24
Integration branch: `feat/INT-full-pipeline-integration`
Integration PR: [#6 — complete backend pipeline](https://github.com/amit-cloudops-ai/resume-screener-pipeline/pull/6) (draft, not merged)
Submission target: 2026-11-25
AWS deployment: NOT PERFORMED; explicit deployment approval remains required.

## Status definitions
- `VERIFIED`: implementation exists on the integration branch and the named CI checks passed.
- `DONE-UNVERIFIED`: implementation exists, but a required runtime, account or deployment proof is absent.
- `DOING`: implementation or verification is still in progress.
- `TODO`: not implemented.
- A passing local/Moto test is not live AWS proof.

## Task board

| ID | Owner | Task | Status | Evidence / remaining gate |
|---|---|---|---|---|
| P1 | Amit | Repository, ownership rules and CI | VERIFIED | PR #6 CI runs `make verify`; direct edits stay on feature branch; main unchanged. |
| P2 | Amit | SAM infrastructure | VERIFIED | CI run 45332343952 passed SAM lint validation and build on current integration head f755f86bca29eeafb68083e47451c5943d69ecbc. Live CloudFormation change-set review remains. |
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
| A1 | Teammate A | Skills taxonomy | VERIFIED | `backend/parsing/skills_taxonomy.json`; alias normalization covered by tests. |
| A2 | Teammate A | Golden set (12 resumes) | TODO | Golden dataset not added; this remains a quality/accuracy gate. |
| A3 | Teammate A | PDF/DOCX/TXT extraction | VERIFIED | Textract async polling/pagination and DOCX paragraphs/tables implemented; mocked/unit tests pass. TXT is enabled for JD only. |
| A4 | Teammate A | Comprehend standard/custom entity extraction | VERIFIED | Standard/custom endpoint calls, UTF-8-safe 4.8 KB chunking and tests implemented. Live endpoint/service behaviour unverified. |
| A5 | Teammate A | Candidate/JD field derivation | VERIFIED | Name/email/employer/title/skills/experience derivation and overlap-union tests implemented. |
| A6 | Teammate A | Resume parse Lambda | VERIFIED | SQS partial-batch handling, deterministic candidate IDs, permanent failure records, parsed S3 artifact and score-queue producer implemented. |
| A7 | Teammate A | JD-parse Lambda | VERIFIED | Required skills/title/years, zero-skill failure, job state update and JD_READY fan-out implemented. |
| A8 | Teammate A | DLQ consumer Lambda | VERIFIED | Stage mapping, source-key resolution, idempotent failed-job persistence implemented. |
| A9 | Teammate A | Custom recognizer model/endpoint | TODO | Optional feature remains disabled; no training dataset or endpoint ARN. |
| A10 | Teammate A | Three reviewed sample outputs | TODO | Automated test artifacts exist, but reviewed sample deliverables are not recorded. |
| B1 | Teammate B | Scoring library + tests | VERIFIED | Deterministic 50/30/20 scorer, edge cases, title seniority, thresholds and schema fields covered. |
| B2 | Teammate B | Score Lambda | VERIFIED | SQS/DynamoDB handler, Decimal conversion, duplicate idempotency and RESCORE behaviour covered. |
| B3 | Teammate B | Jobs API + uploads | VERIFIED | Create/list/get, JD text/file, presigned resume URLs, validation, Cognito subject and CORS covered. Parser checks actual object size because presigned PUT itself does not impose a size range. |
| B4 | Teammate B | Candidates API | VERIFIED | Query, counts, decision filter, score-desc ordering and detail lookup covered. |
| B5 | Teammate B | Decision API + SES | VERIFIED | SCORED-only conditional decisions, interview validation, one-time SES invitation and email status covered with SES isolated in tests. |
| B6 | Teammate B | CSV export | VERIFIED | Exact header order, shortlist filtering, ranking and CSV output covered. |
| B7 | Teammate B | Failed-jobs API + retry | VERIFIED | GSI/scan listing, PARSE/JD_PARSE/SCORE retry routing, conditional state transition and frozen SQS payload reconstruction covered. |
| B8 | Teammate B | Written NLP explanation | VERIFIED | `docs/08_NLP_AND_SCORING.md` explains extraction, taxonomy, experience, scoring and limitations. |
| B9 | Teammate B | Contract tests | VERIFIED | Frozen schema/route tests plus API handler tests and integrated persisted-record validation. |

## CI evidence

- CI run `45332343952` passed on current integration head `f755f86bca29eeafb68083e47451c5943d69ecbc`.
- `make verify`: 138 tests passed; repository integrity and frozen contract checks passed.
- `sam validate --lint --template-file infra/template.yaml`: passed.
- `sam build --template-file infra/template.yaml`: passed; all nine Lambda CodeUri packages built.
- The local integration acceptance processed ten synthetic resume files and one JD. Nine candidates reached SCORED, one corrupt DOCX became FAILED, and persisted candidate/failed-job items passed their JSON schemas.
- Current PR #6 head has green CI: `make verify`, SAM lint validation and SAM build all passed in run `45332343952`.

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
3. Twelve-resume golden set and reviewed sample extraction outputs are missing; extraction/scoring accuracy is not yet benchmarked.
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

1. Confirm all checks on the latest PR #6 head are green.
2. Review final SAM template, IAM policies, event source mappings and CloudFormation change set.
3. Complete frontend, golden set, live smoke and reviewed sample outputs.
4. Request explicit approval for the non-production `rs-dev` deployment.
5. Prove live API auth, S3/SQS, Textract/Comprehend, scoring, decisions, SES, DLQ/retry and alarms.
6. Only then consider production deployment.
