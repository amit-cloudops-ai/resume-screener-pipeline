# SQS message contracts (FROZEN)

## parse-queue and jd-queue
Body = the raw S3 event notification JSON (S3 -> SQS direct). Handler reads `Records[0].s3.bucket.name` and `Records[0].s3.object.key` (URL-decoded).
Key formats: `resumes/{job_id}/{file_name}` and `jd/{job_id}/{file_name}`. Allowed extensions: .pdf .docx (.txt allowed for JD only). Max size 5 MB.

## score-queue
```json
{"job_id": "a1b2c3d4e5f6", "candidate_id": "0123456789abcdef", "reason": "CANDIDATE_PARSED"}
```
`reason` in: CANDIDATE_PARSED | JD_READY | RESCORE. Producer: parse Lambda (A), jd-parse Lambda (A), retry API (B). Consumer: score Lambda (B). Scoring is idempotent.

## DLQ messages
Original message body unchanged. DlqConsumer derives `stage` from the DLQ source ARN (parse-dlq -> PARSE, jd-dlq -> JD_PARSE, score-dlq -> SCORE) and `s3_key`/`job_id` from the body.
