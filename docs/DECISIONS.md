# DECISIONS (locked — do not re-debate; to change one, add a new entry signed off by all 3 owners)

| # | Decision | Why |
|---|---|---|
| D1 | IaC = AWS SAM (single `infra/template.yaml`) | Fastest, auto-rollback, one owner (Amit). Terraform = post-deadline enhancement |
| D2 | Region us-east-1; stacks `rs-dev`, `rs-prod` | Full Textract/Comprehend custom/SES coverage |
| D3 | Python 3.12 for all Lambdas; React + Vite frontend | Team skill + speed |
| D4 | API = API Gateway REST with Cognito User Pool authorizer | Matches spec literally |
| D5 | Frontend login = Cognito user pool via amazon-cognito-identity-js (custom form, SRP) | No hosted-UI redirect complexity |
| D6 | PDF -> Textract async (start+poll inside Lambda); DOCX -> python-docx | Textract can't read DOCX; sync API is single-page only |
| D7 | Queue-driven: S3 -> SQS -> Lambda for jd and parse; score via score-queue; DLQ per queue | Spec + resilience |
| D8 | No shared Python package / Lambda layer; coupling only via `contracts/` + `fixtures/` | Prevents fix-one-break-another across owners |
| D9 | Candidates sorted in API Lambda (query partition by job_id), no GSI | Hundreds of rows per job; simpler |
| D10 | Scoring is deterministic and explainable (docs/04); no LLM in the scoring path | Auditable |
| D11 | Custom recogniser is optional via `CUSTOM_RECOGNIZER_ARN`; taxonomy dictionary is the guaranteed fallback | Training/endpoint cost + time risk |
| D12 | Job titles do NOT come from Comprehend built-in TITLE (creative works only) | Wrong entity type |
| D13 | candidate_id = first 16 hex of sha256(job_id + "/" + s3_key) | Idempotency |
| D14 | Deploy by `make deploy-*` from Amit's machine; GitHub Actions runs tests only | Time; OIDC deploy = parking lot |
| D15 | Default threshold 60, per-job override | Simple |
| D16 | Dashboard visual direction approved by Amit on 2026-11-24: A — Editorial Hiring Desk | Approval required before P6/P7 design; approval recorded in docs/PHASE_A_STEP6_DESIGN_REVIEW.md |
| D17 | All AWS resources tagged Project=resume-screener; hand-made resources logged in docs/RESOURCES.md; teardown = delete stacks + section 2 items | One-pass, provable cleanup |
| D18 | contracts/openapi.yaml is OpenAPI 3.1 (needed for JSON Schema type arrays/const via $ref) and is validated in `make verify` | Real validity, not just file presence |
| D19 | `make verify` = repo check (no empty/missing files) + contract validation + tests; CI runs it on every PR | Guards against a broken import/commit |
