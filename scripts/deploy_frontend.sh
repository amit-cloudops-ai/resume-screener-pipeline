#!/usr/bin/env bash
# Publish the built recruiter SPA to the dedicated private S3 origin and invalidate CloudFront.
# This is intentionally separate from SAM deployment; it requires an existing stack.
set -euo pipefail

STAGE="${1:-dev}"
ALLOW_PROD="${ALLOW_PROD:-0}"
REGION="${AWS_REGION:-us-east-1}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STACK="rs-${STAGE}"

if [[ "$STAGE" != "dev" && "$STAGE" != "prod" ]]; then
  echo "Usage: $0 [dev|prod] (production additionally requires ALLOW_PROD=1)" >&2
  exit 2
fi
if [[ "$STAGE" == "prod" && "$ALLOW_PROD" != "1" ]]; then
  echo "Refusing production frontend publish. Set ALLOW_PROD=1 explicitly." >&2
  exit 2
fi

command -v aws >/dev/null || { echo "AWS CLI v2 is required." >&2; exit 2; }
command -v python3 >/dev/null || { echo "Python 3 is required." >&2; exit 2; }
command -v npm >/dev/null || { echo "Node.js/npm is required." >&2; exit 2; }

outputs="$(aws cloudformation describe-stacks --stack-name "$STACK" --region "$REGION" --query 'Stacks[0].Outputs' --output json)"
get_output() {
  printf '%s' "$outputs" | python3 -c 'import json,sys; rows=json.load(sys.stdin); key=sys.argv[1]; print(next((x["OutputValue"] for x in rows if x["OutputKey"]==key), ""))' "$1"
}

bucket="$(get_output FrontendBucketName)"
api_url="$(get_output ApiUrl)"
user_pool_id="$(get_output UserPoolId)"
client_id="$(get_output UserPoolClientId)"
distribution_id="$(aws cloudformation describe-stack-resource --stack-name "$STACK" --logical-resource-id FrontendDistribution --region "$REGION" --query 'StackResourceDetail.PhysicalResourceId' --output text)"

# Guard against syncing to an unrelated bucket or publishing with incomplete Cognito/API outputs.
case "$bucket" in
  "rs-${STAGE}-frontend-"*) ;;
  *) echo "Unexpected or missing FrontendBucketName output; refusing S3 sync." >&2; exit 1 ;;
esac
for value in "$api_url" "$user_pool_id" "$client_id" "$distribution_id"; do
  if [[ -z "$value" || "$value" == "None" ]]; then
    echo "Stack is missing a required API/Cognito/CloudFront output; refusing publish." >&2
    exit 1
  fi
done
case "$api_url" in https://*) ;; *) echo "ApiUrl must be HTTPS." >&2; exit 1 ;; esac

echo "Building frontend for $STAGE using stack $STACK in $REGION."
npm --prefix "$ROOT/frontend" install --no-audit --no-fund
(
  cd "$ROOT/frontend"
  VITE_COGNITO_USER_POOL_ID="$user_pool_id" \
  VITE_COGNITO_CLIENT_ID="$client_id" \
  VITE_API_BASE_URL="${api_url%/}" \
  VITE_MOCK_API=false \
    npm run build
)

echo "Syncing only the dedicated frontend bucket: $bucket"
aws s3 sync "$ROOT/frontend/dist/" "s3://$bucket/" --delete --region "$REGION"
echo "Invalidating CloudFront distribution $distribution_id."
aws cloudfront create-invalidation --distribution-id "$distribution_id" --paths "/*" >/dev/null
echo "Frontend publish submitted. CloudFront propagation is asynchronous; verify the HTTPS URL before accepting the release."
