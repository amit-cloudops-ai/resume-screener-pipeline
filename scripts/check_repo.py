"""Fail if required files are missing or any tracked file is empty (guards against broken imports/commits)."""
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
REQUIRED = [
    "AGENTS.md", "README.md", "Makefile", ".gitignore", "requirements-dev.txt",
    ".github/CODEOWNERS", ".github/workflows/ci.yml", ".github/pull_request_template.md",
    "docs/00_BRIEF.md", "docs/01_ARCHITECTURE.md", "docs/02_DEFINITION_OF_DONE.md",
    "docs/03_WORK_SPLIT.md", "docs/04_SCORING_LOGIC.md", "docs/05_TIMELINE.md",
    "docs/DECISIONS.md", "docs/STATE.md", "docs/RESOURCES.md", "docs/RISKS.md",
    "docs/TEAMMATE_QUICKSTART.md", "docs/SETUP_CHECKLIST.md",
    "docs/prompts/SESSION_STARTER.md", "docs/prompts/FIX_PROTOCOL.md",
    "contracts/openapi.yaml", "contracts/job.schema.json", "contracts/candidate.schema.json",
    "contracts/failed_job.schema.json", "contracts/sqs_messages.md",
    "fixtures/jobs/job_devops.json", "fixtures/candidates/cand_strong.json",
    "fixtures/candidates/cand_partial.json", "fixtures/candidates/cand_sparse.json",
    "fixtures/failed_jobs/failed_corrupt.json",
]
errors = []
for rel in REQUIRED:
    p = ROOT / rel
    if not p.exists():
        errors.append(f"MISSING required file: {rel}")
    elif p.stat().st_size == 0:
        errors.append(f"EMPTY required file: {rel}")

try:
    tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
except Exception:  # not a git checkout (e.g. zip) -> scan the filesystem
    tracked = [str(p.relative_to(ROOT)) for p in ROOT.rglob("*")
               if p.is_file() and ".git" not in p.parts and ".venv" not in p.parts
               and "__pycache__" not in p.parts and ".pytest_cache" not in p.parts]
for rel in tracked:
    p = ROOT / rel
    if p.is_file() and p.stat().st_size == 0 and p.name != ".gitkeep":
        errors.append(f"EMPTY file: {rel}")

if errors:
    print("REPO CHECK FAILED")
    for e in sorted(set(errors)):
        print(" -", e)
    sys.exit(1)
print("repo OK")
