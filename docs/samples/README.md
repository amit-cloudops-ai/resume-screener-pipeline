# Reviewed deterministic extraction samples

**Evidence class: SYNTHETIC / MOCK. These files are not captured AWS service responses.**

- `deterministic-digital-pdf.json` — R01, selectable-text digital PDF.
- `deterministic-two-column-docx.json` — R05, two-column DOCX.
- `deterministic-scanned-pdf.json` — R09, raster-image-only scanned PDF.

Each sample records the expected extracted text, deterministic parser output, source fixture and evidence limitations. The scanned-PDF text is expected text after OCR; it is not a captured Textract response.

The parser uses Amazon Textract for PDF text extraction, python-docx for DOCX, and local Python taxonomy/regex/date logic for field derivation. No managed NLP entity-recognition service or custom recognizer is part of this pipeline.

## Validation boundary

These samples validate repository-side expected fields against the golden labels. They do not prove OCR quality or live AWS behaviour. After an approved development deployment, capture Textract output with source key, parser version, timestamp and region; keep live provider evidence separate from synthetic fixtures and redact personal data.

## Review status

- [x] Three resume formats represented.
- [x] Deterministic extraction engine identified.
- [x] Synthetic expected output distinguished from live AWS evidence.
- [ ] Actual Textract output captured — requires approved AWS development deployment.
