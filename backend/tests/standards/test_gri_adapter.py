import json

import pytest

from src.standards.gri import GRIAdapter


def test_gri_adapter_loads_requirements_from_seed_json(tmp_path):
    path = tmp_path / "gri.json"
    path.write_text(
        json.dumps(
            [
                {
                    "standard_id": "GRI",
                    "standard_version": "2021",
                    "disclosure_id": "GRI 302",
                    "requirement_id": "GRI 302-1-a",
                    "requirement_text": "Disclose total energy consumption.",
                    "keywords": ["energy", "consumption"],
                }
            ]
        ),
        encoding="utf-8",
    )

    requirements = GRIAdapter(path).load_requirements()

    assert len(requirements) == 1
    assert requirements[0].standard_id == "GRI"
    assert requirements[0].requirement_id == "GRI 302-1-a"


def test_gri_adapter_builds_tasks_with_run_and_report_ids(tmp_path):
    path = tmp_path / "gri.json"
    path.write_text(
        json.dumps(
            [
                {
                    "standard_id": "GRI",
                    "standard_version": "2021",
                    "disclosure_id": "GRI 302",
                    "requirement_id": "GRI 302-1-a",
                    "requirement_text": "Disclose total energy consumption.",
                    "keywords": ["energy"],
                }
            ]
        ),
        encoding="utf-8",
    )

    tasks = GRIAdapter(path).build_tasks(run_id="run-1", report_id="report-1")

    assert len(tasks) == 1
    assert tasks[0].task_id == "run-1:GRI 302-1-a"
    assert tasks[0].run_id == "run-1"
    assert tasks[0].report_id == "report-1"
    assert tasks[0].standard_version == "2021"


def test_gri_adapter_rejects_malformed_requirement_json(tmp_path):
    path = tmp_path / "bad-gri.json"
    path.write_text(json.dumps([{"requirement_id": "missing fields"}]), encoding="utf-8")

    with pytest.raises(ValueError, match="invalid GRI requirement"):
        GRIAdapter(path).load_requirements()


def test_gri_adapter_converts_current_gap_checklist_manifest(tmp_path):
    path = tmp_path / "gri-checklist.json"
    path.write_text(
        json.dumps(
            {
                "metadata": {"manifest_version": "test"},
                "requirements": [
                    {
                        "requirement_id": "current_gap:GRI2:2-1:a",
                        "canonical_disclosure_id": "2-1",
                        "requirement_text": "report its legal name;",
                        "requirement_type": "requirement",
                        "is_mandatory": True,
                        "scoring_role": "hard_score",
                        "standard_year": "2021",
                        "assessment_mode": "current_gap",
                    },
                    {
                        "requirement_id": "watchlist_2027:GRI102",
                        "canonical_disclosure_id": None,
                        "requirement_text": "future item",
                        "requirement_type": "requirement",
                        "is_mandatory": True,
                        "scoring_role": "hard_score",
                        "standard_year": "2027",
                        "assessment_mode": "watchlist_2027",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    requirements = GRIAdapter(path).load_requirements()

    assert len(requirements) == 1
    assert requirements[0].standard_id == "GRI 2"
    assert requirements[0].standard_version == "2021"
    assert requirements[0].disclosure_id == "GRI 2-1"
    assert requirements[0].requirement_id == "GRI 2-1-a"
    assert requirements[0].requirement_text == "report its legal name;"
    assert "legal" in requirements[0].keywords
    assert "name" in requirements[0].keywords


def test_gri_adapter_limits_converted_checklist_requirements(tmp_path):
    path = tmp_path / "gri-checklist.json"
    path.write_text(
        json.dumps(
            {
                "metadata": {"manifest_version": "test"},
                "requirements": [
                    {
                        "requirement_id": f"current_gap:GRI2:2-1:{suffix}",
                        "canonical_disclosure_id": "2-1",
                        "requirement_text": f"report item {suffix};",
                        "requirement_type": "requirement",
                        "is_mandatory": True,
                        "scoring_role": "hard_score",
                        "standard_year": "2021",
                        "assessment_mode": "current_gap",
                    }
                    for suffix in ["a", "b", "c"]
                ],
            }
        ),
        encoding="utf-8",
    )

    requirements = GRIAdapter(path, max_requirements=2).load_requirements()

    assert [requirement.requirement_id for requirement in requirements] == ["GRI 2-1-a", "GRI 2-1-b"]
