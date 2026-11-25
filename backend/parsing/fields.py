"""Field derivation (A5): name, email, skills, titles, employers, years of experience.

Everything here is deterministic and has no AWS imports. Entities come from comprehend_client.merge_entities().
"""
import re
from datetime import date
from functools import lru_cache

import config
import taxonomy as tx

# ---------------------------------------------------------------- email
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}")


def find_email(text: str) -> str | None:
    m = EMAIL_RE.search(text)
    return m.group(0).lower() if m else None


# ---------------------------------------------------------------- skills
# Ordinary English words that are also skill names: only matched when written as Name / NAME.
_AMBIGUOUS = {"express", "spring", "react", "swift", "ruby", "excel", "rails", "bootstrap"}
_LEFT, _RIGHT = r"(?<![A-Za-z0-9+#.])", r"(?![A-Za-z0-9+#])"


@lru_cache(maxsize=1)
def _skill_regexes():
    lookup = tx.skill_lookup()
    names = sorted(lookup, key=len, reverse=True)
    plain = "|".join(re.escape(n) for n in names if n not in _AMBIGUOUS)
    amb = "|".join(f"{re.escape(n.capitalize())}|{re.escape(n.upper())}" for n in names if n in _AMBIGUOUS)
    return (re.compile(f"{_LEFT}(?:{plain}){_RIGHT}", re.I), re.compile(f"{_LEFT}(?:{amb}){_RIGHT}"))


def skills_in_text(text: str) -> set[str]:
    lookup = tx.skill_lookup()
    found = set()
    for rx in _skill_regexes():
        for m in rx.finditer(text):
            found.add(lookup[tx.clean(m.group(0))])
    return found


def derive_skills(text: str, entities: list[dict] = ()) -> list[str]:
    """Dictionary match over the raw text (always) + custom-model SKILL entities (when present)."""
    found = skills_in_text(text)
    for e in entities:
        if e["Type"] == "SKILL":
            canonical = tx.normalize_skill(e["Text"])
            if canonical:
                found.add(canonical)
    return sorted(found)


# ---------------------------------------------------------------- titles
@lru_cache(maxsize=1)
def _title_regex():
    sen = "|".join(re.escape(w) for w in sorted(tx.seniority_lookup(), key=len, reverse=True))
    names = "|".join(re.escape(n) for n in sorted(tx.title_lookup(), key=len, reverse=True))
    return re.compile(rf"(?<![A-Za-z0-9])(?:(?P<sen>{sen})\.?\s+)?(?P<title>{names})(?![A-Za-z0-9])", re.I)


def _compose(sen: str | None, title: str) -> str:
    canonical = tx.title_lookup()[tx.clean(title)]
    prefix = tx.seniority_canonical(sen) if sen else None
    return f"{prefix} {canonical}" if prefix else canonical


def normalize_title(text: str) -> str | None:
    """'Sr. DevOps Eng' -> 'senior devops engineer'. None if not a known title."""
    m = _title_regex().fullmatch(text.strip())
    return _compose(m.group("sen"), m.group("title")) if m else None


def titles_in_line(line: str) -> list[str]:
    return [_compose(m.group("sen"), m.group("title")) for m in _title_regex().finditer(line)]


def derive_titles(text: str, entities: list[dict] = ()) -> list[str]:
    """Titles found on short, non-bullet lines (job-title lines) + custom JOB_TITLE entities, seniority kept."""
    found: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s[0] in "•-*–—▪●·" or len(s.split()) > 14:
            continue
        found += titles_in_line(s)
    for e in entities:
        if e["Type"] == "JOB_TITLE":
            t = normalize_title(e["Text"])
            if t:
                found.append(t)
    return list(dict.fromkeys(found))


# ---------------------------------------------------------------- name, employers
_NOT_A_NAME = {"resume", "curriculum", "vitae", "cv", "profile", "summary", "contact", "experience", "education"}


def _looks_like_name(s: str) -> bool:
    words = s.split()
    if not 2 <= len(words) <= 4:
        return False
    if not all(re.fullmatch(r"[A-Za-z][A-Za-z.'\-]*", w) for w in words):
        return False
    if any(w.lower() in _NOT_A_NAME for w in words):
        return False
    return not titles_in_line(s) and not any(tx.normalize_skill(w) for w in words)


def _tidy_name(s: str) -> str:
    s = " ".join(s.split())
    return s.title() if s.isupper() or s.islower() else s


def derive_name(entities: list[dict], text: str) -> str | None:
    people = sorted(
        (e for e in entities if e["Type"] == "PERSON" and e["Score"] >= 0.6 and e.get("Chunk", 0) == 0),
        key=lambda e: e.get("BeginOffset") or 0,
    )
    for e in people:
        if (e.get("BeginOffset") or 0) < 600 and _looks_like_name(e["Text"]):
            return _tidy_name(e["Text"])
    for line in [ln.strip() for ln in text.splitlines() if ln.strip()][:5]:
        if _looks_like_name(line) and all(w[0].isupper() for w in line.split()):
            return _tidy_name(line)
    return None


def derive_employers(entities: list[dict]) -> list[str]:
    out, seen = [], set()
    for e in entities:
        t = e["Text"].strip()
        if e["Type"] != "ORGANIZATION" or e["Score"] < 0.7 or len(t) < 2:
            continue
        if tx.normalize_skill(t) or t.casefold() in seen:  # "AWS" / "Docker" are not employers
            continue
        seen.add(t.casefold())
        out.append(t)
    return out


# ---------------------------------------------------------------- years of experience
_MONTH = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
_MONTH_RX = (r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|"
             r"sept?(?:ember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?")


def _date_rx(g: str) -> str:
    return (rf"(?<!\d)(?:(?:(?P<m{g}>{_MONTH_RX})\.?,?\s+)|(?:(?P<n{g}>\d{{1,2}})[/.](?=(?:19|20)\d{{2}})))?"
            rf"(?P<y{g}>(?:19|20)\d{{2}})(?!\d)")


_RANGE = re.compile(
    rf"{_date_rx('s')}\s*(?:-|–|—|to|until|till)\s*(?:(?P<pres>present|current|now|date|ongoing)|{_date_rx('e')})", re.I)
_EDU_LINE = re.compile(
    r"\b(b\.?\s?tech|b\.?\s?e\b|bachelor|master|m\.?\s?tech|mba|b\.?\s?sc|m\.?\s?sc|degree|diploma|university|college|school|graduat)", re.I)
_EDU_HEADINGS = {"education", "academic background", "academics", "academic qualifications", "qualifications",
                 "certifications", "courses", "training"}
_OTHER_HEADINGS = {"experience", "work experience", "professional experience", "employment", "employment history",
                   "work history", "summary", "professional summary", "profile", "skills", "technical skills",
                   "projects", "career", "achievements", "languages", "interests", "contact", "objective",
                   "career objective"}
_PHRASE = re.compile(r"(\d{1,2})(?:\.\d+)?\s*\+?\s*(?:years?|yrs?)\s+(?:of\s+)?(?:(?:relevant|professional|total|work|industry|hands-on|overall)\s+)*experience", re.I)


def _month_index(year: int, month: int) -> int:
    return year * 12 + month


def _ranges(text: str, today: date) -> list[tuple[int, int]]:
    now = _month_index(today.year, today.month)
    in_education, out = False, []
    for line in text.splitlines():
        heading = line.strip().strip(":").lower()
        if heading in _EDU_HEADINGS:
            in_education = True
            continue
        if heading in _OTHER_HEADINGS:
            in_education = False
            continue
        if in_education or _EDU_LINE.search(line):
            continue
        for m in _RANGE.finditer(line):
            sm = _MONTH.get((m.group("ms") or "")[:3].lower()) or int(m.group("ns") or 1)
            start = _month_index(int(m.group("ys")), min(max(sm, 1), 12))
            if m.group("pres"):
                end = now
            else:
                em = _MONTH.get((m.group("me") or "")[:3].lower()) or int(m.group("ne") or 12)
                end = _month_index(int(m.group("ye")), min(max(em, 1), 12))
            end = min(end, now)
            if start <= end:
                out.append((start, end))
    return out


def derive_experience_years(text: str, today: date | None = None) -> float:
    """Union of date ranges (overlaps not double counted), 'Present' = today, capped at 40.
    Falls back to a phrase like '6 years of experience'. Unknown -> 0.0 (brief: unknown scores zero)."""
    today = today or date.today()
    spans = sorted(_ranges(text, today))
    if spans:
        months, (cur_s, cur_e) = 0, spans[0]
        for s, e in spans[1:]:
            if s <= cur_e + 1:
                cur_e = max(cur_e, e)
            else:
                months += cur_e - cur_s + 1
                cur_s, cur_e = s, e
        months += cur_e - cur_s + 1
        years = months / 12
    else:
        found = [int(m.group(1)) for m in _PHRASE.finditer(text)]
        years = float(max(found)) if found else 0.0
    return round(min(years, config.MAX_EXPERIENCE_YEARS), 1)


# ---------------------------------------------------------------- everything at once
def parse_resume(text: str, entities: list[dict], today: date | None = None) -> dict:
    return {
        "name": derive_name(entities, text),
        "email": find_email(text),
        "skills": derive_skills(text, entities),
        "employers": derive_employers(entities),
        "titles": derive_titles(text, entities),
        "experience_years": derive_experience_years(text, today),
    }
