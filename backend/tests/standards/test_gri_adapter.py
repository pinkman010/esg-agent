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


def test_gri_adapter_adds_chinese_keywords_for_gri_2_2(tmp_path):
    path = tmp_path / "gri-checklist.json"
    path.write_text(
        json.dumps(
            {
                "metadata": {"manifest_version": "test"},
                "requirements": [
                    {
                        "requirement_id": "current_gap:GRI2:2-2:a",
                        "canonical_disclosure_id": "2-2",
                        "requirement_text": "list all entities included in its sustainability reporting;",
                        "requirement_type": "requirement",
                        "is_mandatory": True,
                        "scoring_role": "hard_score",
                        "standard_year": "2021",
                        "assessment_mode": "current_gap",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    requirements = GRIAdapter(path).load_requirements()

    assert "报告边界" in requirements[0].keywords
    assert "实际运营场所" in requirements[0].keywords
    assert "纳入报告" in requirements[0].keywords


def test_gri_adapter_adds_chinese_keywords_for_gri_2_1_entity_attributes(tmp_path):
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
                        "requirement_id": "current_gap:GRI2:2-1:c",
                        "canonical_disclosure_id": "2-1",
                        "requirement_text": "report the location of its headquarters;",
                        "requirement_type": "requirement",
                        "is_mandatory": True,
                        "scoring_role": "hard_score",
                        "standard_year": "2021",
                        "assessment_mode": "current_gap",
                    },
                    {
                        "requirement_id": "current_gap:GRI2:2-1:d",
                        "canonical_disclosure_id": "2-1",
                        "requirement_text": "report its countries of operation;",
                        "requirement_type": "requirement",
                        "is_mandatory": True,
                        "scoring_role": "hard_score",
                        "standard_year": "2021",
                        "assessment_mode": "current_gap",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    requirements = GRIAdapter(path).load_requirements()
    keywords_by_id = {requirement.requirement_id: requirement.keywords for requirement in requirements}

    assert "有限公司" in keywords_by_id["GRI 2-1-a"]
    assert "Co., Ltd." in keywords_by_id["GRI 2-1-a"]
    assert "总部" in keywords_by_id["GRI 2-1-c"]
    assert "上海总部" in keywords_by_id["GRI 2-1-c"]
    assert "全球市场" in keywords_by_id["GRI 2-1-d"]
    assert "运营国家" in keywords_by_id["GRI 2-1-d"]


def test_gri_adapter_adds_chinese_keywords_for_gri_2_3_2_4_2_5(tmp_path):
    path = tmp_path / "gri-checklist.json"
    path.write_text(
        json.dumps(
            {
                "metadata": {"manifest_version": "test"},
                "requirements": [
                    {
                        "requirement_id": f"current_gap:GRI2:{disclosure}:{suffix}",
                        "canonical_disclosure_id": disclosure,
                        "requirement_text": requirement_text,
                        "requirement_type": "requirement",
                        "is_mandatory": True,
                        "scoring_role": "hard_score",
                        "standard_year": "2021",
                        "assessment_mode": "current_gap",
                    }
                    for disclosure, suffix, requirement_text in [
                        ("2-3", "a", "report the reporting period and frequency;"),
                        ("2-3", "d", "report the contact point for questions;"),
                        ("2-4", "a", "report restatements of information;"),
                        ("2-5", "a", "describe external assurance policy and practice;"),
                        ("2-5", "b", "report external assurance details;"),
                    ]
                ],
            }
        ),
        encoding="utf-8",
    )

    requirements = GRIAdapter(path).load_requirements()
    keywords_by_id = {requirement.requirement_id: requirement.keywords for requirement in requirements}

    assert "报告期" in keywords_by_id["GRI 2-3-a"]
    assert "报告频率" in keywords_by_id["GRI 2-3-a"]
    assert "联系邮箱" in keywords_by_id["GRI 2-3-d"]
    assert "无信息重述" in keywords_by_id["GRI 2-4-a"]
    assert "鉴证报告" in keywords_by_id["GRI 2-5-a"]
    assert "独立有限鉴证" in keywords_by_id["GRI 2-5-b"]


def test_gri_adapter_adds_chinese_keywords_for_gri_2_6_2_7_2_8_2_9(tmp_path):
    path = tmp_path / "gri-checklist.json"
    path.write_text(
        json.dumps(
            {
                "metadata": {"manifest_version": "test"},
                "requirements": [
                    {
                        "requirement_id": f"current_gap:GRI2:{disclosure}:{suffix}",
                        "canonical_disclosure_id": disclosure,
                        "requirement_text": requirement_text,
                        "requirement_type": "requirement",
                        "is_mandatory": True,
                        "scoring_role": "hard_score",
                        "standard_year": "2021",
                        "assessment_mode": "current_gap",
                    }
                    for disclosure, suffix, requirement_text in [
                        ("2-5", "b:ii", "report assurance standards and scope;"),
                        ("2-6", "b", "describe activities, products, services and markets;"),
                        ("2-6", "c", "describe the value chain and business relationships;"),
                        ("2-7", "c:ii", "report methodologies and assumptions used to compile employee data;"),
                        ("2-8", "a", "report workers who are not employees;"),
                        ("2-9", "b", "list committees of the highest governance body;"),
                    ]
                ],
            }
        ),
        encoding="utf-8",
    )

    requirements = GRIAdapter(path).load_requirements()
    keywords_by_id = {requirement.requirement_id: requirement.keywords for requirement in requirements}

    assert "鉴证标准" in keywords_by_id["GRI 2-5-b-ii"]
    assert "主要业务" in keywords_by_id["GRI 2-6-b"]
    assert "价值链" in keywords_by_id["GRI 2-6-c"]
    assert "截至报告期末" in keywords_by_id["GRI 2-7-c-ii"]
    assert "非雇员工作者" in keywords_by_id["GRI 2-8-a"]
    assert "ESG治理架构" in keywords_by_id["GRI 2-9-b"]
