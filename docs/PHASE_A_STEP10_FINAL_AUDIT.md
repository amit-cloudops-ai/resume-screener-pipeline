# Phase A — Step 10: final repository release-readiness audit

**Audit date:** 24 November 2026  
**Working branch:** `feat/phase-a-steps-1-3`  
**Integration base:** `feat/INT-full-pipeline-integration`  
**Scope:** repository, application code, API/data/event contracts, SAM infrastructure, CI, deployment instructions and Phase A evidence.  
**AWS access:** NOT USED. No account inventory, CloudFormation change set, deployment, resource creation or live AWS API operation was performed.

## 1. Executive decision

**Step 10 repository gate: PASS, subject to the evidence and boundaries below.** The Phase A repository deliverables are complete and the code-level findings discovered during this audit have been corrected. The repository is ready to enter **Phase B — controlled AWS preflight and development deployment**, once Amit explicitly authorises that work.

This is not a production release approval. No repository-only audit can prove IAM policies resolve correctly in the target account, Cognito authorisation works against a deployed pool, S3 notifications reach SQS, Textract/Comprehend behave as expected on real documents, SES can deliver mail, alarms notify, or CloudFront serves the live application. Those are Phase B development acceptance gates. Production deployment remains a separate approval after development acceptance.

## 2. Audit scope and result

| Area | Review performed | Result |
|---|---|---|
| Branch and PR | Verified PR #8, base/head, merge status, ahead/behind relationship and main branch SHA | PASS — PR #8 remains draft/unmerged; feature branch is 121 commits ahead and 0 behind its integration base at audit start; main was not modified by this work |
| CI evidence | Inspected workflow run 45345024032 and all three job results on head 612db6b | PASS at pre-audit head — verify, frontend-build and sam-validate all succeeded |
| Python backend | Reviewed jobs, candidates, decision, export and failed-job APIs; parsing, JD parsing, DLQ and scoring paths | PASS after CSV pagination correction and regression test |
| API and data contracts | Reviewed OpenAPI routes, job/candidate/failed-job schemas and SQS message definitions | PASS — contracts remain frozen; no contract changes were required |
| Frontend | Reviewed API client, Cognito SRP flow, runtime config, dashboard workflows and upload path | PASS for typecheck/build and contract alignment; deployed Cognito/API and browser behaviour remain unverified |
| SAM infrastructure | Reviewed S3/SQS notifications and policies, queue redrive/visibility, Lambda event mappings, IAM, DynamoDB, Cognito, API Gateway, CloudFront OAC, logs, alarms, SNS, SES and Budget resources | PASS for static SAM lint/build; CloudFormation deployment and runtime IAM remain unverified |
| Smoke automation | Reviewed explicit execution gates, synthetic fixtures, retry/DLQ assertions and cleanup implications | PASS for offline implementation; live smoke remains a Phase B gate |
| Architecture and cost | Compared Mermaid/SVG and cost worksheet with locked architecture and SAM resource definitions | PASS as repository documentation; prices and account costs require recalculation before change-set approval |
| Deployment runbook | Checked whether stack creation also publishes the static frontend | Corrected — added guarded frontend publish script/Make target (see finding F-02) |

## 3. Findings and corrective actions

### F-01 — DynamoDB pagination in shortlist CSV export

**Severity:** High  
**Finding:** The second-page query supplied a `FilterExpression` against `job_id`, which is already the partition key in the `KeyConditionExpression`. DynamoDB Query does not allow a partition-key condition to be repeated in a filter expression. Exports could fail once the query required pagination.  
**Correction:** Removed the invalid filter expression. Added a regression test that simulates two query pages and asserts both pages are included without a partition-key filter.  
**Files:** `backend/api/export/app.py`, `backend/api/export/test_app.py`.  
**Status:** FIXED; final CI evidence is recorded below after the workflow completes.

### F-02 — Static frontend was not published by SAM deployment

**Severity:** High  
**Finding:** The SAM stack created a private frontend S3 bucket and CloudFront distribution, but `make deploy-dev` / `make deploy-prod` only deployed infrastructure. There was no documented or scripted step to build the React app with the deployed Cognito/API outputs, upload it to the bucket and invalidate CloudFront. A successful stack deployment could therefore still serve an empty frontend origin.  
**Correction:** Added `scripts/deploy_frontend.sh` and `make deploy-frontend`. The script reads the stack outputs, validates required API/Cognito/CloudFront values, confirms the destination bucket matches the stage-specific frontend naming convention, builds with `VITE_MOCK_API=false`, syncs only that dedicated frontend bucket, and submits a CloudFront invalidation. Production publishing requires the separate `ALLOW_PROD=1` opt-in. CI runs `bash -n` against the script.  
**Status:** IMPLEMENTED; syntax and CI evidence are recorded below after the workflow completes.

### F-03 — Documentation drift

**Severity:** Low  
**Finding:** README repeated the Step 8 CI limitation sentence and cited an earlier run as the latest full CI run.  
**Correction:** Update README and STATE to reference the final audit head and remove duplicated status text.  
**Status:** TO VERIFY in the final documentation commit.

## 4. Architecture and security review notes

The repository declares the intended security controls: private S3 buckets with public access blocks and server-side encryption, CloudFront OAC for the frontend origin, Cognito-authorised API methods, scoped Lambda roles, encrypted DynamoDB tables with point-in-time recovery, SQS redrive policies, and bounded log retention. Static validation does not prove the deployed policies or runtime behaviour.

The following design boundaries must remain explicit in Phase B:

1. The user pool is admin-create-only. The API Gateway Cognito authorizer authenticates tokens from that pool; the current single-workspace design does not implement per-job or multi-tenant authorisation. Do not add untrusted users to this pool.
2. The optional Comprehend custom endpoint remains disabled by default. Do not provision it without a separate cost approval.
3. SES remains disabled until the sender is verified and account sending status is approved. The production Make target requires a sender value and alarm email, but cannot itself prove SES account approval or recipient deliverability.
4. The USD 25 AWS Budget is a notification threshold, not a hard spending cap.
5. S3 lifecycle rules expire `resumes/` and `parsed/` objects after 30 days. JD objects and candidate/job records do not currently have an equivalent expiry policy. Confirm and document the candidate-data/JD retention and deletion policy before production use.
6. Candidate scoring is decision support, not an autonomous hiring decision. Human review and bias/fairness assessment remain necessary before operational use.

### F-04 — GitHub branch protection is not enabled

**Severity:** Medium  
**Finding:** GitHub reports branch protection disabled for both `main` and the Phase A working branch; required status checks are not enforced by repository rules. The current draft PR and explicit review boundary prevent this audit from merging anything, but repository settings do not technically prevent a future direct push or merge without CI.  
**Action:** Before merging the release candidate to `main`, enable a ruleset/branch protection requiring pull requests and the CI checks (`verify`, `frontend-build`, `sam-validate`), disallow force pushes, and require at least one approval where practical. This is a merge-governance gate, not a reason to access AWS during Phase A.  
**Status:** OPEN — GitHub settings were inspected read-only; no branch-protection setting was changed.

## 5. Phase B entry checklist

Phase B may begin only after Amit's explicit approval. The first work is account-aware preflight and a development deployment, not production deployment.

- [ ] Confirm AWS account identity, active region, existing `rs-` resources, budgets, credits and quota constraints.
- [ ] Re-price the architecture in AWS Pricing Calculator using actual workload assumptions; confirm the Comprehend custom endpoint remains disabled.
- [ ] Review the generated CloudFormation change set and IAM/resource replacements before execution.
- [ ] Deploy `rs-dev`; record stack ID, outputs and every resource in `docs/STATE.md` / `docs/RESOURCES.md`.
- [ ] Build and publish the frontend using `make deploy-frontend STAGE=dev`; verify CloudFront HTTPS URL and browser loading.
- [ ] Verify unauthenticated API 401 and valid recruiter ID-token API 200; verify recruiter provisioning and first-login flow.
- [ ] Verify S3 presigned uploads, S3-to-SQS delivery, Textract digital/scanned PDF extraction, DOCX parsing and Comprehend field extraction on real samples.
- [ ] Verify candidate scoring, decision persistence, SES sender behaviour, CSV export pagination, failed-job retry and DLQ persistence.
- [ ] Test-fire operational alarms and confirm SNS delivery; confirm budget notification configuration.
- [ ] Run the live Step 8 smoke workflow against dev, retain its job ID, and execute the documented cleanup.
- [ ] Inspect CloudWatch logs for resume text/PII; review access controls, retention, error rates and cost metrics.
- [ ] Resolve development findings and rehearse the complete deployment from a clean clone before production approval.

## 6. Production-only gates that remain open

These are not silently waived by the Phase A repository PASS:

- Live production deployment and HTTPS dashboard verification.
- Cognito 401/200 proof and live service integrations.
- SES sender verification and production sending access.
- Alarm test evidence and budget notification evidence.
- Live end-to-end smoke acceptance.
- Demo video and teammate clean-clone deployment rehearsal.
- Candidate-data retention/deletion policy and bias/fairness review.
- AWS resource inventory and teardown verification after the demonstration.

The unchecked items in `docs/02_DEFINITION_OF_DONE.md` remain unchecked until their required evidence exists. Do not convert static CI results into live AWS evidence.

## 7. Final evidence

The final audit head and CI run will be recorded here after the audit documentation and deployment workflow changes are committed. The passing workflow must include:
- `make verify` including the new paginated CSV export regression test;
- `make golden-evaluate`;
- `bash -n scripts/deploy_frontend.sh`;
- frontend TypeScript/production build;
- SAM lint validation and SAM build.

**Release boundary:** PR #8 remains draft and unmerged. Do not merge it, access AWS, create a CloudFormation change set or deploy any stage without the next explicit approval.
