# Phase A — Step 9: architecture diagram and cost documentation

**Status:** IMPLEMENTED — repository artefacts committed.  
**Date:** 24 November 2026.  
**Scope:** documentation only; no AWS account access or deployment.

## Deliverables

1. docs/architecture.mmd — editable Mermaid source for the system architecture.
2. docs/architecture.svg — rendered, scalable vector architecture diagram.
3. docs/COST.md — workload-based cost worksheet, processing scenarios, cost controls, high-cost switches and AWS pricing references.

## Architecture coverage

The diagram reflects the locked architecture in docs/01_ARCHITECTURE.md and the deployed resource definitions in infra/template.yaml:

- Recruiter browser, React/Vite frontend, Cognito SRP identity and raw ID-token API authorisation.
- CloudFront and private S3 frontend origin.
- API Gateway REST and Jobs, Candidates, Decision, Export and Failed Jobs API Lambdas.
- Private uploads S3 bucket, job/candidate/failed-job DynamoDB tables.
- S3 event notifications to JD and resume SQS queues.
- JD parse, resume parse and deterministic score Lambda workers.
- Textract PDF text extraction, Comprehend standard entity detection and deterministic taxonomy fallback.
- Score queue, per-stage DLQs, DLQ consumer and failed-job persistence.
- SES shortlist email, CloudWatch logs/alarms, SNS notifications and AWS Budget alerts.
- Trust boundaries, encryption, retention, idempotency and optional custom recogniser cost controls.

## Cost model coverage

docs/COST.md documents the AWS service cost meters, workload assumptions, formulas and three processing scenarios (100, 500 and 2,000 resumes/month). It separates the OCR + standard Comprehend processing subtotal from the full infrastructure bill and explicitly excludes unknown request, storage, data transfer, logging and account-specific charges.

The cost document highlights the main cost hazard: a continuously running one-inference-unit synchronous Comprehend custom endpoint can cost approximately USD 1,296 per 30-day month at the published USD 0.0005 per IU-second rate, before model training/management. The architecture therefore retains CustomRecognizerArn=DISABLED as the default.

## Verification boundary

- Diagram source and rendered SVG are repository documentation artefacts.
- Cost calculations are deterministic from the stated assumptions.
- Pricing references point to AWS public pricing pages; rates and free-tier eligibility must be refreshed in the AWS Pricing Calculator before a change set is approved.
- No account-specific AWS usage, inventory, billing, or calculator estimate has been claimed.
- This step does not satisfy the live AWS acceptance criteria in Phase A Step 10 or Phase B.

## Review checklist

- [x] Architecture covers all major components and data flows from the locked architecture.
- [x] API, data, asynchronous processing, failure recovery and operational paths are represented.
- [x] Cost-sensitive optional services and default-off controls are documented.
- [x] Workload assumptions and per-service calculation formulas are explicit.
- [x] Pricing source links are included.
- [x] No live AWS evidence is fabricated.
