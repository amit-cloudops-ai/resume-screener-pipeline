STAGE ?= dev
REGION := us-east-1
PY ?= python3

# Optional deployment settings. Keep SES and custom NLP disabled until verified/configured.
SES_SENDER ?= DISABLED
ALARM_EMAIL ?=
MONTHLY_BUDGET_USD ?= 25
CUSTOM_RECOGNIZER_ARN ?= DISABLED

TAGS := Project=resume-screener Stage=$(STAGE)
SAM_DEPLOY = sam deploy --template-file .aws-sam/build/template.yaml --region $(REGION) --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM --resolve-s3 --no-fail-on-empty-changeset --parameter-overrides Stage=$(STAGE) SesSender=$(SES_SENDER) AlarmEmail=$(ALARM_EMAIL) MonthlyBudgetUsd=$(MONTHLY_BUDGET_USD) CustomRecognizerArn=$(CUSTOM_RECOGNIZER_ARN) --tags $(TAGS)

.PHONY: verify repo contracts test deploy-dev deploy-prod smoke sam-validate sam-build

# One command that must be green before any commit / PR is called "done"
verify: repo contracts test

repo:
	$(PY) scripts/check_repo.py

contracts:
	$(PY) scripts/validate_contracts.py

test:
	$(PY) -m pytest -q tests backend --ignore=tests/e2e

sam-validate:
	sam validate --lint --template-file infra/template.yaml

sam-build:
	sam build --template-file infra/template.yaml

deploy-dev:
	sam build --template-file infra/template.yaml
	$(SAM_DEPLOY) --stack-name rs-dev

deploy-prod:
	sam build --template-file infra/template.yaml
	$(SAM_DEPLOY) --stack-name rs-prod

smoke:
	$(PY) tests/e2e/smoke.py --stage $(STAGE) --region $(REGION)
