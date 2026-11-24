# STATE — live project baseline (evidence-based; update after every task)

Last updated: 2026-11-24
Current gate: Repository and infrastructure readiness; AWS deployment is blocked until all repository gates pass.
Submission target: 2026-11-25.

## Baseline rules
- A branch, PR description, or teammate status message is not proof that a feature is integrated or verified.
- `DONE-UNVERIFIED` means implementation exists in a branch/PR but has not been independently verified end to end.
- `VERIFIED` requires reproducible test output or live AWS evidence recorded below.
- No AWS deployment is authorized by this status document.

## Task board
| ID | Owner | Task | Status | Evidence / next gate |
|---|---|---|---|---|
| P1 | Amit | Repo, CODEOWNERS, CI | DONE-UNVERIFIED | Repository exists; current CI runs make verify. Branch protection and full PR policy not evidenced. |
| P2 | Amit | SAM infrastructure | DOING | PR #1 template inspected. API Events nesting and Jobs Scan IAM defects fixed on feat/P2-infrastructure-readiness; SAM validation/build pending CI. |
| P3 | Amit | Cognito recruiter setup | DONE-UNVERIFIED | User pool, app client and recruiter group are defined in SAM; no deployed pool/user evidence. |
| P4 | Amit | API Gateway + Cognito authorizer | DONE-UNVERIFIED | REST API and default Cognito authorizer are defined; no live 401/200 proof. |
| P5 | Amit | SES identity and production access | TODO | No verified sender or production-access evidence in repo. |
| P6 | Amit | Frontend shell + mocks | TODO | frontend contains README/.gitkeep only. |
| P7 | Amit | Frontend pages | TODO | Not implemented in committed baseline. |
| P8 | Amit | CloudFront deployment | DONE-UNVERIFIED | Distribution/OAC/bucket policy are defined in SAM; no live URL or upload evidence. |
| P9 | Amit | Alarms / budget | DONE-UNVERIFIED | Alarm and budget resources are defined; no deployed alarm test or notification proof. |
| P10 | Amit | E2E smoke test | TODO | tests/e2e/smoke.py is a placeholder; no live smoke test. |
| P11 | Amit | Integration | TODO | No end-to-end integrated environment evidence. |
| P12 | Amit | Demo, diagram, cost sheet, README | TODO | Deliverables not evidenced as complete. |
| A1 | Teammate A | Skills taxonomy | TODO | No implementation evidence on main/P2 baseline. |
| A2 | Teammate A | Golden set (12) | TODO | fixtures/golden contains .gitkeep only. |
| A3 | Teammate A | Text extraction | TODO | Parser implementation not integrated. |
| A4 | Teammate A | Comprehend module | TODO | Parser implementation not integrated. |
| A5 | Teammate A | Field derivation | TODO | Parser implementation not integrated. |
| A6 | Teammate A | Parse Lambda | TODO | Current P2 branch has a stub. |
| A7 | Teammate A | JD-parse Lambda | TODO | Current P2 branch has a stub. |
| A8 | Teammate A | DLQ consumer Lambda | TODO | Current P2 branch has a stub. |
| A9 | Teammate A | Custom recogniser | TODO | Optional integration only; no training/endpoint evidence. |
| A10 | Teammate A | Three sample outputs | TODO | Not evidenced. |
| B1 | Teammate B | Scoring library + tests | DONE-UNVERIFIED | PR #2 exists; reported tests are not independently rerun or merged. |
| B2 | Teammate B | Score Lambda | DONE-UNVERIFIED | PR #3 exists and depends on B1; reported tests are not independently rerun or merged. |
| B3 | Teammate B | Jobs API + uploads | DONE-UNVERIFIED | PR #4 exists; known IAM Scan, CORS, upload-size and JD integration gaps remain under review. |
| B4 | Teammate B | Candidates API | TODO | Branch inspected contained a stub; implementation reported locally is not committed. |
| B5 | Teammate B | Decision API + SES | TODO | Branch inspected contained a stub; implementation not committed. |
| B6 | Teammate B | CSV export | TODO | No implementation evidence. |
| B7 | Teammate B | Failed-jobs API + retry | TODO | No implementation evidence. |
| B8 | Teammate B | Written NLP explanation | TODO | Source notes exist in docs/04; final deliverable not evidenced. |
| B9 | Teammate B | Contract tests | TODO | Only base contract/fixture validation exists; full API contract tests not evidenced. |

## Verified evidence
- Repository file contents and open PR/branch state were inspected through GitHub on 2026-11-24.
- The P2 SAM template contains five API function definitions whose `Events` blocks were outside `Properties`; corrected on `feat/P2-infrastructure-readiness`.
- The API Jobs Lambda used DynamoDB Scan in B3 while its P2 IAM policy omitted `dynamodb:Scan`; permission added on `feat/P2-infrastructure-readiness`.
- CI workflow on `feat/P2-infrastructure-readiness` now includes SAM lint validation and SAM build steps. These checks have NOT yet run.
- No SAM validate/build, `make verify`, AWS deployment, live API auth, S3 event, queue, Textract, Comprehend, SES or E2E execution has been evidenced in this session.

## Blocked / critical gaps
1. SAM validation and build must pass before any AWS deployment.
2. Parsing Lambdas, candidates/decision/export/failed API handlers and frontend are still missing or stubbed in the inspected branches.
3. B3 requires CORS response headers and enforced 5 MB object-size validation before parsing; presigned PUT URL alone does not enforce the limit.
4. Failed-job retry semantics must be reconciled with the frozen failed-job and SQS message contracts before implementation is considered complete.
5. Contract changes require a DECISIONS.md entry and explicit approval from all three owners; no contract change is approved by this status update.
6. AWS account inventory and deployed stack state have not been inspected. Do not assume no resources exist.

## Deployed environment facts
- Region: us-east-1 (architecture decision).
- Stack names: rs-dev and rs-prod (architecture decision).
- AWS account ID: NOT RECORDED.
- rs-dev API URL / CloudFront URL: NOT RECORDED.
- rs-prod API URL / CloudFront URL: NOT RECORDED.
- Cognito pool/client IDs: NOT RECORDED.
- SES sender / production access: NOT VERIFIED.
- Custom recogniser ARN: DISABLED by template default; live state NOT VERIFIED.

## Next task sequence
1. Finish P2 SAM template validation, build and IAM/resource audit.
2. Reconcile B1/B2/B3 PRs against contracts and SAM CodeUri/permissions.
3. Complete Part A parsing and Part B API implementation; resolve contract blockers explicitly.
4. Build frontend, integration and E2E coverage.
5. Only after repository gates pass, inspect AWS account resources and deploy rs-dev.
6. Prove dev E2E and operational alarms before considering rs-prod.
