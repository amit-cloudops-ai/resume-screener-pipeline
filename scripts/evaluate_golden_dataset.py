#!/usr/bin/env python3
"""Measure deterministic golden-set field extraction and scorer ranking."""
from __future__ import annotations

import json
from pathlib import Path

from backend.parsing.common import derive_fields
from backend.scoring.scoring import score_candidate

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "fixtures" / "golden"


def main() -> int:
    expected = json.loads((GOLDEN / "expected.json").read_text(encoding="utf-8"))
    jobs = json.loads((GOLDEN / "job_descriptions.json").read_text(encoding="utf-8"))
    derived = {}
    tp = fp = fn = email_correct = experience_within_tolerance = 0
    per_resume = []

    for row in expected["resumes"]:
        text = (GOLDEN / "source" / f"{row['id'].lower()}.txt").read_text(encoding="utf-8")
        actual = derive_fields(text, row["mock_entities"])
        wanted_skills, actual_skills = set(row["skills"]), set(actual["skills"])
        row_tp = len(wanted_skills & actual_skills)
        row_fp = len(actual_skills - wanted_skills)
        row_fn = len(wanted_skills - actual_skills)
        tp += row_tp
        fp += row_fp
        fn += row_fn
        email_ok = actual["email"] == row["email"]
        years = actual["experience_years"]
        experience_ok = years is not None and abs(years - row["experience_years"]) <= 1
        email_correct += int(email_ok)
        experience_within_tolerance += int(experience_ok)
        derived[row["id"]] = actual
        per_resume.append({
            "resume_id": row["id"],
            "skill_tp": row_tp,
            "skill_fp": row_fp,
            "skill_fn": row_fn,
            "email_correct": email_ok,
            "expected_years": row["experience_years"],
            "actual_years": years,
            "experience_within_1_year": experience_ok,
        })

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    ranking = []
    for job in jobs["jobs"]:
        scored = []
        for row in expected["resumes"]:
            result = score_candidate(
                derived[row["id"]],
                {
                    "required_skills": job["required_skills"],
                    "jd_titles": job["jd_titles"],
                    "required_years": job["required_years"],
                    "threshold": 60,
                },
            )
            scored.append({"resume_id": row["id"], "score": result["score"]})
        scored.sort(key=lambda item: (-item["score"], item["resume_id"]))
        actual_top = scored[0]["resume_id"]
        ranking.append({
            "job_id": job["id"],
            "expected_top_candidate": job["expected_top_candidate"],
            "actual_top_candidate": actual_top,
            "top1_correct": actual_top == job["expected_top_candidate"],
            "top_5": scored[:5],
        })

    report = {
        "evaluation_scope": "deterministic taxonomy/email/date derivation and scorer using synthetic mock entity fixtures; not live Textract or Comprehend model accuracy",
        "resume_count": len(expected["resumes"]),
        "skill_true_positive": tp,
        "skill_false_positive": fp,
        "skill_false_negative": fn,
        "skill_precision": round(precision, 4),
        "skill_recall": round(recall, 4),
        "email_correct": email_correct,
        "email_total": len(expected["resumes"]),
        "experience_within_1_year": experience_within_tolerance,
        "experience_total": len(expected["resumes"]),
        "top1_correct": sum(int(item["top1_correct"]) for item in ranking),
        "job_count": len(ranking),
        "ranking": ranking,
        "per_resume": per_resume,
    }
    print(json.dumps(report, indent=2))
    assert precision >= 0.85
    assert recall >= 0.85
    assert email_correct >= 11
    assert experience_within_tolerance >= 10
    assert all(item["top1_correct"] for item in ranking)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
