# Mentor update — Resume Screener Pipeline

The Resume Screener is deployed as a development prototype on AWS (`rs-dev`, `us-east-1`). It includes recruiter authentication, a React/Vite dashboard, job description creation/parsing, S3 presigned resume uploads, SQS/Lambda asynchronous processing, DynamoDB persistence, deterministic Python extraction, explainable candidate scoring, candidate review and failed-job handling.

In the live development demonstration, the recruiter dashboard loaded, a DevOps Engineer – Barclays (Pune) job reached `JD PARSED`, and three synthetic DOCX resumes were parsed and scored. A batch of nine valid synthetic resumes was uploaded; six PDF resumes remained in `PARSING`.

The PDF path currently invokes Amazon Textract. The live Lambda logs show `SubscriptionRequiredException` from `StartDocumentTextDetection` in the development account. This is documented as a service-access limitation observed in this account; it is not claimed that Textract is categorically unavailable on AWS Free Tier. Amazon Comprehend was removed from the integration implementation and deterministic Python NLP is used instead.

The repository has CI evidence for backend tests, deterministic synthetic evaluation, frontend build/typecheck and SAM validation/build. Those checks do not replace live all-format E2E acceptance. PDF/OCR processing, complete live smoke testing, extraction-quality corrections and production readiness remain outstanding. Production has not been deployed or promoted.

Repository: https://github.com/amit-cloudops-ai/resume-screener-pipeline

Detailed evidence and limitations: [docs/PROJECT_CLOSEOUT.md](PROJECT_CLOSEOUT.md)
