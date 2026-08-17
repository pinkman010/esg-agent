import ast
import inspect
from pathlib import Path

from src.services.ai_assessment_service import AIAssessmentService
from src.tools.evaluate_deepseek_against_manual_review import (
    parse_args,
    register_evaluation_assets,
)


def test_evaluation_cli_defaults_to_no_external_model_call(tmp_path):
    args = parse_args(
        [
            "--review-workbook",
            str(tmp_path / "review.xlsx"),
            "--dry-run",
            "--output-csv",
            str(tmp_path / "evaluation.csv"),
            "--output-summary",
            str(tmp_path / "summary.json"),
        ]
    )

    assert args.dry_run is True
    assert args.confirm_llm is False
    assert args.max_calls == 225
    assert isinstance(args.review_workbook, Path)
    assert args.retry_hard_gate_failures is False
    assert args.requirements.name == "gri_requirement_checklist_v3.json"
    assert (
        args.final_adjudications.name
        == "envision_2024_result_adjudication_v1.csv"
    )
    assert "recommendations" in args.adjudication_recommendations.name


def test_evaluation_cli_requires_exactly_one_execution_mode(tmp_path):
    base = [
        "--review-workbook",
        str(tmp_path / "review.xlsx"),
        "--output-csv",
        str(tmp_path / "evaluation.csv"),
        "--output-summary",
        str(tmp_path / "summary.json"),
    ]

    try:
        parse_args(base)
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("execution mode should be required")


def test_evaluation_cli_accepts_targeted_retry_mode(tmp_path):
    args = parse_args(
        [
            "--review-workbook",
            str(tmp_path / "review.xlsx"),
            "--confirm-llm",
            "--retry-hard-gate-failures",
            "--output-csv",
            str(tmp_path / "evaluation.csv"),
            "--output-summary",
            str(tmp_path / "summary.json"),
        ]
    )

    assert args.confirm_llm is True
    assert args.retry_hard_gate_failures is True


def test_register_evaluation_assets_accepts_utf8_bom_manifest(tmp_path):
    manifest = tmp_path / "assets_manifest.json"
    output = tmp_path / "evaluation.json"
    manifest.write_text('{"assets": []}\n', encoding="utf-8-sig")
    output.write_text('{"ok": true}\n', encoding="utf-8")

    register_evaluation_assets(
        assets_manifest=manifest,
        output_paths=[output],
        summary={
            "model": "deepseek-v4-flash",
            "prompt_version": "deepseek-gri-assist-v1.2",
            "report_id": "report-1",
            "run_id": "run-1",
            "executed_at": "2026-07-20",
        },
    )

    assert "evaluation.json" in manifest.read_text(encoding="utf-8")


def test_explicit_candidate_assessment_documents_the_product_boundary():
    docstring = inspect.getdoc(AIAssessmentService.assess_explicit_candidates) or ""

    assert "offline evaluation" in docstring
    assert "bypasses should_call" in docstring
    assert "default product workflow" in docstring


def test_explicit_candidate_assessment_is_only_called_by_the_offline_evaluator():
    backend_root = Path(__file__).resolve().parents[2]
    source_root = backend_root / "src"
    call_sites: set[str] = set()
    for path in source_root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "assess_explicit_candidates"
            for node in ast.walk(tree)
        ):
            call_sites.add(path.relative_to(backend_root).as_posix())

    assert call_sites == {
        "src/tools/evaluate_deepseek_against_manual_review.py",
    }
