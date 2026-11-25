# Project state — closeout snapshot

**Last updated:** 25 November 2026  
**Closeout branch:** `docs/project-closeout-2026-11-25`  
**Integration source commit:** `d409eed9abf7ccf25424ede85259e07fc59caf42` on `feat/INT-full-pipeline-integration`  
**Integration PR:** [#6](https://github.com/amit-cloudops-ai/resume-screener-pipeline/pull/6) — open, draft, unmerged at time of closeout  
**AWS region:** `us-east-1`  
**Production:** `rs-prod` not modified by this closeout

## Status vocabulary

- **LIVE-OBSERVED:** directly observed in the deployed development environment.
- **REPO/CI-VERIFIED:** implementation and named repository checks passed; this is not live AWS proof.
- **BLOCKED-LIVE:** runtime path was attempted and failed due to an observed live service/account error.
- **NOT-VERIFIED:** no sufficient runtime evidence.
- **NOT-DEPLOYED:** not promoted to the target environment.

## Live development evidence

| Component / action | Status | Evidence |
|---|---|---|
| Recruiter frontend | LIVE-OBSERVED | CloudFront URL loaded recruiter workspace and candidate dashboard |
| Frontend build | LIVE-OBSERVED | `npm run typecheck` and Vite production build passed |
| Frontend S3 publish | LIVE-OBSERVED | Files synced to `rs-dev-frontend-924422830139` |
| CloudFront invalidation | LIVE-OBSERVED | Distribution `E3NI28CL1V2SX4`, status `Completed` |
| JD creation and parsing | LIVE-OBSERVED | Job `474d8d653e9c`, “DevOps Engineer – Barclays (Pune)”, displayed `JD PARSED` |
| DOCX resume parsing | LIVE-OBSERVED | Karan Mehta, Vikram Shetty and Meera Deshpande extracted from DOCX files |
| Candidate scoring | LIVE-OBSERVED | Three candidate scores displayed: 64.3, 41.4 and 39.5 |
| PDF parsing / OCR | BLOCKED-LIVE | Textract `StartDocumentTextDetection` returned `SubscriptionRequiredException` |
| Remaining six PDF messages | BLOCKED-LIVE | Dashboard showed 6 `PARSING`; parse queue: 0 visible, 6 not visible; score queue: 0 |
| Full live E2E acceptance | NOT-VERIFIED | The 9-valid + corrupt-file acceptance scenario did not complete successfully |
| Latest integration backend deployment | NOT-VERIFIED | Frontend was published from the release worktree; the live backend version was not proven to match integration commit `d409eed9` |
| Production stack | NOT-DEPLOYED | No production deployment or promotion performed in this closeout |

### Textract incident evidence

Observed in `/aws/lambda/rs-dev-parse` on 25 November 2026 around 06:28 UTC:

```text
botocore.exceptions.ClientError:
An error occurred (SubscriptionRequiredException)
when calling the StartDocumentTextDetection operation:
The AWS Access Key Id needs a subscription for the service
```

The parser wraps this as `TransientProcessingError("Textract request failed")`, so SQS retries the messages. The queue snapshot at inspection time showed six messages not visible, consistent with in-flight/visibility-timeout retry behaviour.

**Interpretation:** the evidence establishes that the current account/runtime cannot complete the Textract operation. It does not establish that Textract is universally unavailable on Free Tier or why this account is receiving the exception. Do not claim a confirmed account eligibility cause without AWS Support/account evidence.

## Implemented application scope

### Recruiter experience
- Cognito SRP sign-in and temporary-password challenge.
- React/Vite/TypeScript recruiter dashboard.
- Jobs list/detail, JD creation, resume batch upload and per-file progress.
- Candidate review, search/filter, score and score explanation.
- Shortlist/reject workflow, shortlist CSV export and failed-upload view/retry.

### Backend and data flow
- API Gateway REST API with Cognito authorizer.
- API Lambda handlers for jobs, candidates, decisions, CSV export and failed jobs.
- S3 uploads and frontend buckets; presigned uploads and S3 event notifications.
- SQS JD, parse and score queues with DLQs and redrive policies.
- JD parse and resume parse Lambdas.
- DynamoDB jobs, candidates and failed-jobs tables.
- Deterministic Python extraction: skill taxonomy, regex-based fields, date/experience parsing.
- Deterministic 50/30/20 scoring (skills/title/experience).
- Parsed JSON audit artifacts in S3.
- DLQ consumer and stage-aware retry implementation.
- CloudWatch logging/metrics and infrastructure definitions for alerts and AWS Budget notifications.
- SES integration is present in code/infrastructure but live delivery is not accepted/verified; sender/account status remains a gate.

### AI/document service decisions
- Amazon Comprehend entity extraction was removed from the integration implementation; deterministic Python NLP is used instead.
- Amazon Textract remains the PDF text-detection dependency in the current parser.
- DOCX uses `python-docx`.
- A local digital-PDF extraction plus local OCR alternative is a future remediation, not part of this deployed snapshot.

## Repository / CI evidence

The following are historical repository/CI checks on the working integration/Phase A line; they must not be described as live AWS acceptance:

- Integration commit: `d409eed9abf7ccf25424ede85259e07fc59caf42`.
- Integration CI run `45558256875`: `sam-validate`, `frontend-build` and `verify` passed.
- Phase A repository audit run `45346661338`: three CI jobs passed; 160 tests, golden evaluation, frontend typecheck/build, SAM lint/build and frontend script syntax check.
- Deterministic synthetic golden evaluation: 100% skill precision/recall (77 TP, 0 FP/FN), 12/12 email extraction, 12/12 experience within ±1 year, and 3/3 expected top-ranked candidates. These are synthetic deterministic-NLP metrics, not Textract live OCR accuracy.
- Local Moto integration scenario: one JD and ten resumes -> nine scored and one failed corrupt file. This is local integration evidence, not the failed live AWS scenario.

## Known issues and limitations

1. **PDF/OCR unavailable in the current live dev account:** Textract call returns `SubscriptionRequiredException`; digital and scanned PDF uploads are therefore not currently accepted end-to-end.
2. **No local PDF/OCR fallback yet:** implement and test a digital PDF text extractor and a Lambda-compatible local OCR option if account-independent PDF support is required.
3. **Candidate extraction quality:** observed Karan Mehta profile displayed 6.9 years although the synthetic resume states 6 years; employer extraction displayed “Not extracted”. These require regression tests and parser correction.
4. **Candidate drawer score markup:** the frontend rendered literal `<small>/100</small>` inside the score string. This is a confirmed JSX rendering defect in the integration source.
5. **No automatic candidate polling:** the frontend refreshes on load/manual refresh and does not poll while candidates remain in parsing. Dashboard state can appear stale; this does not resolve backend failures.
6. **Live backend version not reconciled:** do not assume the latest integration code/template is deployed just because the frontend was built from the release worktree.
7. **Live E2E incomplete:** no all-file-type acceptance, duplicate upload acceptance, corrupt-file/DLQ recovery acceptance or complete B1–B5 sign-off.
8. **Production gates remain:** SES sender/account verification, alarms/notifications, retention policy, security review, fairness/bias assessment, clean-clone deployment rehearsal and controlled production approval.

## AWS development environment — observed references

| Item | Value |
|---|---|
| Region | `us-east-1` |
| CloudFormation stack | `rs-dev` |
| Last previously confirmed stack status | `UPDATE_COMPLETE` (2026-11-25 03:10:15 UTC; this predates the later frontend publish) |
| Frontend URL | https://d2sdkmafcw9mpe.cloudfront.net |
| CloudFront distribution | `E3NI28CL1V2SX4` |
| Frontend bucket | `rs-dev-frontend-924422830139` |
| Uploads bucket | `rs-dev-uploads-924422830139` |
| API URL | https://pidp0mxkc6.execute-api.us-east-1.amazonaws.com/v1/ |
| Cognito user pool | `us-east-1_ItQy4aUwI` |
| API ID | `pidp0mxkc6` |
| Job ID used for live test | `474d8d653e9c` |

This is an observed reference list, not a fresh inventory. Recheck stack outputs and resources before any future update. The USD 25 budget setting previously recorded is an alert, not a hard cap.

## Closeout boundary and next steps

This closeout records what exists and what was observed. It does not:
- deploy, update, delete or promote AWS resources;
- change `rs-dev` or `rs-prod`;
- purge SQS queues, delete candidate records or remove test uploads;
- claim production readiness or full E2E acceptance.

Recommended follow-up, in order:
1. Fix candidate drawer JSX score rendering and add a component regression test.
2. Add bounded polling/backoff for candidate status while parsing is in progress.
3. Correct experience/employer extraction against labelled fixtures.
4. Implement local digital-PDF extraction and a Lambda-compatible OCR path, or resolve Textract access with AWS before continuing to use it.
5. Add parser regression tests for digital PDFs, image-only PDFs, multi-page files, corrupt/empty files and DOCX.
6. Reconcile deployed Lambda code/template to the intended commit; review a CloudFormation change set before any deployment.
7. Recover/reprocess the six existing PDF records only after the corrected parser is deployed and a safe, idempotent replay plan is reviewed.
8. Run the complete live smoke test and record actual results.
9. Keep production separate until all acceptance, security, cost, privacy and operational gates are approved.
