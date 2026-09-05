from __future__ import annotations

import argparse
import json
import sys
import textwrap
from pathlib import Path
from typing import Any

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


class DemoReportSourceError(ValueError):
    """Raised when the checked-in synthetic report source is incomplete."""


def _load_source(source_path: Path) -> dict[str, Any]:
    try:
        source = json.loads(source_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DemoReportSourceError(
            f"DEMO_REPORT_SOURCE_INVALID: unable to read {source_path.name}"
        ) from exc

    required_strings = ("company_name", "title", "fictional_notice")
    if source.get("schema_version") != 1 or any(
        not isinstance(source.get(field), str) or not source[field].strip()
        for field in required_strings
    ):
        raise DemoReportSourceError(
            "DEMO_REPORT_SOURCE_INVALID: required report identity is missing"
        )
    if not isinstance(source.get("report_year"), int):
        raise DemoReportSourceError(
            "DEMO_REPORT_SOURCE_INVALID: report_year must be an integer"
        )
    pages = source.get("pages")
    if not isinstance(pages, list) or not pages:
        raise DemoReportSourceError(
            "DEMO_REPORT_SOURCE_INVALID: at least one page is required"
        )
    for page in pages:
        if (
            not isinstance(page, dict)
            or not isinstance(page.get("title"), str)
            or not isinstance(page.get("paragraphs"), list)
            or not page["paragraphs"]
            or any(not isinstance(item, str) or not item.strip() for item in page["paragraphs"])
        ):
            raise DemoReportSourceError(
                "DEMO_REPORT_SOURCE_INVALID: each page needs a title and paragraphs"
            )
    return source


def _draw_wrapped(pdf: canvas.Canvas, text: str, *, x: float, y: float, width: int) -> float:
    for line in textwrap.wrap(text, width=width, break_long_words=False):
        pdf.drawString(x, y, line)
        y -= 15
    return y


def generate_demo_report(source_path: Path, output_path: Path) -> Path:
    source_path = Path(source_path)
    output_path = Path(output_path)
    source = _load_source(source_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    pdf = canvas.Canvas(
        str(output_path),
        pagesize=A4,
        pageCompression=1,
        invariant=1,
    )
    metadata = source.get("metadata") or {}
    pdf.setTitle(source["title"])
    pdf.setAuthor(str(metadata.get("author") or "ESG-Agent delivery verification"))
    pdf.setSubject(str(metadata.get("subject") or "Synthetic ESG workflow fixture"))
    pdf.setCreator(str(metadata.get("creator") or "ESG-Agent deterministic report generator"))
    pdf.setKeywords(str(metadata.get("keywords") or "fictional, synthetic"))

    page_width, page_height = A4
    total_pages = len(source["pages"])
    for page_number, page in enumerate(source["pages"], start=1):
        pdf.setFillColorRGB(0.08, 0.20, 0.16)
        pdf.rect(0, page_height - 74, page_width, 74, fill=1, stroke=0)
        pdf.setFillColorRGB(1, 1, 1)
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(42, page_height - 32, source["company_name"])
        pdf.setFont("Helvetica", 9)
        pdf.drawRightString(page_width - 42, page_height - 32, str(source["report_year"]))

        pdf.setFillColorRGB(0.08, 0.20, 0.16)
        pdf.setFont("Helvetica-Bold", 21)
        pdf.drawString(42, page_height - 116, page["title"])
        y = page_height - 152
        pdf.setFillColorRGB(0.13, 0.16, 0.15)
        pdf.setFont("Helvetica", 10.5)
        if page_number == 1:
            pdf.setFont("Helvetica-Bold", 13)
            y = _draw_wrapped(pdf, source["title"], x=42, y=y, width=75) - 12
            pdf.setFont("Helvetica-Bold", 10.5)
            y = _draw_wrapped(pdf, source["fictional_notice"], x=42, y=y, width=92) - 20
            pdf.setFont("Helvetica", 10.5)
        for paragraph in page["paragraphs"]:
            y = _draw_wrapped(pdf, paragraph, x=42, y=y, width=92) - 17
        pdf.setStrokeColorRGB(0.72, 0.79, 0.76)
        pdf.line(42, 48, page_width - 42, 48)
        pdf.setFillColorRGB(0.32, 0.38, 0.36)
        pdf.setFont("Helvetica", 8)
        pdf.drawString(42, 33, "Synthetic delivery fixture — no real company or confidential data")
        pdf.drawRightString(page_width - 42, 33, f"{page_number} / {total_pages}")
        pdf.showPage()
    pdf.save()
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the deterministic ESG-Agent demo PDF")
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        generated = generate_demo_report(args.source, args.output)
    except DemoReportSourceError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(f"DEMO_REPORT_GENERATED path={generated.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
