# Team contributions

This record is based on commit author metadata recovered from the historical feature branches that fed the integrated application. The final integration was squash-merged, which is why GitHub's default-branch contributor graph does not automatically show every original contributor.

| Contributor | Verified GitHub identity | Verified contribution areas | Evidence |
|---|---|---|---|
| Amit | [`amit-cloudops-ai`](https://github.com/amit-cloudops-ai) | Project integration, AWS SAM infrastructure, release coordination, integration fixes, deterministic NLP replacement, CI and project closeout | `feat/INT-full-pipeline-integration`, `feat/P2-infrastructure-readiness`, `feat/remove-comprehend-local-nlp` and integration PR history |
| Gopi Krishna | [`dggk78`](https://github.com/dggk78) | A1 skills taxonomy and A2–A10 parsing pipeline, including golden set and tests | Authored commits `feat(parsing): A1 skills taxonomy` and `feat(parsing): A2-A10 pipeline, golden set, tests` on `feat/A1-skills-taxonomy` and `feat/A2-A10-parsing-pipeline` |
| Sushmitha M | [`sush-kush`](https://github.com/sush-kush) | B1 scoring library; B2 score Lambda; B3 jobs API; B4 candidates API; B5 decision API; B6 shortlist CSV export; B7 failed-jobs API/retry; B8 NLP scoring explanation | Authored commits across `feat/B1-scoring-library` through `feat/B8-nlp-explanation` |

## Attribution notes

- Contributor names and module areas above are supported by commit author metadata and commit messages on the historical feature branches.
- GitHub's Contributors panel may still show only the account that authored the squash merge on `main`. This is a display/history consequence, not a complete team roster.
- The original feature branches are retained as provenance until branch cleanup is performed. Their code was incorporated into the integrated project; this document does not claim the feature branches themselves were merged with individual commit ancestry preserved.
- No commit authorship has been rewritten or fabricated.

## Integrated project areas

The integrated application includes the recruiter frontend, authenticated APIs, job-description parsing, resume ingestion, deterministic extraction, scoring and ranking, candidate decisions, CSV export, failed-job handling, SQS/DLQ processing, AWS SAM infrastructure, test fixtures and CI.
