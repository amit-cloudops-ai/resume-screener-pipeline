# AGENTS.md — READ THIS FIRST, EVERY SESSION

You (ChatGPT / any AI assistant) are helping a 3-person team build ONE project with a hard deadline.
You have no memory between chats. This repo IS your memory. Do not rely on anything else.

## 1. The project in 3 lines
AI Resume Screener on AWS: recruiter uploads a Job Description + resumes (PDF/DOCX) -> Textract/python-docx extract text -> deterministic Python extraction (taxonomy + regex/date patterns) -> scoring engine ranks candidates (skills 50% / title 30% / experience 20%) -> recruiter dashboard (shortlist/reject, SES email, CSV).
Full brief: docs/00_BRIEF.md. Architecture: docs/01_ARCHITECTURE.md.

## 2. The finish line (the ONLY definition of "done")
docs/02_DEFINITION_OF_DONE.md. When every box there is ticked WITH EVIDENCE, the project is finished and we STOP.
Deadline: submit Wed 25 Nov 2026. Prod deployed by Mon 23 Nov (buffer Tue 24). Feature freeze: Sun 22 Nov 23:59 IST.
"Production" here means: deployed in AWS account via IaC (SAM) as stack `rs-prod`, us-east-1, reachable by CloudFront URL, Cognito-protected, alarms on, E2E smoke test passing. NOT localhost, NOT "works on my machine", NOT console-clicked resources.

## 3. Start of every session (mandatory, do in order)
1. Read docs/STATE.md (what is built, what is verified, what is blocked, what is next).
2. Read docs/DECISIONS.md (locked decisions — never re-debate them).
3. Read the contract files relevant to your task in contracts/.
4. Ask the human: "Which task ID are we doing?" (IDs in docs/STATE.md, e.g. A6, B3, P4). Work ONLY on that ID.
5. State back in 3 lines: task ID, files you will touch, how we will know it's done.

## 4. Hard rules
- ONE task ID per session. No drive-by improvements, refactors, renames, or "while I'm here" changes.
- contracts/ is FROZEN. Never edit contracts/*, fixtures/candidates/*, fixtures/jobs/* to make your code pass. If a contract is wrong, STOP and tell the human; the change goes through docs/DECISIONS.md + all three owners.
- Stay inside your owned folders (see .github/CODEOWNERS and docs/03_WORK_SPLIT.md). Never edit another owner's folder.
- No new AWS services, no new dependencies, no new architecture. Managed NLP entity-recognition services and custom recognizer endpoints are intentionally not used. Anything not in docs/01_ARCHITECTURE.md is out of scope.
- Every code change ships with a test. `make verify` must pass before you say "done".
- Never invent AWS resource names, ARNs, env vars, table fields or API routes. Use the ones in contracts/ and docs/01_ARCHITECTURE.md. If missing, ask.
- Never claim something works unless you ran it or the human pasted the output. Say "not verified" instead.
- Prefer small commits on a feature branch: `feat/<task-id>-short-name`. Open a PR; never push to main.
- Never log resume text or PII to CloudWatch. Log IDs only.
- RESOURCE LEDGER: anything created in AWS outside infra/template.yaml (console, CLI, script) MUST be added to docs/RESOURCES.md section 2 immediately, with how to delete it. Every resource must carry tag Project=resume-screener. At the end of every session ask the human: "Did we create anything by hand this session?"

## 4b. GitHub connector rule (guarded direct-repository workflow)
- AI assistants MAY create branches, create/update files, and open PRs directly through the connected GitHub account when the human explicitly authorizes repository edits.
- NEVER write directly to `main`. All changes go to a task-scoped feature branch and are proposed through a PR.
- Before every file update, fetch the current file from the target branch and use its current blob SHA. Never guess a SHA or overwrite from stale content.
- Make writes sequentially, not in parallel, and verify each resulting commit by fetching the changed file and inspecting the resulting branch/PR diff.
- Do not use bulk file generation or multi-file blind overwrites. Keep each commit small and task-scoped; do not create empty files.
- Never delete or recreate the repo, never force-push, never rewrite history.
- GitHub connector writes do not execute repository tests. A successful API write is NOT evidence that code builds or tests pass.
- After any code/configuration change, require GitHub Actions to run `make verify` and the task-specific checks. If those checks cannot run, mark the change NOT VERIFIED and do not merge or deploy.
- Human approval remains required for PR merges, contract changes, AWS deployment, and destructive operations unless explicitly authorized separately.

## 5. Fix protocol (this is what stops the fix-one-break-another loop)
1. Reproduce: paste the exact error / failing output. No guessing from memory.
2. Write a failing test that captures the bug.
3. Make the smallest possible fix.
4. Run `make verify`. ALL tests must pass, not just the new one.
5. If the fix breaks something else: REVERT the fix (git checkout), do not patch on top of a patch.
6. TWO-STRIKE RULE: after 2 failed attempts at the same bug, STOP. Write a diagnosis in docs/STATE.md under "Blocked" (what you tried, what you observed, your best hypothesis) and ask the human. Do not attempt a third blind fix.
7. Never "fix" by weakening a test, loosening a schema, or changing a contract.

## 6. End of every session (mandatory)
Update docs/STATE.md AND docs/RESOURCES.md (if anything was created by hand): task status, evidence (test output / console proof), anything blocked, next task. Commit it.
If you are asked to do something outside the current task ID, say so and add it to STATE.md "Parking lot" instead of doing it.

## 7. Tech stack (locked)
Python 3.12 Lambdas, AWS SAM (CloudFormation) IaC, DynamoDB (3 tables), S3, SQS (+DLQ), Textract, SES, Cognito, API Gateway REST + Cognito authorizer, CloudFront + S3 static frontend (React + Vite).
Region: us-east-1. Stacks: rs-dev, rs-prod. Resource name prefix: rs-<stage>-.
