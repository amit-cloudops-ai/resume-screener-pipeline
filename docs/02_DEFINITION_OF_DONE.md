# 02 — Definition of Done (THE FINISH LINE)

The project is finished when every box is ticked with evidence (command output, screenshot, link) pasted in docs/STATE.md. Nothing else counts. Nothing beyond this list gets built.

## A. Deployed (production)
- [ ] A1. `make deploy-prod` from a clean checkout creates stack `rs-prod` in us-east-1 with zero manual console steps (except Cognito users + SES verification, documented in README).
- [ ] A2. Dashboard loads at the CloudFront HTTPS URL; login via Cognito works.
- [ ] A3. Any API call without a token returns 401; with a valid token returns 200.
- [ ] A4. S3 buckets have public access blocked; DynamoDB SSE enabled; each Lambda has its own least-privilege role.

## B. Pipeline works end to end (E2E acceptance run on prod)
Run `make smoke STAGE=prod` using fixtures: 1 JD + 10 resumes (4 digital PDF, 3 DOCX, 2 scanned PDF, 1 corrupt file).
- [ ] B1. 9 candidates reach status SCORED within 5 minutes; the corrupt file produces exactly 1 failed_jobs row (OPEN) and is visible on the dashboard.
- [ ] B2. Each scored candidate has: name, email (or explicit null), skills[], employers[], titles[], experience_years, score 0-100, score_breakdown, above_threshold.
- [ ] B3. Re-uploading the same file does not create a duplicate candidate.
- [ ] B4. A transient failure test (point a message at a missing object 3x) lands in the DLQ and DlqConsumer writes failed_jobs.
- [ ] B5. Candidates list is sorted by score descending.

## C. Accuracy (measured, not claimed)
Against fixtures/golden (12 hand-labelled resumes, 3 types):
- [ ] C1. Skill extraction recall >= 85% and precision >= 85% (after taxonomy normalisation).
- [ ] C2. Email extracted correctly in >= 11/12.
- [ ] C3. Experience years within +/-1 year of label in >= 10/12.
- [ ] C4. Score ordering: for the 3 golden JDs (A2) the top-1 candidate matches the human-ranked label.
- [ ] C5. Scoring unit tests cover every branch in docs/04_SCORING_LOGIC.md (incl. missing years, no title, empty skills).

## D. Dashboard
- [x] D1. Job list, create job, upload JD + resumes with progress.
- [x] D2. Candidate table sorted by score with taxonomy-derived skill tags and a score breakdown view.
- [x] D3. One-click Shortlist (with interview details form) and Reject; decision persisted with who/when.
- [x] D4. Shortlist sends SES email; email_status updated (SENT / FAILED / NO_EMAIL).
- [x] D5. Download shortlist CSV.
- [x] D6. Failed jobs view with error details.

## E. Reliability and ops
- [ ] E1. DLQ alarms and Lambda error alarms exist and have been test-fired once.
- [ ] E2. Logs contain no resume text or PII (spot-checked).
- [ ] E3. Budget alert configured; Any optional external NLP endpoint (if independently provisioned) has a documented delete step.

## F. Deliverables
- [ ] F1. Demo video (<= 8 min) showing the full flow on prod.
- [ ] F2. Sample Comprehend entity output for 3 resume types committed in docs/samples/.
- [ ] F3. Written NLP matching explanation + 3 enhancements (docs/04_SCORING_LOGIC.md finalised).
- [x] F4. Architecture diagram committed as a scalable vector (docs/architecture.svg) with editable source (docs/architecture.mmd); cost sheet committed (docs/COST.md).
- [ ] F5. README deployment instructions tested by a teammate from a clean clone.

## G. Cleanup readiness
- [ ] G1. docs/RESOURCES.md section 2 is complete and matches what exists in the console.
- [ ] G2. All stack resources carry the Project=resume-screener tag (Tag Editor shows them).
- [ ] G3. After submission: teardown done in order, Tag Editor returns 0 results.

## STOP RULE
When A-F are ticked: stop. Any new idea goes to "Parking lot" in docs/STATE.md.
