# 01 — Architecture (implemented design and live status)

## Runtime flow

```text
Recruiter browser
  ├─ CloudFront HTTPS → private S3 React/Vite frontend
  └─ Cognito SRP sign-in → raw Cognito ID token
       └─ API Gateway REST (Cognito authorizer)
            └─ API Lambdas: jobs · candidates · decisions · export · failed jobs
                 ├─ DynamoDB: jobs · candidates · failed_jobs
                 ├─ S3 presigned uploads / parsed JSON artifacts
                 └─ SES shortlist email (implemented; live delivery not accepted)

S3 JD object → SQS JD queue → JD parse Lambda
  └─ document text → deterministic Python NLP → DynamoDB job criteria
       └─ SQS score queue (JD_READY fan-out)

S3 resume object → SQS parse queue → Resume parse Lambda
  ├─ DOCX → python-docx (live-observed working)
  └─ PDF → Amazon Textract async text detection (live dev blocked:
             SubscriptionRequiredException from StartDocumentTextDetection)
       └─ deterministic Python extraction
            ├─ DynamoDB candidate
            ├─ S3 parsed/{job_id}/{candidate_id}.json
            └─ SQS score queue → Score Lambda
                 └─ deterministic 50% skills / 30% title / 20% experience score

JD / parse / score queue failures → DLQs → DLQ consumer → failed_jobs table
CloudWatch logs/metrics and configured alert resources support operations.
```

The current parser does **not** use Amazon Comprehend. The integration implementation replaced managed NLP entity extraction with deterministic Python taxonomy, regex and date-range extraction. Amazon Textract remains the PDF extraction dependency in the current code.

## Live development evidence (25 November 2026)

- Recruiter dashboard loaded through the deployed CloudFront URL.
- A DevOps Engineer – Barclays (Pune) job reached `JD PARSED`.
- Three synthetic DOCX resumes were parsed and scored.
- Six PDF resumes remained in `PARSING`; the parse Lambda logs showed Textract `StartDocumentTextDetection` returning `SubscriptionRequiredException`.
- The frontend was built, uploaded to the dedicated dev frontend bucket and CloudFront invalidation reached `Completed`.
- Full live E2E acceptance did not pass. Production was not deployed or promoted.

See [PROJECT_CLOSEOUT.md](PROJECT_CLOSEOUT.md) and [STATE.md](STATE.md) for evidence, identifiers and remaining gates.

## Resources (names are fixed; `<stage>` = dev|prod)

| Type | Name |
|---|---|
| Stack | `rs-<stage>` |
| S3 uploads | `rs-<stage>-uploads-${AWS::AccountId}` |
| S3 frontend | `rs-<stage>-frontend-${AWS::AccountId}` |
| DynamoDB | `rs-<stage>-jobs`, `rs-<stage>-candidates`, `rs-<stage>-failed-jobs` |
| SQS | `rs-<stage>-jd-queue`, `-parse-queue`, `-score-queue`, `-parse-dlq`, `-jd-dlq`, `-score-dlq` |
| Lambdas | JD parse, resume parse, score, DLQ consumer, jobs/candidates/decision/export/failed APIs |
| Cognito | recruiter user pool and public app client |
| API | API Gateway REST API, stage `v1`, Cognito authorizer |
| SES | shortlist notification integration; sender/account verification required |
| SSM | `/rs/<stage>/threshold-default` |

## Queue and failure policy

- Parse/JD queues use long visibility timeouts and bounded receives; score queue has its own retry/DLQ policy.
- Permanent failures (unsupported, corrupt, empty) are recorded in failed_jobs and acknowledged.
- Transient service/network failures are retried and eventually sent to a DLQ.
- Candidate IDs are deterministic from job ID and S3 key, making same-object processing idempotent.
- Do not purge queues or delete records during incident recovery without an explicit reviewed plan.

## Security and operational controls

- Private S3 buckets with public access blocked; CloudFront OAC for frontend origin.
- Cognito authorizer protects API methods; recruiter ID token is sent raw in the Authorization header (no Bearer prefix).
- Lambda IAM roles are scoped to required tables, queues and S3 prefixes.
- SQS visibility timeout must be at least six times the consuming Lambda timeout.
- Uploads are limited to PDF/DOCX resumes and bounded to 5 MiB by parser-side object inspection.
- Resume screening is decision support; a human recruiter must review decisions.
- AWS Budget is an alert, not a hard spend cap.
- Resume and parsed artifact lifecycle is configured for 30 days; job/candidate record retention needs a separately approved policy.

## Known service dependency and remediation path

Textract currently blocks PDF parsing in the observed development account. The returned error is an account/service-access error; the available evidence does not prove that Textract is categorically excluded from AWS Free Tier or establish the exact account eligibility cause.

If account-independent PDF support is required, implement digital PDF text extraction locally and package a Lambda-compatible OCR engine for image-only scans. This is a proposed follow-up, not an existing feature.
