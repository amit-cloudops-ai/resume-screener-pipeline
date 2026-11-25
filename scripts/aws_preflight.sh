#!/usr/bin/env bash
# Read-only AWS preflight for the resume screener.
# This script does not create, update, delete, deploy, or modify AWS resources.
set -Eeuo pipefail

REGION="${AWS_REGION:-us-east-1}"
AWS=(aws --no-cli-pager --region "$REGION")

section() {
  printf '\n\n========== %s ==========\n' "$1"
}
run_read_only() {
  local label="$1"
  shift
  section "$label"
  if ! "${AWS[@]}" "$@"; then
    printf 'WARNING: command failed (likely missing read permission); no changes were made.\n' >&2
  fi
}

if ! command -v aws >/dev/null 2>&1; then
  echo "AWS CLI v2 is required." >&2
  exit 1
fi

section "Execution context"
printf 'Region: %s\nProfile: %s\n' "$REGION" "${AWS_PROFILE:-default credential chain}"
run_read_only "Caller identity" sts get-caller-identity
run_read_only "CLI configuration" configure list

run_read_only "Resume Screener CloudFormation stacks" cloudformation list-stacks \
  --stack-status-filter CREATE_IN_PROGRESS CREATE_COMPLETE UPDATE_IN_PROGRESS UPDATE_COMPLETE UPDATE_ROLLBACK_COMPLETE ROLLBACK_COMPLETE ROLLBACK_FAILED DELETE_FAILED \
  --query "StackSummaries[?starts_with(StackName, 'rs-')].[StackName,StackStatus,LastUpdatedTime,StackId]" \
  --output table

run_read_only "Matching S3 buckets" s3api list-buckets \
  --query "Buckets[?starts_with(Name, 'rs-')].[Name,CreationDate]" --output table

run_read_only "Matching DynamoDB tables" dynamodb list-tables \
  --query "TableNames[?starts_with(@, 'rs-')]" --output table

run_read_only "Matching SQS queues" sqs list-queues \
  --queue-name-prefix rs- --output table

run_read_only "Matching Lambda functions" lambda list-functions \
  --query "Functions[?starts_with(FunctionName, 'rs-')].[FunctionName,Runtime,LastModified]" --output table

run_read_only "API Gateway REST APIs" apigateway get-rest-apis \
  --query "items[?starts_with(name, 'rs-') || contains(name, 'resume')].[id,name]" --output table

run_read_only "Cognito user pools" cognito-idp list-user-pools --max-results 60 \
  --query "UserPools[?starts_with(Name, 'rs-')].[Id,Name,CreationDate]" --output table

run_read_only "CloudFront distributions (review for project-owned origins)" cloudfront list-distributions \
  --query "DistributionList.Items[].[Id,DomainName,Status,Comment]" --output table


run_read_only "SES identities" ses list-identities --output table

run_read_only "SNS topics" sns list-topics \
  --query "Topics[?contains(TopicArn, ':rs-')].TopicArn" --output table

ACCOUNT_ID="$("${AWS[@]}" sts get-caller-identity --query Account --output text 2>/dev/null || true)"
if [[ -n "$ACCOUNT_ID" && "$ACCOUNT_ID" != "None" ]]; then
  run_read_only "AWS Budgets" budgets describe-budgets --account-id "$ACCOUNT_ID" \
    --query "Budgets[].[BudgetName,BudgetLimit.Amount,BudgetLimit.Unit,TimeUnit]" --output table
else
  section "AWS Budgets"
  echo "Skipped: caller account ID could not be read."
fi

START_DATE="$(date -u -d '30 days ago' +%Y-%m-%d)"
END_DATE="$(date -u -d 'tomorrow' +%Y-%m-%d)"
run_read_only "Cost Explorer — last 30 days (may require ce:GetCostAndUsage)" ce get-cost-and-usage \
  --time-period "Start=$START_DATE,End=$END_DATE" --granularity MONTHLY \
  --metrics UnblendedCost --group-by Type=DIMENSION,Key=SERVICE \
  --query "ResultsByTime[].[TimePeriod.Start,Groups[].[Keys[0],Metrics.UnblendedCost.Amount,Metrics.UnblendedCost.Unit]]" \
  --output json

section "Manual console checks still required"
cat <<'EOF'
1. Billing → Credits: inspect active credits, expiry dates, and eligible services.
2. Billing → Bills / Cost Explorer: confirm current month-to-date spend and forecast.
3. Service Quotas: check CloudFront distribution and relevant service quotas.
4. Confirm there are no unexpected resources outside the us-east-1 inventory above.
5. Save this output for review before creating any CloudFormation change set.

This script is read-only. It does not create a change set or deploy a stack.
EOF
