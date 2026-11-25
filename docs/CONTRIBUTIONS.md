# Team contributions

This record is based on verified Git commit author metadata from the historical feature branches that fed the integrated application. The final integration was squash-merged, so GitHub's default-branch contributor graph does not automatically show every original contributor.

| Contributor | Verified GitHub identity | Verified contribution areas | Evidence |
|---|---|---|---|
| Amit | [`amit-cloudops-ai`](https://github.com/amit-cloudops-ai) | Project integration, AWS SAM infrastructure, release coordination, integration fixes, deterministic NLP replacement, CI and project closeout | Integration and infrastructure feature history |
| Gopi Krishna | [`dggk78`](https://github.com/dggk78) | A1 skills taxonomy; A2–A10 parsing pipeline, golden set and tests | [A1 commit `116cf19`](https://github.com/amit-cloudops-ai/resume-screener-pipeline/commit/116cf192b15f0440517ac3a28e2a19972280e419); [A2–A10 commit `d9ca4a4`](https://github.com/amit-cloudops-ai/resume-screener-pipeline/commit/d9ca4a499976f22ac22eb8af45d4b67a0141b904) |
| Sushmitha M | [`sush-kush`](https://github.com/sush-kush) | B1 scoring library; B2 score Lambda; B3 jobs API; B4 candidates API; B5 decision API; B6 shortlist CSV export; B7 failed-jobs API/retry; B8 NLP scoring explanation | [B1](https://github.com/amit-cloudops-ai/resume-screener-pipeline/commit/e24d367cc2c1eab5e7100a092671731e289f9093), [B2](https://github.com/amit-cloudops-ai/resume-screener-pipeline/commit/65c0cb2828f365018aad853d5f8b73eb467dcb92), [B3](https://github.com/amit-cloudops-ai/resume-screener-pipeline/commit/5ebbdb3983a1a235e9247a12b6f7c58d966c0e76), [B4](https://github.com/amit-cloudops-ai/resume-screener-pipeline/commit/d4e4e2e2a6f7c93a7fa491175c78bdf5de84206c), [B5](https://github.com/amit-cloudops-ai/resume-screener-pipeline/commit/d3080730161d3361f1bae1831a1a5dcb83d76236), [B6](https://github.com/amit-cloudops-ai/resume-screener-pipeline/commit/fc2bda7e03d6a4d951de46d3011cf65bd8557089), [B7](https://github.com/amit-cloudops-ai/resume-screener-pipeline/commit/3a015f1202bc4ff5b1cbd5adca9c7b23bf177758), [B8](https://github.com/amit-cloudops-ai/resume-screener-pipeline/commit/7d887cbbe479ff3029da8c6679cf0de734084b3b) |

## Attribution notes

- Names, GitHub identities and areas above are supported by commit author metadata and commit messages.
- The integrated default branch was squash-merged; therefore GitHub's Contributors panel may show the squash author rather than all original commit authors.
- Original feature branch refs are historical provenance. Their individual commit SHAs are linked above so the contributions remain auditable even after branch cleanup.
- No commit authorship has been rewritten or fabricated.

## Integrated project areas

The integrated application includes the recruiter frontend, authenticated APIs, job-description parsing, resume ingestion, deterministic extraction, scoring and ranking, candidate decisions, CSV export, failed-job handling, SQS/DLQ processing, AWS SAM infrastructure, test fixtures and CI.
