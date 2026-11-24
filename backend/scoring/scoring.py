"""Deterministic, explainable candidate scoring for the resume screener."""
from __future__ import annotations

import math
import os
import re
from decimal import Decimal
from collections.abc import Mapping, Sequence
from typing import Any

SCORER_VERSION = os.getenv("SCORER_VERSION", "1.0.0")
SKILLS_WEIGHT = 0.5
TITLE_WEIGHT = 0.3
EXPERIENCE_WEIGHT = 0.2

_ALIASES = {
    "sde": "software engineer",
    "software developer": "software engineer",
    "dev ops": "devops",
}
_LEVELS = {
    "intern": 0,
    "junior": 1,
    "mid": 2,
    "senior": 3,
    "lead": 4,
    "principal": 5,
}

_WORDS = re.compile(r"[a-z0-9]+(?:[+#./-][a-z0-9]+)*")


def _object(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    return value


def _strings(value: Any, name: str) -> list[str]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError(f"{name} must be a list of strings")
    result = set()
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"{name} must contain only strings")
        item = item.strip().casefold()
        if item:
            result.add(item)
    return sorted(result)


def _number(value: Any, name: str, nullable: bool = False) -> float | None:
    if value is None and nullable:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError(f"{name} must be a number" + (" or null" if nullable else ""))
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise ValueError(f"{name} must be a finite non-negative number")
    return result


def _normalise_title(value: str) -> tuple[set[str], int]:
    text = value.casefold().strip()
    for alias, canonical in _ALIASES.items():
        text = re.sub(rf"\b{re.escape(alias)}\b", canonical, text)
    words = _WORDS.findall(text)
    levels = [_LEVELS[word] for word in words if word in _LEVELS]
    level = levels[0] if levels else 2
    return {word for word in words if word not in _LEVELS}, level


def _title_similarity(left: str, right: str) -> float:
    left_words, left_level = _normalise_title(left)
    right_words, right_level = _normalise_title(right)
    union = left_words | right_words
    score = len(left_words & right_words) / len(union) if union else 0.0
    gap = abs(left_level - right_level)
    if gap >= 2:
        score *= 0.5
    elif gap == 1:
        score *= 0.85
    return score


def score_candidate(candidate: Mapping[str, Any], job: Mapping[str, Any]) -> dict[str, Any]:
    """Score a candidate against a parsed job; inputs are never modified."""
    candidate = _object(candidate, "candidate")
    job = _object(job, "job")

    candidate_skills = _strings(candidate.get("skills", []), "candidate.skills")
    required_skills = _strings(job.get("required_skills", []), "job.required_skills")
    if not required_skills:
        raise ValueError("job.required_skills must contain at least one skill")

    matched = sorted(set(candidate_skills) & set(required_skills))
    missing = sorted(set(required_skills) - set(candidate_skills))
    skills_score = len(matched) / len(required_skills)

    candidate_titles = _strings(candidate.get("titles", []), "candidate.titles")
    job_titles = _strings(job.get("jd_titles", []), "job.jd_titles")
    if not job_titles:
        fallback = job.get("title")
        if isinstance(fallback, str) and fallback.strip():
            job_titles = [fallback.strip().casefold()]

    best_pair = None
    title_score = 0.0
    if candidate_titles and job_titles:
        best = -1.0
        for candidate_title in candidate_titles:
            for job_title in job_titles:
                current = _title_similarity(candidate_title, job_title)
                if current > best:
                    best = current
                    best_pair = [candidate_title, job_title]
        title_score = max(best, 0.0)

    candidate_years = _number(
        candidate.get("experience_years"), "candidate.experience_years", nullable=True
    )
    required_years = _number(
        job.get("required_years"), "job.required_years", nullable=True
    )
    if required_years is None or required_years == 0:
        experience_score = 1.0
    elif candidate_years is None:
        experience_score = 0.0
    else:
        experience_score = min(candidate_years / required_years, 1.0)

    final_score = round(
        100 * (
            SKILLS_WEIGHT * skills_score
            + TITLE_WEIGHT * title_score
            + EXPERIENCE_WEIGHT * experience_score
        ),
        1,
    )
    threshold = _number(job.get("threshold", 60), "job.threshold")
    if threshold is None or threshold > 100:
        raise ValueError("job.threshold must be between 0 and 100")

    breakdown = {
        "skills": {
            "score": round(skills_score, 3),
            "weight": SKILLS_WEIGHT,
            "matched": matched,
            "missing": missing,
        },
        "title": {
            "score": round(title_score, 3),
            "weight": TITLE_WEIGHT,
            "best_pair": best_pair,
        },
        "experience": {
            "score": round(experience_score, 3),
            "weight": EXPERIENCE_WEIGHT,
            "years_counted": candidate_years,
            "required_years": required_years,
        },
        "scorer_version": SCORER_VERSION,
    }
    return {
        "score": final_score,
        "above_threshold": final_score >= threshold,
        "score_breakdown": breakdown,
    }
