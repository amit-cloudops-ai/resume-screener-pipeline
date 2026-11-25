# Dashboard screenshot evidence

This directory is reserved for the dated development-dashboard captures associated with the project closeout.

The screenshots are intended to document:
- Workspace overview and dashboard metrics
- Active job and selected-role summary
- Candidate review table
- Create-role form
- Batch resume upload dialog
- Candidate profile and score explanation panels

**Evidence boundary:** the captures show the development UI as observed on 25 November 2026. They do not prove production readiness or complete end-to-end processing. In the observed run, three DOCX candidates were scored; six PDF candidates remained in `PARSING` after Textract returned `SubscriptionRequiredException`. The candidate profile screenshot also exposes a literal HTML `<small>` rendering defect in the score display.

The actual PNG files are not yet committed in this directory. This index is not a substitute for those image files. The architecture diagram already in the repository is `docs/architecture.svg`, with editable source in `docs/architecture.mmd`.
