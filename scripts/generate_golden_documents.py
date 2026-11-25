#!/usr/bin/env python3
"""Generate the 12 synthetic PDF/DOCX golden resumes from committed text fixtures."""
from __future__ import annotations

import json
import textwrap
import zlib
from pathlib import Path

from docx import Document

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "fixtures" / "golden"
SOURCE = GOLDEN / "source"
OUTPUT = GOLDEN / "resumes"

# Compact 5x7 bitmap alphabet used to render raster-only scanned PDF pages.
FONT = {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01111", "10000", "10000", "10000", "10000", "10000", "01111"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01111", "10000", "10000", "10111", "10001", "10001", "01111"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("11111", "00100", "00100", "00100", "00100", "00100", "11111"),
    "J": ("00111", "00010", "00010", "00010", "10010", "10010", "01100"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "10101", "01010"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00010", "00100", "01000", "11111"),
    "3": ("11110", "00001", "00001", "01110", "00001", "00001", "11110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "10000", "11110", "00001", "00001", "11110"),
    "6": ("01110", "10000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00001", "01110"),
    "@": ("01110", "10001", "10111", "10101", "10111", "10000", "01110"),
    ".": ("00000", "00000", "00000", "00000", "00000", "00110", "00110"),
    ",": ("00000", "00000", "00000", "00000", "00110", "00100", "01000"),
    ":": ("00000", "00110", "00110", "00000", "00110", "00110", "00000"),
    "/": ("00001", "00010", "00010", "00100", "01000", "01000", "10000"),
    "-": ("00000", "00000", "00000", "11111", "00000", "00000", "00000"),
    "+": ("00000", "00100", "00100", "11111", "00100", "00100", "00000"),
    ";": ("00000", "00110", "00110", "00000", "00110", "00100", "01000"),
    "|": ("00100", "00100", "00100", "00100", "00100", "00100", "00100"),
    "(": ("00010", "00100", "01000", "01000", "01000", "00100", "00010"),
    ")": ("01000", "00100", "00010", "00010", "00010", "00100", "01000"),
    "'": ("00100", "00100", "00000", "00000", "00000", "00000", "00000"),
    "&": ("01100", "10010", "10100", "01000", "10101", "10010", "01101"),
    "_": ("00000", "00000", "00000", "00000", "00000", "00000", "11111"),
}


def _build_pdf(objects: list[bytes]) -> bytes:
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{number} 0 obj\n".encode("ascii"))
        pdf.extend(obj + b"\nendobj\n")
    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    return bytes(pdf)


def _escape_line(value: str) -> str:
    value = value.encode("ascii", "replace").decode("ascii")
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _write_text_pdf(text: str, destination: Path) -> None:
    commands = ["BT /F1 10 Tf 42 750 Td"]
    for line in text.splitlines():
        commands.extend([f"({_escape_line(line[:105])}) Tj", "0 -20 Td"])
    commands.append("ET")
    stream = "\n".join(commands).encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n"
        + stream + b"\nendstream",
    ]
    destination.write_bytes(_build_pdf(objects))


def _write_two_column_docx(text: str, destination: Path) -> None:
    lines = text.splitlines()
    doc = Document()
    doc.add_heading(lines[0], 0)
    doc.add_paragraph(lines[1])
    for heading, indexes in (
        ("PROFESSIONAL SUMMARY", [3]),
        ("PROFESSIONAL EXPERIENCE", [5, 6, 7]),
    ):
        doc.add_heading(heading, level=1)
        for index in indexes:
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
    # A real raster-only page: the PDF embeds a grayscale image and has no text layer.
    width, height, scale = 1240, 1754, 3
    pixels = bytearray([255]) * (width * height)
    y0 = 80
    for line in text.splitlines():
        for wrapped in textwrap.wrap(line.upper(), width=58) or [""]:
            x0 = 75
            for character in wrapped:
                glyph = FONT.get(character)
                if glyph:
                    for row, bitmap_row in enumerate(glyph):
                        for column, bit in enumerate(bitmap_row):
                            if bit == "1":
                                px = x0 + column * scale
                                py = y0 + row * scale
                                for dy in range(scale):
                                    offset = (py + dy) * width + px
                                    pixels[offset:offset + scale] = b"\x00" * scale
                x0 += 6 * scale
            y0 += 42

    image_data = zlib.compress(bytes(pixels), level=9)
    page_stream = b"q 612 0 0 792 0 0 cm /Im0 Do Q"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /XObject << /Im0 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(page_stream)).encode("ascii") + b" >>\nstream\n"
        + page_stream + b"\nendstream",
        b"<< /Type /XObject /Subtype /Image /Width " + str(width).encode("ascii")
        + b" /Height " + str(height).encode("ascii")
        + b" /ColorSpace /DeviceGray /BitsPerComponent 8 /Filter /FlateDecode /Length "
        + str(len(image_data)).encode("ascii") + b" >>\nstream\n"
        + image_data + b"\nendstream",
    ]
    destination.write_bytes(_build_pdf(objects))


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
        if row["format"] == "digital_pdf":
            assert b" Tj" in data and b"/Subtype /Image" not in data, path
        if row["format"] == "scanned_pdf":
            assert b"/Subtype /Image" in data
            assert b"BT" not in data and b" Tj" not in data
        if row["format"] == "two_column_docx":
            document = Document(path)
            assert document.tables and len(document.tables[0].columns) == 2, path

    print("golden documents generated:", counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
