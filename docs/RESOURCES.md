# RESOURCES — AWS inventory, ownership and teardown

## Inventory status — 24 November 2026

**The AWS account has not been inventoried in this work session.** No stack IDs, API URLs, CloudFront URLs, Cognito IDs or manual-resource ARNs have been recorded in `docs/STATE.md`. Therefore, the planned resources below must not be interpreted as proof that they exist or do not exist.

Before the first deployment, inspect the AWS account in `us-east-1` and record any pre-existing `rs-` resources. After deployment, record every stack ID and output URL in `docs/STATE.md`. Any resource created outside `infra/template.yaml` must be recorded in section 2 immediately.

Tag supported resources with `Project=resume-screener` and `Stage=dev|prod`. CloudFormation stack tags are propagated only to resource types that support tagging; retain resource names, ARNs and region for services without resource-level tags.

## 1. Stack-owned resources (intended inventory; existence not verified)

| Stack | Expected ownership | Existence |
|---|---|---|
| `rs-dev` | S3 x2, DynamoDB x3, SQS x6, Lambda functions, Cognito pool/client/group, API Gateway, CloudFront, alarms, SNS, log groups and IAM roles | NOT VERIFIED |
| `rs-prod` | Same resource families as dev, isolated by stage | NOT VERIFIED |

Stack IDs / URLs: fill in `docs/STATE.md` → "Deployed environment facts" only after successful deployment.

## 2. Manual resources (planned or created outside the stack)

The rows below are known manual-resource categories from the project plan. Their existence is currently **NOT VERIFIED**. Change the status to `CREATED` only after confirming the resource in AWS and recording its ARN/name. Do not delete a resource based only on its presence in this planning table.

| Resource | Region | Owner/task | Cost risk | Existence | Delete how |
|---|---|---|---|---|---|
| SES verified sender and demo-recipient identities | us-east-1 | Amit / P5 | No direct identity charge | NOT VERIFIED | SES → Verified identities → select identity → Delete |
| AWS Budget and email notifications | Global | Amit / P9 | No direct budget charge | NOT VERIFIED | Billing → Budgets → select budget → Delete |
| Cognito recruiter users created outside the stack | us-east-1 | Amit / P3 | No direct user charge at expected scale | NOT VERIFIED | Delete users from the user pool; deleting the pool removes its users |

Add rows for every manual resource created. Record the exact physical resource identifier, region, creation date, owner/task and deletion status. Never store secrets or credentials here.

## 3. Teardown order (only after submission is accepted)

1. Confirm the exact resources to remove from sections 1 and 2. Do not assume both stacks or all manual resources exist.
2. Empty uploads and frontend S3 buckets for each deployed stage.
3. CloudFormation cannot delete non-empty S3 buckets; confirm each bucket's retention/backup policy before emptying it.
4. Delete deployed application stacks in reverse environment order: `rs-prod`, then `rs-dev`. Wait for `DELETE_COMPLETE`. If deletion fails, inspect CloudFormation Events and resolve the named resource.
5. Delete confirmed manual SES identities, budgets and other resources that remain.
6. Check for SAM artifact buckets created by `--resolve-s3` (often associated with `aws-sam-cli-managed-default`); empty and remove only if confirmed and no longer needed.
7. Verify the account inventory and billing after cleanup.

## 4. Verification (proof of cleanup)

- Resource Groups & Tag Editor → Tag Editor → all regions/resource types → filter `Project = resume-screener`; confirm zero remaining tagged resources.
- Search for `rs-` resources in S3, DynamoDB, SQS, Lambda, CloudFront, Cognito and CloudWatch log groups.
- Inspect manually created S3 buckets separately because not every resource type necessarily supports the same tagging workflow.
- Check Billing → Cost Explorer grouped by service again after 24–48 hours for residual Comprehend, CloudFront, Lambda or storage charges.
- Record the verification date and result in this file before declaring cleanup complete.
