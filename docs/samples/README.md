# Sample Comprehend output (A10)

Run the real pipeline stages on the three resume types and commit the results here:

```bash
aws s3 cp fixtures/golden/resumes/ s3://BUCKET/golden/ --recursive
python backend/parsing/tools/sample_run.py --bucket BUCKET --keys golden/g01.pdf golden/g02.docx golden/g03.pdf
```

Expected files: `g01.*` digital PDF, `g02.*` two-column DOCX, `g03.*` scanned PDF; each has `.comprehend.json` (raw
entities) and `.parsed.json` (the derived record). Files are fake data only.
