from pathlib import Path

from src.tools.evaluate_deepseek_against_manual_review import parse_args


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
