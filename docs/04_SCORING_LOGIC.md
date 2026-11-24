# NLP and Matching Logic

## Overview

The matching pipeline turns a job description and uploaded resumes into structured records, then compares each candidate with the job. PDF text is extracted with Amazon Textract, while DOCX text is read with `python-docx`. Amazon Comprehend entity detection and deterministic text matching help derive candidate and job fields. The scoring stage compares required skills, job titles, and experience, then stores a score and component breakdown for the recruiter.

This document records the behavior specified by the project architecture and scoring rules. Parsing and scoring source implementations are absent from this checkout, so runtime behavior has not been independently verified. The custom entity recognizer is optional; this explanation does not assume that a trained model or endpoint is active.

## Resume data extraction

1. **Text extraction:** PDF files use Textract; DOCX files use `python-docx`. Textract is asynchronous for PDFs. Unsupported or unreadable files follow the project's failure handling rather than receiving a score.
2. **Entity detection:** Amazon Comprehend's standard `DetectEntities` output is used for PERSON (name), ORGANIZATION (employer), and DATE (employment periods). The built-in TITLE entity is not used for job titles. If a custom entity recognizer is configured, it can contribute SKILL and JOB_TITLE entities; it is optional.
3. **Skill normalisation:** Extracted skills are lowercased, punctuation is stripped, aliases are mapped to canonical taxonomy entries, and duplicates are removed. The taxonomy is also matched against raw text, so a skill can be found even when entity recognition misses it. For example, `k8s` maps to `kubernetes`. The resulting skills are canonical names.
4. **Email:** An email address is extracted with a regular expression; a missing address remains null.
5. **Experience:** Detected date ranges are combined as a union so overlapping employment periods are not double-counted. `Present` is treated as the current date. The derived value is capped at 40 years; when dates are unavailable, an `N+ years` phrase may be used as a fallback. If experience cannot be derived, the candidate field remains null.

The job description is processed into canonical `required_skills`, `jd_titles`, and `required_years`. If it produces zero required skills, the job is marked FAILED with `JD_NO_SKILLS` and is not scored. A recruiter must provide a usable job description before scoring can proceed.

## NLP matching and scoring

Each component has a value from 0 to 1 and contributes according to its fixed weight.

### Skills

The skills component is the number of canonical skills shared by the candidate and job, divided by the number of required job skills:

`skills = matched_required_skills / required_skills`

Skills that are not in the job's required list do not increase this component. A job with no required skills is rejected before scoring, so this denominator is never zero for a scored job.

### Job title

Candidate and job titles are lowercased, aliases are expanded (for example, `sde` to `software engineer`), and seniority words are separated from the role words. Role similarity uses Jaccard similarity: the number of shared role tokens divided by the number of distinct role tokens in either title.

Seniority levels are intern 0, junior 1, mid 2, senior 3, lead 4, and principal or higher 5. A title without a recognised seniority word defaults to mid (level 2). The role similarity is multiplied by 0.85 when the seniority-level gap is 1, and by 0.5 when the gap is 2 or more. With no candidate titles, the title component is 0. When there are multiple candidate titles or job titles, the best title pair score is used.

### Experience

When required experience is a positive number, the component is the candidate's counted years divided by required years, capped at 1:

`experience = min(candidate_years / required_years, 1)`

If `required_years` is null or zero, the component is 1.0. If `experience_years` is null, the component is 0. These are deliberate scoring rules: a missing job experience requirement does not reduce a candidate's score, while missing candidate experience receives no experience credit.

## Scoring formula

The component weights are skills 50%, title 30%, and experience 20%. The stored final score is rounded to one decimal place:

`final = round(100 * (0.50*skills + 0.30*title + 0.20*experience), 1)`

`above_threshold` is true when the final score is greater than or equal to the job's threshold. The default threshold is 60, and a job may have its own threshold.

## Worked example

Suppose a job requires four skills, five years of experience, and the title `DevOps Engineer`. A candidate matches three of the four required skills, has four counted years, and lists `Senior DevOps Engineer`.

- Skills: `3 / 4 = 0.75`
- Title: the role tokens match (Jaccard 1.0). The job title has no seniority word, so it defaults to mid (level 2); the candidate's seniority level is 3, a gap of 1. Therefore, `1.0 * 0.85 = 0.85`.
- Experience: `min(4 / 5, 1) = 0.80`
- Weighted calculation: `100 * (0.50*0.75 + 0.30*0.85 + 0.20*0.80) = 100 * (0.375 + 0.255 + 0.160) = 79.0`

The final score is **79.0**. At the default threshold of 60, `above_threshold` is **true**.

## Explainability and auditability

The candidate record stores the final score, `above_threshold`, and a `score_breakdown` with each component's score and fixed weight. The breakdown records matched and missing skills, the best title pair when available, years counted, required years, and the scorer version. Component scores are rounded to three decimals in the breakdown. These fields follow `contracts/candidate.schema.json`.

The parsing flow is specified to preserve raw Comprehend output in an S3 audit object at `parsed/{job_id}/{candidate_id}.json`. The candidate and job records provide the inputs used by scoring. Recruiter decisions are appended to `decision_history` with the action, actor (`by`), and timestamp (`at`). These records support review of both how the score was formed and what action followed. The raw audit object and application runtime are not present in this checkout, so their operation is not verified here.

## Limitations

- Dictionary matching depends on the coverage and quality of the taxonomy. Unlisted aliases, abbreviations, or context-specific meanings can be missed; matching a term in raw text does not establish how deeply a candidate used that skill.
- Jaccard title similarity compares tokens, not meaning. Different wording for similar work can score poorly, while titles sharing generic words can appear similar. The fixed seniority multiplier is a simple rule and cannot capture every role's level structure.
- Missing experience data receives a zero component, while a missing or zero job requirement receives full experience credit. Date parsing and fallback phrases can be ambiguous, so derived years can be incomplete or inaccurate.
- This deterministic score applies the same stated rules to every record, but it is not a complete measure of candidate suitability. It does not understand context, validate claims, or replace recruiter review. No LLM, embeddings, sentiment analysis, or always-on trained custom recognizer is part of the documented current scoring path.

## Proposed future enhancements

These are proposals, not currently implemented features:

1. **Improve extraction with a reviewed taxonomy and recruiter feedback.** Expand and review the skill and job-title aliases with domain experts, then use recruiter corrections and feedback to identify missing terms and improve taxonomy coverage.
2. **Add semantic matching with embeddings.** Compare skill and phrase meanings to identify related terms that exact dictionary matching can miss, such as `container orchestration` and `Kubernetes`. This would be a separate, evaluated enhancement to the current deterministic matching path.
3. **Add fairness auditing and clearer recruiter explanations.** Audit score behavior and outcomes for unexpected patterns, and explain the evidence behind each component in the recruiter interface. Do not use protected characteristics or infer sensitive attributes for scoring.
