from argparse import Namespace
from pathlib import Path

import src.tools.regenerate_review_csv as module
from src.tools.regenerate_review_csv import filter_eligible_assessments, parse_args


def test_parse_args_defaults_disable_llm_and_ocr(tmp_path: Path):
    args = parse_args(
        [
            "--report-id",
            "envision_2024",
            "--pdf",
            "backend/data/reports/Envision Energy 2024-zh.pdf",
            "--profile",
            "backend/data/reports/profiles/envision_2024.json",
            "--output",
            str(tmp_path / "out.csv"),
        ]
    )

    assert args.confirm_llm is False
    assert args.enable_ocr is False


def test_filter_eligible_assessments_removes_compilation_requirements():
    assessments = [
        {"requirement_id": "GRI 2-1-a", "requirement_type": "assessment"},
        {"requirement_id": "GRI 305-2-2.3", "requirement_type": "compilation_requirement"},
        {"requirement_id": "GRI 305-2-2.3.4", "requirement_type": "assessment"},
    ]

    filtered = filter_eligible_assessments(assessments)

    assert filtered == [{"requirement_id": "GRI 2-1-a", "requirement_type": "assessment"}]


def test_parse_args_accepts_baseline_and_diff_outputs(tmp_path: Path):
    args = parse_args(
        [
            "--report-id",
            "envision_2024",
            "--pdf",
            "backend/data/reports/Envision Energy 2024-zh.pdf",
            "--profile",
            "backend/data/reports/profiles/envision_2024.json",
            "--output",
            str(tmp_path / "out.csv"),
            "--baseline",
            "tmp/review/current_577_review_after_profile_routing.csv",
            "--audit-output",
            str(tmp_path / "audit.json"),
            "--diff-summary-output",
            str(tmp_path / "diff.json"),
        ]
    )

    assert str(args.baseline).endswith("current_577_review_after_profile_routing.csv")
    assert args.audit_output.name == "audit.json"
    assert args.diff_summary_output.name == "diff.json"


def test_run_single_report_regeneration_uses_workflow_without_llm_or_ocr(monkeypatch, tmp_path):
    calls = {}

    class FakeRun:
        run_id = "run-1"
        status = "completed"
        error_message = None

    class FakeWorkflow:
        def run(self, report_id, pdf_path, source_file_hash, confirm_llm, enable_ocr=False, ocr_pages=None):
            calls["report_id"] = report_id
            calls["pdf_path"] = pdf_path
            calls["source_file_hash"] = source_file_hash
            calls["confirm_llm"] = confirm_llm
            calls["enable_ocr"] = enable_ocr
            calls["ocr_pages"] = ocr_pages
            return FakeRun()

    class FakeRepository:
        def __init__(self):
            self.reports = []

        def create_report(self, report):
            self.reports.append(report)
            return report

        def list_assessments_by_run(self, run_id):
            assert run_id == "run-1"
            return [{"requirement_id": "GRI 2-1-a", "requirement_type": "assessment"}]

    fake_repo = FakeRepository()
    pdf_path = tmp_path / "report.pdf"
    pdf_path.write_bytes(b"pdf")
    monkeypatch.setattr(module, "build_workflow", lambda args, repository: FakeWorkflow())
    monkeypatch.setattr(module, "open_repository_session", lambda: module.RepositoryContext(fake_repo, None))

    args = Namespace(
        report_id="envision_2024",
        pdf=pdf_path,
        profile=tmp_path / "profile.json",
        confirm_llm=False,
        enable_ocr=False,
        ocr_pages=[],
    )

    result = module.run_single_report_regeneration(args)

    assert result == [{"requirement_id": "GRI 2-1-a", "requirement_type": "assessment"}]
    assert calls["confirm_llm"] is False
    assert calls["enable_ocr"] is False
    assert calls["ocr_pages"] == []
    assert calls["report_id"].startswith("envision_2024-regeneration-")
    assert fake_repo.reports[0].file_hash
