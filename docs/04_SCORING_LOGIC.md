# 04 — NLP & Matching Logic (source of truth; B8 finalises into the written deliverable)

## Extraction (Part A)
1. Text: Textract (PDF) / python-docx (DOCX).
2. Skills are extracted from raw text using the controlled `skills_taxonomy.json`, with alias-to-canonical normalisation and deterministic boundary matching.
3. Job titles are extracted using conservative role/title patterns; the JD's submitted title remains the fallback when no title phrase is found.
4. Email is extracted by regex. Employment duration is calculated by unioning explicit month/year or year-only date ranges; overlapping roles are not double-counted.
5. Name and employer extraction use conservative line/label patterns. When evidence is absent, fields remain null/empty rather than being guessed. Extraction audit artifacts record the engine version and extracted fields, not provider-specific entity payloads.

## Score (Part B) — deterministic, explainable
`final = round(100 * (0.50*skills + 0.30*title + 0.20*experience), 1)`

**skills** = |candidate_skills ∩ required_skills| / |required_skills|. A JD that yields ZERO required skills is never scored: jd-parse sets job status FAILED and writes a failed_jobs row (stage JD_PARSE, error_type JD_NO_SKILLS) so the recruiter sees it and can upload a better JD.
**title** = max over candidate titles of sim(candidate_title, jd_title) where
 - normalise: lowercase, expand aliases (sde -> software engineer), remove seniority words into a seniority level (intern 0, junior 1, mid 2, senior 3, lead 4, principal+ 5; default 2).
 - role_sim = Jaccard(role tokens).
 - if |seniority gap| >= 2: role_sim * 0.5; if gap == 1: role_sim * 0.85.
 - no candidate titles -> 0. Several jd_titles -> take the best.
**experience** = min(candidate_years / required_years, 1). required_years null or 0 -> 1.0. candidate_years null -> 0.

**above_threshold** = final >= job.threshold (default 60).
**score_breakdown** stores each component score and weight, `skills.matched`, `skills.missing`, `title.best_pair`, `experience.years_counted`, `experience.required_years`, and `scorer_version`. Component scores are rounded to 3 decimals. These field names match the frozen candidate schema.

## Why this is explainable / auditable
Every number can be reproduced from the stored candidate + job rows and the breakdown. `parsed/{job}/{cand}.json` keeps the deterministic extraction audit artifact. Decisions keep who/when history.

## Enhancement ideas (for the written deliverable)
1. Custom entity recogniser trained on real, annotated resumes (more skills, JOB_TITLE, certifications) with a continuous feedback loop from recruiter shortlist/reject.
2. Sentiment / key-phrase analysis on cover letters (Comprehend DetectSentiment/DetectKeyPhrases) as a soft signal; plus semantic skill matching with embeddings (e.g. "container orchestration" ~ Kubernetes).
3. Bias auditing: strip PERSON/gender/age/photo signals before scoring, log score distributions per group, and add recruiter-facing "why this score" explanations.
