from datetime import date

import pytest

import fields as f

TODAY = date(2026, 11, 23)


def ent(text, type_, score=0.99, begin=0, chunk=0):
    return {"Text": text, "Type": type_, "Score": score, "BeginOffset": begin, "Chunk": chunk}


# ---- email
@pytest.mark.parametrize("text,expected", [("Mail: Asha.Verma@Example.COM today", "asha.verma@example.com"),
                                           ("a+b@sub.example.co.in", "a+b@sub.example.co.in"), ("no email here", None)])
def test_email(text, expected):
    assert f.find_email(text) == expected


# ---- skills
def test_skills_normalise_aliases_and_respect_word_boundaries():
    text = "Skills: K8s, Amazon Web Services, CI/CD, Node.js, C++, C#, MySQL and Java. Also NoSQL and JavaScripty things."
    got = f.derive_skills(text)
    assert {"kubernetes", "aws", "ci/cd", "node.js", "c++", "c#", "mysql", "java"} <= set(got)
    assert "javascript" not in got and "sql" not in got  # no partial matches inside other words


def test_ambiguous_words_need_proper_capitalisation():
    assert "react" not in f.derive_skills("They react quickly and express interest in spring weather")
    assert {"react", "express"} <= set(f.derive_skills("Built apps with React and Express"))


def test_custom_model_skills_are_normalised_and_unknowns_dropped():
    got = f.derive_skills("nothing here", [ent("K8s", "SKILL"), ent("Basket weaving", "SKILL")])
    assert got == ["kubernetes"]


# ---- titles
def test_titles_keep_seniority_and_expand_aliases():
    text = "Sr. DevOps Eng | Acme\nSoftware Developer, Beta\n- Worked with product managers daily\nSite Reliability Engineer"
    assert f.derive_titles(text) == ["senior devops engineer", "software engineer", "site reliability engineer"]


def test_normalize_title():
    assert f.normalize_title("Senior SRE") == "senior site reliability engineer"
    assert f.normalize_title("Chief Banana Officer") is None


# ---- name / employers
def test_name_from_person_entity_then_first_line_fallback():
    assert f.derive_name([ent("asha verma", "PERSON")], "x") == "Asha Verma"
    assert f.derive_name([], "ASHA VERMA\nDevOps Engineer") == "Asha Verma"
    assert f.derive_name([], "Senior DevOps Engineer\nAcme") is None  # a title is not a name
    assert f.derive_name([ent("Zed", "PERSON")], "no name") is None


def test_employers_filtered():
    ents = [ent("Acme Corp", "ORGANIZATION"), ent("acme corp", "ORGANIZATION"), ent("AWS", "ORGANIZATION"),
            ent("Beta Ltd", "ORGANIZATION", 0.5), ent("Gamma Inc", "ORGANIZATION", 0.8)]
    assert f.derive_employers(ents) == ["Acme Corp", "Gamma Inc"]


# ---- experience
def years(text):
    return f.derive_experience_years(text, TODAY)


def test_overlaps_are_not_double_counted():
    assert years("EXPERIENCE\nA | Jan 2020 - Dec 2021\nB | Jun 2021 - Dec 2022") == 3.0


def test_present_means_today():
    assert years("EXPERIENCE\nA | Jan 2025 - Present") == 1.9  # Jan 2025..Nov 2026 = 23 months


def test_separate_ranges_add_up():
    assert years("EXPERIENCE\nA | Jan 2018 - Dec 2018\nB | Jan 2020 - Dec 2020") == 2.0


def test_numeric_and_year_only_formats():
    assert years("EXPERIENCE\nA | 03/2019 - 02/2021") == 2.0
    assert years("EXPERIENCE\nA | 2019 - 2021") == 3.0


def test_education_dates_are_ignored():
    text = "EDUCATION\nB.Tech Computer Science 2012 - 2016\nEXPERIENCE\nA | Jan 2019 - Dec 2019"
    assert years(text) == 1.0
    assert years("B.Tech, 2012 - 2016, State University\nA | Jan 2019 - Dec 2019") == 1.0


def test_phrase_fallback_and_unknown_and_cap():
    assert years("Seasoned engineer with 6+ years of experience") == 6.0
    assert years("no dates at all") == 0.0
    assert years("EXPERIENCE\nA | 1970 - Present") == 40.0


def test_future_and_reversed_ranges_are_ignored():
    assert years("EXPERIENCE\nA | Jan 2031 - Dec 2032\nB | Dec 2020 - Jan 2019") == 0.0
