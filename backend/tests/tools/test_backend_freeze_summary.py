import json
from pathlib import Path

from src.tools.build_backend_freeze_summary import build_acceptance_summary


def test_build_acceptance_summary_hashes_artifacts_and_updates_manifest(tmp_path: Path):
    project_root = tmp_path
    structure = tmp_path / "structure.json"
    ai = tmp_path / "ai.json"
    envision = tmp_path / "envision.json"
    goldwind = tmp_path / "goldwind.json"
    artifact = tmp_path / "result.csv"
    output = tmp_path / "acceptance.json"
    manifest = tmp_path / "assets_manifest.json"
    structure.write_text('{"standard_unit_count": 577}\n', encoding="utf-8")
    ai.write_text('{"evaluated_count": 225}\n', encoding="utf-8")
    envision.write_text('{"new_false_disclosed_count": 0}\n', encoding="utf-8")
    goldwind.write_text('{"false_disclosed_count": 0}\n', encoding="utf-8")
    artifact.write_text("requirement_id\nGRI 2-1-a\n", encoding="utf-8")
    manifest.write_text('{"assets": [], "notes": []}\n', encoding="utf-8")

    summary = build_acceptance_summary(
        project_root=project_root,
        output_path=output,
        assets_manifest=manifest,
        structure_summary_path=structure,
        ai_summary_path=ai,
        envision_summary_path=envision,
        goldwind_summary_path=goldwind,
        artifact_specs=[("acceptance_result", artifact)],
        git_head="abc123",
        backend_test_count=625,
        frontend_test_file_count=19,
        frontend_test_count=51,
    )

    assert summary["database"]["head"] == "0011_ai_suggestions"
    assert summary["tests"]["backend_passed"] == 625
    assert summary["artifacts"][0]["sha256"]
    registered = json.loads(manifest.read_text(encoding="utf-8"))["assets"]
    assert {item["asset_type"] for item in registered} == {
        "acceptance_result",
        "backend_freeze_acceptance_summary",
    }
