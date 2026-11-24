# Phase A — Golden dataset accuracy report

Evaluation date: 2026-11-24  
Branch: `feat/phase-a-steps-1-3`  
Commit: `904f4ab6972032cd86687e02deb4699a8df0f37c`  
GitHub Actions run: [45337062084](https://github.com/amit-cloudops-ai/resume-screener-pipeline/actions/runs/45337062084)

## Results

| Metric | Measured | Definition of Done | Result |
|---|---:|---:|---|
| Skill precision | 100% (77 TP, 0 FP) | ≥85% | PASS |
| Skill recall | 100% (77 TP, 0 FN) | ≥85% | PASS |
| Email extraction | 12/12 (100%) | ≥11/12 | PASS |
| Experience within ±1 year | 12/12 (100%) | ≥10/12 | PASS |
| Human-labelled top-1 ranking | 3/3 (100%) | 3/3 | PASS |

## Ranking evidence

| Job | Human-labelled top candidate | Actual top candidate | Score |
|---|---|---|---:|
| JD01 — DevOps Engineer | R01 | R01 | 95.5 |
| JD02 — Data Engineer | R05 | R05 | 100.0 |
| JD03 — Software Engineer | R09 | R09 | 95.5 |

## Dataset and methodology

The evaluation contains 12 synthetic resumes: 4 digital PDFs, 4 two-column DOCX documents and 4 scanned image-only PDFs. It also contains three synthetic job descriptions and human-labelled expected candidate fields/rankings.

The evaluator measures:
- Taxonomy matching from the committed synthetic resume text.
- Email extraction using the parser's email expression.
- Experience derivation from explicit month/year intervals.
- Candidate ranking with the production deterministic scoring library.

For PERSON, ORGANIZATION and JOB_TITLE, the evaluation uses deterministic mock entity fixtures stored in `expected.json`. Those fixtures isolate parser field mapping from the live Comprehend model.

**Important limitation:** These results are not live Textract OCR accuracy or live Amazon Comprehend model accuracy. The scanned PDF files are real image-only PDFs, but their OCR has not been tested against AWS. The mock entity fixtures are not Comprehend responses. Live service quality must be measured after development deployment.

## Reproduction

From the repository root:

```bash
pip install -r requirements-dev.txt
make golden-generate
make golden-evaluate
```

The same generation and evaluation commands run in GitHub Actions. The recorded CI run also passed `make verify` (153 tests), SAM lint validation and SAM build.
