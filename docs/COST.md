# AWS cost model — Resume Screening Pipeline

**Planning date:** 24 November 2026  
**Region:** us-east-1 (US East — N. Virginia)  
**Currency:** USD, before tax  
**Status:** planning estimate only; no AWS account inventory or deployment has been performed.

This is a transparent workload model, not a quote or a promise of a monthly bill. Actual charges depend on the account's current AWS pricing plan, free-tier/credit eligibility, request sizes, page counts, retention, traffic, data transfer, log volume and regional rates. Re-price the design in the AWS Pricing Calculator immediately before creating a CloudFormation change set.

## 1. Cost-sensitive architecture choices

| Component | Current design | Cost behaviour | Guardrail |
|---|---|---|---|
| Textract | Async DetectDocumentText for PDF | Per page processed; scanned PDFs are the direct variable OCR cost | Reject oversized files before OCR; count pages and monitor monthly volume |
| Comprehend standard | DetectEntities on text chunks | Per 100-character unit, with a 300-character minimum per request | Keep sentence-aware chunk limit; avoid duplicate calls |
| Comprehend custom | Optional custom entity recogniser endpoint | Endpoint billed by provisioned inference units and elapsed seconds, including idle time | CustomRecognizerArn=DISABLED by default; do not create an endpoint for the baseline |
| Lambda | Python 3.12, x86_64, 256 MB global default; selected worker timeouts | Request count + GB-seconds | Queue-driven execution; reserved parse concurrency 5; review duration and memory |
| SQS | JD, parse, score queues + three DLQs | Request API usage; payload and retry volume affect request count | Batch size, visibility timeout, max receive count and DLQ alarms are explicitly configured |
| DynamoDB | Three on-demand tables | Read/write request units + stored data + backups/PITR | PAY_PER_REQUEST; inspect item size and retention |
| S3 | Private upload and frontend buckets | Storage, PUT/GET/LIST requests, data transfer | 30-day lifecycle for resumes/ and parsed/ objects; keep static frontend small |
| API Gateway REST | Cognito-authorized API | API calls + response data transfer | No API cache provisioned; use pagination if list sizes grow |
| CloudFront | HTTPS static frontend distribution | Data transfer + HTTP(S) requests and any optional features | Cache immutable assets; avoid enabling real-time logs without a need |
| Cognito | Recruiter user pool and app client | Monthly active users and selected tier/features | Recruiter-only access; no candidate accounts |
| SES | Shortlist interview emails | Per outbound email and optional message data / plan charges | Keep sender disabled until verified; send only on confirmed shortlist |
| CloudWatch / SNS | Logs, alarms and notifications | Log ingestion/storage, custom metrics, alarm and notification usage | 14-day log retention; alert on errors/DLQ depth; avoid logging resume content |
| AWS Budgets | Monthly budget alert | Budget feature itself is a notification control; underlying monitored service usage still bills | Default MonthlyBudgetUsd=25; alert is not a spending cap |

## 2. Explicit variable-cost worksheet

Use these formulas with the current rates selected in the AWS Pricing Calculator.

| Meter | Usage input | Formula |
|---|---|---|
| Textract DetectDocumentText | pdf_pages | pdf_pages × Textract_price_per_page |
| Comprehend standard entity detection | entity_units | entity_units × Comprehend_price_per_100_chars_unit |
| Lambda requests | lambda_requests | max(0, requests − eligible_free_requests) × request_price_per_million / 1,000,000 |
| Lambda compute | lambda_gb_seconds | max(0, GB_seconds − eligible_free_GB_seconds) × GB_second_price |
| API Gateway REST | api_requests | billable_requests × REST_price_per_million / 1,000,000 |
| S3 Standard storage | average_GB_month | GB_month × S3_storage_price_per_GB_month |
| S3 PUT/COPY/POST/LIST | write_requests | requests / 1,000 × PUT_price_per_1K |
| S3 GET | read_requests | requests / 1,000 × GET_price_per_1K |
| DynamoDB | read_units, write_units, storage_GB | On-demand RRU + WRU + storage + PITR/backup components |
| SQS | api_requests | Billable requests after applicable free tier × regional request rate |
| CloudFront | GB_out, http_requests, https_requests | Region-specific data transfer + request pricing / applicable plan allowance |
| SES Essentials plan | outbound_emails | Tiered plan price per 1,000 emails × billable recipient count |
| SES à-la-carte | outbound_emails | emails / 1,000 × $0.10 at the published à-la-carte rate, plus applicable data/features |
| CloudWatch | log_GB_ingested, retained_GB, custom_metrics | Ingestion + retention + metrics + alarms + dashboards |
| Custom Comprehend endpoint | IU_seconds | IU_seconds × $0.0005 at the published per-IU-second rate |

**Do not add the standard Comprehend free tier or any AWS Free Tier allowance to the baseline until the target account's eligibility and remaining allowance have been checked.** Free-tier terms vary by service and account age.

## 3. Worked processing scenarios

To make the document useful before account-specific calculator inputs exist, the table below isolates the two directly measurable NLP processing meters. It is intentionally not labelled as total monthly infrastructure cost.

### Assumptions

- Every resume is a PDF requiring text detection; this is a conservative OCR-heavy scenario. DOCX files use python-docx and do not incur Textract page charges.
- Average document length: 2 pages and 5,000 extracted characters per resume.
- Textract planning rate: **$0.0015 per DetectDocumentText page** (confirm the live us-east-1 rate in the calculator).
- Comprehend standard entity detection: **$0.0001 per 100-character unit** in the published example; 3 units minimum per request.
- At 5,000 characters, the 4,500-character chunking limit yields approximately 45 + 5 units = 50 units per resume.
- Custom Comprehend endpoint is disabled.
- The model excludes JD parsing, API/Lambda/SQS/DynamoDB/S3/CloudFront/CloudWatch/SNS/SES, data transfer, PITR, tax and any non-default add-ons.

| Resumes / month | Textract pages | Textract estimate | Comprehend units | Comprehend estimate | NLP subtotal |
|---:|---:|---:|---:|---:|---:|
| 100 | 200 | $0.30 | 5,000 | $0.50 | **$0.80** |
| 500 | 1,000 | $1.50 | 25,000 | $2.50 | **$4.00** |
| 2,000 | 4,000 | $6.00 | 100,000 | $10.00 | **$16.00** |

These totals are workload illustrations, not forecasts. The actual Textract count is driven by PDF pages, not the number of resumes. The actual Comprehend count is driven by text length and number of chunks/calls.

### Custom recogniser endpoint — high-cost switch

The published Comprehend pricing page states **$0.0005 per second per inference unit** for a synchronous endpoint. One continuously running inference unit therefore has an approximate compute charge of:

- 1 hour: $1.80
- 24 hours: $43.20
- 30 days: **$1,296.00**

This excludes model training and model management. The published page lists model training at $3/hour and custom model management at $0.50/month. The exact endpoint configuration and current regional rate must be confirmed before provisioning.

**Decision:** do not enable a custom recogniser endpoint for initial deployment. The deterministic taxonomy fallback is the guaranteed baseline. The endpoint must be treated as an explicit cost approval, not a default dependency.

## 4. Monthly fixed/usage floor and known exclusions

There is no honest fixed monthly total until the workload, AWS account, deployment configuration and current regional rates are known. The SAM template uses on-demand DynamoDB, serverless Lambda, standard SQS and S3; there is no always-on EC2 or NAT Gateway in the declared architecture. This avoids several common idle-hour cost sources.

The following are not zero-cost guarantees:
- CloudFront origin and internet transfer, API Gateway responses, and S3 request/data transfer.
- CloudWatch log ingestion, retention, custom metrics and alarms.
- DynamoDB point-in-time recovery, storage and request volume.
- SQS retries, DLQ retention and request volume.
- SES plan selection, email volume and optional features.
- AWS support, taxes, credits expiry and other account-level charges.

The default budget value in Makefile is USD 25/month. An AWS Budget alert is **not** a hard spending limit and does not stop resources or requests when the threshold is crossed.

## 5. Cost controls already present in the repository

- Region is locked to us-east-1; stack names are rs-dev and rs-prod.
- DynamoDB tables use PAY_PER_REQUEST.
- Parse Lambda has reserved concurrency 5.
- SQS queues have explicit visibility timeout and redrive policies.
- Uploads bucket expires resumes/ and parsed/ objects after 30 days.
- CloudWatch log retention is configured for 14 days in the SAM template.
- Budget alert defaults to USD 25 and optional email notification.
- Custom Comprehend endpoint defaults to DISABLED.
- SES sender defaults to DISABLED.
- Production deploy target requires ALARM_EMAIL and a non-disabled SES_SENDER.
- The docs/RESOURCES.md inventory and teardown instructions must be maintained for manual resources.

## 6. Pre-deployment calculator checklist

Before Phase B deployment, populate and attach an AWS Pricing Calculator estimate for each environment, then review:

1. Expected monthly resumes, average PDF pages, PDF/DOCX mix, and average extracted characters.
2. Number of JD uploads and Comprehend chunks per JD.
3. Expected API requests, recruiter MAUs and candidate rows per job.
4. Expected S3 storage, average retention and data transfer.
5. Lambda request counts, memory and measured average duration from dev.
6. DynamoDB reads/writes, storage and PITR.
7. SQS messages including retries and DLQ retention.
8. CloudFront egress/requests and CloudWatch log ingestion.
9. SES email plan, volume and attachment data.
10. Explicit custom endpoint decision: disabled or separately approved with an hourly/monthly ceiling.

Do not use the development bill as the production forecast without adjusting for production traffic, retention and availability requirements. Revisit the estimate after the first 7 days of dev metrics and again before production approval.

## 7. Pricing references

AWS public prices change. These are the source pages used for the planning model; use the calculator and current region selector for the final estimate.

- [AWS Pricing Calculator](https://calculator.aws/)
- [Amazon Textract pricing](https://aws.amazon.com/textract/pricing/)
- [Amazon Comprehend pricing](https://aws.amazon.com/comprehend/pricing/)
- [AWS Lambda pricing](https://aws.amazon.com/lambda/pricing/)
- [Amazon DynamoDB pricing](https://aws.amazon.com/dynamodb/pricing/)
- [Amazon S3 pricing](https://aws.amazon.com/s3/pricing/)
- [Amazon API Gateway pricing](https://aws.amazon.com/api-gateway/pricing/)
- [Amazon SQS pricing](https://aws.amazon.com/sqs/pricing/)
- [Amazon CloudFront pricing](https://aws.amazon.com/cloudfront/pricing/)
- [Amazon Cognito pricing](https://aws.amazon.com/cognito/pricing/)
- [Amazon SES pricing](https://aws.amazon.com/ses/pricing/)
- [Amazon CloudWatch pricing](https://aws.amazon.com/cloudwatch/pricing/)
- [Amazon SNS pricing](https://aws.amazon.com/sns/pricing/)

## 8. Evidence boundary

This cost model was prepared from the committed SAM template and architecture documents. No AWS account inventory, Price Calculator estimate tied to the user's account, CloudFormation change set, deployment, or live billing data was accessed or generated. The first account-specific estimate belongs in Phase B preflight, after explicit approval to inspect the AWS account.
