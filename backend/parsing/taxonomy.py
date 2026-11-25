"""Skills / job-title / seniority taxonomy loader (task A1). No AWS imports."""
import json
import re
from functools import lru_cache
from pathlib import Path

DEFAULT_PATH = Path(__file__).with_name("skills_taxonomy.json")


def clean(text: str) -> str:
    """Lower-case, trim, collapse whitespace. Keeps symbols like + # . / used in c++, c#, ci/cd."""
    return re.sub(r"\s+", " ", str(text).strip().lower())


@lru_cache(maxsize=None)
def load_taxonomy(path: str | None = None) -> dict:
    with open(path or DEFAULT_PATH, encoding="utf-8") as f:
        return json.load(f)


def _lookup(entries: list[dict]) -> dict[str, str]:
    table: dict[str, str] = {}
    for e in entries:
        for name in [e["canonical"], *e["aliases"]]:
            table[clean(name)] = e["canonical"]
    return table


def skill_lookup(path: str | None = None) -> dict[str, str]:
    """alias or canonical (lower-case) -> canonical skill."""
    return _lookup(load_taxonomy(path)["skills"])


def title_lookup(path: str | None = None) -> dict[str, str]:
    return _lookup(load_taxonomy(path)["job_titles"])


def seniority_lookup(path: str | None = None) -> dict[str, int]:
    """seniority word -> level (0 = lowest)."""
    table: dict[str, int] = {}
    for e in load_taxonomy(path)["seniority_levels"]:
        for name in [e["canonical"], *e["aliases"]]:
            table[clean(name)] = e["level"]
    return table


def normalize_skill(text: str) -> str | None:
    """'K8s' -> 'kubernetes'. Returns None if the text is not a known skill."""
    return skill_lookup().get(clean(text))


def seniority_canonical(word: str) -> str | None:
    """'sr' -> 'senior'. None if the word is not a seniority word."""
    level = seniority_lookup().get(clean(word))
    if level is None:
        return None
    return next(e["canonical"] for e in load_taxonomy()["seniority_levels"] if e["level"] == level)
