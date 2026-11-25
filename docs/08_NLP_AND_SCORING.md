# NLP, Extraction and Explainable Scoring

This document explains the deterministic extraction and ranking pipeline used by the Resume Screener. It is an implementation explanation, not a claim that every managed AWS integration has been exercised in a live account.

## 1. Processing stages

A recruiter creates a job and uploads a job description (JD) and resumes. S3 stores the original files under the frozen prefixes `jd/{job_id}/` and `resumes/{job_id}/`. S3 object-created notifications publish the raw S3 event envelope to the corresponding SQS queue. Queue consumers process one document at a time and use partial-batch failure reporting so an isolated bad message can be retried without silently acknowledging it.

The parser distinguishes a permanent input failure from a transient service failure. Unsupported formats, corrupt documents, empty extracted text and a JD with no usable required skills are permanent failures. Throttling, service unavailability and network errors are transient; they are allowed to retry and eventually move to the configured dead-letter queue. The DLQ consumer records the stage, source key, error category, bounded diagnostic message, attempts, message ID and creation time in the failed-jobs table. Resume text and other candidate PII must never be written to CloudWatch logs.

## 2. Text extraction

### PDF

PDF documents use Amazon Textract asynchronous text detection. The parser starts a document-text-detection job against the S3 object, then retrieves the result pages after completion. Asynchronous extraction is appropriate for multi-page PDFs and avoids relying on a synchronous response that may not contain the complete document. The implementation must handle pagination using Textract's `NextToken`, preserve block order, and treat a successful job with no meaningful text as an `EMPTY_TEXT` failure.

Textract output is structured blocks, not a clean resume. The parser combines LINE text in document order and retains the raw provider response in the parsed artifact for auditability. It must not log the text itself.

### DOCX

DOCX documents are read with python-docx. Paragraphs and table cells both matter: resumes frequently place contact details, skills and employment history in tables. The extractor should preserve a stable reading order and normalise whitespace without discarding section boundaries. A corrupt or encrypted document is recorded as a permanent parsing failure rather than retried indefinitely.

### Upload size and type

The upload API issues short-lived presigned PUT URLs for PDF and DOCX files. A presigned PUT URL does not, by itself, impose the application's maximum byte size. Therefore the parser must call S3 HeadObject and reject any object larger than 5 MiB before invoking Textract or DOCX parsing. The accepted extensions and MIME types must agree with the upload API and frozen queue contract.

## 3. Deterministic entity and skill extraction

The parser does not call Amazon managed NLP entity service or any other managed NLP entity service. It derives fields locally in Python so parsing behaviour is reproducible, has no per-request managed NLP entity service cost, and does not depend on a trained endpoint.

Skills are extracted from raw text using the controlled `skills_taxonomy.json`. Canonical names and aliases are matched case-insensitively with explicit token boundaries, then deduplicated and sorted. The taxonomy is versioned and changes should be reviewed against the golden resume set.

Email extraction uses a conservative regular expression. Titles are detected with a bounded set of role-pattern expressions. Names are accepted only from conservative standalone name-like lines; employers are accepted only from explicit labels such as `Company:` or `Employer:`. Missing or uncertain values remain null or empty rather than being guessed. The parser writes an audit artifact containing the deterministic engine version and extracted fields.

This approach deliberately favours precision over recall. It can miss unusual layouts, unconventional job titles, unlabeled employers, names embedded in headers or education details. Those limitations must be measured against representative resumes before production use; they must not be hidden by treating the extractor as equivalent to a trained entity-recognition model.

## 4. Experience derivation

Employment periods are derived from date ranges, not by adding every duration independently. Overlapping roles must be unioned so concurrent employment does not double-count experience. Open-ended ranges use a documented reference date. Invalid or ambiguous date ranges are excluded from the numeric total and retained as uncertainty rather than being converted into invented years.

The output `experience_years` is nullable. A null value means the parser could not derive a reliable duration; it is not equivalent to zero years.

## 5. Job-description parsing

The JD parser extracts:
- `required_skills`: canonical, deduplicated skills found in the JD;
- `jd_titles`: role titles used for title similarity;
- `required_years`: a non-negative numeric minimum when clearly stated, otherwise null.

A JD that produces zero required skills is not scored. It transitions to FAILED and creates a failed-job record with stage `JD_PARSE` and error type `JD_NO_SKILLS`. This is deliberate: dividing by an empty required-skill set would make the skill score undefined and create misleading rankings.

## 6. Deterministic candidate score

The final score is:

`final = round(100 × (0.50 × skills + 0.30 × title + 0.20 × experience), 1)`

Each component is between 0 and 1.

### Skills (50%)

`skills = |candidate_skills ∩ required_skills| / |required_skills|`

The parser and taxonomy normaliser should produce canonical skill strings. The scoring function case-folds and deduplicates inputs before matching. It records matched and missing skills so a recruiter can inspect the reason for the result.

### Title (30%)

The scorer compares every candidate title against every JD title and selects the best pair. It expands configured aliases such as SDE → software engineer, tokenises the role, and computes Jaccard similarity:

`J(A, B) = |A ∩ B| / |A ∪ B|`

Seniority words are removed from role tokens and mapped to levels: intern 0, junior 1, mid 2, senior 3, lead 4, principal 5. The role similarity is multiplied by 0.85 when the seniority gap is one and by 0.5 when the gap is two or more. If the candidate has no title, title score is zero.

### Experience (20%)

`experience = min(candidate_years / required_years, 1)`

If required years are null or zero, the experience component is 1.0 because the JD has not specified a minimum. If the JD specifies a positive minimum and candidate experience is unknown, the component is zero. This is a scoring policy choice and should be made visible to recruiters.

### Threshold and audit record

A candidate is above threshold when `final_score >= job.threshold`; equality qualifies. The default threshold is 60 unless the recruiter supplies another value. The stored score breakdown contains component scores rounded to three decimals, component weights, matched/missing skills, the best title pair, years counted, required years and scorer version.

The score Lambda reads the job and candidate records consistently, writes numeric values in DynamoDB-compatible Decimal form, and preserves recruiter decision fields. Duplicate SQS deliveries with an unchanged result do not refresh `scored_at`; an explicit `RESCORE` message does.

## 7. Interpretation and limitations

The score is a deterministic ranking aid, not a hiring decision. Keyword overlap can reward resumes that repeat JD language and miss transferable skills expressed differently. Title similarity is lexical rather than semantic. Experience dates can be incomplete or ambiguous. A missing value can reflect extraction uncertainty rather than a candidate's lack of capability.

Recruiters should review the underlying evidence before making a decision. Do not infer protected characteristics from names, photos, age clues or other sensitive signals. Avoid using proxy variables that reproduce discriminatory outcomes. A production deployment should retain a representative, consented golden set, evaluate false positives and false negatives, inspect score distributions, and document changes to taxonomy, aliases, weights and thresholds.

## 8. Validation strategy

Unit tests cover deterministic scoring, aliases, seniority penalties, missing values, invalid numeric values, inclusive thresholds and input immutability. Handler tests cover DynamoDB Decimal conversion, idempotent duplicate delivery, explicit rescoring and retry-triggering failures. Contract tests must validate persisted candidate/job/failed-job records against the frozen JSON schemas. Golden-set evaluation must compare extraction and ranking output against human-reviewed expected fields; it must not be replaced by a handful of synthetic fixtures.

## 9. Current verification boundary

Passing unit tests, SAM lint and SAM build proves code-level and template-level checks only. It does not prove Textract job completion notifications, managed NLP entity service quotas/permissions, SES deliverability, Cognito authorisation, S3 notification delivery, live DLQ recovery or production suitability. Those require an approved dev deployment and recorded end-to-end evidence.
