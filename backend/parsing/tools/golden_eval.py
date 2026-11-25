"""Accuracy evaluation on the golden set (brief section 2, group C).

  python backend/parsing/tools/golden_eval.py --offline                      # clean text + real DOCX, taxonomy fallback only (no AWS)
  python backend/parsing/tools/golden_eval.py --bucket BUCKET --prefix golden/   # real Textract + Comprehend on files already uploaded
Writes fixtures/golden/ACCURACY.md. Targets: skill recall and precision >= 85%, email 11/12, experience within 1 year 10/12,
correct top candidate for all 3 golden JDs.
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).parent)]
import comprehend_client as cc  # noqa: E402
import extract  # noqa: E402
import fields  # noqa: E402
import jd_handler  # noqa: E402
import scoring_reference as ref  # noqa: E402

AS_OF = date(2026, 11, 23)
GOLD = ROOT / "fixtures/golden"


def load_labels():
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted((GOLD / "labels").glob("*.json"))}


def parse_offline(labels):
    out = {}
    for rid, lab in labels.items():
        if lab["file"].endswith(".docx"):
            text = extract.docx_text((GOLD / "resumes" / lab["file"]).read_bytes())
        else:  # PDFs: the clean ground-truth text a perfect OCR would return
            text = (GOLD / "text" / f"{rid}.txt").read_text(encoding="utf-8")
        out[rid] = fields.parse_resume(text, [], AS_OF)
    return out


def parse_aws(labels, bucket, prefix):
    import boto3
    import config
    s3, textract, comprehend = boto3.client("s3"), boto3.client("textract"), boto3.client("comprehend")
    out = {}
    for rid, lab in labels.items():
        text = extract.extract_text(bucket, f"{prefix}{lab['file']}", s3=s3, textract=textract)
        out[rid] = fields.parse_resume(text, cc.merge_entities(cc.detect_entities(text, comprehend, config.comprehend_endpoint_arn())), AS_OF)
    return out


def evaluate(parsed, labels):
    tp = fp = fn = 0
    for rid, lab in labels.items():
        want, got = set(lab["skills"]), set(parsed[rid]["skills"])
        tp, fp, fn = tp + len(want & got), fp + len(got - want), fn + len(want - got)
    return {
        "skill_recall": tp / (tp + fn), "skill_precision": tp / (tp + fp),
        "email_correct": sum(parsed[r]["email"] == l["email"] for r, l in labels.items()),
        "experience_within_1y": sum(abs(parsed[r]["experience_years"] - l["experience_years"]) <= 1 for r, l in labels.items()),
        "name_correct": sum((parsed[r]["name"] or "").casefold() == l["name"].casefold() for r, l in labels.items()),
        "titles_exact": sum(set(parsed[r]["titles"]) == set(l["titles"]) for r, l in labels.items()),
        "n": len(labels),
    }


def ranking(parsed):
    rows = []
    for jd in json.loads((GOLD / "jds/expected.json").read_text())["jds"]:
        text = (GOLD / "jds" / jd["file"]).read_text(encoding="utf-8")
        job = {"required_skills": fields.derive_skills(text), "jd_titles": jd_handler.jd_titles(text, None),
               "required_years": jd_handler.required_years(text)}
        order = ref.rank(parsed, job)
        rows.append({"jd": jd["id"], "top_ok": order[0] == jd["expected_top"], "order_ok": order == jd["expected_ranking"],
                     "job_fields_ok": job == {k: jd[k] for k in job} or {k: (sorted(v) if k == "required_skills" else v) for k, v in job.items()} ==
                     {k: (sorted(jd[k]) if k == "required_skills" else jd[k]) for k in job}, "got_top": order[0], "want_top": jd["expected_top"]})
    return rows


def report(m, rank_rows, mode):
    ok = lambda b: "PASS" if b else "FAIL"  # noqa: E731
    n = m["n"]
    lines = [f"# Accuracy report ({mode})", "", f"As-of date for experience: {AS_OF}. Golden set: {n} resumes, 3 JDs.", "",
             "| Check | Result | Target | Status |", "|---|---|---|---|",
             f"| Skill recall | {m['skill_recall']:.1%} | >= 85% | {ok(m['skill_recall'] >= .85)} |",
             f"| Skill precision | {m['skill_precision']:.1%} | >= 85% | {ok(m['skill_precision'] >= .85)} |",
             f"| Email correct | {m['email_correct']}/{n} | >= 11/12 | {ok(m['email_correct'] >= 11)} |",
             f"| Experience within 1 year | {m['experience_within_1y']}/{n} | >= 10/12 | {ok(m['experience_within_1y'] >= 10)} |",
             f"| Name correct (info) | {m['name_correct']}/{n} | - | - |", f"| Titles exact (info) | {m['titles_exact']}/{n} | - | - |"]
    lines += ["", "| JD | Top candidate | Expected | Status | Full order matches |", "|---|---|---|---|---|"]
    lines += [f"| {r['jd']} | {r['got_top']} | {r['want_top']} | {ok(r['top_ok'])} | {r['order_ok']} |" for r in rank_rows]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--bucket")
    ap.add_argument("--prefix", default="golden/")
    a = ap.parse_args()
    labels = load_labels()
    if a.offline:
        parsed, mode = parse_offline(labels), "offline: clean text + real DOCX, taxonomy fallback only"
    elif a.bucket:
        parsed, mode = parse_aws(labels, a.bucket, a.prefix), f"AWS: Textract + Comprehend, s3://{a.bucket}/{a.prefix}"
    else:
        ap.error("use --offline or --bucket")
    text = report(evaluate(parsed, labels), ranking(parsed), mode)
    (GOLD / "ACCURACY.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
