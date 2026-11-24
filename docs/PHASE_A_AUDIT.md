# Phase A — Steps 1–3 audit record

Last updated: 2026-11-24
Working branch: `feat/phase-a-steps-1-3`
Base: `feat/INT-full-pipeline-integration`
AWS access: **NOT USED**. No AWS inventory, stack operation, change set, or deployment was performed.

## Step 1 — Backend and SAM infrastructure audit

### Findings and corrective changes

| Finding | Risk | Correction | Evidence |
|---|---|---|---|
| Skills taxonomy contained 56 canonical entries although the work split requires at least 150 | Coverage gaps and false negatives for common cloud/data/platform roles | Expanded taxonomy to 155 canonical skills and checked canonical/alias uniqueness | `tests/test_phase_a_quality.py::test_taxonomy_meets_work_split_minimum_and_has_no_alias_collisions` |
| Standard Comprehend `TITLE` entities were mapped to candidate job titles | False job titles because standard TITLE represents creative works, contrary to locked decision D12 | Removed standard TITLE as a job-title source; custom `JOB_TITLE` remains the supported source | `tests/test_phase_a_quality.py::test_standard_comprehend_title_is_not_treated_as_a_job_title`; updated legacy parser test |
| Experience parser did not support the specified `N+ years` fallback | Candidates with summary-only experience were left unscored for experience | Added fallback only when no explicit date intervals are present | `tests/test_phase_a_quality.py::test_experience_uses_n_plus_fallback_when_dates_are_absent` |
| Experience was capped at 60 years instead of the 40-year work-split requirement | Out-of-spec experience values | Set implementation cap to 40; frozen schema still permits up to 60, so no contract change was needed | `tests/test_phase_a_quality.py::test_experience_fallback_is_capped_at_40_years` and cap/date-union tests |
| Scoring numeric validation rejected DynamoDB `Decimal` values | Runtime scoring failure when numeric fields are read from DynamoDB | Accepted `Decimal` alongside int/float while continuing to reject bool | `tests/test_phase_a_quality.py::test_scoring_accepts_dynamodb_decimal_values` |
| Comprehend chunking did not follow the sentence-boundary guidance | Splitting mid-sentence can reduce entity extraction quality | Added sentence-first chunking with 4,500-character and 4,800-byte limits; oversized single sentences fall back to UTF-8-safe splitting | `tests/test_phase_a_quality.py` chunking tests |

### SAM/infrastructure static review

| Area | Static result | Live proof still required |
|---|---|---|
| Lambda packaging | Nine function packages/handlers are wired in SAM | Deployed invocation of each handler |
| S3 → SQS | Queue policies, bucket notifications and dependencies are defined | Real S3 event delivery |
| SQS retries | Visibility timeout is at least six times the consuming Lambda timeout; partial batch failures are configured for queue consumers | Real transient-failure and redrive behaviour |
| DLQs | Parse, JD and score DLQs plus consumer are defined | Real DLQ delivery, consumer persistence and alarm notification |
| DynamoDB | Three tables, key/index definitions and encryption settings are declared | Live reads/writes and authorization |
| IAM | Function-specific policies are scoped to required resources; Textract/Comprehend actions retain service-required resource scope | CloudFormation policy resolution and runtime AccessDenied tests |
| API Gateway/Cognito | Cognito authorizer is the default for API methods; CORS is configured | Live unauthenticated 401 and authenticated 200 |
| S3 security | Public access blocks, encryption and upload CORS are defined | Live bucket-policy and presigned-upload verification |
| CloudFront | Private frontend bucket, OAC and HTTPS distribution are defined | Live distribution and browser verification |
| Logs/alarms | 14-day log retention, DLQ alarms, Lambda error alarms and API 5XX alarm are defined | Test-fire each alarm and verify notification |
| Budget | Conditional AWS Budget resource is defined | Confirm budget and notification in account; budget is not a hard spending cap |
| SES | Sender parameter and IAM path are wired | Sender verification and production access approval |
| Custom Comprehend recognizer | Disabled by default, configurable through deployment parameter | Optional endpoint only if separately approved |

### Known design constraints retained

- Presigned PUT cannot enforce the maximum object size by itself. The parser checks S3 object size before extraction and rejects files over 5 MiB.
- The optional custom Comprehend recognizer remains disabled by default.
- No OpenAPI, JSON schema, or SQS message contract was changed.
- No new AWS service or runtime dependency was introduced.

### Step 1 status

Code-level audit and identified corrections are implemented on this working branch. Step 1 is **not complete until CI re-runs successfully on the latest head and the final code review is recorded**.

## Step 2 — Golden dataset

### Dataset contents currently committed

- 12 fictional resume source texts under `fixtures/golden/source/`.
- 4 labelled as digital PDF, 4 as two-column DOCX, and 4 as scanned PDF in `expected.json`.
- Hand-labelled expected fields: name, fake `example.com` email, skills, employer, title and experience.
- Three synthetic job descriptions with required skills, title/experience requirements and human-labelled expected top candidate.
- Deterministic mock entity fixtures to isolate parser field derivation from live Comprehend model behaviour.

All identities, employers, institutions and contact details are fictional.

### Important remaining artifact gate

The source text and labels are present. The 12 actual PDF/DOCX binary files must also be materialized and validated in their declared formats before Step 2 can be marked complete. The `mock_entities` fixtures are test inputs, **not actual Comprehend responses**. Actual service-generated samples belong to the post-deployment validation stage.

## Step 3 — Accuracy measurement

Automated golden evaluation has been added for:
- Skill precision and recall (micro-averaged across the 12 resumes).
- Email correctness (at least 11/12).
- Experience within ±1 year (at least 10/12).
- Top-ranked candidate matching the human-labelled top candidate for all three JDs.

The deterministic evaluation uses the synthetic mock entity fixtures for PERSON, ORGANIZATION and JOB_TITLE. Therefore, it measures taxonomy matching, email extraction, date-derived experience, deterministic field mapping and scoring/ranking. It does **not** measure live Textract OCR or Comprehend model accuracy.

Final metric values and CI run evidence will be recorded only after the full suite passes on the final Phase A branch head.

## Release boundary

Steps 1–3 are repository-only. Do not access AWS until the complete Phase A repository gate has passed. Do not merge PR #8 or deploy AWS without explicit approval.
