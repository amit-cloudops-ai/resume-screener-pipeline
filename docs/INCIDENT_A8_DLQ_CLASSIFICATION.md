# A8 incident: DLQ classification diagnostics

**Incident window:** 24 November 2026 (UTC)  
**Affected stage:** `rs-dev`  
**Task:** A8 — DLQ consumer Lambda  
**Status:** Code correction verified by local `make verify` (167 passed) and GitHub Actions CI run #221; PR #15 approved for merge. Live `rs-dev` deployment and acceptance remain pending.

## Observed impact

Three failed-job records were persisted by `rs-dev-dlq-consumer`:

- One Barclays JD record (`job_id=474d8d653e9c`) was classified as `JD_PARSE`, with four attempts.
- Two records were persisted with `stage=UNKNOWN`, `job_id=unknown`, and `s3_key=unknown`.

The consumer's CloudWatch invocations completed without logged exceptions. All three DLQ event-source mappings were enabled and pointed to the expected queues.

## Confirmed implementation defect

The deployed consumer classified source queues using loose string suffix checks against `eventSourceARN`. It then caught every exception from S3-notification parsing and replaced the stage with `UNKNOWN` without preserving the reason. Invalid score payloads were also reduced to `UNKNOWN` without a useful diagnostic. The persisted record contained a generic error message and omitted the source ARN and classification reason.

The failed-job schema is frozen and has `additionalProperties: false`; this correction therefore does not add DynamoDB attributes or alter any contract. It stores a bounded diagnostic in the existing `error_message` field and emits structured CloudWatch logs containing message ID, source ARN, stage and reason only. Message bodies and candidate/resume PII must never be logged.

## Historical root-cause boundary

The original SQS message bodies and event metadata for the two historical UNKNOWN records were not retained. Their exact historical classification failure cannot be reconstructed from the remaining DynamoDB records and CloudWatch logs. Do not claim that a particular missing field or malformed payload caused those records.

The Barclays JD's earlier parser failure is separately explained by the missing `CANDIDATES_TABLE` environment variable, which was subsequently added to the deployed JD parser configuration. Reprocessing that JD and verifying successful downstream scoring remains outstanding.

## Correction

The A8 correction:

1. Reads the standard `eventSourceARN` field and tolerates the casing alias `eventSourceArn`.
2. Classifies only the exact known project queue names for dev/prod parse, JD and score DLQs.
3. Validates S3 object key prefixes and job-scoped key shape before extracting job identity.
4. Records safe, bounded diagnostics for malformed S3 notifications, malformed score payloads and unrecognized/missing source queues.
5. Emits structured logs without logging message bodies or PII.
6. Preserves idempotent failed-job writes and the frozen failed-job schema.
7. Adds regression coverage for all queue types, event-source field casing, malformed payloads, wrong key prefixes, missing/unrecognized source metadata and duplicate delivery.

## Verification and release gates

- [x] GitHub Actions `make verify` passes on this branch (run #221; commit `b9be4d9788200e6b94129665dc55a691a7ef38ac`).
- [x] Review PR diff and CI results; no contract or SAM resource changes.
- [x] Human approval to merge received; merge operation is the next repository action.
- [ ] Deploy only to `rs-dev` after explicit approval.
- [ ] Verify deployed Lambda package hash/configuration matches the merged artifact.
- [ ] Exercise controlled parse, JD and score DLQ fixtures in dev and inspect diagnostic logs.
- [ ] Safely recover and reprocess the Barclays JD; verify `JD_PARSED` and downstream candidate scoring.
- [ ] Resolve historical UNKNOWN records only after deciding whether they can be safely repaired; do not purge or blindly redrive them.
- [ ] Keep `rs-prod` untouched until all dev acceptance and separate production release gates pass.
