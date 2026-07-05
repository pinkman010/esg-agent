# Requirement/Evidence Ontology Refactor Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有逐 `requirement_id` 的 evidence contract 抽象为 requirement 语义标签、evidence 类型和 verdict matrix，提高后续 requirement 首版召回与判定一致性。

**Architecture:** 在现有 contract、`DisclosureAgent`、KPI preview helper、review CSV audit 和 550 轮已验证规则之上增量重构。新增 ontology/matrix 只做纯规则抽象，per-ID contract 继续作为 override 和 guardrail，避免短期重写检索链路或放松 `disclosed` 门槛。

**Tech Stack:** Python 3.11、pytest、Pydantic v2、现有 FastAPI 后端、现有 GRI checklist/pack、pdfplumber 抽取结果、review CSV artifact。

---

## 1. 背景

截至 `tmp/review/current_550_review_after_rules.csv`，系统在字段契约、页码、`global_fallback`、`omission_note`、KPI 页 `complex_table` 和明显假阳性防护上已经稳定很多。但新增批次首版仍持续出现漏检：

- `current_500_review.csv` 新增 451-500 共 50 条全部为 `unknown + needs_manual_review`。
- `current_550_review.csv` 新增 501-550 共 49 条 `unknown`，唯一 `disclosed` 的 `GRI 408-1-a-ii` 还属于政策文本误升。
- 修复 `GRI 308` 后，结构高度相似的 `GRI 414` 没有自然继承。
- 修复 `GRI 403-9` 后，结构相近的 `GRI 403-10` 仍需要人工指出 KPI 证据。
- KPI 页能标记 `complex_table`，但 leaf requirement 与 KPI 行之间的绑定仍主要靠具体 ID 规则。
- 当前 checklist 总数为 661 条，但现有独立核查过滤口径实际产出 577 条 requirement；剩余 84 条均为 `compilation_requirement`，应进入充分性规则、`missing_items`、guardrail 和口径校验，不应作为独立 disclosed/unknown assessment。

本计划要把已经人工复核过的规律抽象为可测试的 ontology/matrix，减少“发现错误 -> 给具体 ID 加规则 -> 回归通过”的循环。当前 308/414、403-9/403-10、404/405 的大量 contract 和测试已经存在，计划重点是抽象与重构，不重复规划同一批 per-ID 补丁。

## 2. 不做范围

- 不启用外部模型。
- 不更换 PDF parser。
- 不新增数据库字段。
- 不改前端 UI。
- 不一次性覆盖全部 661 条 GRI requirement。
- 不删除现有 per-ID contract；先让 ontology 与现有 contract 并行，逐步吸收重复规则。
- 不用页码作为跨报告核心逻辑；页码只作为 Envision 2024 报告回归样本。
- 不把 first-pass recall 的提升建立在放宽 `disclosed` 门槛上。

## 3. 影响文件

- Create: `backend/src/standards/evidence_ontology.py`
  - 定义 `RequirementFacet`、`EvidenceKind`、`SemanticGroup`、verdict matrix 和纯函数。
- Modify: `backend/src/standards/evidence_contracts.py`
  - 只增加轻量 metadata 字段，并逐步引用 ontology 常量；per-ID contract 继续作为 override 和 guardrail。
- Test: `backend/tests/standards/test_evidence_contracts.py`
  - 覆盖 308/414、403-9/403-10、404/405 的 semantic group 与 facet 复用。
- Modify: `backend/src/agents/disclosure_agent.py`
  - 在证据识别后接入 ontology/matrix；per-ID contract 保持最终覆盖。
- Test: `backend/tests/agents/test_disclosure_agent.py`
  - 用已人工复核样本验证同构 requirement 共享 matrix 口径。
- Modify: `backend/src/tools/evidence.py`
  - 将 KPI preview 与 evidence kind 绑定，减少页级 preview 伪装成行级证据。
- Test: `backend/tests/tools/test_evidence.py`
  - 覆盖 KPI 行级 anchor 与多 anchor 场景。
- Modify: `backend/src/tools/review_csv_audit.py`
  - 增加 `page_label` 字面量 `\u` 转义检查；若需要命令行执行，再增加 CLI 入口。
- Test: `backend/tests/tools/test_review_csv_audit.py`
  - 使用现有 `write_csv` helper 覆盖 `page_label` 中 `\u` 被 hard gate 拦截。
- Create: `backend/src/tools/first_pass_quality.py`
  - 统计首版质量，并支持人工复核 gold 字段。
- Test: `backend/tests/tools/test_first_pass_quality.py`
  - 用小型 CSV fixture 验证 first-pass recall、false disclosed、wrong source page 和 unknown leakage。
- Generate: `tmp/review/compilation_requirement_mapping.csv`
  - 阶段性导出 84 条 `compilation_requirement` 到 leaf requirement / facet / missing item / guardrail 的映射草表；该文件属于临时审查产物。
- Modify: `docs/DEVELOPMENT.md`
  - 记录 ontology 口径、规则优先级、review CSV gate 和首版质量指标命令。

## 4. 设计口径

### 4.1 规则优先级

固定顺序如下，实施时不得交换：

1. `omission_note` / `not_applicable` 先短路为 `unknown + needs_manual_review`，不进入普通 disclosed/partial 判断。
2. contract/report profile 提供候选页；`single_report_workflow.py` 已支持 contract candidate fallback，ontology candidate 规则必须复用该机制，避免无索引项时回到 `global_no_index`。
3. 根据 evidence 内容识别 `EvidenceKind`。
4. ontology matrix 给默认 verdict、review status 和 missing items。
5. per-ID contract 作为最终 override/guardrail，用于已知例外、禁止页、当前报告回归保护。

### 4.2 Requirement 语义标签

首批标签放在 `backend/src/standards/evidence_ontology.py`：

```python
class RequirementFacet(StrEnum):
    REQUIRES_COUNT = "requires_count"
    REQUIRES_PERCENTAGE = "requires_percentage"
    REQUIRES_GENDER_BREAKDOWN = "requires_gender_breakdown"
    REQUIRES_EMPLOYEE_CATEGORY_BREAKDOWN = "requires_employee_category_breakdown"
    REQUIRES_REGION_BREAKDOWN = "requires_region_breakdown"
    REQUIRES_METHOD_OR_ASSUMPTION = "requires_method_or_assumption"
    REQUIRES_WORKER_BOUNDARY = "requires_worker_boundary"
    REQUIRES_RISK_LOCATION = "requires_risk_location"
    REQUIRES_IMPACT_TYPE = "requires_impact_type"
    REQUIRES_REMEDIATION_STATUS = "requires_remediation_status"
    REQUIRES_REASON_WHY = "requires_reason_why"
    REQUIRES_GOVERNANCE_BODY = "requires_governance_body"
```

首批复用范围：

- `GRI 308` 与 `GRI 414`：供应商筛选、供应商影响评估、改进、终止关系。
- `GRI 403-9` 与 `GRI 403-10`：工伤和职业健康 KPI。
- `GRI 404-1` 与 `GRI 404-3`：总体数值与性别/员工类别拆分。
- `GRI 405-1`：治理机构、管理层、员工类别、多元化维度。

### 4.3 Evidence 类型

```python
class EvidenceKind(StrEnum):
    KPI_VALUE = "kpi_value"
    KPI_BREAKDOWN = "kpi_breakdown"
    EXPLICIT_ZERO_STATEMENT = "explicit_zero_statement"
    POLICY = "policy"
    MANAGEMENT_MECHANISM = "management_mechanism"
    CASE = "case"
    RISK_IDENTIFICATION_RESULT = "risk_identification_result"
    METHODOLOGY = "methodology"
    INDEX_STATEMENT = "index_statement"
    OMISSION_NOTE = "omission_note"
```

原则：

- `kpi_value` 可直接支撑数量、比例、率值类 leaf。
- `policy`、`management_mechanism` 通常只能支撑 parent 或措施类 leaf 的 partial。
- `explicit_zero_statement` 只传播到数量 leaf，不传播到整改状态、原因、影响类型等 leaf。
- `omission_note` 不计入实质 evidence。
- `index_statement` 只用于索引页明确事实声明，不能用于章节定位。

### 4.4 Verdict Matrix

先实现小矩阵，不做完整推理引擎：

| Requirement 需要 | Evidence 情况 | Verdict |
| --- | --- | --- |
| 数量 | 有明确数量或 0 声明 | `disclosed` |
| 比例 | 有明确比例 | `disclosed` |
| 比例 | 只有数量 | `partially_disclosed` |
| 性别和员工类别拆分 | 只有总体值 | `partially_disclosed` |
| 地区拆分 | 只有性别/年龄 | `partially_disclosed` |
| 风险运营点/供应商类型/地区 | 只有政策或准则 | `partially_disclosed` 或 `unknown` |
| 影响类型 | 只有影响数量为 0 | `partially_disclosed` |
| 终止关系比例和 why | 只有退出机制 | `partially_disclosed` |
| 安保人员人权培训比例 | 只有一般员工培训 | `unknown` |
| 治理机构组成 | 只有管理层或高管数据 | `partially_disclosed` |

### 4.5 当前报告 Profile 边界

- PDF 第 65、66、67 页只能作为 Envision 2024 报告的回归样本。
- 通用逻辑必须依赖 KPI 行标签、年份列、单位、证据类型和 requirement facet，不依赖固定页码。
- report profile 可提供当前报告的候选页提示，但不能成为跨报告核心逻辑。

### 4.6 首版质量指标

`first_pass_quality` 需要支持两类输入：

- `current_N_review.csv` 与 `current_N_review_after_rules.csv` 的差异比较。
- 人工复核 gold 字段：`manual_label`、`correct_pdf_pages`、`suggested_verdict`、`issue_type`。

输出至少包括：

- `first_pass_disclosed_count`
- `first_pass_partial_count`
- `first_pass_unknown_count`
- `first_pass_recall`
- `manual_false_disclosed_count`
- `wrong_source_page_count`
- `unknown_leakage_count`
- `after_rules_delta_disclosed`
- `after_rules_delta_partial`
- `after_rules_delta_unknown`

这些指标用于评估系统是否开始泛化，不能只看 after-rules CSV 是否通过。

### 4.7 Compilation Requirement 处理口径

当前 84 条 `compilation_requirement` 是 GRI 编制说明、计算口径、排除项、边界和充分性要求，不进入独立 assessment 计数。

处理原则：

- 映射到一个或多个 leaf requirement，作为 `RequirementFacet`、`missing_items`、`guardrail_effect` 或 verdict matrix 的输入。
- 不生成独立 `disclosed`、`partially_disclosed` 或 `unknown` 结论。
- 不提高 `disclosed` 门槛以外的召回率；缺少编制口径、方法、假设、边界或拆分维度时，优先生成 `partially_disclosed` 或 `unknown + needs_manual_review`。
- 映射草表先保存为 `tmp/review/compilation_requirement_mapping.csv`，人工复核后再决定是否进入 manifest 或代码规则。

建议字段：

- `compilation_requirement_id`
- `canonical_disclosure_id`
- `target_requirement_ids`
- `facet`
- `missing_item_template`
- `guardrail_effect`
- `source_requirement_text`

## 5. 实施任务

### Task 1: 修正计划和现有实现假设

**Files:**
- Modify: `docs/plan/requirement-evidence-ontology-plan.md`

- [ ] **Step 1: 删除过期任务描述**

移除“新增 414、403、404、405 contract”的表述，替换为“为现有 contract 增加 ontology metadata 并验证复用”。

- [ ] **Step 2: 修正 helper 和 CLI 假设**

明确：

- `backend/tests/tools/test_review_csv_audit.py` 使用现有 `write_csv` helper。
- `backend/tests/agents/test_disclosure_agent.py` 的 `make_task()` 目前无参数；新增测试要么扩展 helper，要么直接构造 `DisclosureTask`。
- `backend/src/tools/review_csv_audit.py` 目前无 CLI；若计划使用 `python -m src.tools.review_csv_audit`，必须先实现 CLI。

- [ ] **Step 3: 文本自查**

Run:

```bash
rg "[A-Za-z]:\\\\|make_task\\(|PDF 第 65|PDF 第 66|PDF 第 67" docs/plan/requirement-evidence-ontology-plan.md
```

Expected:

- 不出现本机绝对路径。
- 不出现过期或未定义的 CSV helper 名称。
- 若出现 `make_task(`，必须说明 helper 需要扩展或直接构造 `DisclosureTask`。
- 固定页码只出现在 Envision 2024 回归样本语境。

### Task 2: 导出并复核 compilation requirement mapping

**Files:**
- Generate: `tmp/review/compilation_requirement_mapping.csv`
- Modify: `docs/DEVELOPMENT.md`
- Modify: `docs/plan/requirement-evidence-ontology-plan.md`

- [ ] **Step 1: 导出 84 条 compilation requirement**

从 checklist 中筛选 `requirement_type=compilation_requirement`，导出映射草表。每行至少包含：

- `compilation_requirement_id`
- `canonical_disclosure_id`
- `target_requirement_ids`
- `facet`
- `missing_item_template`
- `guardrail_effect`
- `source_requirement_text`

- [ ] **Step 2: 人工复核映射**

复核重点：

- 是否正确关联到 leaf requirement。
- 是否应转化为 `RequirementFacet`。
- 是否应转化为 `missing_items` 模板。
- 是否属于 disclosed guardrail，例如缺方法、缺边界、缺拆分维度时不得升格。

- [ ] **Step 3: 更新 ontology 实施边界**

复核后更新本计划中首批 ontology 覆盖范围，避免直接把 84 条转为 per-ID contract。

### Task 3: 新增 ontology 纯规则模块

**Files:**
- Create: `backend/src/standards/evidence_ontology.py`
- Test: `backend/tests/standards/test_evidence_ontology.py`

- [ ] **Step 1: 写失败测试**

新增测试验证 ontology matrix 的基础行为：

```python
from src.domain.enums import AssessmentVerdict
from src.standards.evidence_ontology import EvidenceKind, RequirementFacet, SemanticGroup, evaluate_ontology_verdict


def test_ontology_discloses_percentage_when_kpi_value_matches_percentage_requirement():
    result = evaluate_ontology_verdict(
        semantic_group=SemanticGroup.SUPPLIER_ASSESSMENT,
        facets={RequirementFacet.REQUIRES_PERCENTAGE},
        evidence_kinds={EvidenceKind.KPI_VALUE},
    )

    assert result.verdict is AssessmentVerdict.DISCLOSED
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd backend
uv run --no-sync pytest tests/standards/test_evidence_ontology.py -q
```

Expected: FAIL，模块不存在。

- [ ] **Step 3: 实现最小 ontology 模块**

实现 `RequirementFacet`、`EvidenceKind`、`SemanticGroup`、`OntologyVerdictResult` 和 `evaluate_ontology_verdict()`。第一版只覆盖供应商评估、OHS KPI、拆分维度三类。

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
cd backend
uv run --no-sync pytest tests/standards/test_evidence_ontology.py -q
```

Expected: PASS。

### Task 4: 给现有 contract 增加 ontology metadata

**Files:**
- Modify: `backend/src/standards/evidence_contracts.py`
- Test: `backend/tests/standards/test_evidence_contracts.py`

- [ ] **Step 1: 写失败测试**

验证 308/414 共享 semantic group：

```python
from src.standards.evidence_contracts import get_requirement_contract
from src.standards.evidence_ontology import RequirementFacet, SemanticGroup


def test_supplier_environmental_and_social_contracts_share_semantic_group():
    contract_308 = get_requirement_contract("GRI 308-1-a")
    contract_414 = get_requirement_contract("GRI 414-1-a")

    assert contract_308 is not None
    assert contract_414 is not None
    assert contract_308.semantic_group is SemanticGroup.SUPPLIER_ASSESSMENT
    assert contract_414.semantic_group is SemanticGroup.SUPPLIER_ASSESSMENT
    assert RequirementFacet.REQUIRES_PERCENTAGE in contract_308.facets
    assert RequirementFacet.REQUIRES_PERCENTAGE in contract_414.facets
```

- [ ] **Step 2: 扩展 contract dataclass**

给 `RequirementEvidenceContract` 增加：

```python
facets: tuple[RequirementFacet, ...] = ()
evidence_kinds: tuple[EvidenceKind, ...] = ()
semantic_group: SemanticGroup | None = None
```

- [ ] **Step 3: 标注首批现有 contract**

最低覆盖：

- 308/414：`SemanticGroup.SUPPLIER_ASSESSMENT`
- 403-9/403-10：`SemanticGroup.OHS_KPI`
- 404/405：`SemanticGroup.BREAKDOWN_DIMENSION`

- [ ] **Step 4: 运行测试**

Run:

```bash
cd backend
uv run --no-sync pytest tests/standards/test_evidence_contracts.py -q
```

Expected: PASS。

### Task 5: 在 `DisclosureAgent` 中接入 matrix

**Files:**
- Modify: `backend/src/agents/disclosure_agent.py`
- Test: `backend/tests/agents/test_disclosure_agent.py`

- [ ] **Step 1: 写复用行为测试**

直接构造 `DisclosureTask`，不要依赖带参数的 `make_task()`。测试应证明同一 semantic group 下，308/414 通过 matrix 使用同一套 verdict 规则。

- [ ] **Step 2: 接入顺序**

实现顺序必须符合：

1. 已有 evidence 过滤和 forbidden page guardrail。
2. evidence kind 识别。
3. ontology matrix 默认 verdict。
4. per-ID contract 覆盖 verdict、review status、missing items、allowed/forbidden pages。

- [ ] **Step 3: 运行聚焦测试**

Run:

```bash
cd backend
uv run --no-sync pytest tests/agents/test_disclosure_agent.py -q
```

Expected: PASS。

### Task 6: 将 KPI preview 与 evidence kind 绑定

**Files:**
- Modify: `backend/src/tools/evidence.py`
- Test: `backend/tests/tools/test_evidence.py`

- [ ] **Step 1: 写多 anchor 测试**

使用现有 `build_kpi_evidence_preview()`，验证目标 KPI 行优先于整页文本：

```python
def test_kpi_preview_anchors_recordable_injury_row():
    text = (
        "员工工作小时数 44,528,901 "
        "员工可记录工伤数量 13 "
        "员工总可记录工伤率（TRIR） 0.29 "
        "职业病病例数量 0"
    )

    preview = build_kpi_evidence_preview(text, ["员工可记录工伤数量", "TRIR"])

    assert "员工可记录工伤数量 13" in preview
    assert "TRIR" in preview
```

- [ ] **Step 2: 必要时扩展 preview 函数**

若测试失败，扩展 `build_kpi_evidence_preview()` 对多 anchor 的评分，优先选择同时包含目标指标、数值和单位的窗口。

- [ ] **Step 3: 运行测试**

Run:

```bash
cd backend
uv run --no-sync pytest tests/tools/test_evidence.py -q
```

Expected: PASS。

### Task 7: 新增 first-pass quality 工具

**Files:**
- Create: `backend/src/tools/first_pass_quality.py`
- Test: `backend/tests/tools/test_first_pass_quality.py`

- [ ] **Step 1: 写失败测试**

测试需要自己定义 CSV writer，不引用项目中不存在的测试 helper：

```python
import csv
from pathlib import Path

from src.tools.first_pass_quality import compare_first_pass_to_after_rules


def write_csv(path: Path, rows: list[dict]) -> None:
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_first_pass_quality_counts_manual_gold_fields(tmp_path: Path):
    current = tmp_path / "current.csv"
    after = tmp_path / "after.csv"
    write_csv(
        current,
        [
            {
                "requirement_id": "GRI 414-1-a",
                "verdict": "unknown",
                "source_pdf_page": "",
                "manual_label": "漏检",
                "correct_pdf_pages": "[67]",
                "suggested_verdict": "disclosed",
                "issue_type": "missed_evidence",
            }
        ],
    )
    write_csv(after, [{"requirement_id": "GRI 414-1-a", "verdict": "disclosed", "source_pdf_page": "67"}])

    result = compare_first_pass_to_after_rules(current, after)

    assert result.first_pass_unknown_count == 1
    assert result.unknown_leakage_count == 1
    assert result.after_rules_delta_disclosed == 1
```

- [ ] **Step 2: 实现工具**

按 `requirement_id` 聚合首行，支持人工 gold 字段，输出 dataclass 结果。

- [ ] **Step 3: 增加 CLI**

提供：

```bash
python -m src.tools.first_pass_quality ../tmp/review/current_550_review.csv ../tmp/review/current_550_review_after_rules.csv
```

CLI 输出 JSON 或简洁文本均可，但必须包含 unknown leakage、false disclosed、wrong source page。

- [ ] **Step 4: 运行测试**

Run:

```bash
cd backend
uv run --no-sync pytest tests/tools/test_first_pass_quality.py -q
```

Expected: PASS。

### Task 8: 增加 holdout 验收

**Files:**
- Test: `backend/tests/standards/test_evidence_ontology.py`
- Test: `backend/tests/agents/test_disclosure_agent.py`

- [ ] **Step 1: 选定 holdout**

默认使用 551-600 作为 holdout。实施期间禁止针对 holdout 新增 per-ID contract，除非用户另行批准。

- [ ] **Step 2: 写 synthetic unseen analog 测试**

构造一个非真实 GRI ID 的同构 requirement，例如 `HOLDOUT supplier screening percentage`，通过 semantic group/facet/evidence kind 命中 matrix，证明不靠 per-ID contract 也能得出正确默认 verdict。

- [ ] **Step 3: 运行测试**

Run:

```bash
cd backend
uv run --no-sync pytest tests/standards/test_evidence_ontology.py tests/agents/test_disclosure_agent.py -q
```

Expected: PASS。

### Task 9: 更新开发文档与回归验证

**Files:**
- Modify: `docs/DEVELOPMENT.md`

- [ ] **Step 1: 记录 ontology 口径**

增加章节：

```markdown
### Requirement/Evidence Ontology

系统将 requirement 拆为语义标签，将 evidence 拆为证据类型，再通过 verdict matrix 判断 disclosed / partially_disclosed / unknown。

规则优先级：
1. omission_note / not_applicable 先短路为 unknown + needs_manual_review。
2. contract/report profile 提供候选页。
3. evidence kind 识别证据类型。
4. ontology matrix 给默认 verdict。
5. per-ID contract 作为最终 override/guardrail。

关键边界：
- KPI 数量或比例可以支撑数值类 leaf。
- 总体值不能自动传播到性别、员工类别、地区拆分 leaf。
- 政策和管理机制不能自动支撑具体风险运营点或供应商类型。
- 固定 PDF 页码只用于当前报告回归样本，跨报告逻辑必须依赖 KPI 行标签、年份列、单位和 evidence type。
```

- [ ] **Step 2: 运行聚焦测试**

Run:

```bash
cd backend
uv run --no-sync pytest tests/standards/test_evidence_ontology.py tests/standards/test_evidence_contracts.py tests/tools/test_evidence.py tests/tools/test_review_csv_audit.py tests/tools/test_first_pass_quality.py tests/agents/test_disclosure_agent.py -q
```

Expected: PASS。

- [ ] **Step 3: 运行首版质量命令**

Run:

```bash
cd backend
uv run --no-sync python -m src.tools.first_pass_quality ../tmp/review/current_550_review.csv ../tmp/review/current_550_review_after_rules.csv
```

Expected: 输出 first-pass unknown、unknown leakage、false disclosed、wrong source page 和 after-rules delta。

## 6. 验收标准

- `review_csv_audit` 能拦截 `page_label` 中的字面量 `\u` 转义。
- `evidence_ontology.py` 存在，并只包含 enum、matrix 数据结构和纯函数。
- `GRI 308` 与 `GRI 414` 共享 `supplier_assessment` semantic group。
- `GRI 403-9` 与 `GRI 403-10` 共享 `ohs_kpi` semantic group。
- `GRI 404` 与 `GRI 405` 拆分维度规则共享 `breakdown_dimension` semantic group。
- `DisclosureAgent` 接入 matrix 后，per-ID contract 仍是最终 override/guardrail。
- PDF 第 65、66、67 页 KPI evidence 保持 `complex_table`。
- first-pass quality 工具能使用人工 gold 字段统计漏检、误判和错页。
- holdout 样本不靠新增 per-ID contract 也能通过 semantic group/facet/evidence kind 得到默认判定。
- 不调用外部模型。

## 7. 风险与取舍

- 短期会增加 ontology 模块和 contract metadata，但能减少后续逐 ID 补丁。
- 首批 ontology 仍以 Envision 2024 报告为回归样本，不能宣称跨报告完全泛化。
- 规则矩阵必须保持保守，宁可 partial/unknown 进入人工复核，也不能因为追求 recall 放宽 disclosed。
- 现有 per-ID contract 不应立即删除；等 matrix 覆盖稳定后再清理重复规则。
- 固定页码只能作为当前报告 profile 的候选提示；后续切换报告时必须重新生成 report profile 或依赖行级语义匹配。

## 8. 执行顺序建议

1. 先做 Task 1，确保计划文件与当前代码事实一致。
2. 再做 Task 2，导出并复核 84 条 `compilation_requirement` 映射。
3. 再做 Task 3-4，把 ontology 模块和 contract metadata 建起来。
4. 再做 Task 5-6，让 `DisclosureAgent` 和 KPI preview 使用 ontology/evidence kind。
5. 再做 Task 7，建立 first-pass quality 指标。
6. 最后做 Task 8-9，用 holdout 和开发文档约束后续继续打补丁的风险。
