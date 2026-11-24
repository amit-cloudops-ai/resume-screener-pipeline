# Reviewed extraction samples — repository-side fixtures

**Evidence class: SYNTHETIC / MOCK. These files are not captured Amazon Comprehend or Textract service responses.**

These three examples correspond to the golden-set document formats:
- `comprehend-digital-pdf.json` — R01, selectable-text digital PDF.
- `comprehend-two-column-docx.json` — R05, two-column DOCX.
- `comprehend-scanned-pdf.json` — R09, raster-image-only scanned PDF.

The sample entity arrays are deterministic fixtures based on the hand-labelled records in `fixtures/golden/expected.json`. They illustrate the *shape and interpretation* of standard and custom entity output, not model confidence, OCR quality, service latency, or real entity detection.

## Entity-source contract

| Source | Supported use in this pipeline |
|---|---|
| Standard entity detection | `PERSON`, `ORGANIZATION`, `DATE` |
| Custom entity recognizer | `SKILL`, `JOB_TITLE`, only when a configured endpoint is supplied |
| Deterministic taxonomy | Canonical skill matching and alias normalisation against extracted text |
| Parser derivation | Email regex, date-range experience union, sorted/deduplicated skills, employers and titles |

**Do not map standard `TITLE` entities to job titles.** The built-in Comprehend TITLE type represents creative works. The implementation only accepts custom `JOB_TITLE` entities for candidate titles (decision D12).

## File structure

Each JSON file includes:
- `evidence_class`: always `SYNTHETIC_MOCK` for this repository-side sample set.
- `source_fixture`: the golden resume ID and format.
- `extracted_text_excerpt`: a short excerpt from the fictional source resume; for the scanned PDF this is the expected text after OCR, not a captured Textract result.
- `comprehend.standard` and `comprehend.custom`: illustrative entity records in the same Type/Text/Score family used by the parser.
- `parser_output`: expected deterministic derived fields, not a live pipeline response.

The parser consumes the provider entity arrays and extracted text; it returns the structure documented in `backend/parsing/common.py`. Confidence values in these examples are illustrative placeholders and must not be compared with production model confidence.

## Replacing these examples with real service evidence

After an explicitly approved development deployment:
1. Use the same three golden source documents (digital PDF, two-column DOCX, scanned image-only PDF).
2. Record the source object key, file format, parser version, extraction timestamp and AWS region without including credentials.
3. Capture Textract LINE output for PDFs and the actual standard/custom Comprehend entity responses returned for each text chunk.
4. Keep the provider response separate from the parser-derived candidate record.
5. Redact or replace personal data before committing. The current golden identities are fictional.
6. Record whether custom recognition was disabled; when disabled, `custom` is expected to be empty.
7. Re-run the accuracy evaluation and document OCR/entity errors rather than editing expected labels to match model output.

Real service samples must use a separate `evidence_class: AWS_CAPTURED` label and include provenance. Never overwrite these synthetic fixtures with unverified or fabricated responses.

## Review status

- [x] Three resume formats represented.
- [x] Standard and custom entity sources separated.
- [x] Custom recognizer optionality documented.
- [x] Standard TITLE misuse explicitly prohibited.
- [x] Expected parser output distinguished from provider response.
- [ ] Actual Textract and Comprehend responses captured — requires approved AWS development deployment.
