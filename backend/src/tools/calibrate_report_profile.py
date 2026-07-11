from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from src.reports.profile import load_report_profile
from src.reports.profile_builder import calibrate_requirement_routes


def calibrate_profile_file(profile_path: Path, reviewed_csv: Path, output_path: Path) -> None:
    with reviewed_csv.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    reviewed_pages: dict[str, list[int]] = {}
    for row in rows:
        requirement_id = (row.get("requirement_id") or "").strip()
        if not requirement_id:
            continue
        raw_pages = row.get("correct_pdf_pages") or "[]"
        parsed = json.loads(raw_pages)
        reviewed_pages[requirement_id] = [int(page) for page in parsed]

    calibrated = calibrate_requirement_routes(load_report_profile(profile_path), reviewed_pages)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    try:
        temporary.write_text(
            json.dumps(calibrated.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(output_path)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibrate report-profile routes from manually reviewed pages.")
    parser.add_argument("profile", type=Path)
    parser.add_argument("reviewed_csv", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    calibrate_profile_file(args.profile, args.reviewed_csv, args.output)


if __name__ == "__main__":
    main()
