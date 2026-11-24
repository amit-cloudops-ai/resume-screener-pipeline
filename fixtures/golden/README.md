# Golden dataset

This is a fully synthetic evaluation dataset. All people, employers, schools and email addresses use fictional names and reserved `example.com` addresses.

## Dataset layout

- `expected.json`: hand-labelled fields and deterministic mock entity fixtures for all 12 resumes.
- `job_descriptions.json`: three synthetic JDs, required skills, title/experience requirements and human-labelled expected top candidate.
- `source/`: canonical text content for each resume.
- `resumes/`: generated binary resume files (4 digital PDFs, 4 two-column DOCX files, 4 image-only scanned PDFs). Generate them with `pip install -r requirements-dev.txt` followed by `make golden-generate`. The generator is deterministic and is also run before the test suite in CI.

The `mock_entities` values are deterministic test inputs used to isolate parser field derivation and scoring before AWS access. They are **not** represented as actual Amazon Comprehend output. Live Comprehend sample payloads must be captured only after the AWS service integration is deployed.

## Evaluation protocol

1. Extract source text from each generated resume format.
2. Derive skills using the repository taxonomy, email using the parser regex, and experience from date ranges.
3. Supply the synthetic entity fixtures to test deterministic name/employer/job-title mapping independently from Comprehend model quality.
4. Compare derived skill sets, emails and experience values against `expected.json`.
5. Score all candidates against each JD using the production scoring library and compare the top-ranked candidate with `expected_top_candidate`.

The reported pre-AWS results must distinguish deterministic parser/scorer accuracy from live OCR and Comprehend model accuracy.

## Reproducibility

`python scripts/generate_golden_documents.py` materializes the 12 files under `fixtures/golden/resumes/`. Digital PDFs contain selectable text, DOCX files contain a two-column skills table, and scanned PDFs contain a raster-only page with no PDF text layer. The generator uses only the repository's existing development dependencies and standard-library PDF construction; it adds no Lambda/runtime dependency.
