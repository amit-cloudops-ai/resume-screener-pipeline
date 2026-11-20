# 01 — Architecture (locked)

```
Recruiter (browser) -> CloudFront -> S3 (React app)
        |  Cognito login (JWT)
        v
API Gateway REST (Cognito authorizer) -> API Lambdas (Part B) -> DynamoDB / S3 presign / SES

S3 uploads bucket
  jd/{job_id}/{file}        -> S3 event -> SQS jd-queue     -> JdParse Lambda (A)
  resumes/{job_id}/{file}   -> S3 event -> SQS parse-queue  -> Parse Lambda (A)
                                                 |  (after 3 failed receives)
                                                 v
                                           parse-dlq -> DlqConsumer Lambda (A) -> failed_jobs

Parse Lambda: Textract (PDF) | python-docx (DOCX) -> Comprehend (standard + custom) -> taxonomy normalise
              -> DynamoDB candidates (status PARSED) + S3 parsed/{job_id}/{candidate_id}.json (audit)
              -> SQS score-queue {job_id, candidate_id, reason}
JdParse Lambda: same extraction -> DynamoDB jobs (required_skills, jd_titles, required_years, status JD_PARSED)
              -> enqueue score-queue for every existing candidate of that job (reason JD_READY)
Score Lambda (B): reads job + candidate -> writes score, breakdown, above_threshold, status SCORED
              (job not JD_PARSED yet -> raise -> SQS retry; after 5 receives -> score-dlq -> DlqConsumer)
```

## Resources (names are fixed; `<stage>` = dev|prod)
| Type | Name |
|---|---|
| Stack | `rs-<stage>` |
| S3 uploads | `rs-<stage>-uploads-${AWS::AccountId}` |
| S3 frontend | `rs-<stage>-frontend-${AWS::AccountId}` |
| DynamoDB | `rs-<stage>-jobs`, `rs-<stage>-candidates`, `rs-<stage>-failed-jobs` |
| SQS | `rs-<stage>-jd-queue`, `-parse-queue`, `-score-queue`, `-parse-dlq`, `-jd-dlq`, `-score-dlq` |
| Lambdas | `rs-<stage>-jd-parse`, `-parse`, `-score`, `-dlq-consumer`, `-api-jobs`, `-api-candidates`, `-api-decision`, `-api-export`, `-api-failed` |
| Cognito | user pool `rs-<stage>-recruiters`, app client `rs-<stage>-web` (no secret), group `recruiters` |
| API | REST API `rs-<stage>-api`, stage `v1`, Cognito User Pool authorizer on ALL routes |
| SES | verified sender identity (env `SES_SENDER`) |
| SSM params | `/rs/<stage>/custom-recognizer-arn` (value `DISABLED` = off; SSM cannot hold an empty string), `/rs/<stage>/threshold-default` (60) |

## Lambda env vars (every Lambda gets what it needs from this list; no others)
`STAGE`, `JOBS_TABLE`, `CANDIDATES_TABLE`, `FAILED_TABLE`, `UPLOADS_BUCKET`, `SCORE_QUEUE_URL`, `PARSER_VERSION`, `SCORER_VERSION`, `CUSTOM_RECOGNIZER_ARN`, `SES_SENDER`, `LOG_LEVEL`.

`CUSTOM_RECOGNIZER_ARN` rule: the custom recogniser is used ONLY when the value starts with `arn:aws:comprehend:`. Empty or `DISABLED` = skip it (taxonomy fallback only).

## Known AWS gotchas (Amit: handle these in template.yaml; they cause most "it deployed but nothing happens" bugs)
1. S3 -> SQS notifications: each queue needs a queue policy allowing `s3.amazonaws.com` (condition on the bucket ARN). Build the bucket name with `!Sub` (not `!Ref` of the bucket) inside the policy and in the notification config, or CloudFormation reports a circular dependency.
2. API Gateway + Cognito: the `Authorization` header carries the raw Cognito **ID token** (no `Bearer ` prefix). Enable CORS (incl. `Authorization` header) and add CORS headers to the gateway 4XX/5XX responses, otherwise a 401 shows up in the browser as a confusing CORS error.
3. SQS visibility timeout must be >= 6x the consuming Lambda timeout.
4. Textract async from Lambda needs `textract:StartDocumentTextDetection`, `textract:GetDocumentTextDetection` and `s3:GetObject` on `resumes/*`.
5. CloudFront + S3 frontend: use Origin Access Control, a custom error response mapping 403/404 to `/index.html`, and add the CloudFront domain to the uploads bucket CORS rules (presigned PUT).
6. SES sandbox: sender AND recipients must be verified until production access is granted.
7. CloudFormation cannot delete non-empty S3 buckets; teardown must empty them first (docs/RESOURCES.md).

## Queue settings
- parse-queue / jd-queue: visibility timeout 900s, maxReceiveCount 3, Lambda batch size 1, `ReportBatchItemFailures`, parse Lambda reserved concurrency 5 (Textract TPS), Lambda timeout 120s.
- score-queue: visibility timeout 180s, maxReceiveCount 5, batch size 5.
- DLQ retention 14 days.

## Error policy
- PERMANENT (unsupported type, corrupt file, empty text): write failed_jobs row (status OPEN), set candidate status FAILED, ACK the message (no retry).
- TRANSIENT (throttling, timeout, 5xx): raise so SQS retries. After maxReceiveCount message lands in DLQ; DlqConsumer writes failed_jobs row (stage from message source).
- All writes idempotent: candidate_id = first 16 hex of sha256(job_id + "/" + s3_key). Reprocessing the same object overwrites, never duplicates.

## Security
Block public access on both buckets; uploads bucket SSE-S3 + CORS for presigned PUT from the CloudFront domain; CloudFront uses OAC to read the frontend bucket; per-Lambda IAM roles scoped to the exact tables/queues/bucket prefixes; Cognito self-signup disabled (admin creates recruiter users); API Gateway throttling default 50 rps; uploads lifecycle: delete `resumes/` and `parsed/` after 30 days.

## Observability
CloudWatch log retention 14 days; alarms: each DLQ depth >= 1 -> SNS email; Lambda Errors >= 1 (5 min); API 5XX >= 1; AWS Budget alert on the account.
