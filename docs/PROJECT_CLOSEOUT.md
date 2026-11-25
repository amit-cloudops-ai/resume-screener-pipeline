# Project closeout — implementation demonstrated to date

**Date:** 25 November 2026  
**Repository:** [amit-cloudops-ai/resume-screener-pipeline](https://github.com/amit-cloudops-ai/resume-screener-pipeline)  
**Integrated source:** PR #6 merged to `main` as `edf3b25a57c12b7427a628c6f797b3f4ca230463`  
**Environment:** AWS `rs-dev`, `us-east-1`  
**Purpose:** provide a mentor-ready, accurate record of the implemented application and its current live limitations.

## Executive summary

The Resume Screener is an AWS-based event-driven application with a React recruiter interface, Cognito authentication, API Gateway/Lambda APIs, S3 uploads, SQS processing, DynamoDB persistence, deterministic Python NLP and explainable candidate scoring.

The development application is deployed and has been demonstrated with a real recruiter session. A job description was parsed successfully. Nine synthetic resumes were uploaded to that job. Three DOCX resumes were parsed and scored. Six PDF resumes did not complete because the parser's Amazon Textract `StartDocumentTextDetection` request returned `SubscriptionRequiredException`.

This is therefore a **working partial development prototype**, not a fully accepted all-format pipeline and not a production release.

## What was implemented

### Recruiter-facing application
- Cognito SRP sign-in, including temporary-password challenge handling.
- React/Vite/TypeScript dashboard.
- Job creation and job listing/detail views.
- JD input/upload and resume batch upload through presigned S3 URLs.
- Candidate review with extracted fields, skills, score and decision state.
- Shortlist/reject workflow, shortlist CSV export and failed-job views/retry.
- Static frontend deployment to private S3 origin behind CloudFront.

### Backend
- API Gateway REST routes protected by Cognito authorizer.
- Separate Lambda handlers for jobs, candidates, decisions, CSV export and failed-job operations.
- S3 object storage, presigned upload flow and S3-to-SQS event path.
- SQS queues for JD parsing, resume parsing and scoring, with dead-letter queues.
- JD parsing and resume parsing Lambda handlers.
- DynamoDB tables for jobs, candidates and failed jobs.
- Parsed JSON artifacts in S3.
- Deterministic Python extraction using a skills taxonomy, regex-based email/name/title/employer logic and date-range experience calculation.
- Deterministic explainable scoring: 50% skill match, 30% title match and 20% experience match.
- Failure persistence, retry routing and DLQ consumer implementation.

### Managed AI services and design evolution
The initial design explored Amazon Comprehend for entity extraction and Amazon Textract for PDF text extraction/OCR.

- **Comprehend:** removed from the integration implementation. The current integration code uses deterministic Python extraction and does not require Comprehend at runtime.
- **Textract:** remains in the current PDF path. The live development account returned a service-access exception when the parser called `StartDocumentTextDetection`.
- **DOCX:** uses `python-docx` and was observed working in the live development test.
- **Potential follow-up:** local PDF text extraction for digital PDFs and a Lambda-compatible local OCR engine for image-only PDFs. This is not implemented in the closeout snapshot and must not be described as an existing capability.

## Live demonstration record

### Job description
- Job title: DevOps Engineer – Barclays (Pune)
- Job ID: `474d8d653e9c`
- Dashboard status: `JD PARSED`

### Resume batch
Nine valid synthetic resumes were uploaded. The dashboard showed nine candidate rows:

| Format | Count | Observed result |
|---|---:|---|
| DOCX | 3 | Three candidate profiles extracted and scored |
| Digital PDF | 4 | Did not complete; parse path invokes Textract |
| Scanned PDF | 2 | Did not complete; parse path invokes Textract |
| **Total** | **9** | **3 scored, 6 parsing at time of inspection** |

Three displayed candidate scores were 64.3, 41.4 and 39.5. One observed candidate profile also exposed extraction-quality issues: Karan Mehta's resume stated six years, while the UI showed 6.9 years; employer extraction showed “Not extracted”. These are known parser-quality defects requiring correction and regression tests.

### Queue and Lambda evidence

At the time of inspection:
- Parse queue: 0 visible messages, 6 not visible, 0 delayed.
- Score queue: 0 visible, 0 not visible, 0 delayed.
- Parse and score event source mappings were both `Enabled`.
- Parse Lambda logs contained repeated `SubscriptionRequiredException` errors from Textract.
- Score Lambda had successfully processed the three DOCX-derived candidates.

The six messages were not shown as successfully processed. Do not purge queues or delete their candidate/source records. A safe replay plan should be designed only after a corrected parser is deployed.

### Frontend publish evidence
The frontend was built from the release worktree:
- `npm install` succeeded.
- `npm run typecheck` succeeded.
- `vite build` succeeded.
- Assets synced to `rs-dev-frontend-924422830139`.
- CloudFront invalidation submitted for `E3NI28CL1V2SX4`.
- Invalidation status later returned `Completed`.
- Development URL: https://d2sdkmafcw9mpe.cloudfront.net

The frontend drawer has a known rendering defect in the source: a score string includes literal `<small>/100</small>`, which React displays as text. The candidate list score display is separate and correctly formatted. The dashboard also does not currently poll candidate status automatically; manual refresh is required to retrieve newer server state.

## AWS environment and release boundary

Known development references:
- Stack: `rs-dev`
- Region: `us-east-1`
- Frontend CloudFront: `E3NI28CL1V2SX4`
- Frontend URL: https://d2sdkmafcw9mpe.cloudfront.net
- Frontend bucket: `rs-dev-frontend-924422830139`
- Upload bucket: `rs-dev-uploads-924422830139`
- API: `https://pidp0mxkc6.execute-api.us-east-1.amazonaws.com/v1/`
- Cognito pool: `us-east-1_ItQy4aUwI`

The last previously confirmed CloudFormation stack status was `UPDATE_COMPLETE` at 2026-11-25 03:10:15 UTC, before the later frontend publish. The frontend publish did not deploy the backend. The exact Lambda/template version currently live has not been reconciled to main-branch merge commit `edf3b25a`; do not claim that the complete integration branch was deployed.

**No production deployment or promotion was performed as part of this closeout.** `rs-prod` remains separate and untouched. This work does not authorize stack changes, queue purges, data deletion or production deployment.

## CI and repository verification

Repository checks before integration merge:
- Integration commit `d409eed9abf7ccf25424ede85259e07fc59caf42`: CI run `45558256875` passed `sam-validate`, `frontend-build` and `verify`.
- Phase A audit CI run `45346661338`: three jobs passed; 160 tests, golden evaluation, frontend typecheck/build, SAM lint/build and deployment-script syntax validation.
- Synthetic deterministic NLP evaluation: skill precision/recall 100% (77 TP, 0 FP/FN), email 12/12, experience within ±1 year 12/12, top-1 ranking 3/3.
- Local Moto scenario: one JD and ten resumes -> nine scored and one failed corrupt DOCX.

These are repository/CI/local integration results. They are not a substitute for live AWS validation. In particular, the golden evaluation does not demonstrate live Textract OCR quality.

## Remaining work (explicitly not claimed complete)

1. Fix candidate profile score JSX so the numeric score and denominator render as separate elements.
2. Add bounded polling/backoff while candidates are processing.
3. Correct experience overlap/range handling and employer extraction against reviewed fixtures.
4. Resolve Textract access with AWS or implement local digital-PDF extraction plus packaged OCR for scanned PDFs.
5. Add regression coverage for digital, scanned, multi-page, empty and corrupt PDFs.
6. Reconcile the live Lambda code/template with the intended integration commit.
7. Review a CloudFormation change set before any backend deployment.
8. Safely recover/reprocess the six existing PDF candidates after the parser fix.
9. Complete the live smoke test: successful processing, duplicate protection, corrupt-file failure persistence and DLQ recovery.
10. Verify SES, alarms, budget notifications, retention/deletion policy, security controls and cost exposure.
11. Complete human-review and bias/fairness assessment before any real hiring use.
12. Keep production deployment as a separate approval after development acceptance.

## Mentor-facing status

The project is merged into GitHub `main` and demonstrates a deployed AWS recruiter workflow with working authentication, job-description parsing, DOCX resume processing and candidate scoring. The event-driven infrastructure, APIs, deterministic extraction, scoring and recovery paths are implemented and have repository-level CI/local test evidence. The remaining live blocker is PDF/OCR processing: the current Textract API call is rejected by the development account with `SubscriptionRequiredException`. The project is being presented as a working partial prototype with this limitation explicitly documented, not as a fully completed production system.
