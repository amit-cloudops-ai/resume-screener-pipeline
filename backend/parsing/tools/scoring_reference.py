"""Reference implementation of the brief's section 7 scoring formula.

FOR EVALUATION ONLY (golden-set ranking check). Part B owns the real scorer in backend/scoring/;
Part A never imports Part B's code, so this is an independent copy of the written spec.
"""
SENIORITY = {"intern": 0, "junior": 1, "mid": 2, "senior": 3, "lead": 4, "principal": 5}


def _split(title: str):
    words = title.split()
    if words and words[0] in SENIORITY:
        return SENIORITY[words[0]], words[1:]
    return SENIORITY["mid"], words


def title_score(candidate_titles, jd_titles) -> float:
    best = 0.0
    for ct in candidate_titles:
        lc, cw = _split(ct)
        for jt in jd_titles:
            lj, jw = _split(jt)
            jaccard = len(set(cw) & set(jw)) / len(set(cw) | set(jw)) if (cw or jw) else 0.0
            diff = abs(lc - lj)
            best = max(best, jaccard * (1.0 if diff == 0 else 0.85 if diff == 1 else 0.5))
    return best


def score(candidate: dict, job: dict) -> float:
    req = job["required_skills"]
    skills = len(set(req) & set(candidate["skills"])) / len(req) if req else 0.0
    years_req = job.get("required_years") or 0
    exp = 1.0 if not years_req else min(candidate["experience_years"] / years_req, 1.0)
    return round(100 * (0.50 * skills + 0.30 * title_score(candidate["titles"], job["jd_titles"]) + 0.20 * exp), 1)


def rank(candidates: dict[str, dict], job: dict) -> list[str]:
    return [cid for cid, _ in sorted(((c, score(v, job)) for c, v in candidates.items()), key=lambda x: (-x[1], x[0]))]
