"""A9 (stretch): build Comprehend custom-entity training data for SKILL and JOB_TITLE.

  python backend/parsing/training/build_training_data.py --out training_data
Writes documents.txt (one document per line) and annotations.csv (File, Line, Begin Offset, End Offset, Type).
Comprehend needs >= 250 documents and >= 100 annotations per entity type; this script asserts both.

HONEST LIMIT: these documents are synthetic and built from our own taxonomy, so the model can only learn what the
taxonomy already knows. Mix in real, hand-annotated resumes (fake or consented data only) to make it better.
The taxonomy matcher stays the guaranteed fallback, so the pipeline never depends on this model.
"""
import argparse
import csv
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import taxonomy as tx  # noqa: E402

COMPANIES = ["Northwind Systems", "Bluepeak Technologies", "Orbit Labs", "Kestrel Analytics", "Lumen Software", "Harbor Cloud Services"]
SKILL_TEMPLATES = ["Skills: {}.", "Technical skills include {}.", "Hands-on with {}.", "Tools and technologies: {}."]
TITLE_TEMPLATES = ["{} at {}.", "Worked as {} for {}.", "Joined {} as {}.", "{} | {}"]


def build(n_docs=300, seed=7):
    rng = random.Random(seed)
    data = tx.load_taxonomy()
    skill_names = [n for e in data["skills"] for n in [e["canonical"], *e["aliases"]]]
    title_names = [n for e in data["job_titles"] for n in [e["canonical"], *e["aliases"]]]
    seniority = ["", "Senior ", "Junior ", "Lead ", "Principal "]
    docs, ann = [], []
    for line in range(n_docs):
        text, spans = "", []

        def add(sentence_parts, kind):
            nonlocal text
            for part in sentence_parts:
                if isinstance(part, tuple):  # (entity text, type)
                    start = len(text)
                    text += part[0]
                    spans.append((start, len(text), part[1]))
                else:
                    text += part
        title = rng.choice(seniority) + rng.choice(title_names).title()
        company = rng.choice(COMPANIES)
        tpl = rng.choice(TITLE_TEMPLATES)
        if tpl == "Joined {} as {}.":
            add(["Joined ", company, " as ", (title, "JOB_TITLE"), "."], "t")
        elif tpl == "Worked as {} for {}.":
            add(["Worked as ", (title, "JOB_TITLE"), " for ", company, "."], "t")
        elif tpl == "{} | {}":
            add([(title, "JOB_TITLE"), " | ", company], "t")
        else:
            add([(title, "JOB_TITLE"), " at ", company, "."], "t")
        text += " "
        chosen = [rng.choice([n, n.capitalize(), n.upper() if len(n) <= 4 else n.title()]) for n in rng.sample(skill_names, rng.randint(3, 7))]
        sk_tpl = rng.choice(SKILL_TEMPLATES)
        pre, post = sk_tpl.split("{}")
        parts = [pre]
        for i, s in enumerate(chosen):
            parts += [(s, "SKILL")] + ([", "] if i < len(chosen) - 1 else [])
        add(parts + [post], "s")
        docs.append(text)
        ann += [(line, b, e, t) for b, e, t in spans]
    assert len(docs) >= 250 and all(sum(1 for a in ann if a[3] == t) >= 100 for t in ("SKILL", "JOB_TITLE"))
    return docs, ann


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="training_data")
    ap.add_argument("--docs", type=int, default=300)
    a = ap.parse_args()
    docs, ann = build(a.docs)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "documents.txt").write_text("\n".join(docs) + "\n", encoding="utf-8")
    with open(out / "annotations.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["File", "Line", "Begin Offset", "End Offset", "Type"])
        w.writerows([["documents.txt", l, b, e, t] for l, b, e, t in ann])
    print(f"{len(docs)} documents, {len(ann)} annotations -> {out}/")


if __name__ == "__main__":
    main()
