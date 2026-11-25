# Part A: Understand (backend/parsing)

Turns a resume file in S3 into a structured candidate row, and a JD into structured job fields.

| Task | Files |
|---|---|
| A1 taxonomy | `skills_taxonomy.json` (182 skills, 30 titles, 6 seniority levels), `taxonomy.py` |
| A2 golden set | `../../fixtures/golden/` (12 resumes, labels, 3 JDs, expected ranking), `tools/make_golden.py` |
| A3 extraction | `extract.py` (Textract async for PDF, python-docx incl. tables for DOCX) |
| A4 Comprehend | `comprehend_client.py` |
| A5 fields | `fields.py` (name, email, skills, titles, employers, years) |
| A6 parse Lambda | `parse_handler.py` -> `parse_handler.handler` |
| A7 JD-parse Lambda | `jd_handler.py` -> `jd_handler.handler` |
| A8 DLQ consumer | `dlq_handler.py` -> `dlq_handler.handler` |
| A9 custom recogniser | `training/build_training_data.py`, `training/train_recognizer.py` (dry run by default) |
| A10 samples | `tools/sample_run.py` -> `docs/samples/` |
| shared | `errors.py`, `config.py`, `records.py`, `aws_io.py`, `s3_events.py` |

Part A never imports Part B code. `tools/scoring_reference.py` is an independent copy of the brief's section 7 formula, used only to check the golden ranking.

## Run the tests (WSL or Git Bash)
```bash
pip install -r backend/parsing/requirements-dev.txt
python -m pytest backend/parsing -q
python backend/parsing/tools/golden_eval.py --offline     # writes fixtures/golden/ACCURACY.md
```

## Contract alignment (verified against contracts/ on 25 Nov)
`records.py` and the handlers follow `candidate.schema.json`, `failed_job.schema.json` and `sqs_messages.md`:
every candidate row has `source_key`, `file_name`, `created_at`, `decision`; failed_jobs `stage` is one of
`TEXT_EXTRACT | COMPREHEND | PARSE | JD_PARSE | SCORE | UNKNOWN` (taken from the pipeline step, or from the DLQ source ARN);
score messages use `CANDIDATE_PARSED` (parse Lambda) and `JD_READY` (jd-parse Lambda); job ids are 12 hex characters; table
names are `rs-<stage>-candidates | -jobs | -failed-jobs`. `tests/test_contracts.py` validates the builders AND the rows the handlers
really write; it must run (not skip) on your machine. Never loosen a schema to make it pass.

## STILL TO CHECK (not in the contracts)
1. **job.schema.json** was not read when this was written: the job fields Part A writes are `required_skills`, `jd_titles`,
   `required_years` (0 = no requirement stated) and `status` (`JD_PARSED` / `FAILED`). `test_contracts.py` checks them property by property.
2. **Handler paths.** Modules are flat inside `backend/parsing/`; the template stubs must point at `parse_handler.handler`,
   `jd_handler.handler`, `dlq_handler.handler` (or rename the files to match the stubs).
3. **Env var names** (all in `config.py`, change only there): `CANDIDATES_TABLE`, `JOBS_TABLE`, `FAILED_JOBS_TABLE`, `SCORE_QUEUE_URL`,
   `COMPREHEND_ENDPOINT_ARN`, `STAGE`. Defaults follow the contract names above.
4. **Edge values:** no email -> `null`; unknown experience -> `0.0`; titles are stored normalised with seniority first (`senior devops engineer`).

## What Amit's template must provide
- Parse Lambda timeout >= 150 s (Textract poll cap is 100 s); SQS visibility timeout >= 6x that; parse concurrency limited to 5; small SQS batch size (a transient failure retries the whole batch; writes are idempotent).
- IAM per Lambda: `textract:StartDocumentTextDetection|GetDocumentTextDetection`, `s3:GetObject` on `resumes/*` `jd/*`, `s3:PutObject` on `parsed/*`, `comprehend:DetectEntities`, DynamoDB `GetItem|UpdateItem|PutItem|Query` on the 3 tables, `sqs:SendMessage` on score-queue (+ `sqs:GetQueueUrl` if `SCORE_QUEUE_URL` is not set).
- `python-docx` packaged with the parse and JD Lambdas (`requirements.txt`).
- DLQ consumer subscribed to all three DLQs (queue names must contain `parse`, `jd` or `score`).

## Honest status
- DONE and tested locally (68 tests): everything above except the items needing real AWS.
- STILL NEEDS A REAL AWS RUN (brief says so): A3 real run on 3 PDFs, A4 one real Comprehend call, A10 samples, and the AWS accuracy run (`golden_eval.py --bucket`). The offline 100% result uses clean text and my own labels, so it is a regression guard, not proof. OCR noise on the scanned files is untested until Textract runs.
- A9 (custom recogniser) is a stretch with a fallback; the training data is synthetic from our own taxonomy, so it cannot beat the taxonomy matcher without real annotated resumes.
- Known limits: words that are also skills (`react`, `express`, `spring`, `swift`, `ruby`, `excel`...) match only when capitalised, so "Swift delivery" at a sentence start can false-match; generic skills such as `monitoring` can match ordinary prose; DOCX text boxes are not read; two-column PDFs depend on Textract's reading order.
