# Phase A Step 6 — dashboard visual direction review

Decision D16 was approved by Amit on 24 November 2026: A — Editorial Hiring Desk. This approval authorises the dashboard-specific visual system and page layout described below.

## Product constraints shared by all directions

Recruiter-only workspace. The primary jobs are to create a role, upload a JD and resumes, review ranked candidates, inspect explainable scores, shortlist/reject, export CSV and resolve failed uploads. The dashboard must prioritize data legibility, status clarity, keyboard access and efficient desktop workflows while remaining usable on mobile.

Common interaction model:
- Persistent left navigation on desktop; compact mobile navigation.
- Job context visible on every job-scoped page.
- Candidate list with sortable score column, decision/status, extracted skill tags and clear detail access.
- Score breakdown in a side panel or detail view, not an overloaded table.
- Shortlist/reject actions require explicit confirmation; shortlist collects interview date/time and location/link.
- Failed jobs have retry affordances only where the API reports retryable stages.
- WCAG AA contrast, visible focus, semantic forms and responsive layouts.

## Direction A — Editorial Hiring Desk (recommended)

**Mood:** considered, calm, editorial and high-trust; a modern recruiting operations workspace rather than a generic SaaS admin template.

- Canvas: warm off-white (#F6F5F0), white data surfaces, deep ink (#20251F).
- Accent: restrained forest green (#315B43) for primary actions and positive states; amber/red reserved for warnings/errors.
- Typography: Newsreader for large editorial page titles + IBM Plex Sans for UI/data.
- Composition: generous page margins, strong title hierarchy, compact but breathable tables, thin dividers, minimal elevation, small status pills and a distinctive candidate detail panel.
- Best fit: premium visual character without compromising dense recruiter workflows.

## Direction B — Precision Talent Console

**Mood:** crisp, systematic, precise and enterprise-ready.

- Canvas: cool light grey (#F3F6F8), white surfaces, graphite text (#202A33).
- Accent: deep teal (#087E83), with neutral blue-grey secondary states.
- Typography: Manrope for UI/headings + IBM Plex Mono for IDs, scores and technical metadata.
- Composition: tighter grid, structured metric strip, high-information tables, restrained borders and compact filters.
- Best fit: recruiters processing many roles and candidates who value scan speed over editorial character.

## Direction C — Dark Intelligence Workspace

**Mood:** focused, technical and immersive, like a private talent intelligence desk.

- Canvas: deep charcoal (#171C1A), elevated graphite surfaces (#222A26), warm light text.
- Accent: muted lime/green (#A6C96A), used sparingly for primary action and score emphasis.
- Typography: Space Grotesk for headings + Inter for UI/data.
- Composition: dark navigation rail, high-contrast score visualizations, compact candidate rows and a bright detail panel hierarchy.
- Best fit: teams who work in the dashboard for long sessions and explicitly prefer dark interfaces. Requires extra contrast and state-color review.

## Approved direction

**A — Editorial Hiring Desk** was selected and approved by Amit. It gives the product a distinctive visual identity while keeping candidate data, score breakdowns and decision controls readable. It avoids the generic blue SaaS dashboard look and avoids using a dark surface as a substitute for information hierarchy.

## Approval record

- Selected direction: **A — Editorial Hiring Desk**.
- Approved by: **Amit**.
- Approval date: **24 November 2026**.
- Decision D16: **APPROVED**; see docs/DECISIONS.md.
- Step 6 completion: **COMPLETE** — visual direction approved and recorded.
- Step 7 dashboard build: authorised and implemented on the Phase A working branch.

## Step 7 implementation mapping

The recruiter workspace now uses this approved visual system and implements the recruiter flows against the existing OpenAPI routes: job list/create, JD upload, batch resume uploads with per-file progress, candidate ranking/search/filter, candidate detail and weighted score breakdown, shortlist with interview details, reject confirmation, CSV export, failed-job inspection and stage-aware retry. The frontend retains the existing Cognito SRP module and raw ID-token Authorization header. No API/OpenAPI/JSON/SQS contract or SAM resource was changed.

GitHub Actions run 45344597945 passed make verify, golden evaluation, frontend TypeScript check/production build, SAM lint validation and SAM build (3/3 jobs). Live Cognito/API behaviour remains a post-deployment acceptance gate.
