STAGE ?= dev
REGION := us-east-1
PY ?= python3
TAGS := Project=resume-screener
SAM_DEPLOY = sam deploy --template-file .aws-sam/build/template.yaml --region $(REGION) --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM --resolve-s3 --no-fail-on-empty-changeset

.PHONY: verify repo contracts test deploy-dev deploy-prod smoke

# One command that must be green before any commit / PR is called "done"
verify: repo contracts test

repo:
	$(PY) scripts/check_repo.py

contracts:
	$(PY) scripts/validate_contracts.py

test:
	$(PY) -m pytest -q tests backend --ignore=tests/e2e

deploy-dev:
	sam build --template infra/template.yaml
	$(SAM_DEPLOY) --stack-name rs-dev --parameter-overrides Stage=dev --tags $(TAGS) Stage=dev

deploy-prod:
	sam build --template infra/template.yaml
	$(SAM_DEPLOY) --stack-name rs-prod --parameter-overrides Stage=prod --tags $(TAGS) Stage=prod

smoke:
	$(PY) tests/e2e/smoke.py --stage $(STAGE) --region $(REGION)
