#!/usr/bin/env python3
"""Materialize the synthetic PDF/DOCX golden resumes from committed text fixtures."""
from __future__ import annotations

import json
from pathlib import Path
from zipfile import BadZipFile

from docx import Document
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "fixtures" / "golden"
SOURCE = GOLDEN / "source"
OUTPUT = GOLDEN / "resumes"


def _pdf_escape(value: str) -> str:
    value = value.encode("ascii", "replace").decode("ascii")
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _write_text_pdf(text: str, destination: Path) -> None:
    lines = text.splitlines()
    commands = ["BT", "/F1 10 Tf", "42 750 Td"]
    for line in lines:
        commands.append(f"({_pdf_escape(line[:105])}) Tj")
        commands.append("0 -20 Td")
    commands.append("ET")
    stream = ("\n".join(commands) + "\n").encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"endstream",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{number} 0 obj\n".encode("ascii"))
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")
    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    destination.write_bytes(pdf)


def _write_two_column_docx(text: str, destination: Path) -> None:
    lines = text.splitlines()
    doc = Document()
    doc.add_heading(lines[0], 0)
    doc.add_paragraph(lines[1])
    for heading, line_indexes in (
        ("PROFESSIONAL SUMMARY", [3]),
        ("PROFESSIONAL EXPERIENCE", [5, 6, 7]),
    ):
        doc.add_heading(heading, level=1)
        for index in line_indexes:
            doc.add_paragraph(lines[index])
    doc.add_heading("TECHNICAL SKILLS", level=1)
    skills = [item.strip() for item in lines[9].split(";") if item.strip()]
    table = doc.add_table(rows=0, cols=2)
    for index in range(0, len(skills), 2):
        cells = table.add_row().cells
        cells[0].text = skills[index]
        cells[1].text = skills[index + 1] if index + 1 < len(skills) else ""
    doc.add_heading("EDUCATION", level=1)
    doc.add_paragraph(lines[11])
    doc.add_paragraph(lines[12])
    doc.save(destination)


def _write_scanned_pdf(text: str, destination: Path) -> None:
    # Raster-only page: no PDF text layer. Textract must OCR the image.
    image = Image.new("1", (1240, 1754), 1)
    draw = ImageDraw.Draw(image)
    font_path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    font = ImageFont.truetype(str(font_path), 22) if font_path.exists() else ImageFont.load_default()
    y = 80
    for line in text.splitlines():
        draw.text((75, y), line[:100], fill=0, font=font)
        y += 112
    image.save(destination, format="PDF", resolution=150)


def main() -> int:
    expected = json.loads((GOLDEN / "expected.json").read_text(encoding="utf-8"))
    OUTPUT.mkdir(parents=True, exist_ok=True)
    counts = {"digital_pdf": 0, "two_column_docx": 0, "scanned_pdf": 0}

    for row in expected["resumes"]:
        source_path = SOURCE / f"{row['id'].lower()}.txt"
        if not source_path.is_file():
            raise FileNotFoundError(source_path)
        text = source_path.read_text(encoding="utf-8")
        destination = OUTPUT / row["file_name"]
        if row["format"] == "digital_pdf":
            _write_text_pdf(text, destination)
        elif row["format"] == "two_column_docx":
            _write_two_column_docx(text, destination)
        elif row["format"] == "scanned_pdf":
            _write_scanned_pdf(text, destination)
        else:
            raise ValueError(f"unsupported golden format: {row['format']}")
        counts[row["format"]] += 1

    assert counts == {"digital_pdf": 4, "two_column_docx": 4, "scanned_pdf": 4}
    for row in expected["resumes"]:
        path = OUTPUT / row["file_name"]
        data = path.read_bytes()
        if row["format"] in {"digital_pdf", "scanned_pdf"}:
            assert data.startswith(b"%PDF-"), path
        if row["format"] == "scanned_pdf":
            assert b"/Subtype /Image" in data and b"BT" not in data, path
        if row["format"] == "two_column_docx":
            try:
                doc = Document(path)
            except (BadZipFile, Exception) as exc:
                raise AssertionError(f"invalid DOCX fixture: {path}") from exc
            assert doc.tables and len(doc.tables[0].columns) == 2, path

    print("golden documents generated:", counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
