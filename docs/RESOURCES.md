# RESOURCES — AWS inventory, ownership and teardown

**Last updated:** 25 November 2026  
**Region:** us-east-1  
**Inventory quality:** partial, based on stack outputs/resource names and live application evidence shared during development. This is not a complete fresh account-wide inventory.

## 1. Observed development resources

| Resource | Observed identifier/value | Evidence / qualification |
|---|---|---|
| CloudFormation stack | `rs-dev` | Last previously confirmed `UPDATE_COMPLETE` at 2026-11-25 03:10:15 UTC; later frontend publish did not update the stack |
| Frontend S3 bucket | `rs-dev-frontend-924422830139` | Frontend assets synced successfully |
| Uploads S3 bucket | `rs-dev-uploads-924422830139` | Used by the development upload flow |
| CloudFront distribution | `E3NI28CL1V2SX4` | Invalidation status verified `Completed` |
| CloudFront URL | https://d2sdkmafcw9mpe.cloudfront.net | Recruiter UI observed |
| API Gateway ID | `pidp0mxkc6` | API endpoint below |
| API URL | https://pidp0mxkc6.execute-api.us-east-1.amazonaws.com/v1/ | Previously recorded stack output |
| Cognito user pool | `us-east-1_ItQy4aUwI` | Recruiter sign-in observed |
| DynamoDB tables | `rs-dev-jobs`, `rs-dev-candidates`, `rs-dev-failed-jobs` | Previously recorded live inventory |
| SQS queues | `rs-dev-jd-queue`, `rs-dev-score-queue`, `rs-dev-parse-queue` | Queue attributes inspected during resume test |
| Lambda log groups | `/aws/lambda/rs-dev-parse`, `/aws/lambda/rs-dev-score` | Logs inspected during resume test |
| Test job | `474d8d653e9c` | DevOps Engineer – Barclays (Pune); keep test data until retention/cleanup is deliberately reviewed |

This table is not proof that every listed resource is still present or that the full stack is at the latest integration commit. Re-run read-only AWS inventory commands before any future deployment or teardown.

## 2. Production boundary

- `rs-prod` was not changed by the 25 November closeout.
- No production stack deployment, promotion, resource deletion or cleanup was performed.
- Do not infer that a production stack exists merely because the template supports a `prod` stage.
- Verify production resource existence and state separately before any operation.

## 3. Manual resources and account-level items

The existence of SES identities, SNS subscriptions, AWS Budgets, SAM artifact buckets, IAM users/roles created outside CloudFormation and other manual resources has not been comprehensively re-inventoried in this closeout. Verify each exact resource identifier before changing or deleting it.

| Resource category | Status |
|---|---|
| SES sender identity / production sending approval | Not verified for live mail |
| AWS Budget and notification subscription | Template/configuration exists; live subscription not re-verified in this closeout |
| SAM-managed artifact bucket | Not freshly inventoried |
| Additional manual AWS resources | Not freshly inventoried |

Never store access keys, secret values, Cognito tokens or candidate PII in this file.

## 4. Teardown — do not execute without a separate approval

1. Confirm exact stack-owned and manual resources from a fresh AWS inventory.
2. Confirm retention and backup requirements for uploaded resumes, parsed artifacts, jobs and candidates.
3. Empty an S3 bucket only after its contents and retention obligations have been reviewed.
4. Delete only the explicitly approved stack/environment; do not assume both `rs-dev` and `rs-prod` should be removed.
5. Confirm CloudFormation reaches `DELETE_COMPLETE`; inspect events for failures.
6. Recheck for SAM artifact buckets and manually created resources.
7. Review Billing/Cost Explorer after 24–48 hours for residual charges.
8. Record the exact verification date and result.

**No cleanup is part of the current project closeout.** Existing dev resources and the live test job are preserved.
