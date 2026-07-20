from pathlib import Path

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
