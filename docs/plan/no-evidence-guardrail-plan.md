# 无证据门禁实施计划

> **执行要求：** 实施本计划时必须使用 `superpowers:executing-plans`，按任务逐项执行。任务使用复选框（`- [ ]`）跟踪状态。

**目标：** 将剩余 68 条 `unknown + needs_manual_review` per-ID explicit verdict 迁移为结构化 `no_evidence_guardrail`，保留无证据误命中阻断能力，并保持 577 baseline 输出不回退。

**架构：** 新增独立 guardrail 层，只负责“清空不充分 evidence 并返回 unknown”，不负责制造 evidence 或提升 verdict。第一版仍可按 requirement_id 注册，但必须同时标注 guardrail category、facets、forbidden evidence kinds 和 missing item 模板，后续再合并为跨 requirement 的 semantic rule。

**技术栈：** Python 3.11、pytest、`DisclosureAgent`、`RequirementEvidenceContract`、`evidence_ontology.py`、577 review CSV regression gate、`review_csv_audit`、`first_pass_quality`。

---

## 1. 当前状态

已完成 evidence-backed verdict 迁移。剩余 per-ID explicit verdict 为 68 条，全部满足：

- `verdict=unknown`
- `review_status=needs_manual_review`
- `allowed_pages=()`
- `candidate_pages=()`

这些条目当前的作用不是判断披露充分性，而是防止泛化证据误进入对应 leaf requirement。例如：

- 零事件总声明不能传播到罚款、警告、自愿准则、投诉来源分类。
- 政策、准则、管理机制不能替代具体风险运营点、供应商类型、国家/地区。
- KPI 总量不能替代方法、排除范围、基准年、气体种类、人员排除说明。
- 一般培训不能替代安保人员人权培训。

现有剩余清单位于：

- `tmp/review/remaining_explicit_verdicts.csv`

## 2. 不做范围

- 不把 68 条直接删除。
- 不允许 no-evidence guardrail 生成 `disclosed` 或 `partially_disclosed`。
- 不允许 guardrail 生成 evidence。
- 不改变候选页、页码、quality flags、OCR/VLM 字段。
- 不调用外部模型。
- 不改数据库 schema。
- 不改前端 UI。
- 不一次迁移全部 68 条。

## 3. 核心设计

新增结构：

```python
from dataclasses import dataclass
from enum import StrEnum

from src.standards.evidence_ontology import EvidenceKind, RequirementFacet, SemanticGroup


class NoEvidenceGuardrailCategory(StrEnum):
    INCIDENT_CLASSIFICATION = "incident_classification"
    RISK_LOCATION = "risk_location"
    METHOD_SCOPE = "method_scope"
    BREAKDOWN_DIMENSION = "breakdown_dimension"
    SECURITY_PERSONNEL = "security_personnel"


@dataclass(frozen=True)
class NoEvidenceGuardrail:
    requirement_id: str
    category: NoEvidenceGuardrailCategory
    semantic_group: SemanticGroup | None
    required_facets: tuple[RequirementFacet, ...]
    forbidden_evidence_kinds: tuple[EvidenceKind, ...]
    missing_items: tuple[str, ...]
    rationale: str
```

新增行为：

```text
当 no_evidence_guardrail 命中：
1. 清空 evidence。
2. verdict = unknown。
3. review_status = needs_manual_review。
4. missing_items = guardrail.missing_items。
5. rationale = guardrail.rationale。
6. decision_source = no_evidence_guardrail。
```

执行优先级：

```text
1. omission_note / not_applicable 短路
2. no_evidence_guardrail 判断是否清空 evidence
3. contract/report profile 提供候选页
4. evidence kind 识别
5. ontology matrix 给 verdict
6. per-ID contract guardrail 做最终约束
```

实现上可以先接入到 `DisclosureAgent._filter_requirement_specific_pages()`，保持当前“无 allowed pages 的 unknown 清空 evidence”行为等价；后续再把 evidence kind 判断前移。

## 4. 停止条件

任一批次出现以下情况，必须暂停：

- 577 unique requirement 数量变化。
- `global_fallback` 回归。
- 任意 `unknown` 变成 `partially_disclosed` 或 `disclosed`。
- 任意 evidence 页码、`page_label`、`evidence_type`、`retrieval_strategy`、`quality_flags`、OCR/VLM 字段变化。
- `omission_note` 或 `not_applicable` 升格。
- `disclosed` 数量增加。
- `review_status` 与 verdict 错配。
- KPI evidence 丢失 `complex_table`。
- no-evidence guardrail 生成了 evidence。
- no-evidence guardrail 无法解释为 category/facet/evidence kind，只能靠自然语言描述硬编码。

触发后处理：

1. 输出触发 requirement 和 diff 字段。
2. 若是实现 bug，修复并重跑当前批次。
3. 若是规则过宽，退回 per-ID explicit unknown。
4. 若是 baseline 争议，暂停等待人工复核。

## 5. 文件职责

- Create: `backend/src/standards/no_evidence_guardrails.py`
  - 定义 `NoEvidenceGuardrailCategory`、`NoEvidenceGuardrail`、注册表和查询函数。
- Modify: `backend/src/agents/disclosure_agent.py`
  - 在 evidence filter 阶段使用 no-evidence guardrail 清空不应进入判断的 evidence。
- Modify: `backend/src/standards/evidence_contracts.py`
  - 分批移除对应 68 条中的 explicit `verdict/review_status/rationale`，保留或迁移 missing items 到 guardrail。
- Test: `backend/tests/standards/test_no_evidence_guardrails.py`
  - 覆盖 guardrail 注册表、分类、missing items 和查询函数。
- Test: `backend/tests/agents/test_disclosure_agent.py`
  - 覆盖 no-evidence guardrail 清空泛化 evidence 的行为。
- Optional Modify: `docs/DEVELOPMENT.md`
  - 记录最终迁移结果、剩余 explicit unknown 数量和 577 gate 结果。

## 6. 任务 1：建立 no-evidence guardrail 基础结构

**Files:**
- Create: `backend/src/standards/no_evidence_guardrails.py`
- Test: `backend/tests/standards/test_no_evidence_guardrails.py`

- [ ] **步骤 1：写失败测试**

Add:

```python
from src.standards.evidence_ontology import EvidenceKind, RequirementFacet
from src.standards.no_evidence_guardrails import (
    NoEvidenceGuardrailCategory,
    get_no_evidence_guardrail,
)


def test_get_no_evidence_guardrail_returns_incident_classification_rule():
    guardrail = get_no_evidence_guardrail("GRI 416-2-a-i")

    assert guardrail is not None
    assert guardrail.requirement_id == "GRI 416-2-a-i"
    assert guardrail.category is NoEvidenceGuardrailCategory.INCIDENT_CLASSIFICATION
    assert RequirementFacet.REQUIRES_INCIDENT_CLASSIFICATION in guardrail.required_facets
    assert EvidenceKind.EXPLICIT_ZERO_STATEMENT in guardrail.forbidden_evidence_kinds
    assert "罚款或处罚事件数量" in guardrail.missing_items
```

- [ ] **步骤 2：运行失败测试**

运行：

```powershell
uv run --no-sync pytest --basetemp tmp/pytest-no-evidence-guardrail backend/tests/standards/test_no_evidence_guardrails.py -q
```

预期：

```text
ModuleNotFoundError: No module named 'src.standards.no_evidence_guardrails'
```

- [ ] **步骤 3：新增最小实现**

Create `backend/src/standards/no_evidence_guardrails.py`:

```python
from dataclasses import dataclass
from enum import StrEnum

from src.standards.evidence_ontology import EvidenceKind, RequirementFacet, SemanticGroup


class NoEvidenceGuardrailCategory(StrEnum):
    INCIDENT_CLASSIFICATION = "incident_classification"
    RISK_LOCATION = "risk_location"
    METHOD_SCOPE = "method_scope"
    BREAKDOWN_DIMENSION = "breakdown_dimension"
    SECURITY_PERSONNEL = "security_personnel"


@dataclass(frozen=True)
class NoEvidenceGuardrail:
    requirement_id: str
    category: NoEvidenceGuardrailCategory
    semantic_group: SemanticGroup | None
    required_facets: tuple[RequirementFacet, ...]
    forbidden_evidence_kinds: tuple[EvidenceKind, ...]
    missing_items: tuple[str, ...]
    rationale: str


_GUARDRAILS: dict[str, NoEvidenceGuardrail] = {
    "GRI 416-2-a-i": NoEvidenceGuardrail(
        requirement_id="GRI 416-2-a-i",
        category=NoEvidenceGuardrailCategory.INCIDENT_CLASSIFICATION,
        semantic_group=SemanticGroup.ZERO_EVENT_COMPLIANCE,
        required_facets=(RequirementFacet.REQUIRES_INCIDENT_CLASSIFICATION,),
        forbidden_evidence_kinds=(EvidenceKind.EXPLICIT_ZERO_STATEMENT,),
        missing_items=("罚款或处罚事件数量",),
        rationale="A general zero product-safety harm statement does not disclose incidents resulting in fines or penalties.",
    ),
}


def get_no_evidence_guardrail(requirement_id: str) -> NoEvidenceGuardrail | None:
    return _GUARDRAILS.get(requirement_id)
```

- [ ] **步骤 4：运行测试通过**

运行：

```powershell
uv run --no-sync pytest --basetemp tmp/pytest-no-evidence-guardrail backend/tests/standards/test_no_evidence_guardrails.py -q
```

预期：

```text
1 passed
```

## 7. 任务 2：迁移第一批 zero-event classification guardrail

**Files:**
- Modify: `backend/src/standards/no_evidence_guardrails.py`
- Modify: `backend/src/standards/evidence_contracts.py`
- Test: `backend/tests/standards/test_no_evidence_guardrails.py`
- Test: `backend/tests/agents/test_disclosure_agent.py`

目标覆盖：

- `GRI 406-1-b`
- `GRI 406-1-b-i`
- `GRI 406-1-b-ii`
- `GRI 406-1-b-iii`
- `GRI 406-1-b-iv`
- `GRI 416-2-a-i`
- `GRI 416-2-a-ii`
- `GRI 416-2-a-iii`
- `GRI 417-2-a`
- `GRI 417-2-a-i`
- `GRI 417-2-a-ii`
- `GRI 417-2-a-iii`
- `GRI 417-2-b`
- `GRI 417-3-a`
- `GRI 417-3-a-i`
- `GRI 417-3-a-ii`
- `GRI 417-3-a-iii`
- `GRI 417-3-b`
- `GRI 418-1-a-i`
- `GRI 418-1-a-ii`

- [ ] **步骤 1：扩展 guardrail 注册表测试**

Add:

```python
import pytest

from src.standards.no_evidence_guardrails import NoEvidenceGuardrailCategory, get_no_evidence_guardrail


@pytest.mark.parametrize(
    "requirement_id",
    [
        "GRI 406-1-b",
        "GRI 406-1-b-i",
        "GRI 406-1-b-ii",
        "GRI 406-1-b-iii",
        "GRI 406-1-b-iv",
        "GRI 416-2-a-i",
        "GRI 416-2-a-ii",
        "GRI 416-2-a-iii",
        "GRI 417-2-a",
        "GRI 417-2-a-i",
        "GRI 417-2-a-ii",
        "GRI 417-2-a-iii",
        "GRI 417-2-b",
        "GRI 417-3-a",
        "GRI 417-3-a-i",
        "GRI 417-3-a-ii",
        "GRI 417-3-a-iii",
        "GRI 417-3-b",
        "GRI 418-1-a-i",
        "GRI 418-1-a-ii",
    ],
)
def test_zero_event_classification_guardrails_are_registered(requirement_id):
    guardrail = get_no_evidence_guardrail(requirement_id)

    assert guardrail is not None
    assert guardrail.category is NoEvidenceGuardrailCategory.INCIDENT_CLASSIFICATION
    assert guardrail.missing_items
    assert guardrail.rationale
```

- [ ] **步骤 2：在 agent 测试中锁定清空 evidence 行为**

Add a case to existing disclosure agent tests:

```python
def test_no_evidence_guardrail_blocks_zero_event_statement_from_classification_leaf():
    task = DisclosureTask(
        task_id="task-GRI 416-2-a-i",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI 416",
        standard_version="2016",
        disclosure_id="GRI 416-2",
        requirement_id="GRI 416-2-a-i",
        requirement_text="incidents of non-compliance resulting in a fine or penalty;",
        keywords=["产品质量安全", "未发生", "罚款"],
        candidate_pages=[46],
    )
    chunk = DocumentChunk(
        chunk_id="chunk-GRI 416-2-a-i-46",
        report_id="report-1",
        text="报告期内未发生因产品质量安全而导致客户健康安全受到伤害的事件",
        source_page=46,
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        source_file_hash="hash-1",
    )

    result = DisclosureAgent().analyze(task, [chunk], confirm_llm=False)

    assert result.assessment.verdict is AssessmentVerdict.UNKNOWN
    assert result.assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
    assert result.assessment.evidence == []
    assert "罚款或处罚事件数量" in result.assessment.missing_items
```

- [ ] **步骤 3：实现 guardrail filter**

Modify `DisclosureAgent._filter_requirement_specific_pages()`:

```python
from src.standards.no_evidence_guardrails import get_no_evidence_guardrail
```

Add before contract explicit unknown handling:

```python
guardrail = get_no_evidence_guardrail(task.requirement_id)
if guardrail is not None:
    return []
```

Modify `_classify_rule_based()` before `if not bounded_evidence`:

```python
guardrail = get_no_evidence_guardrail(task.requirement_id)
if guardrail is not None and not bounded_evidence:
    return (
        AssessmentVerdict.UNKNOWN,
        guardrail.rationale,
        list(guardrail.missing_items),
    )
```

- [ ] **步骤 4：移除第一批 contract explicit verdict**

For each target requirement in this task, remove:

```python
verdict=AssessmentVerdict.UNKNOWN,
review_status=ReviewStatus.NEEDS_MANUAL_REVIEW,
rationale="...",
missing_items=(...),
```

Then add metadata:

```python
facets=(RequirementFacet.REQUIRES_INCIDENT_CLASSIFICATION,),
evidence_kinds=(EvidenceKind.EXPLICIT_ZERO_STATEMENT,),
semantic_group=SemanticGroup.ZERO_EVENT_COMPLIANCE,
```

Keep `candidate_pages=()` so current report profile remains strict.

- [ ] **步骤 5：运行 focused tests**

运行：

```powershell
uv run --no-sync pytest --basetemp tmp/pytest-no-evidence-zero backend/tests/standards/test_no_evidence_guardrails.py backend/tests/agents/test_disclosure_agent.py backend/tests/standards/test_evidence_contracts.py -q
```

预期：

```text
all selected tests pass
```

- [ ] **步骤 6：运行 577 regression gate**

Use the same commands from `docs/plan/ontology-regression-validation-plan.md`.

预期：

```text
before_count = 577
after_count = 577
added_requirements = []
removed_requirements = []
changed_by_field.verdict = 0
changed_by_field.review_status = 0
changed_by_field.source_pdf_page = 0
changed_by_field.evidence_type = 0
new_disclosed = []
```

- [ ] **步骤 7：提交**

运行：

```powershell
git add backend/src/standards/no_evidence_guardrails.py backend/src/standards/evidence_contracts.py backend/src/agents/disclosure_agent.py backend/tests/standards/test_no_evidence_guardrails.py backend/tests/agents/test_disclosure_agent.py backend/tests/standards/test_evidence_contracts.py
git commit -m "refactor: add zero event no-evidence guardrails"
```

## 8. 任务 3：迁移 risk-location guardrail

**Files:**
- Modify: `backend/src/standards/no_evidence_guardrails.py`
- Modify: `backend/src/standards/evidence_contracts.py`
- Test: `backend/tests/standards/test_no_evidence_guardrails.py`
- Test: `backend/tests/agents/test_disclosure_agent.py`

目标覆盖：

- `GRI 407-1-a`
- `GRI 407-1-a-i`
- `GRI 407-1-a-ii`
- `GRI 408-1-b`
- `GRI 408-1-b-i`
- `GRI 408-1-b-ii`
- `GRI 409-1-a-i`
- `GRI 409-1-a-ii`
- `GRI 413-2-a`
- `GRI 413-2-a-i`
- `GRI 413-2-a-ii`

Guardrail metadata:

```python
category=NoEvidenceGuardrailCategory.RISK_LOCATION
semantic_group=SemanticGroup.HUMAN_RIGHTS_POLICY or SemanticGroup.COMMUNITY_PROGRAM
required_facets=(RequirementFacet.REQUIRES_RISK_LOCATION,)
forbidden_evidence_kinds=(EvidenceKind.POLICY, EvidenceKind.MANAGEMENT_MECHANISM, EvidenceKind.CASE)
```

Required negative test:

```python
def test_no_evidence_guardrail_blocks_policy_from_risk_location_leaf():
    task = DisclosureTask(
        task_id="task-GRI 408-1-b-i",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI 408",
        standard_version="2016",
        disclosure_id="GRI 408-1",
        requirement_id="GRI 408-1-b-i",
        requirement_text="types of operations and suppliers considered to have significant risk for incidents of young workers exposed to hazardous work;",
        keywords=["童工", "青年员工", "供应商"],
        candidate_pages=[52],
    )
    chunk = DocumentChunk(
        chunk_id="chunk-GRI 408-1-b-i-52",
        report_id="report-1",
        text="供应商不得使用童工，并应遵守供应商行为准则。",
        source_page=52,
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        source_file_hash="hash-1",
    )

    result = DisclosureAgent().analyze(task, [chunk], confirm_llm=False)

    assert result.assessment.verdict is AssessmentVerdict.UNKNOWN
    assert result.assessment.evidence == []
    assert "风险运营点或供应商类型" in result.assessment.missing_items
```

运行 focused tests 和 577 gate。提交：

```powershell
git commit -m "refactor: add risk location no-evidence guardrails"
```

## 9. 任务 4：迁移 method/scope guardrail

**Files:**
- Modify: `backend/src/standards/no_evidence_guardrails.py`
- Modify: `backend/src/standards/evidence_contracts.py`
- Test: `backend/tests/standards/test_no_evidence_guardrails.py`
- Test: `backend/tests/agents/test_disclosure_agent.py`

目标覆盖：

- `GRI 305-2-c`
- `GRI 305-2-d`
- `GRI 305-2-d-i`
- `GRI 305-7-a`
- `GRI 403-9-f`
- `GRI 403-9-g`
- `GRI 403-10-d`
- `GRI 403-10-e`

Guardrail metadata:

```python
category=NoEvidenceGuardrailCategory.METHOD_SCOPE
required_facets=(RequirementFacet.REQUIRES_METHOD_OR_ASSUMPTION,)
forbidden_evidence_kinds=(EvidenceKind.KPI_VALUE, EvidenceKind.METHODOLOGY)
```

Required negative test:

```python
def test_no_evidence_guardrail_blocks_kpi_from_method_scope_leaf():
    task = DisclosureTask(
        task_id="task-GRI 403-9-g",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI 403",
        standard_version="2018",
        disclosure_id="GRI 403-9",
        requirement_id="GRI 403-9-g",
        requirement_text="whether the rates have been calculated based on 200,000 or 1,000,000 hours worked;",
        keywords=["TRIR", "LTIR", "方法"],
        candidate_pages=[67],
    )
    chunk = DocumentChunk(
        chunk_id="chunk-GRI 403-9-g-67",
        report_id="report-1",
        text="TRIR 0.29 LTIR 0.10 可记录工伤数量 13",
        source_page=67,
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        source_file_hash="hash-1",
    )

    result = DisclosureAgent().analyze(task, [chunk], confirm_llm=False)

    assert result.assessment.verdict is AssessmentVerdict.UNKNOWN
    assert result.assessment.evidence == []
    assert "数据编制方法和假设" in result.assessment.missing_items
```

运行 focused tests 和 577 gate。提交：

```powershell
git commit -m "refactor: add method scope no-evidence guardrails"
```

## 10. 任务 5：迁移 breakdown/security/remaining guardrail

**Files:**
- Modify: `backend/src/standards/no_evidence_guardrails.py`
- Modify: `backend/src/standards/evidence_contracts.py`
- Test: `backend/tests/standards/test_no_evidence_guardrails.py`
- Test: `backend/tests/agents/test_disclosure_agent.py`

目标覆盖剩余：

- `GRI 402-1-b`
- `GRI 403-1-a-i`
- `GRI 403-2-c`
- `GRI 403-8-a-ii`
- `GRI 403-8-b`
- `GRI 403-8-c`
- `GRI 403-9-a-iv`
- `GRI 403-9-b-iv`
- `GRI 403-9-c-ii`
- `GRI 403-10-a-iii`
- `GRI 403-10-b-iii`
- `GRI 403-10-c-ii`
- `GRI 404-1-a-i`
- `GRI 404-1-a-ii`
- `GRI 404-2-b`
- `GRI 405-2-b`
- `GRI 410-1-a`
- `GRI 410-1-b`
- `GRI 413-1-a-i`
- `GRI 413-1-a-ii`
- `GRI 413-1-a-iii`
- `GRI 413-1-a-vi`
- `GRI 413-1-a-vii`
- `GRI 413-1-a-viii`
- `GRI 416-1-a`
- `GRI 417-1-a-i`
- `GRI 417-1-a-iv`
- `GRI 417-1-a-v`
- `GRI 417-1-b`

Use categories:

- `BREAKDOWN_DIMENSION`
- `SECURITY_PERSONNEL`
- `METHOD_SCOPE`
- `RISK_LOCATION`

Required negative test for security:

```python
def test_no_evidence_guardrail_blocks_general_training_from_security_personnel_leaf():
    task = DisclosureTask(
        task_id="task-GRI 410-1-a",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI 410",
        standard_version="2016",
        disclosure_id="GRI 410-1",
        requirement_id="GRI 410-1-a",
        requirement_text="percentage of security personnel who have received formal training in human rights policies or procedures;",
        keywords=["人权", "培训", "安保"],
        candidate_pages=[59],
    )
    chunk = DocumentChunk(
        chunk_id="chunk-GRI 410-1-a-59",
        report_id="report-1",
        text="公司开展商业道德和合规培训。",
        source_page=59,
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        source_file_hash="hash-1",
    )

    result = DisclosureAgent().analyze(task, [chunk], confirm_llm=False)

    assert result.assessment.verdict is AssessmentVerdict.UNKNOWN
    assert result.assessment.evidence == []
    assert "安保人员人权政策培训比例" in result.assessment.missing_items
```

运行 focused tests 和 577 gate。提交：

```powershell
git commit -m "refactor: add remaining no-evidence guardrails"
```

## 11. 任务 6：最终清理和验收

**Files:**
- Modify: `docs/DEVELOPMENT.md`
- Generate: `tmp/review/remaining_explicit_verdicts.csv`

- [ ] **步骤 1：重新导出 remaining explicit verdict 清单**

运行：

```powershell
cd backend
@'
import csv
from pathlib import Path
from src.standards.evidence_contracts import _CONTRACTS

out = Path("../tmp/review/remaining_explicit_verdicts.csv")
rows = []
for requirement_id, contract in sorted(_CONTRACTS.items()):
    if contract.verdict is not None:
        rows.append({
            "requirement_id": requirement_id,
            "verdict": contract.verdict.value,
            "review_status": contract.review_status.value if contract.review_status else "",
            "allowed_pages": list(contract.allowed_pages),
            "candidate_pages": list(contract.candidate_pages),
            "missing_items": list(contract.missing_items),
            "retention_reason": "requires manual retention after no-evidence guardrail migration",
        })
with out.open("w", encoding="utf-8-sig", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=[
        "requirement_id",
        "verdict",
        "review_status",
        "allowed_pages",
        "candidate_pages",
        "missing_items",
        "retention_reason",
    ])
    writer.writeheader()
    writer.writerows(rows)
print("remaining_explicit=", len(rows))
'@ | uv run --no-sync python -
```

预期：

```text
remaining_explicit= 0
```

If remaining is not 0, inspect each row and decide whether it is justified manual retention.

- [ ] **步骤 2：运行最终测试套件**

运行：

```powershell
uv run --no-sync pytest --basetemp tmp/pytest-no-evidence-final backend/tests/standards/test_evidence_ontology.py backend/tests/standards/test_evidence_contracts.py backend/tests/standards/test_no_evidence_guardrails.py backend/tests/tools/test_evidence.py backend/tests/tools/test_review_csv_audit.py backend/tests/tools/test_first_pass_quality.py backend/tests/agents/test_disclosure_agent.py -q
```

预期：

```text
all selected tests pass
```

- [ ] **步骤 3：运行最终 577 regression gate**

Use `docs/plan/ontology-regression-validation-plan.md`.

预期：

```text
before_count = 577
after_count = 577
added_requirements = []
removed_requirements = []
changed_by_field.verdict = 0
changed_by_field.review_status = 0
changed_by_field.source_pdf_page = 0
changed_by_field.evidence_type = 0
new_disclosed = []
compilation_overlap = 0
review_csv_audit ok = True
```

- [ ] **步骤 4：更新 development log**

Add to `docs/DEVELOPMENT.md`:

```markdown
- no-evidence guardrail migration 已完成：原剩余 68 条 `unknown + needs_manual_review` per-ID explicit verdict 已迁移到 `no_evidence_guardrails.py`，用于结构化阻断零事件分类、风险地点、方法范围、拆分维度和安保人员培训等无效 evidence 传播。577 regression gate 无 verdict/review/evidence/page/quality/OCR 字段变化，`compilation_overlap=0`。
```

- [ ] **步骤 5：提交最终记录**

运行：

```powershell
git add docs/DEVELOPMENT.md tmp/review/remaining_explicit_verdicts.csv
git commit -m "docs: record no-evidence guardrail migration"
```

If `tmp/` remains gitignored and cannot be committed, commit only `docs/DEVELOPMENT.md` and mention the generated CSV path in final response.

## 12. 最终验收标准

完成后必须满足：

- `_CONTRACTS` 中 `contract.verdict is not None` 的数量为 0，或剩余项有明确人工保留理由。
- 577 regression gate 通过。
- `review_csv_audit` 通过。
- `first_pass_quality` delta 为 0。
- no-evidence guardrail 不生成 evidence。
- no-evidence guardrail 不产生 `partial/disclosed`。
- 零事件声明不传播到分类 leaf。
- 政策/机制不传播到风险地点 leaf。
- KPI 不传播到方法/范围 leaf。
- 一般培训不传播到安保人员培训 leaf。

## 13. 自查清单

- [ ] 计划文件没有本机绝对路径。
- [ ] 没有把固定 PDF 页码写成跨报告通用规则。
- [ ] 没有把 no-evidence guardrail 设计成 verdict 提升器。
- [ ] 每批都有 focused pytest、577 gate 和 commit。
- [ ] 68 条迁移后仍能保持当前 577 输出不变。
- [ ] `tmp/` 产物只作为本地审查材料，不要求提交。
