"""Builds the golden set (A2) and the smoke-test resumes: fake people, fake e-mails, hand-written labels.

Run from the repo root:  python backend/parsing/tools/make_golden.py     (needs: reportlab python-docx pillow)
The labels below are written BY HAND; they are not produced by the extraction code under test.
Experience convention: months are counted inclusively, ranges are merged, 'Present' = AS_OF.
"""
import json
import shutil
import sys
import textwrap
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).parent))
import scoring_reference as ref  # noqa: E402

AS_OF = (11, 2026)  # (month, year), same order as the job dates below
MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
SUMMARY = "Focused on clear communication and dependable delivery."
EDU = {"b": "B.Tech Computer Science | State Institute of Technology | 2012 - 2016",
       "m": "M.Sc Statistics | Coastal University | 2013 - 2015",
       "d": "Diploma in Computer Applications | City Polytechnic | 2014 - 2017"}


TRAPS = {"g08": "Quick to react to feedback and keen to learn every week.",
         "g11": "Enjoys swift delivery of small fixes.",
         "g12": "Happy to express concerns early and keep plans on track."}


def J(title, canon, company, start, end, bullets):
    return dict(title=title, canon=canon, company=company, start=start, end=end, bullets=bullets)


R = [
 dict(id="g01", fmt="digital_pdf", name="Asha Verma", email="asha.verma@example.com", edu="b",
      skills=[("AWS", "aws"), ("Docker", "docker"), ("K8s", "kubernetes"), ("Terraform", "terraform"), ("CI/CD", "ci/cd"),
              ("Python", "python"), ("Linux", "linux"), ("Jenkins", "jenkins"), ("Helm", "helm"), ("Git", "git")],
      jobs=[J("Senior DevOps Engineer", "senior devops engineer", "Northwind Systems", (3, 2020), None,
              ["Run production Kubernetes clusters on Amazon Web Services for 40 services",
               "Cut deployment time by 60% with automated CI/CD pipelines",
               "Codified infrastructure with Terraform and Docker images"]),
            J("DevOps Engineer", "devops engineer", "Bluepeak Technologies", (6, 2017), (2, 2020),
              ["Maintained Linux build servers and release scripts in Python", "Set up Jenkins jobs for every repository"])]),
 dict(id="g02", fmt="docx_two_column", name="Rohan Iyer", email="rohan.iyer@example.com", edu="b",
      skills=[("Python", "python"), ("Docker", "docker"), ("AWS", "aws"), ("EC2", "ec2"), ("Linux", "linux"), ("Git", "git")],
      jobs=[J("Software Developer", "software engineer", "Orbit Labs", (1, 2021), (12, 2024),
              ["Built internal tools in Python and shipped them in Docker containers", "Deployed services to AWS EC2 instances running Linux"]),
            J("Junior Software Engineer", "junior software engineer", "Kestrel Analytics", (7, 2019), (12, 2020),
              ["Wrote automated checks and maintained Git workflows"])]),
 dict(id="g03", fmt="scanned_pdf", name="Meera Nair", email="meera.nair@example.com", edu="d",
      skills=[("AWS", "aws"), ("Kubernetes", "kubernetes"), ("Docker", "docker"), ("Terraform", "terraform"), ("CI/CD", "ci/cd"), ("Linux", "linux")],
      jobs=[J("Cloud Engineer", "cloud engineer", "Harbor Cloud Services", (2, 2020), (10, 2026),
              ["Moved legacy workloads to AWS and automated rollouts with Terraform",
               "Operate Kubernetes clusters and Docker based services on Linux hosts", "Maintain CI/CD pipelines for release teams"]),
            J("System Administrator", "system administrator", "Lumen Software", (8, 2016), (1, 2020),
              ["Looked after Linux servers and backups"])]),
 dict(id="g04", fmt="digital_pdf", name="Kabir Shah", email="kabir.shah@example.com", edu="b",
      skills=[("JavaScript", "javascript"), ("React", "react"), ("HTML", "html"), ("CSS", "css"), ("Docker", "docker"), ("Git", "git")],
      jobs=[J("Frontend Developer", "frontend engineer", "Bluepeak Technologies", (9, 2022), None,
              ["Built dashboards with JavaScript, React and CSS", "Packaged the app in Docker for the QA team"]),
            J("UI Developer", "frontend engineer", "Orbit Labs", (6, 2020), (8, 2022), ["Converted designs into HTML pages"])]),
 dict(id="g05", fmt="docx_two_column", name="Divya Menon", email="divya.menon@example.com", edu="m",
      skills=[("Python", "python"), ("SQL", "sql"), ("pandas", "pandas"), ("Scikit Learn", "scikit-learn"),
              ("TensorFlow", "tensorflow"), ("Machine Learning", "machine learning"), ("Statistics", "statistics")],
      jobs=[J("Senior Data Scientist", "senior data scientist", "Kestrel Analytics", (4, 2021), None,
              ["Trained churn models with scikit-learn and TensorFlow", "Ran experiments and statistical analysis for pricing",
               "Wrangled data with pandas and SQL"]),
            J("Data Scientist", "data scientist", "Lumen Software", (1, 2018), (3, 2021),
              ["Built forecasting notebooks in Python", "Applied machine learning to demand data"])]),
 dict(id="g06", fmt="digital_pdf", name="Arjun Rao", email="arjun.rao@example.com", edu="b",
      skills=[("Python", "python"), ("SQL", "sql"), ("pandas", "pandas"), ("Excel", "excel"), ("Tableau", "tableau"),
              ("Power BI", "power bi"), ("Statistics", "statistics")],
      jobs=[J("Data Analyst", "data analyst", "Harbor Cloud Services", (3, 2022), None,
              ["Built weekly reports in Excel and Tableau", "Cleaned data with Python and pandas",
               "Wrote SQL queries for finance and sales teams", "Ran statistical analysis on campaign results"]),
            J("Junior Data Analyst", "junior data analyst", "Orbit Labs", (7, 2020), (2, 2022), ["Prepared dashboards in Power BI"])]),
 dict(id="g07", fmt="scanned_pdf", name="Sneha Kulkarni", email="sneha.kulkarni@example.com", edu="b",
      skills=[("Python", "python"), ("SQL", "sql"), ("pandas", "pandas"), ("scikit-learn", "scikit-learn"),
              ("TensorFlow", "tensorflow"), ("PyTorch", "pytorch"), ("Machine Learning", "machine learning")],
      jobs=[J("ML Engineer", "machine learning engineer", "Northwind Systems", (10, 2021), None,
              ["Deployed machine learning models built with TensorFlow and PyTorch", "Prepared training data with Python, pandas and SQL"]),
            J("Junior Data Scientist", "junior data scientist", "Kestrel Analytics", (2, 2020), (9, 2021),
              ["Trained baseline models with scikit-learn"])]),
 dict(id="g08", fmt="docx_two_column", name="Vikram Das", email="vikram.das@example.com", edu="d",
      skills=[("Python", "python"), ("SQL", "sql"), ("pandas", "pandas")],
      jobs=[J("Junior Data Scientist", "junior data scientist", "Lumen Software", (8, 2024), None,
              ["Cleaned datasets with pandas and Python", "Wrote SQL for ad hoc questions"]),
            J("Data Intern", None, "Orbit Labs", (1, 2024), (6, 2024), ["Helped label training data"])]),
 dict(id="g09", fmt="digital_pdf", name="Pooja Singh", email="pooja.singh@example.com", edu="b",
      skills=[("JavaScript", "javascript"), ("TypeScript", "typescript"), ("React", "react"), ("HTML", "html"), ("CSS", "css"),
              ("REST API", "rest api"), ("Git", "git")],
      jobs=[J("Senior Frontend Engineer", "senior frontend engineer", "Harbor Cloud Services", (2, 2019), None,
              ["Lead a React and TypeScript codebase used by 200k people", "Built accessible pages with HTML and CSS",
               "Integrated REST APIs and wrote JavaScript tests"]),
            J("Frontend Developer", "frontend engineer", "Bluepeak Technologies", (5, 2016), (1, 2019),
              ["Maintained Git repositories and release branches"])]),
 dict(id="g10", fmt="docx_two_column", name="Nikhil Joshi", email="nikhil.joshi@example.com", edu="b",
      skills=[("JavaScript", "javascript"), ("React", "react"), ("HTML", "html"), ("CSS", "css"), ("Git", "git")],
      jobs=[J("Frontend Engineer", "frontend engineer", "Orbit Labs", (9, 2021), None,
              ["Built React components in JavaScript", "Styled pages with HTML and CSS"]),
            J("Frontend Developer", "frontend engineer", "Kestrel Analytics", (3, 2020), (8, 2021), ["Managed code in Git"])]),
 dict(id="g11", fmt="scanned_pdf", name="Tara Bose", email="tara.bose@example.com", edu="d",
      skills=[("HTML", "html"), ("CSS", "css"), ("JavaScript", "javascript"), ("jQuery", "jquery"), ("Git", "git")],
      jobs=[J("Junior Frontend Developer", "junior frontend engineer", "Lumen Software", (1, 2025), None,
              ["Built landing pages with HTML, CSS and JavaScript", "Added small features with jQuery"])]),
 dict(id="g12", fmt="scanned_pdf", name="Imran Qureshi", email="imran.qureshi@example.com", edu="b",
      skills=[("Python", "python"), ("Django", "django"), ("Postgres", "postgresql"), ("REST API", "rest api"),
              ("AWS", "aws"), ("Docker", "docker"), ("Git", "git")],
      jobs=[J("Backend Engineer", "backend engineer", "Northwind Systems", (5, 2020), None,
              ["Built APIs with Python and Django", "Stored data in Postgres and wrote REST API notes", "Deployed to AWS using Docker"])]),
]

JDS = [
 dict(id="jd1", file="jd1_devops.txt", titles=["devops engineer"], years=3,
      skills=["aws", "docker", "kubernetes", "terraform", "ci/cd", "python", "linux"],
      text="DevOps Engineer\n\nWe are hiring a DevOps Engineer to run our delivery platform.\n\nYou will work with AWS, Docker, Kubernetes, Terraform, CI/CD pipelines, Python and Linux.\n\nRequirements\nMinimum 3+ years of experience in DevOps or platform roles.\nGood written communication.\n"),
 dict(id="jd2", file="jd2_data_scientist.txt", titles=["data scientist"], years=3,
      skills=["python", "sql", "pandas", "machine learning", "scikit-learn", "tensorflow", "statistics"],
      text="Data Scientist\n\nWe are hiring a Data Scientist to build models for our customers.\n\nYou will use Python, SQL, pandas, machine learning, scikit-learn, TensorFlow and statistics every day.\n\nRequirements\n3+ years of experience building models in production.\n"),
 dict(id="jd3", file="jd3_frontend.txt", titles=["frontend engineer"], years=2,
      skills=["javascript", "typescript", "react", "html", "css", "rest api", "git"],
      text="Frontend Engineer\n\nWe are hiring a Frontend Engineer for our web product.\n\nYou will write JavaScript, TypeScript, React, HTML and CSS, call REST APIs and use Git daily.\n\nRequirements\nAt least 2 years of experience shipping web interfaces.\n"),
]


def mi(m, y):
    return y * 12 + m


def label_years(jobs):
    spans = sorted((mi(*j["start"]), mi(*(j["end"] or AS_OF))) for j in jobs)
    total, (s, e) = 0, spans[0]
    for a, b in spans[1:]:
        if a <= e + 1:
            e = max(e, b)
        else:
            total, s, e = total + e - s + 1, a, b
    return round((total + e - s + 1) / 12, 1)


def fmt_range(j):
    a = f"{MON[j['start'][0]-1]} {j['start'][1]}"
    b = "Present" if j["end"] is None else f"{MON[j['end'][0]-1]} {j['end'][1]}"
    return f"{a} - {b}"


def blocks(r):
    """Single-column layout shared by digital PDF, scanned PDF and the .txt ground truth."""
    out = [("name", r["name"]), ("contact", f"{r['email']} | Pune, India"), ("heading", "SUMMARY"), ("text", TRAPS.get(r["id"], SUMMARY)),
           ("heading", "SKILLS"), ("text", ", ".join(s for s, _ in r["skills"])), ("heading", "EXPERIENCE")]
    for j in r["jobs"]:
        out.append(("job", f"{j['title']} | {j['company']} | {fmt_range(j)}"))
        out += [("bullet", f"\u2022 {b}") for b in j["bullets"]]
    return out + [("heading", "EDUCATION"), ("text", EDU[r["edu"]])]


def write_digital_pdf(r, path):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    base = ParagraphStyle("b", fontName="Helvetica", fontSize=10.5, leading=14)
    st = {"name": ParagraphStyle("n", parent=base, fontName="Helvetica-Bold", fontSize=20, leading=24),
          "heading": ParagraphStyle("h", parent=base, fontName="Helvetica-Bold", fontSize=11.5, spaceBefore=10, spaceAfter=3),
          "job": ParagraphStyle("j", parent=base, fontName="Helvetica-Bold", spaceBefore=4), "bullet": ParagraphStyle("bl", parent=base, leftIndent=10)}
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=50, rightMargin=50, topMargin=50, bottomMargin=50)
    doc.build([Paragraph(escape(t), st.get(k, base)) for k, t in blocks(r)])


def write_docx(r, path):
    from docx import Document
    from docx.shared import Inches, Pt
    doc = Document()
    table = doc.add_table(rows=1, cols=2)
    left, right = table.rows[0].cells
    left.width, right.width = Inches(2.2), Inches(4.4)

    def add(cell, text, bold=False, size=10, first=[True]):
        p = cell.paragraphs[0] if not cell.text and len(cell.paragraphs) == 1 and not cell.paragraphs[0].text else cell.add_paragraph()
        run = p.add_run(text)
        run.bold, run.font.size = bold, Pt(size)

    add(left, r["name"], True, 16)
    add(left, r["email"])
    add(left, "SKILLS", True, 11)
    for s, _ in r["skills"]:
        add(left, s)
    add(left, "EDUCATION", True, 11)
    add(left, EDU[r["edu"]])
    add(right, "SUMMARY", True, 11)
    add(right, TRAPS.get(r["id"], SUMMARY))
    add(right, "EXPERIENCE", True, 11)
    for j in r["jobs"]:
        add(right, f"{j['title']} | {j['company']} | {fmt_range(j)}", True)
        for b in j["bullets"]:
            add(right, f"\u2022 {b}")
    doc.save(path)


def _font(bold, size):
    from PIL import ImageFont
    names = (["DejaVuSans-Bold.ttf", "arialbd.ttf"] if bold else ["DejaVuSans.ttf", "arial.ttf"])
    for n in names:
        try:
            return ImageFont.truetype(n, size)
        except OSError:
            continue
    return ImageFont.load_default()


def write_scanned_pdf(r, path):
    """Image-only PDF with slight rotation, noise and blur: Textract must OCR it (no text layer)."""
    from PIL import Image, ImageDraw, ImageFilter
    W, H, x, y = 1654, 2339, 120, 130
    img = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(img)
    for kind, text in blocks(r):
        bold, size, gap = kind in ("name", "heading", "job"), {"name": 44, "heading": 28}.get(kind, 26), {"name": 18, "heading": 26, "job": 10}.get(kind, 4)
        y += gap if kind != "heading" else gap
        for line in textwrap.wrap(text, 78 if size < 30 else 40) or [""]:
            d.text((x, y), line, font=_font(bold, size), fill=20)
            y += size + 12
    img = img.rotate(0.7, resample=Image.BICUBIC, fillcolor=255)
    img = Image.blend(img.filter(ImageFilter.GaussianBlur(0.6)), Image.effect_noise((W, H), 14), 0.07)
    img.save(path, "PDF", resolution=200)


def main():
    gold, smoke = ROOT / "fixtures/golden", ROOT / "fixtures/resumes"
    for sub in ("resumes", "text", "labels", "jds"):
        (gold / sub).mkdir(parents=True, exist_ok=True)
    smoke.mkdir(parents=True, exist_ok=True)
    labels = {}
    for r in R:
        ext = "docx" if r["fmt"].startswith("docx") else "pdf"
        fname = f"{r['id']}.{ext}"
        {"digital_pdf": write_digital_pdf, "docx_two_column": write_docx, "scanned_pdf": write_scanned_pdf}[r["fmt"]](r, gold / "resumes" / fname)
        (gold / "text" / f"{r['id']}.txt").write_text("\n".join(t for _, t in blocks(r)) + "\n", encoding="utf-8")
        titles = list(dict.fromkeys(j["canon"] for j in r["jobs"] if j["canon"]))
        labels[r["id"]] = dict(id=r["id"], file=fname, format=r["fmt"], name=r["name"], email=r["email"],
                               skills=sorted({c for _, c in r["skills"]}), titles=titles,
                               employers=list(dict.fromkeys(j["company"] for j in r["jobs"])),
                               experience_years=label_years(r["jobs"]), as_of="2026-11-23")
        (gold / "labels" / f"{r['id']}.json").write_text(json.dumps(labels[r["id"]], indent=2) + "\n", encoding="utf-8")
    expected = []
    for jd in JDS:
        (gold / "jds" / jd["file"]).write_text(jd["text"], encoding="utf-8")
        job = dict(required_skills=jd["skills"], jd_titles=jd["titles"], required_years=jd["years"])
        order = ref.rank({k: v for k, v in labels.items()}, job)
        expected.append(dict(id=jd["id"], file=jd["file"], **job, expected_ranking=order, expected_top=order[0]))
    (gold / "jds" / "expected.json").write_text(json.dumps({"as_of": "2026-11-23", "note": "Ranking = brief section 7 formula applied to the hand labels; Amit reviews.", "jds": expected}, indent=2) + "\n")
    # smoke-test set: 4 digital PDF, 3 DOCX, 2 scanned PDF, 1 corrupt (brief group B)
    for f in ["g01.pdf", "g04.pdf", "g06.pdf", "g09.pdf", "g02.docx", "g05.docx", "g08.docx", "g03.pdf", "g07.pdf"]:
        shutil.copy(gold / "resumes" / f, smoke / f)
    (smoke / "corrupt.pdf").write_bytes(b"this is not a real pdf file")
    shutil.copy(gold / "jds" / "jd1_devops.txt", smoke / "smoke_jd.txt")
    print("golden set written:", len(R), "resumes,", len(JDS), "JDs")
    for e in expected:
        print(e["id"], "top:", e["expected_top"], "order:", e["expected_ranking"])


if __name__ == "__main__":
    main()
