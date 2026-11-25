# Accuracy report (offline: clean text + real DOCX, taxonomy fallback only)

As-of date for experience: 2026-11-23. Golden set: 12 resumes, 3 JDs.

| Check | Result | Target | Status |
|---|---|---|---|
| Skill recall | 100.0% | >= 85% | PASS |
| Skill precision | 100.0% | >= 85% | PASS |
| Email correct | 12/12 | >= 11/12 | PASS |
| Experience within 1 year | 12/12 | >= 10/12 | PASS |
| Name correct (info) | 12/12 | - | - |
| Titles exact (info) | 12/12 | - | - |

| JD | Top candidate | Expected | Status | Full order matches |
|---|---|---|---|---|
| jd1 | g01 | g01 | PASS | True |
| jd2 | g05 | g05 | PASS | True |
| jd3 | g09 | g09 | PASS | True |
