# Reviewed extraction samples — repository-side fixtures

**Evidence class: SYNTHETIC / MOCK. These files are not captured Amazon Comprehend or Textract service responses.**

Three examples map to the golden dataset: R01 digital PDF, R05 two-column DOCX and R09 raster-image-only scanned PDF. Entity arrays are deterministic fixtures based on `fixtures/golden/expected.json`; they illustrate entity-source handling and parser output, not model accuracy, OCR quality, confidence or latency.

## Entity-source contract

| Source | Supported use |
|---|---|
| Standard Comprehend | `PERSON`, `ORGANIZATION`, `DATE` |
| Optional custom recognizer | `SKILL`, `JOB_TITLE`, only when an endpoint is configured |
| Deterministic taxonomy | Canonical skill matching and alias normalisation against extracted text |
| Parser derivation | Email regex, date-range experience union, deduplicated skills/employers/titles |

**Never map standard `TITLE` entities to candidate job titles.** Built-in TITLE represents creative works. Candidate titles come only from custom `JOB_TITLE` entities (D12).

Each JSON file separates provider-like entity arrays from expected parser-derived fields. The scanned-PDF excerpt is expected text after OCR, not a captured Textract result. Confidence values are null because no model inference occurred.

## Replacing with real service evidence

After explicitly approved development deployment:
1. Process the same three golden documents.
2. Record source object key, format, parser version, timestamp and AWS region (never credentials).
3. Capture actual Textract LINE output for PDFs and standard/custom Comprehend responses per chunk.
4. Keep provider responses separate from parser-derived candidate records.
5. Redact personal data before committing.
6. Record whether custom recognition was disabled; custom output should be empty when disabled.
7. Compare results with hand-labelled values and document errors.

Real captures must be separately labelled `AWS_CAPTURED` with provenance. Never overwrite synthetic fixtures with unverified responses.

## Review checklist

- [x] Three document formats represented.
- [x] Standard and custom entity sources separated.
- [x] Custom recognizer optionality documented.
- [x] Standard TITLE misuse prohibited.
- [x] Provider output distinguished from parser output.
- [ ] Actual Textract and Comprehend responses captured — requires approved AWS development deployment.
