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


def test_gri_adapter_adds_chinese_keywords_for_gri_2_10_to_2_20_governance_rules(tmp_path):
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
                        ("2-9", "a", "describe its governance structure;"),
                        ("2-10", "a", "describe nomination and selection processes;"),
                        ("2-12", "a", "describe the role of the highest governance body in overseeing impacts;"),
                        ("2-13", "a:i", "whether senior executives are responsible for impact management;"),
                        ("2-19", "a", "describe remuneration policies;"),
                        ("2-20", "a", "describe the process to determine remuneration;"),
                    ]
                ],
            }
        ),
        encoding="utf-8",
    )

    requirements = GRIAdapter(path).load_requirements()
    keywords_by_id = {requirement.requirement_id: requirement.keywords for requirement in requirements}

    assert "ESG治理架构" in keywords_by_id["GRI 2-9-a"]
    assert "从略披露" in keywords_by_id["GRI 2-10-a"]
    assert "ESG委员会" in keywords_by_id["GRI 2-12-a"]
    assert "季度汇报" in keywords_by_id["GRI 2-13-a-i"]
    assert "从略披露" in keywords_by_id["GRI 2-19-a"]
    assert "因商业保密限制从略披露" in keywords_by_id["GRI 2-20-a"]


def test_gri_adapter_adds_chinese_keywords_for_gri_2_20_to_3_1_policy_rules(tmp_path):
    path = tmp_path / "gri-checklist.json"
    path.write_text(
        json.dumps(
            {
                "metadata": {"manifest_version": "test"},
                "requirements": [
                    {
                        "requirement_id": f"current_gap:GRI{standard}:{disclosure}:{suffix}",
                        "canonical_disclosure_id": disclosure,
                        "requirement_text": requirement_text,
                        "requirement_type": "requirement",
                        "is_mandatory": True,
                        "scoring_role": "hard_score",
                        "standard_year": "2021",
                        "assessment_mode": "current_gap",
                    }
                    for standard, disclosure, suffix, requirement_text in [
                        ("2", "2-20", "a:iii", "describe remuneration process;"),
                        ("2", "2-21", "a", "report annual total compensation ratio;"),
                        ("2", "2-22", "a", "statement on sustainable development strategy;"),
                        ("2", "2-23", "a", "policy commitments;"),
                        ("2", "2-24", "a", "embedding policy commitments;"),
                        ("2", "2-25", "b", "grievance mechanisms;"),
                        ("2", "2-26", "a:ii", "raise concerns about business conduct;"),
                        ("2", "2-27", "a", "non-compliance with laws and regulations;"),
                        ("2", "2-28", "a", "membership associations;"),
                        ("2", "2-29", "a", "stakeholder engagement approach;"),
                        ("2", "2-30", "a", "collective bargaining agreements;"),
                        ("3", "3-1", "a", "process to determine material topics;"),
                    ]
                ],
            }
        ),
        encoding="utf-8",
    )

    requirements = GRIAdapter(path).load_requirements()
    keywords_by_id = {requirement.requirement_id: requirement.keywords for requirement in requirements}

    assert "因商业保密限制从略披露" in keywords_by_id["GRI 2-20-a-iii"]
    assert "年度总薪酬比率" in keywords_by_id["GRI 2-21-a"]
    assert "董事长致辞" in keywords_by_id["GRI 2-22-a"]
    assert "政策承诺" in keywords_by_id["GRI 2-23-a"]
    assert "供应商行为准则" in keywords_by_id["GRI 2-24-a"]
    assert "阳光热线" in keywords_by_id["GRI 2-25-b"]
    assert "举报电话" in keywords_by_id["GRI 2-26-a-ii"]
    assert "未发生违法违规事件" in keywords_by_id["GRI 2-27-a"]
    assert "UNGC" in keywords_by_id["GRI 2-28-a"]
    assert "利益相关方沟通" in keywords_by_id["GRI 2-29-a"]
    assert "集体谈判协议" in keywords_by_id["GRI 2-30-a"]
    assert "重要性评估" in keywords_by_id["GRI 3-1-a"]


def test_gri_adapter_adds_chinese_keywords_for_topic_specific_200_rules(tmp_path):
    path = tmp_path / "gri-checklist.json"
    path.write_text(
        json.dumps(
            {
                "metadata": {"manifest_version": "test"},
                "requirements": [
                    {
                        "requirement_id": f"current_gap:GRI{standard}:{disclosure}:{suffix}",
                        "canonical_disclosure_id": disclosure,
                        "requirement_text": requirement_text,
                        "requirement_type": "requirement",
                        "is_mandatory": True,
                        "scoring_role": "hard_score",
                        "standard_year": "2021",
                        "assessment_mode": "current_gap",
                    }
                    for standard, disclosure, suffix, requirement_text in [
                        ("201", "201-1", "a", "direct economic value generated and distributed;"),
                        ("201", "201-2", "a:i", "risks and opportunities posed by climate change;"),
                        ("201", "201-3", "d", "employee and employer contribution percentages;"),
                        ("201", "201-4", "a", "financial assistance received from government;"),
                        ("202", "202-1", "a", "standard entry level wage by gender compared to local minimum wage;"),
                        ("202", "202-2", "a", "senior management hired from local community;"),
                        ("203", "203-1", "a", "infrastructure investments and services supported;"),
                        ("203", "203-2", "b", "significant indirect economic impacts;"),
                    ]
                ],
            }
        ),
        encoding="utf-8",
    )

    requirements = GRIAdapter(path).load_requirements()
    keywords_by_id = {requirement.requirement_id: requirement.keywords for requirement in requirements}

    assert "因商业保密限制从略披露" in keywords_by_id["GRI 201-1-a"]
    assert "气候风险" in keywords_by_id["GRI 201-2-a-i"]
    assert "退休计划" in keywords_by_id["GRI 201-3-d"]
    assert "政府给予的财政补贴" in keywords_by_id["GRI 201-4-a"]
    assert "最低工资" in keywords_by_id["GRI 202-1-a"]
    assert "当地社区高管比例" in keywords_by_id["GRI 202-2-a"]
    assert "携手社区" in keywords_by_id["GRI 203-1-a"]
    assert "间接经济影响" in keywords_by_id["GRI 203-2-b"]


def test_gri_adapter_adds_chinese_keywords_for_topic_specific_250_rules(tmp_path):
    path = tmp_path / "gri-checklist.json"
    path.write_text(
        json.dumps(
            {
                "metadata": {"manifest_version": "test"},
                "requirements": [
                    {
                        "requirement_id": f"current_gap:GRI{standard}:{disclosure}:{suffix}",
                        "canonical_disclosure_id": disclosure,
                        "requirement_text": requirement_text,
                        "requirement_type": "requirement",
                        "is_mandatory": True,
                        "scoring_role": "hard_score",
                        "standard_year": "2021",
                        "assessment_mode": "current_gap",
                    }
                    for standard, disclosure, suffix, requirement_text in [
                        ("204", "204-1", "a", "proportion of spending on local suppliers;"),
                        ("205", "205-1", "a", "operations assessed for risks related to corruption;"),
                        ("205", "205-2", "c", "anti-corruption policies and procedures communicated to business partners;"),
                        ("205", "205-3", "b", "employees dismissed or disciplined for corruption;"),
                        ("206", "206-1", "a", "legal actions for anti-competitive behavior;"),
                    ]
                ],
            }
        ),
        encoding="utf-8",
    )

    requirements = GRIAdapter(path).load_requirements()
    keywords_by_id = {requirement.requirement_id: requirement.keywords for requirement in requirements}

    assert "因商业保密限制从略披露" in keywords_by_id["GRI 204-1-a"]
    assert "风险评估" in keywords_by_id["GRI 205-1-a"]
    assert "供应商阳光协议" in keywords_by_id["GRI 205-2-c"]
    assert "员工因腐败被开除或受到处分的事件数量" in keywords_by_id["GRI 205-3-b"]
    assert "反竞争行为事件数量" in keywords_by_id["GRI 206-1-a"]


def test_gri_adapter_adds_chinese_keywords_for_tax_and_energy_250_rules(tmp_path):
    path = tmp_path / "gri-checklist.json"
    path.write_text(
        json.dumps(
            {
                "metadata": {"manifest_version": "test"},
                "requirements": [
                    {
                        "requirement_id": f"current_gap:GRI{standard}:{disclosure}:{suffix}",
                        "canonical_disclosure_id": disclosure,
                        "requirement_text": requirement_text,
                        "requirement_type": "requirement",
                        "is_mandatory": True,
                        "scoring_role": "hard_score",
                        "standard_year": "2021",
                        "assessment_mode": "current_gap",
                    }
                    for standard, disclosure, suffix, requirement_text in [
                        ("207", "207-1", "a", "approach to tax;"),
                        ("207", "207-1", "a:iii", "approach to regulatory compliance;"),
                        ("207", "207-2", "a", "tax governance control and risk management;"),
                        ("207", "207-4", "b:x", "country-by-country reporting;"),
                        ("302", "302-1", "a", "non-renewable fuel consumption inside the organization;"),
                        ("302", "302-1", "c", "electricity heating cooling and steam consumption;"),
                    ]
                ],
            }
        ),
        encoding="utf-8",
    )

    requirements = GRIAdapter(path).load_requirements()
    keywords_by_id = {requirement.requirement_id: requirement.keywords for requirement in requirements}

    assert "税务治理" in keywords_by_id["GRI 207-1-a"]
    assert "税收协定" in keywords_by_id["GRI 207-1-a-iii"]
    assert "财务合规与安全部门" in keywords_by_id["GRI 207-2-a"]
    assert "因商业保密限制从略披露" in keywords_by_id["GRI 207-4-b-x"]
    assert "不可再生能源消耗总量" in keywords_by_id["GRI 302-1-a"]
    assert "电力消耗总量" in keywords_by_id["GRI 302-1-c"]


def test_gri_adapter_adds_chinese_keywords_for_energy_and_water_300_rules(tmp_path):
    path = tmp_path / "gri-checklist.json"
    path.write_text(
        json.dumps(
            {
                "metadata": {"manifest_version": "test"},
                "requirements": [
                    {
                        "requirement_id": f"current_gap:GRI{standard}:{disclosure}:{suffix}",
                        "canonical_disclosure_id": disclosure,
                        "requirement_text": requirement_text,
                        "requirement_type": "requirement",
                        "is_mandatory": True,
                        "scoring_role": "hard_score",
                        "standard_year": "2021",
                        "assessment_mode": "current_gap",
                    }
                    for standard, disclosure, suffix, requirement_text in [
                        ("302", "302-1", "e", "total energy consumption inside the organization;"),
                        ("302", "302-4", "a", "amount of reductions in energy consumption achieved;"),
                        ("303", "303-1", "b", "approach to identifying water-related impacts;"),
                        ("303", "303-2", "a", "minimum standards set for quality of effluent discharge;"),
                        ("303", "303-3", "a:i", "surface water withdrawal;"),
                        ("303", "303-4", "b:ii", "other water discharge;"),
                        ("305", "305-1", "a", "gross direct Scope 1 GHG emissions in metric tons of CO2 equivalent;"),
                        ("305", "305-1", "e", "source of emission factors and global warming potential rates used;"),
                        ("305", "305-2", "a", "gross location-based energy indirect Scope 2 GHG emissions;"),
                        ("305", "305-2", "b", "gross market-based energy indirect Scope 2 GHG emissions;"),
                        ("305", "305-2", "c", "gases included in the calculation;"),
                    ]
                ],
            }
        ),
        encoding="utf-8",
    )

    requirements = GRIAdapter(path).load_requirements()
    keywords_by_id = {requirement.requirement_id: requirement.keywords for requirement in requirements}

    assert "能源使用总量" in keywords_by_id["GRI 302-1-e"]
    assert "节能措施促成节电量" in keywords_by_id["GRI 302-4-a"]
    assert "WWF Water Risk Filter" in keywords_by_id["GRI 303-1-b"]
    assert "废水分类收集" in keywords_by_id["GRI 303-2-a"]
    assert "地表水总量" in keywords_by_id["GRI 303-3-a-i"]
    assert "其他水排水量" in keywords_by_id["GRI 303-4-b-ii"]
    assert "范围一" in keywords_by_id["GRI 305-1-a"]
    assert "排放因子" in keywords_by_id["GRI 305-1-e"]
    assert "范围二（基于位置）" in keywords_by_id["GRI 305-2-a"]
    assert "范围二（基于市场）" in keywords_by_id["GRI 305-2-b"]
    assert "温室气体种类" in keywords_by_id["GRI 305-2-c"]
