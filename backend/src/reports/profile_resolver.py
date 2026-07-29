import unicodedata
from pathlib import Path

from pydantic import ValidationError

from src.reports.profile import ReportProfile, load_report_profile


class ReportProfileResolutionError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def _normalized_filename(value: str) -> str:
    basename = value.strip().replace("\\", "/").rsplit("/", 1)[-1].strip()
    return unicodedata.normalize("NFKC", basename).casefold()


class ReportProfileResolver:
    def __init__(self, profile_root: Path):
        self.profile_root = profile_root

    def resolve(
        self,
        *,
        original_filename: str,
        page_count: int,
    ) -> Path | None:
        target = _normalized_filename(original_filename)
        matches: list[tuple[Path, ReportProfile]] = []

        for path in sorted(self.profile_root.glob("*.json")):
            try:
                profile = load_report_profile(path)
            except (OSError, ValueError, ValidationError) as exc:
                raise ReportProfileResolutionError(
                    "invalid_report_profile",
                    "报告 profile 配置无效。",
                ) from exc
            if _normalized_filename(profile.pdf_file) == target:
                matches.append((path, profile))

        if not matches:
            return None
        if len(matches) > 1:
            raise ReportProfileResolutionError(
                "duplicate_report_profile",
                "同一报告匹配到多个 profile。",
            )

        path, profile = matches[0]
        if profile.total_pdf_pages != page_count:
            raise ReportProfileResolutionError(
                "report_profile_page_count_mismatch",
                "报告页数与匹配的 profile 不一致。",
            )
        return path
