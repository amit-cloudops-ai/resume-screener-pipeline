# infra/ (Owner: Amit)

`template.yaml` is the single source of truth for AWS resources. Static SAM validation/lint and build are CI-verified; live CloudFormation change-set review and deployment are separate release gates.

The runtime architecture uses Textract for PDF OCR, python-docx for DOCX extraction, and deterministic local Python taxonomy/regex/date extraction. There is no managed NLP entity-recognition service, custom recognizer endpoint, recognizer ARN parameter, or recognizer SSM parameter.

## Read before changing the template

Review `docs/01_ARCHITECTURE.md` for resource inventory and known AWS constraints, including S3-to-SQS queue policies, Cognito/CORS, visibility timeouts, Textract permissions, CloudFront OAC, SES sandbox and bucket teardown. Apply `Project=resume-screener` and `Stage` tags.

## Manual prerequisites

Not provisioned by this template: Cognito recruiter users (`scripts/create_user.sh`), SES identity verification and SES production-access approval. Verify sender identity and recipient scope before enabling shortlist email in production.

For dev, `ALARM_EMAIL` is optional; without it, SNS email subscription and AWS Budget resources are not created. For production, `make deploy-prod` requires both `ALARM_EMAIL` and a non-`DISABLED` `SES_SENDER`. Budget alerts are notifications, not spending caps. Keep `SES_SENDER=DISABLED` in dev until sender verification and email behaviour are explicitly tested.
