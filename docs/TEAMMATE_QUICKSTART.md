# Teammate Quickstart (read this first, 5 minutes)

## What we're building
An AI resume screener on AWS. Recruiter uploads a job description + resumes -> Textract/Comprehend extract skills -> we score and rank candidates -> recruiter shortlists in a dashboard. Full picture: `docs/00_BRIEF.md`. Deadline: submit **Wed 25 Nov 2026**; production live by **Mon 23 Nov**.

## Your part
- **Part A (Teammate A)** — turn a resume file into structured data. Tasks A1-A10 in `docs/03_WORK_SPLIT.md`. You own `backend/parsing/` and `fixtures/golden/`.
- **Part B (Teammate B)** — scoring + the HTTP API. Tasks B1-B9. You own `backend/scoring/` and `backend/api/`.
- **Amit (Part P)** — AWS infrastructure, dashboard, integration. He owns everything else.
Don't edit folders you don't own. If you need something changed in another part, tell Amit in the PR.

## One-time setup (Windows users: use WSL Ubuntu or Git Bash — `make` doesn't run in plain PowerShell)
```bash
git clone <repo-url> && cd resume-screener-pipeline
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
make verify          # must print: repo OK / contracts OK / passed
```

## Daily workflow
1. `git checkout main && git pull` then `git checkout -b feat/<task-id>-short-name` (e.g. `feat/B1-scoring-library`).
2. Start your AI chat by pasting `docs/prompts/SESSION_STARTER.md`, filled in with your task ID.
3. Build ONLY that task. Add tests. Run `make verify`.
4. Update your row in `docs/STATE.md` (status + evidence), commit, push, open a PR. Amit merges when CI is green.
5. If a bug takes 2 attempts: stop, write it under "Blocked" in `docs/STATE.md`, message the team.

## The rules that keep us from breaking each other
- `contracts/` and `fixtures/candidates|jobs` are FROZEN. Your code adapts to them, never the reverse.
- The only way parts talk is through those contracts. No importing each other's code.
- Never let an AI bulk-commit files through a GitHub connector (it can create empty files). Copy the output, commit with git, run `make verify`.
- No new AWS services, no new libraries, no extra features. Good ideas go to the "Parking lot" in `docs/STATE.md`.
- Never put real candidate data in this repo. Test resumes must be fully fake.
- Never commit AWS keys or `.env` files.

## Daily 10-minute sync
Done (with evidence) / blocked / who needs what from whom.
