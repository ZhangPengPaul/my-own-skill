#!/usr/bin/env python3
"""Generate deterministic fictional PDF and image fixtures."""

import argparse
from pathlib import Path
import xml.etree.ElementTree as ET


HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
SVG_NAMESPACE = "http://www.w3.org/2000/svg"
MATH_LINES = (
    "Fictional mathematics review",
    "1. Solve x^2 - 5x + 6 = 0.",
    "Student answer: x = 2. The second root was omitted.",
    "2. For y = (x - 1)^2 + 3, state the vertex.",
    "Student answer: (1, -3).",
)
ESSAY_LINES = (
    "My weekend volunteer work",
    "Last Saturday I go to the community library.",
    "I helped children find books and read stories.",
    "Although I was tired, but I felt useful.",
    "I hope to join the activity again next month.",
)


def escape_pdf(text):
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def write_pdf(path, lines):
    stream_lines = ["BT", "/F1 12 Tf", "72 760 Td"]
    for index, line in enumerate(lines):
        if index:
            stream_lines.append("0 -22 Td")
        stream_lines.append("(%s) Tj" % escape_pdf(line))
    stream_lines.append("ET")
    stream = ("\n".join(stream_lines) + "\n").encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"endstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(("%d 0 obj\n" % number).encode("ascii"))
        output.extend(body)
        output.extend(b"\nendobj\n")
    xref = len(output)
    output.extend(("xref\n0 %d\n" % (len(objects) + 1)).encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(("%010d 00000 n \n" % offset).encode("ascii"))
    output.extend(
        (
            "trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
            % (len(objects) + 1, xref)
        ).encode("ascii")
    )
    path.write_bytes(output)


def write_svg(path, lines=ESSAY_LINES):
    ET.register_namespace("", SVG_NAMESPACE)
    root = ET.Element(
        f"{{{SVG_NAMESPACE}}}svg", {"width": "900", "height": "280"}
    )
    ET.SubElement(
        root,
        f"{{{SVG_NAMESPACE}}}rect",
        {"width": "100%", "height": "100%", "fill": "white"},
    )
    for index, line in enumerate(lines):
        element = ET.SubElement(
            root,
            f"{{{SVG_NAMESPACE}}}text",
            {"x": "30", "y": str(50 + index * 38), "font-size": "20"},
        )
        element.text = line
    path.write_text(ET.tostring(root, encoding="unicode") + "\n", encoding="utf-8")


def generate_fixtures(output_dir=FIXTURES):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_pdf(
        output_dir / "math-exam.pdf",
        MATH_LINES,
    )
    write_svg(output_dir / "english-essay.svg")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=FIXTURES)
    args = parser.parse_args(argv)
    generate_fixtures(args.output_dir)


if __name__ == "__main__":
    main()
