from collections import Counter

import taxonomy as t

DATA = t.load_taxonomy()


def _all_names(entries):
    return [t.clean(n) for e in entries for n in [e["canonical"], *e["aliases"]]]


def test_loads_and_has_enough_skills():
    assert len(DATA["skills"]) >= 150


def test_no_duplicate_names_across_skills():
    dupes = [n for n, c in Counter(_all_names(DATA["skills"])).items() if c > 1]
    assert dupes == []


def test_no_duplicate_names_across_titles():
    dupes = [n for n, c in Counter(_all_names(DATA["job_titles"])).items() if c > 1]
    assert dupes == []


def test_no_duplicate_seniority_words():
    words = [t.clean(n) for e in DATA["seniority_levels"] for n in [e["canonical"], *e["aliases"]]]
    assert [n for n, c in Counter(words).items() if c > 1] == []


def test_names_are_clean_lowercase_and_not_empty():
    for entries in (DATA["skills"], DATA["job_titles"]):
        for e in entries:
            for n in [e["canonical"], *e["aliases"]]:
                assert n and n == t.clean(n), f"bad entry: {n!r}"


def test_seniority_levels_are_ordered_from_zero():
    assert [e["level"] for e in DATA["seniority_levels"]] == list(range(len(DATA["seniority_levels"])))


def test_brief_examples():
    assert t.normalize_skill("k8s") == "kubernetes"
    assert t.normalize_skill("K8s ") == "kubernetes"
    assert t.normalize_skill("Amazon Web Services") == "aws"
    for s in ["aws", "docker", "kubernetes", "terraform", "ci/cd", "python", "linux"]:  # JD from section 7
        assert t.normalize_skill(s) == s
    assert t.normalize_skill("not a real skill") is None


def test_titles_and_seniority():
    assert t.title_lookup()["sre"] == "site reliability engineer"
    assert t.seniority_lookup()["sr"] == t.seniority_lookup()["senior"]
    assert t.seniority_lookup()["junior"] < t.seniority_lookup()["senior"]
