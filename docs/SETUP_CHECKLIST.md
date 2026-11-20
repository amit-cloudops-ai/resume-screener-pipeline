# Setup Checklist (Amit, one time, today)

## GitHub
- [ ] Create repo `resume-screener-pipeline` on **amit-cloudops-ai**. Use **Private** (fixtures/resumes will exist later). Do NOT tick "add README/.gitignore/license".
- [ ] Push this project (commands in the chat message that delivered the zip, or below).
- [ ] Actions tab: the `ci` run is green.
- [ ] Settings > Collaborators: invite Teammate A and Teammate B (write access).
- [ ] After they accept: uncomment their lines in `.github/CODEOWNERS` with real usernames, commit via PR.
- [ ] Settings > Branches > add rule for `main`: require a pull request, require status check `verify`, block force pushes.

```bash
cd ~ && mkdir -p projects && cd projects
unzip /mnt/c/Users/amitm/Downloads/resume-screener-pipeline.zip
cd resume-screener-pipeline
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt && make verify
git init -b main
git config user.email "amitpm.github@gmail.com"
git config user.name "Amit"
git add -A && git commit -m "feat: project foundation (docs, contracts, fixtures, CI)"
git remote add origin git@github-cloudops:amit-cloudops-ai/resume-screener-pipeline.git
git push -u origin main
```

## AWS (console)
- [ ] Billing > Budgets: create a monthly cost budget with email alerts (set it low).
- [ ] SES (us-east-1) > Verified identities: create + verify your sender email. Then Account dashboard > **Request production access** (do today, approval can take ~a day).
- [ ] Verify 2-3 extra emails (teammates) to use as demo candidates while in sandbox.
- [ ] Bedrock: nothing to do unless we later approve the optional stretch task.

## Local tools
- [ ] `sam --version` works (install AWS SAM CLI if not).
- [ ] `aws sts get-caller-identity` shows the right account; default region us-east-1.
- [ ] Python 3.12 (`python3 --version`).

## Then
- [ ] Fill the "Deployed environment facts" section in `docs/STATE.md` as things get created.
- [ ] Send teammates: repo link + `docs/TEAMMATE_QUICKSTART.md`.
- [ ] Next task: P2 (SAM `template.yaml` with stub Lambdas) — Gate 1 is Fri 20 Nov noon.
