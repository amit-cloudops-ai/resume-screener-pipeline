# Golden set (A2)

12 fake resumes (fake names, `@example.com` e-mails): 4 digital PDF (`g01 g04 g06 g09`), 4 two-column DOCX
(`g02 g05 g08 g10`), 4 scanned image-only PDF (`g03 g07 g11 g12`). `labels/*.json` are hand-written expected values
(experience as of 2026-11-23, months counted inclusively). `text/*.txt` is the clean ground-truth text of each resume.
`jds/` has 3 JDs plus `expected.json` (required fields and expected ranking = brief section 7 formula on the labels;
**Amit reviews the labels**). `../resumes/` is the 10-file smoke set (4 digital, 3 DOCX, 2 scanned, 1 corrupt) + `smoke_jd.txt`.

Regenerate: `python backend/parsing/tools/make_golden.py`. Evaluate: `python backend/parsing/tools/golden_eval.py --offline`.
Includes deliberate trap sentences ("react to feedback", "express concerns", "swift delivery") that must NOT create skills.
