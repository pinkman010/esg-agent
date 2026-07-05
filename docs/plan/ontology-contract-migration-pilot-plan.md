# Ontology Contract Migration Pilot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立 per-ID contract verdict 向 ontology matrix 迁移的可重复机制，并完成 `GRI 308 / GRI 414 supplier assessment` 第一组试点。

**Architecture:** 保留 per-ID contract 的候选页、allowed pages、missing items 和 guardrail，把可泛化的 verdict 判定下沉到 `supplier_assessment` semantic group。每次只迁移一组高相似 requirement，迁移后重跑 577 条 regression diff，要求 diff 为 0 或只有已人工确认的预期变化。

**Tech Stack:** Python 3.11、pytest、现有 `RequirementEvidenceContract`、`evidence_ontology.py` verdict matrix、`DisclosureAgent`、review CSV audit、first-pass quality。

---

## 1. 目标边界

本计划不是 577 条全量 ontology 迁移。当前目标是完成第一组试点，并沉淀一套以后可重复执行的迁移流程。

本计划区分两件事：

- **迁移 verdict 判断权**：把可泛化的 `verdict` / `review_status` / `rationale` 从 per-ID contract 下沉到 ontology matrix。
- **保留 per-ID guardrail**：per-ID contract 继续承载候选页、allowed pages、forbidden pages、KPI 页、`missing_items`、最大 verdict 限制和当前报告回归保护。

试点范围只包括：

- `GRI 308-1-a`
- `GRI 308-2-a`
- `GRI 308-2-b`
- `GRI 308-2-c`
- `GRI 308-2-d`
- `GRI 308-2-e`
- `GRI 414-1-a`
- `GRI 414-2-a`
- `GRI 414-2-b`
- `GRI 414-2-c`
- `GRI 414-2-d`
- `GRI 414-2-e`

后续可按相同机制迁移：

- `403-9 / 403-10 OHS KPI`
- `404 / 405 breakdown dimension`
- `416 / 417 / 418 zero-event guardrail`
- 84 条 `compilation_requirement` 对应的 sufficiency guardrail

## 2. 不做范围

- 不一次性迁移 577 条。
- 不删除 per-ID contract。
- 不移除 per-ID contract 的候选页、allowed pages、forbidden pages、KPI 页和 `missing_items`。
- 不放宽 `disclosed` 门槛。
- 不让 policy / management mechanism 自动支撑具体数量、比例、供应商类型、影响类型或终止原因。
- 不因为同属 `supplier_assessment` semantic group 就自动升为 `disclosed`。
- 不调用外部模型。
- 不新增数据库字段。
- 不把固定 PDF 页码写成跨报告通用逻辑。

## 3. 当前问题

当前 `evidence_contracts.py` 中 `GRI 308` 和 `GRI 414` 的 verdict 仍主要逐 ID 写死。两组 requirement 结构高度相似：

- 新供应商筛选比例。
- 已评估供应商数量。
- 具有重大实际或潜在负面影响的供应商数量。
- 识别出的重大负面影响类型。
- 评估后同意改进的比例或数量。
- 终止关系比例及原因。

这类规则适合沉淀到 `SemanticGroup.SUPPLIER_ASSESSMENT`，但 partial / disclosed 边界必须保守：

- KPI 直接给出比例或数量，且 leaf 只要求该比例或数量时，可 `disclosed`。
- KPI 只给数量为 0，但 leaf 要求影响类型时，只能 `partially_disclosed`。
- 有终止关系比例但缺少 why 时，只能 `partially_disclosed`。
- 供应商退出机制不能单独支撑终止原因。

## 4. 影响文件

- Modify: `backend/src/standards/evidence_ontology.py`
  - 扩展 `RequirementFacet` 和 `evaluate_ontology_verdict`，覆盖 supplier assessment 的数量、比例、影响类型、改进、终止原因边界。
- Modify: `backend/src/standards/evidence_contracts.py`
  - 给 308/414 全组补齐 `semantic_group`、`facets`、`evidence_kinds`。
  - 对可由 ontology 接管的条目移除显式 `verdict` / `review_status` / `rationale`。
  - 对必须保留的 guardrail 继续保留 `missing_items`、allowed pages、candidate pages、KPI table pages。
- Modify: `backend/src/agents/disclosure_agent.py`
  - 确保 ontology matrix 可以和 contract `missing_items` 合并，且 per-ID 显式 verdict 仍最终覆盖。
- Test: `backend/tests/standards/test_evidence_ontology.py`
  - 覆盖 supplier assessment matrix 的 disclosed / partial / unknown 边界。
- Test: `backend/tests/standards/test_evidence_contracts.py`
  - 覆盖 308/414 全组共享 `supplier_assessment` semantic group。
- Test: `backend/tests/agents/test_disclosure_agent.py`
  - 保留现有 308/414 行为测试，确保迁移后外部行为不变。
- Reuse: `docs/plan/ontology-regression-validation-plan.md`
  - 迁移后按该计划重跑 577 regression diff。

## 5. 设计口径

### 5.0 迁移分类

| 类别 | 含义 | 本次试点处理 |
| --- | --- | --- |
| 可以移除 explicit verdict | leaf 的判断可以由 `semantic_group + facet + evidence_kind + matrix` 完整表达 | `308-1-a`、`308-2-a`、`308-2-b`、`414-1-a`、`414-2-a`、`414-2-b` |
| 保留 guardrail，但移除 explicit verdict | matrix 给出默认 verdict，contract 继续限制缺口、最大 verdict 或证据边界 | `308-2-c`、`308-2-e`、`414-2-c`、`414-2-e` |
| 暂不迁移 | 证据类型和 leaf 语义仍有歧义，继续由 per-ID verdict 接管 | `308-2-d`、`414-2-d` |

后续迁移时也必须先把目标 contract 放入这三类之一，不允许直接批量删除 verdict。

### 5.1 Supplier Assessment Facets

建议新增或复用以下 facet：

- `REQUIRES_COUNT`
- `REQUIRES_PERCENTAGE`
- `REQUIRES_IMPACT_TYPE`
- `REQUIRES_REMEDIATION_STATUS`
- `REQUIRES_REASON_WHY`

如现有 facet 名称足够表达含义，不新增近义词。

### 5.2 Supplier Assessment Evidence Kind

首批只使用现有 evidence kind：

- `KPI_VALUE`
- `KPI_BREAKDOWN`
- `MANAGEMENT_MECHANISM`

本试点不新增复杂 evidence kind。若需要区分“供应商退出机制”与“实际终止关系比例”，通过 facet 和 missing item 控制。

### 5.3 Verdict Matrix 规则

| Requirement 语义 | Evidence 情况 | Verdict |
| --- | --- | --- |
| 要求数量 | KPI 直接给出数量 | `disclosed + not_required` |
| 要求比例 | KPI 直接给出比例 | `disclosed + not_required` |
| 要求影响类型 | 只有重大影响供应商数量或 0 值 | `partially_disclosed + needs_manual_review` |
| 要求改进比例或数量 | KPI 直接给出对应比例或数量 | `disclosed + not_required` |
| 要求终止关系比例和 why | 只有终止比例或退出机制 | `partially_disclosed + needs_manual_review` |
| 只有管理机制，无数量或比例 | `partially_disclosed + needs_manual_review` |

### 5.4 disclosed 红线

matrix 只有在以下条件同时满足时才允许输出 `disclosed + not_required`：

1. `semantic_group` 匹配。
2. `facet` 能完整表达 leaf requirement 的要求。
3. `evidence_kind` 是可支撑该 facet 的强证据，例如 KPI 数量或比例。
4. evidence scope 与 requirement scope 一致，例如环境评价不能支撑社会评价，员工数据不能支撑非雇员工作者。
5. 没有 contract 或 compilation guardrail 指出的未满足 `missing_items`。

只要缺少范围、拆分、原因、影响类型、方法或边界中的任一关键项，matrix 必须输出 `partially_disclosed` 或 `unknown`。

### 5.5 decision_source

迁移后需要能解释 verdict 来源。第一版不新增数据库字段，先在 assessment rationale 或 evidence metadata 中落轻量标记，后续再决定是否产品化为正式字段。

建议来源枚举：

- `contract_explicit_verdict`
- `ontology_matrix`
- `contract_guardrail+ontology_matrix`

验收时至少要能通过测试确认：被迁移条目不再走 `contract_explicit_verdict`，仍保留 per-ID guardrail 的条目走 `contract_guardrail+ontology_matrix`。

### 5.6 后续迁移路线

| semantic group | 第一批 requirements | 可移除 explicit verdict | 仍保留 guardrail | 验收 |
| --- | --- | --- | --- | --- |
| `supplier_assessment` | `308 / 414` | 筛选比例、评估数量、重大影响数量 | impact type、why、退出机制、改进比例边界 | 577 diff = 0 |
| `ohs_kpi` | `403-9 / 403-10` | 死亡、工时、TRIR、职业病数量 | worker boundary、ill health scope、method、hazard type | 后续迁移 |
| `breakdown_dimension` | `404 / 405` | 总体数值 partial | gender/category/governance body guardrail | 后续迁移 |
| `zero_event_compliance` | `416 / 417 / 418` | 明确零事件 leaf | 不传播到罚款、警告、来源分类、往期事件 | 后续迁移 |

## 6. Task 1：写 supplier assessment ontology 测试

**Files:**
- Modify: `backend/tests/standards/test_evidence_ontology.py`

- [ ] **Step 1: 增加 disclosed 数量/比例测试**

在 `backend/tests/standards/test_evidence_ontology.py` 增加：

```python
def test_supplier_assessment_discloses_direct_kpi_count_or_percentage():
    percentage = evaluate_ontology_verdict(
        semantic_group=SemanticGroup.SUPPLIER_ASSESSMENT,
        facets={RequirementFacet.REQUIRES_PERCENTAGE},
        evidence_kinds={EvidenceKind.KPI_VALUE},
    )
    count = evaluate_ontology_verdict(
        semantic_group=SemanticGroup.SUPPLIER_ASSESSMENT,
        facets={RequirementFacet.REQUIRES_COUNT},
        evidence_kinds={EvidenceKind.KPI_VALUE},
    )

    assert percentage.verdict is AssessmentVerdict.DISCLOSED
    assert percentage.review_status is ReviewStatus.NOT_REQUIRED
    assert count.verdict is AssessmentVerdict.DISCLOSED
    assert count.review_status is ReviewStatus.NOT_REQUIRED
```

- [ ] **Step 2: 增加 impact type partial 测试**

同文件增加：

```python
def test_supplier_assessment_keeps_impact_type_partial_when_only_kpi_value_exists():
    result = evaluate_ontology_verdict(
        semantic_group=SemanticGroup.SUPPLIER_ASSESSMENT,
        facets={RequirementFacet.REQUIRES_IMPACT_TYPE},
        evidence_kinds={EvidenceKind.KPI_VALUE},
    )

    assert result.verdict is AssessmentVerdict.PARTIALLY_DISCLOSED
    assert result.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
    assert "重大负面影响类型" in result.missing_items
```

- [ ] **Step 3: 增加 termination why partial 测试**

同文件增加：

```python
def test_supplier_assessment_keeps_termination_reason_partial_when_reason_is_missing():
    result = evaluate_ontology_verdict(
        semantic_group=SemanticGroup.SUPPLIER_ASSESSMENT,
        facets={RequirementFacet.REQUIRES_PERCENTAGE, RequirementFacet.REQUIRES_REASON_WHY},
        evidence_kinds={EvidenceKind.KPI_VALUE},
    )

    assert result.verdict is AssessmentVerdict.PARTIALLY_DISCLOSED
    assert result.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
    assert "终止关系原因说明" in result.missing_items
```

- [ ] **Step 4: 增加 negative tests**

同文件增加反例测试：

```python
def test_supplier_assessment_policy_only_cannot_disclose_quantity_or_percentage():
    result = evaluate_ontology_verdict(
        semantic_group=SemanticGroup.SUPPLIER_ASSESSMENT,
        facets={RequirementFacet.REQUIRES_PERCENTAGE},
        evidence_kinds={EvidenceKind.MANAGEMENT_MECHANISM},
    )

    assert result.verdict is AssessmentVerdict.PARTIALLY_DISCLOSED
    assert result.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
    assert "percentage" in result.missing_items


def test_supplier_assessment_impact_count_does_not_satisfy_impact_type():
    result = evaluate_ontology_verdict(
        semantic_group=SemanticGroup.SUPPLIER_ASSESSMENT,
        facets={RequirementFacet.REQUIRES_IMPACT_TYPE},
        evidence_kinds={EvidenceKind.KPI_VALUE},
    )

    assert result.verdict is AssessmentVerdict.PARTIALLY_DISCLOSED
    assert "重大负面影响类型" in result.missing_items


def test_supplier_assessment_exit_mechanism_does_not_satisfy_percentage_and_reason():
    result = evaluate_ontology_verdict(
        semantic_group=SemanticGroup.SUPPLIER_ASSESSMENT,
        facets={RequirementFacet.REQUIRES_PERCENTAGE, RequirementFacet.REQUIRES_REASON_WHY},
        evidence_kinds={EvidenceKind.MANAGEMENT_MECHANISM},
    )

    assert result.verdict is AssessmentVerdict.PARTIALLY_DISCLOSED
    assert result.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
    assert "终止关系百分比" in result.missing_items
    assert "终止关系原因说明" in result.missing_items
```

- [ ] **Step 5: 运行红灯测试**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/standards/test_evidence_ontology.py -q
```

Expected:

```text
至少 impact type 或 termination reason 测试失败
```

## 7. Task 2：扩展 ontology matrix

**Files:**
- Modify: `backend/src/standards/evidence_ontology.py`

- [ ] **Step 1: 实现 supplier assessment partial 规则**

在 `evaluate_ontology_verdict` 中，放在通用 `REQUIRES_PERCENTAGE` 和 `REQUIRES_COUNT` 规则之前：

```python
    if semantic_group is SemanticGroup.SUPPLIER_ASSESSMENT:
        if RequirementFacet.REQUIRES_REASON_WHY in facets and EvidenceKind.KPI_VALUE in evidence_kinds:
            return OntologyVerdictResult(
                verdict=AssessmentVerdict.PARTIALLY_DISCLOSED,
                review_status=ReviewStatus.NEEDS_MANUAL_REVIEW,
                rationale="KPI evidence is directionally relevant, but the reason why supplier relationships were terminated is missing.",
                missing_items=("终止关系原因说明",),
            )
        if RequirementFacet.REQUIRES_REASON_WHY in facets and EvidenceKind.MANAGEMENT_MECHANISM in evidence_kinds:
            return OntologyVerdictResult(
                verdict=AssessmentVerdict.PARTIALLY_DISCLOSED,
                review_status=ReviewStatus.NEEDS_MANUAL_REVIEW,
                rationale="Supplier exit mechanism evidence is directionally relevant, but it does not disclose the termination percentage or reasons.",
                missing_items=("终止关系百分比", "终止关系原因说明"),
            )
        if RequirementFacet.REQUIRES_IMPACT_TYPE in facets and EvidenceKind.KPI_VALUE in evidence_kinds:
            return OntologyVerdictResult(
                verdict=AssessmentVerdict.PARTIALLY_DISCLOSED,
                review_status=ReviewStatus.NEEDS_MANUAL_REVIEW,
                rationale="KPI evidence discloses supplier impact assessment results, but it does not describe the significant impact types.",
                missing_items=("重大负面影响类型",),
            )
```

- [ ] **Step 2: 运行 ontology 测试**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/standards/test_evidence_ontology.py -q
```

Expected:

```text
PASS
```

## 8. Task 3：补齐 308/414 contract metadata

**Files:**
- Modify: `backend/src/standards/evidence_contracts.py`
- Modify: `backend/tests/standards/test_evidence_contracts.py`

- [ ] **Step 1: 扩展 contract metadata 测试**

在 `backend/tests/standards/test_evidence_contracts.py` 增加：

```python
def test_supplier_assessment_contracts_have_shared_ontology_metadata():
    cases = {
        "GRI 308-1-a": {RequirementFacet.REQUIRES_PERCENTAGE},
        "GRI 308-2-a": {RequirementFacet.REQUIRES_COUNT},
        "GRI 308-2-b": {RequirementFacet.REQUIRES_COUNT},
        "GRI 308-2-c": {RequirementFacet.REQUIRES_IMPACT_TYPE},
        "GRI 308-2-d": {RequirementFacet.REQUIRES_PERCENTAGE},
        "GRI 308-2-e": {RequirementFacet.REQUIRES_PERCENTAGE, RequirementFacet.REQUIRES_REASON_WHY},
        "GRI 414-1-a": {RequirementFacet.REQUIRES_PERCENTAGE},
        "GRI 414-2-a": {RequirementFacet.REQUIRES_COUNT},
        "GRI 414-2-b": {RequirementFacet.REQUIRES_COUNT},
        "GRI 414-2-c": {RequirementFacet.REQUIRES_IMPACT_TYPE},
        "GRI 414-2-d": {RequirementFacet.REQUIRES_COUNT},
        "GRI 414-2-e": {RequirementFacet.REQUIRES_PERCENTAGE, RequirementFacet.REQUIRES_REASON_WHY},
    }

    for requirement_id, expected_facets in cases.items():
        contract = get_requirement_contract(requirement_id)
        assert contract is not None
        assert contract.semantic_group is SemanticGroup.SUPPLIER_ASSESSMENT
        assert set(contract.facets) == expected_facets
        assert EvidenceKind.KPI_VALUE in contract.evidence_kinds
```

确保文件顶部已导入：

```python
from src.standards.evidence_ontology import EvidenceKind, RequirementFacet, SemanticGroup
```

- [ ] **Step 2: 运行红灯测试**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/standards/test_evidence_contracts.py -q
```

Expected:

```text
部分 308/414 contract 缺少 semantic_group、facets 或 evidence_kinds
```

- [ ] **Step 3: 给 308/414 contract 补 metadata**

在 `backend/src/standards/evidence_contracts.py` 中为试点范围内 12 条 contract 补齐：

```python
semantic_group=SemanticGroup.SUPPLIER_ASSESSMENT
evidence_kinds=(EvidenceKind.KPI_VALUE,)
```

按 requirement 配置 facets：

```python
"GRI 308-1-a": (RequirementFacet.REQUIRES_PERCENTAGE,)
"GRI 308-2-a": (RequirementFacet.REQUIRES_COUNT,)
"GRI 308-2-b": (RequirementFacet.REQUIRES_COUNT,)
"GRI 308-2-c": (RequirementFacet.REQUIRES_IMPACT_TYPE,)
"GRI 308-2-d": (RequirementFacet.REQUIRES_PERCENTAGE,)
"GRI 308-2-e": (RequirementFacet.REQUIRES_PERCENTAGE, RequirementFacet.REQUIRES_REASON_WHY)
"GRI 414-1-a": (RequirementFacet.REQUIRES_PERCENTAGE,)
"GRI 414-2-a": (RequirementFacet.REQUIRES_COUNT,)
"GRI 414-2-b": (RequirementFacet.REQUIRES_COUNT,)
"GRI 414-2-c": (RequirementFacet.REQUIRES_IMPACT_TYPE,)
"GRI 414-2-d": (RequirementFacet.REQUIRES_COUNT,)
"GRI 414-2-e": (RequirementFacet.REQUIRES_PERCENTAGE, RequirementFacet.REQUIRES_REASON_WHY)
```

- [ ] **Step 4: 运行 contract 测试**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/standards/test_evidence_contracts.py -q
```

Expected:

```text
PASS
```

## 9. Task 4：迁移可由 ontology 接管的 verdict

**Files:**
- Modify: `backend/src/standards/evidence_contracts.py`
- Modify: `backend/src/agents/disclosure_agent.py`
- Test: `backend/tests/agents/test_disclosure_agent.py`

- [ ] **Step 1: 增加 decision_source 测试**

在 `backend/tests/agents/test_disclosure_agent.py` 的 synthetic ontology 测试中增加断言，确保 ontology 接管路径可观测：

```python
assert result.assessment.evidence[0].metadata["decision_source"] == "ontology_matrix"
```

再为保留 contract `missing_items` 的 synthetic guardrail 场景增加：

```python
assert result.assessment.evidence[0].metadata["decision_source"] == "contract_guardrail+ontology_matrix"
```

- [ ] **Step 2: 实现 decision_source 标记**

在 `DisclosureAgent._classify_rule_based` 的 contract explicit verdict 分支中，将 evidence metadata 标记为：

```python
for item in evidence:
    item.metadata.setdefault("decision_source", "contract_explicit_verdict")
```

在 ontology branch 中，如果 `contract.missing_items` 非空：

```python
decision_source = "contract_guardrail+ontology_matrix"
```

否则：

```python
decision_source = "ontology_matrix"
```

并写入所有 evidence metadata。

- [ ] **Step 3: 移除第一批显式 verdict**

先只迁移行为最清晰的 6 条：

- `GRI 308-1-a`
- `GRI 308-2-a`
- `GRI 308-2-b`
- `GRI 414-1-a`
- `GRI 414-2-a`
- `GRI 414-2-b`

从这些 contract 中移除 explicit verdict 字段：

```python
verdict=...
review_status=...
rationale=...
```

保留：

```python
allowed_pages
candidate_pages
kpi_table_pages
facets
evidence_kinds
semantic_group
```

- [ ] **Step 4: 运行 agent 行为测试**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/agents/test_disclosure_agent.py::test_disclosure_agent_handles_308_supplier_environmental_assessment_rules tests/agents/test_disclosure_agent.py::test_disclosure_agent_handles_413_414_416_social_and_product_rules -q
```

Expected:

```text
PASS
```

- [ ] **Step 5: 迁移 partial 规则条目**

若 Step 4 通过，再迁移：

- `GRI 308-2-c`
- `GRI 308-2-e`
- `GRI 414-2-c`
- `GRI 414-2-e`

从这些 contract 中移除 explicit verdict 字段：

```python
verdict=...
review_status=...
rationale=...
```

保留：

```python
missing_items
allowed_pages
candidate_pages
kpi_table_pages
facets
evidence_kinds
semantic_group
```

说明：这些条目的 `missing_items` 可以继续由 contract 承载，`DisclosureAgent` 需要能将 ontology matrix 的默认 `missing_items` 与 contract `missing_items` 合并去重。迁移后 decision source 应为 `contract_guardrail+ontology_matrix`。

- [ ] **Step 6: 暂不迁移 308-2-d / 414-2-d**

`308-2-d` 和 `414-2-d` 虽然也可由 matrix 判断，但 `414-2-d` 当前人工判断认为 KPI 是数量而不是 GRI 要求的特定比例，因此先保留 per-ID verdict，避免矩阵过宽。

## 10. Task 5：合并 ontology 与 contract missing_items

**Files:**
- Modify: `backend/src/agents/disclosure_agent.py`
- Test: `backend/tests/agents/test_disclosure_agent.py`

- [ ] **Step 1: 增加 missing_items 合并测试**

在 `backend/tests/agents/test_disclosure_agent.py` 增加一个 synthetic contract 测试：

```python
def test_disclosure_agent_merges_contract_missing_items_with_ontology_result(monkeypatch):
    def fake_contract(requirement_id):
        if requirement_id != "GRI TEST-supplier-termination":
            return None
        return RequirementEvidenceContract(
            requirement_id=requirement_id,
            allowed_pages=(67,),
            candidate_pages=(67,),
            kpi_table_pages=(67,),
            facets=(RequirementFacet.REQUIRES_PERCENTAGE, RequirementFacet.REQUIRES_REASON_WHY),
            evidence_kinds=(EvidenceKind.KPI_VALUE,),
            semantic_group=SemanticGroup.SUPPLIER_ASSESSMENT,
            missing_items=("终止关系百分比", "终止关系原因说明"),
        )

    monkeypatch.setattr("src.agents.disclosure_agent.get_requirement_contract", fake_contract)
    task = DisclosureTask(
        task_id="task-supplier-termination",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI TEST",
        standard_version="2021",
        disclosure_id="GRI TEST",
        requirement_id="GRI TEST-supplier-termination",
        requirement_text="percentage of supplier relationships terminated and why.",
        keywords=["终止关系", "供应商"],
        candidate_pages=[67],
    )
    chunk = DocumentChunk(
        chunk_id="chunk-supplier-termination",
        report_id="report-1",
        text="评估后终止关系的供应商百分比（%） 0",
        source_page=67,
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        source_file_hash="hash-1",
    )

    result = DisclosureAgent().analyze(task, [chunk], confirm_llm=False)

    assert result.assessment.verdict is AssessmentVerdict.PARTIALLY_DISCLOSED
    assert result.assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
    assert result.assessment.missing_items.count("终止关系原因说明") == 1
    assert "终止关系百分比" in result.assessment.missing_items
```

- [ ] **Step 2: 实现合并逻辑**

在 `DisclosureAgent._classify_rule_based` 的 ontology branch 中，把：

```python
list(ontology_result.missing_items)
```

替换为去重合并：

```python
missing_items = [*ontology_result.missing_items]
for item in contract.missing_items:
    if item not in missing_items:
        missing_items.append(item)
```

- [ ] **Step 3: 运行 agent 测试**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/agents/test_disclosure_agent.py -q
```

Expected:

```text
PASS
```

## 11. Task 6：577 回归验收

**Files:**
- Reuse: `docs/plan/ontology-regression-validation-plan.md`
- Generate: `tmp/review/current_577_review_after_ontology.csv`
- Generate: `tmp/review/current_577_review_ontology_diff.csv`

- [ ] **Step 1: 重跑 577 regression**

按 `docs/plan/ontology-regression-validation-plan.md` 执行生成、audit、diff。

Expected:

```text
unique_requirements=577
review_csv_audit ok=True
```

- [ ] **Step 2: 检查 diff**

Expected:

```text
changed_requirements=0
new_disclosed=[]
```

若出现 diff：

- 只允许迁移导致的 rationale 或 missing_items 预期变化。
- verdict、review_status、source page、evidence_type、quality_flags 出现变化时必须停止并人工判断。

## 12. Task 7：提交

**Files:**
- Modified source/test files from previous tasks.

- [ ] **Step 1: 跑聚焦测试**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/standards/test_evidence_ontology.py tests/standards/test_evidence_contracts.py tests/agents/test_disclosure_agent.py tests/tools/test_review_csv_audit.py tests/tools/test_first_pass_quality.py -q
```

Expected:

```text
PASS
```

- [ ] **Step 2: 提交**

Run:

```powershell
git add backend/src/standards/evidence_ontology.py backend/src/standards/evidence_contracts.py backend/src/agents/disclosure_agent.py backend/tests/standards/test_evidence_ontology.py backend/tests/standards/test_evidence_contracts.py backend/tests/agents/test_disclosure_agent.py docs/plan/ontology-contract-migration-pilot-plan.md
git commit -m "refactor: migrate supplier assessment verdicts to ontology"
```

Expected:

```text
提交成功
```

## 13. 验收标准

- 试点只覆盖 `GRI 308 / GRI 414 supplier assessment`。
- 577 regression diff 为 0，或只出现人工确认的 rationale / missing_items 预期变化。
- `disclosed` 不新增。
- `partial` 不误升 `disclosed`。
- `global_fallback=0` 保持。
- `omission_note` 不升格。
- KPI 页继续带 `complex_table`。
- `308-2-d` 和 `414-2-d` 暂时不迁移，保留 per-ID verdict。
- 迁移后的 `decision_source` 能区分 `ontology_matrix`、`contract_guardrail+ontology_matrix` 和 `contract_explicit_verdict`。
- negative tests 证明 policy-only、exit-mechanism-only、impact-count-only 不会被误升 `disclosed`。

## 14. 自查清单

- [ ] 计划文件未写入本机绝对路径。
- [ ] 计划目标不是 577 全量沉淀。
- [ ] 每个迁移任务都要求 577 diff 验收。
- [ ] 没有要求调用外部模型。
- [ ] 没有把页码写成跨报告通用规则。
- [ ] 保留 per-ID contract 作为 page / guardrail / missing_items owner。
