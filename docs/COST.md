# AWS cost model — Resume Screening Pipeline

**Planning date:** 24 November 2026; status note updated 25 November 2026  
**Region:** us-east-1 (US East — N. Virginia)  
**Currency:** USD, before tax  
**Status:** planning model plus limited live development observations. This is not an account bill, quote or complete forecast.

Actual charges depend on account age, free-tier/credit eligibility, current pricing plan, request volume, PDF page count, retention, traffic, data transfer and regional rates. Re-price in the AWS Pricing Calculator before any additional deployment or production approval.

## 1. Current service design and cost implications

| Component | Current design/status | Cost behaviour | Guardrail |
|---|---|---|---|
| Textract | Async DetectDocumentText for PDFs; live dev call currently returns SubscriptionRequiredException | Per page processed; no successful PDF OCR volume was demonstrated in the observed test | Do not retry manually at scale; resolve account access or implement local extraction |
| Comprehend | Removed from integration implementation; deterministic Python extraction is used | No Comprehend runtime usage in current integration code | Do not budget Comprehend calls for this implementation unless reintroduced by a reviewed change |
| Comprehend custom | Not part of current implementation | Provisioned endpoints can incur ongoing inference-unit charges | Do not provision |
| Lambda | Python 3.12, x86_64; worker timeouts and concurrency configured in SAM | Requests + GB-seconds | Queue-driven execution; monitor duration, errors and concurrency |
| SQS | JD, parse, score queues + three DLQs | API requests and retry volume | Bounded retries, visibility timeout and DLQ monitoring |
| DynamoDB | Three on-demand tables | Read/write units, storage and backups/PITR | PAY_PER_REQUEST; review retention and item sizes |
| S3 | Private upload and frontend buckets | Storage, requests and transfer | 30-day lifecycle for resumes/ and parsed/ artifacts |
| API Gateway / CloudFront | REST API and HTTPS static frontend | API calls, HTTP requests and data transfer | Avoid unnecessary caching/logging features |
| Cognito | Recruiter user pool and app client | Monthly active users and tier/features | Recruiter-only access |
| SES | Shortlist email integration; live delivery not accepted | Email plan/volume | Keep sender disabled until verified and account sending status is confirmed |
| CloudWatch / SNS | Logs, metrics, alarms/notifications | Log ingestion, retention, metrics, alarms, notifications | 14-day log retention; avoid logging resume contents |
| AWS Budgets | Alert threshold configured in template | Notification control, not a hard service limit | USD 25 setting is an alert, not a spending cap |

## 2. Cost worksheet

Use current calculator rates and actual workload assumptions.

| Meter | Usage input | Formula |
|---|---|---|
| Textract DetectDocumentText | pdf_pages | pdf_pages × current regional price per page |
| Lambda | requests, GB-seconds | eligible usage × current request/compute rate |
| API Gateway REST | api_requests | billable requests × regional REST rate |
| S3 | GB-month, PUT/GET requests, transfer | storage + requests + transfer |
| DynamoDB | reads, writes, storage, PITR | on-demand reads/writes + storage + backup |
| SQS | API requests, retries | billable requests × regional request rate |
| CloudFront | GB out, HTTP(S) requests | regional transfer + request pricing |
| Cognito | monthly active users | current tier and MAU pricing |
| SES | outbound messages | current plan or à-la-carte rate |
| CloudWatch | log GB, metrics, alarms | ingestion + retention + metrics + alarms |

**Comprehend standard/custom rows from the earlier design are intentionally excluded from the current baseline because Comprehend was removed from the integration implementation.** A future local OCR package may increase Lambda package size, memory and duration; measure it before estimating.

## 3. Cost-control facts and limitations

- The project uses serverless Lambda, SQS, S3, API Gateway and on-demand DynamoDB; there is no always-on EC2/NAT Gateway in the declared baseline.
- Resume and parsed artifact objects have a 30-day lifecycle in the template.
- CloudWatch log retention is configured for 14 days.
- SES sender defaults to disabled.
- Comprehend custom endpoint is not required by the current code.
- The default USD 25 AWS Budget is an alert, not a spending cap or automatic shutdown.
- A Free Tier label does not guarantee that every service/API is available to every account. Confirm the account's current plan and eligibility before depending on a managed service.

## 4. Live evidence boundary

The development environment has been used for recruiter sign-in, job-description parsing, DOCX parsing and three candidate scores. The observed PDF parser call to Textract failed with `SubscriptionRequiredException`; do not infer a billable successful OCR workload from those failed attempts. No account-level Cost Explorer or Billing report is included in this document.

## 5. Pre-production calculator checklist

1. Monthly JD and resume volumes, PDF/DOCX mix and PDF page distribution.
2. Expected API requests, recruiter MAUs and candidate rows per job.
3. S3 object size, retention, request volume and CloudFront transfer.
4. Lambda duration/memory measured from dev after PDF path is fixed.
5. DynamoDB reads/writes, storage and PITR.
6. SQS retries and DLQ retention.
7. CloudWatch log ingestion, metrics, alarms and SNS notifications.
8. SES plan, sender status and expected mail volume.
9. Account-specific free-tier/credit eligibility and existing account usage.
10. Explicit approval for any managed AI service or provisioned endpoint.

## 6. Pricing references

- [AWS Pricing Calculator](https://calculator.aws/)
- [Amazon Textract pricing](https://aws.amazon.com/textract/pricing/)
- [AWS Lambda pricing](https://aws.amazon.com/lambda/pricing/)
- [Amazon DynamoDB pricing](https://aws.amazon.com/dynamodb/pricing/)
- [Amazon S3 pricing](https://aws.amazon.com/s3/pricing/)
- [Amazon API Gateway pricing](https://aws.amazon.com/api-gateway/pricing/)
- [Amazon SQS pricing](https://aws.amazon.com/sqs/pricing/)
- [Amazon CloudFront pricing](https://aws.amazon.com/cloudfront/pricing/)
- [Amazon Cognito pricing](https://aws.amazon.com/cognito/pricing/)
- [Amazon SES pricing](https://aws.amazon.com/ses/pricing/)
- [Amazon CloudWatch pricing](https://aws.amazon.com/cloudwatch/pricing/)

