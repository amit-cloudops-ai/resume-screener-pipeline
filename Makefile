STAGE ?= dev
REGION := us-east-1
PY ?= python3

# Optional deployment settings. Keep SES and custom NLP disabled until verified/configured.
SES_SENDER ?= DISABLED
ALARM_EMAIL ?=
MONTHLY_BUDGET_USD ?= 25
CUSTOM_RECOGNIZER_ARN ?= DISABLED
PARSER_VERSION ?= 1.0.0
SCORER_VERSION ?= 1.0.0

COMMON_PARAMS = SesSender=$(SES_SENDER) AlarmEmail=$(ALARM_EMAIL) MonthlyBudgetUsd=$(MONTHLY_BUDGET_USD) CustomRecognizerArn=$(CUSTOM_RECOGNIZER_ARN) ParserVersion=$(PARSER_VERSION) ScorerVersion=$(SCORER_VERSION)
SAM_DEPLOY_BASE = sam deploy --template-file .aws-sam/build/template.yaml --region $(REGION) --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM --resolve-s3 --no-fail-on-empty-changeset
COMMON_TAGS = Project=resume-screener

.PHONY: verify repo contracts test golden-generate deploy-dev deploy-prod smoke sam-validate sam-build

# One command that must be green before any commit / PR is called "done"
verify: repo contracts test

repo:
	$(PY) scripts/check_repo.py

contracts:
	$(PY) scripts/validate_contracts.py

golden-generate:
	$(PY) scripts/generate_golden_documents.py

test: golden-generate
	$(PY) -m pytest -q tests backend --ignore=tests/e2e

sam-validate:
	sam validate --lint --template-file infra/template.yaml

sam-build:
	sam build --template-file infra/template.yaml

deploy-dev:
	sam build --template-file infra/template.yaml
	$(SAM_DEPLOY_BASE) --stack-name rs-dev --parameter-overrides Stage=dev $(COMMON_PARAMS) --tags $(COMMON_TAGS) Stage=dev

deploy-prod:
	@test -n "$(ALARM_EMAIL)" || (echo "ALARM_EMAIL is required for production so budget/operational notifications are configured." >&2; exit 1)
	@test "$(SES_SENDER)" != "DISABLED" || (echo "SES_SENDER must be a verified sender identity for production." >&2; exit 1)
	sam build --template-file infra/template.yaml
	$(SAM_DEPLOY_BASE) --stack-name rs-prod --parameter-overrides Stage=prod $(COMMON_PARAMS) --tags $(COMMON_TAGS) Stage=prod

smoke:
	$(PY) tests/e2e/smoke.py --stage $(STAGE) --region $(REGION)
