# RESOURCES — ledger of everything that exists in AWS (and how to delete it)

RULE: any AWS resource created OUTSIDE `infra/template.yaml` (console, CLI, script) is added to section 2 THE MOMENT it is created. ChatGPT must ask "did we create anything by hand?" at the end of every session.
Every resource gets tag `Project=resume-screener` (+ `Stage=dev|prod`). The SAM template applies it to all stack resources via stack tags.

## 1. Created by the stacks (deleted by deleting the stack)
| Stack | What it owns |
|---|---|
| rs-dev | S3 x2, DynamoDB x3, SQS x6, Lambdas, Cognito pool+client, API Gateway, CloudFront, alarms, SNS, log groups, IAM roles |
| rs-prod | same as above |
Stack IDs / URLs: fill in docs/STATE.md "Deployed environment facts".

## 2. Created BY HAND (NOT deleted with the stack) — keep this table current
| Resource | Region | Created by (task) | Cost risk | Delete how (console) | Deleted? |
|---|---|---|---|---|---|
| Comprehend custom recogniser (model) | us-east-1 | A9 | low | Comprehend > Custom entity recognition > select > Delete | [ ] |
| Comprehend endpoint (real-time) | us-east-1 | A9 | **HIGH (hourly)** | Comprehend > Endpoints > Delete | [ ] |
| Comprehend training data S3 bucket/prefix | us-east-1 | A9 | low | S3 > empty then delete | [ ] |
| SES verified identities (sender + demo emails) | us-east-1 | P5 | none | SES > Verified identities > Delete | [ ] |
| AWS Budget alert | global | P9 | none | Billing > Budgets > Delete | [ ] |
| Cognito users (if created by script outside template) | us-east-1 | P3 | none | gone with the user pool | [ ] |
| (add rows) | | | | | |

## 3. Teardown order (after submission is accepted)
1. Comprehend: delete the **endpoint first** (stops billing), then the custom recogniser.
2. S3: empty `rs-prod-uploads-*` and `rs-prod-frontend-*` (CloudFormation cannot delete non-empty buckets), same for dev. Also empty the Comprehend training bucket.
3. CloudFormation > delete stack `rs-prod`, then `rs-dev`. Wait for DELETE_COMPLETE. If DELETE_FAILED, read the Events tab: it names the stuck resource (usually a non-empty bucket).
4. Delete anything left in section 2 (SES identities, budget).
5. CloudWatch > Log groups: delete any `/aws/lambda/rs-*` left behind.
6. SAM artifact bucket (created by `--resolve-s3`, name starts with `aws-sam-cli-managed-default-`): empty and delete its stack `aws-sam-cli-managed-default`.
7. Verify nothing remains (section 4).

## 4. Verification (proof it's all gone)
- Console > Resource Groups & Tag Editor > Tag Editor > Regions: All regions, Resource types: All, Tag `Project = resume-screener` > must return 0 results.
- Console search for `rs-` in: S3, DynamoDB, SQS, Lambda, CloudFront, Cognito, Comprehend, CloudWatch log groups.
- Billing > Cost Explorer, group by Service, check again after 24-48 hours: no new Comprehend/CloudFront/Lambda charges.
