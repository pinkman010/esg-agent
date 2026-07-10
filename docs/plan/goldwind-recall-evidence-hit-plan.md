# Goldwind Recall Evidence Hit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 Goldwind holdout 中已生成 profile route 的重点漏检项稳定命中 evidence，并生成下一轮人工复核包。

**Architecture:** 本阶段不新增 Goldwind per-ID contract，不把 Goldwind 固定页码写入通用 GRI 规则。改造集中在 profile route handoff、bounded retrieval、KPI/段落行级匹配、ontology partial matrix 和 review pack 输出；每轮自动验证后停在人工复核点。

**Tech Stack:** Python 3.11、pytest、`SingleReportWorkflow`、`EvidenceRouter`、`retrieve_evidence`、`kpi_row_matcher`、`EvidenceKind`、`SemanticGroup`、`first_pass_quality`、`review_csv_audit`、`regenerate_review_csv`。

---

## 背景结论

人工复核 `tmp/review/holdout_goldwind_2024_review_pack.csv` 后，当前 5 个 gold case 的处理口径为：

- `GRI 205-1-a`：应命中 PDF 第 21 页，建议 `partially_disclosed`。证据是反腐败审计、风险管理和商业道德机制；缺运营点总数和百分比。
- `GRI 205-1-b`：应命中 PDF 第 21 页，建议 `partially_disclosed`。证据是反腐败机制和审计策略；缺重大腐败风险类型、地点、业务环节或评估结果。
- `GRI 414-1-a`：应命中 PDF 第 31-32 页，建议 `partially_disclosed`。证据是供应商社会责任审核和审核率；缺“新供应商”分母、数量和百分比。
- `GRI 403-9-a-i`：应命中 PDF 第 37 或 47 页，建议 `partially_disclosed`。证据是员工因工死亡人数；缺死亡率。
- `GRI 418-1-a`：当前 `unknown` 合理。一般信息安全、数据或隐私泄露零事件不能支撑客户隐私投诉数量及来源分类。

当前质量基线：

- `global_fallback_count=0`。
- `global_no_index_count=4`。
- `profile_route_requirement_count=464`。
- `profile_route_hit_count=53`。
- `false_disclosed_count=0`。
- Goldwind 最大 PDF 页码为 52。
- Envision 577 重生成 gate 已可执行，且当前严格 diff 为 0。

## 硬边界

- 不新增 Goldwind per-ID contract。
- 不把 Goldwind 固定页码写入通用 GRI 标准规则。
- Goldwind `source_pdf_page` 是权威字段；`source_report_page` 只用于展示。
- GRI index PDF 50/51 只能作为 candidate route 来源，不能成为 `substantive evidence`。
- `GRI 418-1-a` 必须保持 `unknown + needs_manual_review`，除非报告直接披露客户隐私投诉数量及来源分类。
- `GRI 205-1-a`、`GRI 205-1-b`、`GRI 414-1-a`、`GRI 403-9-a-i` 本阶段最多允许 `partially_disclosed`，不得自动升为 `disclosed`。
- 有机制、审计、培训、审核数量、零事件或总数，但缺运营点百分比、新供应商分母、死亡率、来源分类时，只能进入 partial 或 unknown。
- 任何 `unknown/partial -> disclosed` 变化必须暂停并进入人工复核。

## 停止条件

触发任一条件即暂停并汇报：

- `false_disclosed_count > 0`。
- `wrong_source_page_count > 0`。
- `global_fallback_count > 0`。
- `source_pdf_page` 或 `candidate_pdf_pages` 超过 Goldwind 报告总页数 52。
- Goldwind GRI index PDF 50/51 被标为 `substantive evidence`。
- `GRI 418-1-a` 从 `unknown` 升为 `partially_disclosed` 或 `disclosed`。
- `GRI 205-1-a`、`GRI 205-1-b`、`GRI 414-1-a`、`GRI 403-9-a-i` 任一条被自动升为 `disclosed`。
- Envision 577 regeneration gate 出现 requirement 数量变化。
- Envision 577 regeneration gate 出现非预期 verdict、review_status、source page、evidence_type、quality_flags、OCR/VLM 字段变化。
- 需要新增 Goldwind per-ID contract 才能继续。
- focused tests 失败且不能通过小范围修复解决。

## 文件职责

- `backend/src/tools/holdout_review_pack.py`：输出 route handoff、profile candidate、evidence hit 状态和人工复核包。
- `backend/src/tools/holdout_recall_diagnosis.py`：把人工 gold case 转成结构化诊断表。
- `backend/src/tools/retrieval.py`：bounded evidence 命中。增加 profile route 下的中文管理机制和 metric terms 段落匹配。
- `backend/src/tools/kpi_row_matcher.py`：KPI/段落行匹配。支持中文连续文本中“指标附近数值”。
- `backend/src/tools/evidence.py`：preview 锚点生成。让 route/evidence kind 的锚点优先进入 `evidence_preview`。
- `backend/src/standards/evidence_ontology.py`：matrix verdict。为反腐败风险评估、供应商评估和 OHS KPI 增加保守 partial 边界。
- `backend/src/standards/evidence_contracts.py`：只允许补 semantic metadata、facet、evidence kind，不允许新增 Goldwind candidate pages。
- `backend/tests/tools/test_holdout_review_pack.py`：覆盖 route handoff 字段和 review pack 状态。
- `backend/tests/tools/test_retrieval.py`：覆盖 bounded retrieval 命中管理机制和拒绝 global fallback。
- `backend/tests/tools/test_kpi_row_matcher.py`：覆盖供应商审核、工伤死亡人数等 KPI/段落行匹配。
- `backend/tests/standards/test_evidence_ontology.py`：覆盖 partial matrix 和 418 guardrail。
- `backend/tests/standards/test_evidence_contracts.py`：覆盖 semantic metadata。
- `docs/DEVELOPMENT.md`：记录本轮指标、产物和人工复核停止点。

## 产物

- `tmp/review/holdout_goldwind_2024_first_pass.csv`
- `tmp/review/holdout_goldwind_2024_reviewed.csv`
- `tmp/review/holdout_goldwind_2024_audit.json`
- `tmp/review/holdout_goldwind_2024_route_improvement.csv`
- `tmp/review/holdout_goldwind_2024_review_pack.csv`
- `tmp/review/holdout_goldwind_2024_evidence_hit_summary.json`
- `tmp/review/current_577_review_regenerated.csv`
- `tmp/review/current_577_review_regenerated_audit.json`
- `tmp/review/current_577_review_regeneration_diff_summary.json`

---

## Task 1: 锁定 Route Handoff Diagnostics

**Files:**
- Modify: `backend/src/tools/holdout_review_pack.py`
- Test: `backend/tests/tools/test_holdout_review_pack.py`

- [ ] **Step 1: 写失败测试，验证无 evidence 的 unknown 也能显示 profile route**

在 `backend/tests/tools/test_holdout_review_pack.py` 增加：

```python
def test_route_improvement_marks_profile_route_without_evidence_as_keyword_miss(tmp_path: Path):
    diagnosis = tmp_path / "diagnosis.csv"
    diagnosis.write_text(
        "requirement_id,issue_type,correct_pdf_pages,evidence_kind,suggested_profile_route,route_failure_reason\n"
        "GRI 205-1-a,keyword_miss,[21],management_mechanism,[21],candidate_pages_present_keyword_miss\n",
        encoding="utf-8",
    )
    first_pass = tmp_path / "first.csv"
    first_pass.write_text(
        "requirement_id,verdict,review_status,source_pdf_page,candidate_pdf_pages,candidate_page_source,evidence_preview\n"
        "GRI 205-1-a,unknown,needs_manual_review,,,,\n",
        encoding="utf-8",
    )
    profile = tmp_path / "profile.json"
    profile.write_text(
        """{
          "report_id": "goldwind_2024",
          "company_name": "Goldwind",
          "report_year": 2024,
          "pdf_file": "goldwind.pdf",
          "total_pdf_pages": 52,
          "page_numbering": {"report_index_pdf_page": 50, "report_index_report_page": 96, "total_pdf_pages": 52},
          "gri_index": {"pdf_pages": [50, 51]},
          "sections": [],
          "index_note_pages": [],
          "assurance_pages": [],
          "requirement_routes": {
            "GRI 205-1-a": {"candidate_pdf_pages": [21], "kpi_table_pages": [], "metric_terms": ["反腐败", "审计"]}
          }
        }""",
        encoding="utf-8",
    )

    rows = build_route_improvement_rows(diagnosis, first_pass, profile)

    assert rows[0]["profile_candidate_pdf_pages"] == "[21]"
    assert rows[0]["route_status"] == "candidate_without_evidence"
    assert rows[0]["route_failure_reason"] == "candidate_pages_present_keyword_miss"
```

- [ ] **Step 2: 运行测试确认失败或确认已覆盖**

Run:

```powershell
cd backend
uv run --no-sync pytest --basetemp ../tmp/pytest-route-diagnostics tests/tools/test_holdout_review_pack.py::test_route_improvement_marks_profile_route_without_evidence_as_keyword_miss -q
```

Expected: 若测试已通过，记录为已有能力；若失败，按 Step 3 实现。

- [ ] **Step 3: 实现 route handoff 字段**

在 `backend/src/tools/holdout_review_pack.py` 中确保 `ROUTE_IMPROVEMENT_COLUMNS` 包含：

```python
"route_failure_reason",
"before_candidate_page_source",
"profile_candidate_pdf_pages",
"route_status",
```

确保 `build_route_improvement_rows()` 输出：

```python
"route_failure_reason": diagnosis.get("route_failure_reason", ""),
"before_candidate_page_source": _first_non_empty(rows, "candidate_page_source"),
"profile_candidate_pdf_pages": profile_candidate_pages,
"route_status": _route_status(candidate_pages, source_pages, correct_pages, profile_candidate_pages),
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```powershell
cd backend
uv run --no-sync pytest --basetemp ../tmp/pytest-route-diagnostics tests/tools/test_holdout_review_pack.py -q
```

Expected: PASS。

---

## Task 2: 增强 Bounded Retrieval 的管理机制命中

**Files:**
- Modify: `backend/src/tools/retrieval.py`
- Test: `backend/tests/tools/test_retrieval.py`

- [ ] **Step 1: 写 205 管理机制命中测试**

在 `backend/tests/tools/test_retrieval.py` 增加：

```python
def test_retrieve_evidence_matches_management_mechanism_terms_on_profile_route():
    task = DisclosureTask(
        task_id="task-205-1-a",
        run_id="run-1",
        report_id="goldwind",
        standard_id="GRI",
        standard_version="2016",
        disclosure_id="GRI 205-1",
        requirement_id="GRI 205-1-a",
        requirement_text="operations assessed for risks related to corruption",
        keywords=["operations", "assessed", "risks", "corruption"],
        candidate_pages=[21],
        candidate_pdf_pages=[21],
        candidate_report_pages=[38],
        candidate_page_source="report_profile",
        kpi_metric_terms=["反腐败", "审计", "商业道德", "舞弊"],
    )
    chunks = [
        DocumentChunk(
            chunk_id="p21",
            report_id="goldwind",
            text="审计委员会领导审计监察部开展反腐败制度建设，按业务单位特点和风险程度制定审计策略，并在审计中关注商业道德问题。",
            source_page=21,
            source_method=EvidenceSourceMethod.PDFPLUMBER,
            source_file_hash="hash",
        )
    ]

    evidence = retrieve_evidence(task, chunks)

    assert len(evidence) == 1
    assert evidence[0].source_page == 21
    assert evidence[0].metadata["retrieval_strategy"] == "index_page_bounded"
    assert "反腐败" in evidence[0].evidence_preview
```

- [ ] **Step 2: 运行测试确认失败或确认已覆盖**

Run:

```powershell
cd backend
uv run --no-sync pytest --basetemp ../tmp/pytest-management-retrieval tests/tools/test_retrieval.py::test_retrieve_evidence_matches_management_mechanism_terms_on_profile_route -q
```

Expected: 若测试已通过，记录为已有能力；若失败，按 Step 3 实现。

- [ ] **Step 3: 实现 metric terms 参与普通段落匹配**

在 `backend/src/tools/retrieval.py` 的 keyword 匹配路径中合并：

```python
terms = [*task.keywords, *task.kpi_metric_terms]
keywords = [term.lower() for term in terms if term]
```

同时保持：

```python
if task.candidate_pages:
    bounded_chunks = [chunk for chunk in chunks if chunk.source_page in set(task.candidate_pages)]
```

避免命中候选页以外内容。

- [ ] **Step 4: 运行测试确认通过**

Run:

```powershell
cd backend
uv run --no-sync pytest --basetemp ../tmp/pytest-management-retrieval tests/tools/test_retrieval.py::test_retrieve_evidence_matches_management_mechanism_terms_on_profile_route -q
```

Expected: PASS。

---

## Task 3: 增强 Goldwind KPI/段落行匹配

**Files:**
- Modify: `backend/src/tools/kpi_row_matcher.py`
- Test: `backend/tests/tools/test_kpi_row_matcher.py`

- [ ] **Step 1: 写供应商社会责任审核匹配测试**

在 `backend/tests/tools/test_kpi_row_matcher.py` 增加：

```python
def test_match_kpi_rows_matches_supplier_social_audit_nearby_values():
    chunk = DocumentChunk(
        chunk_id="p31",
        report_id="goldwind",
        text="2024年，公司完成85家风电机组零部件供应商社会责任审核，其中A级83家、B级2家，主要零部件制造商社会责任审核率100%。",
        source_page=31,
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        source_file_hash="hash",
    )

    matches = match_kpi_rows([chunk], ["供应商社会责任审核", "社会责任审核率"], year_columns=["2024"])

    assert matches
    assert matches[0].source_page == 31
    assert "供应商社会责任审核" in matches[0].preview or "社会责任审核率" in matches[0].preview
```

- [ ] **Step 2: 写工伤死亡人数匹配测试**

同文件增加：

```python
def test_match_kpi_rows_matches_ohs_fatality_count_without_rate():
    chunk = DocumentChunk(
        chunk_id="p37",
        report_id="goldwind",
        text="2024年，员工因工死亡人数为1，重大安全事故数为0，职业病发病次数为0，安全培训总学时约为441630小时。",
        source_page=37,
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        source_file_hash="hash",
    )

    matches = match_kpi_rows([chunk], ["员工因工死亡人数", "因工死亡人数"], year_columns=["2024"])

    assert matches
    assert matches[0].source_page == 37
    assert "因工死亡人数" in matches[0].preview
```

- [ ] **Step 3: 运行测试确认失败或确认已覆盖**

Run:

```powershell
cd backend
uv run --no-sync pytest --basetemp ../tmp/pytest-kpi-goldwind tests/tools/test_kpi_row_matcher.py -q
```

Expected: 若新增测试通过，记录为已有能力；若失败，按 Step 4 实现。

- [ ] **Step 4: 实现中文附近数值匹配**

在 `backend/src/tools/kpi_row_matcher.py` 中确保 metric 命中时取前后窗口：

```python
def _match_metric_line(text: str, term: str, year_columns: list[str]) -> tuple[str | None, str | None, str | None] | None:
    index = text.find(term)
    if index < 0:
        return None
    window = text[max(0, index - 80) : index + len(term) + 180]
    year = next((candidate for candidate in year_columns if candidate in window or candidate in text[:index]), None)
    after_term = text[index + len(term) : index + len(term) + 120]
    before_term = text[max(0, index - 80) : index]
    value = _first_numeric_value(after_term) or _first_numeric_value(before_term)
    if value is None:
        return None
    unit = _infer_unit(after_term)
    return unit, value, year
```

并新增：

```python
def _first_numeric_value(text: str) -> str | None:
    match = re.search(r"-?\d[\d,]*(?:\.\d+)?%?", text)
    return match.group(0) if match else None


def _infer_unit(text: str) -> str | None:
    for unit in ("%", "家", "人", "次", "小时", "天", "tCO2e", "吨", "MWh", "kWh"):
        if unit in text[:40]:
            return unit
    return None
```

- [ ] **Step 5: 运行测试确认通过**

Run:

```powershell
cd backend
uv run --no-sync pytest --basetemp ../tmp/pytest-kpi-goldwind tests/tools/test_kpi_row_matcher.py -q
```

Expected: PASS。

---

## Task 4: 增加 Partial Verdict Matrix 边界

**Files:**
- Modify: `backend/src/standards/evidence_ontology.py`
- Modify: `backend/src/standards/evidence_contracts.py`
- Test: `backend/tests/standards/test_evidence_ontology.py`
- Test: `backend/tests/standards/test_evidence_contracts.py`

- [ ] **Step 1: 写反腐败风险评估 partial 测试**

在 `backend/tests/standards/test_evidence_ontology.py` 增加：

```python
def test_anti_corruption_management_mechanism_stays_partial_without_operation_percentage():
    result = evaluate_ontology_verdict(
        semantic_group=SemanticGroup.ANTI_CORRUPTION_RISK,
        facets={RequirementFacet.REQUIRES_COUNT, RequirementFacet.REQUIRES_PERCENTAGE},
        evidence_kinds={EvidenceKind.MANAGEMENT_MECHANISM},
    )

    assert result.verdict == AssessmentVerdict.PARTIALLY_DISCLOSED
    assert result.review_status == ReviewStatus.NEEDS_MANUAL_REVIEW
    assert "运营点总数和百分比" in result.missing_items
```

- [ ] **Step 2: 写供应商社会审核 partial 测试**

同文件增加：

```python
def test_supplier_assessment_audit_count_stays_partial_without_new_supplier_percentage():
    result = evaluate_ontology_verdict(
        semantic_group=SemanticGroup.SUPPLIER_ASSESSMENT,
        facets={RequirementFacet.REQUIRES_PERCENTAGE},
        evidence_kinds={EvidenceKind.KPI_VALUE},
    )

    assert result.verdict == AssessmentVerdict.PARTIALLY_DISCLOSED
    assert result.review_status == ReviewStatus.NEEDS_MANUAL_REVIEW
    assert "新供应商百分比" in result.missing_items
```

- [ ] **Step 3: 写 OHS 死亡人数 partial 测试**

同文件增加：

```python
def test_ohs_fatality_count_stays_partial_without_rate():
    result = evaluate_ontology_verdict(
        semantic_group=SemanticGroup.OHS_KPI,
        facets={RequirementFacet.REQUIRES_COUNT, RequirementFacet.REQUIRES_PERCENTAGE},
        evidence_kinds={EvidenceKind.KPI_VALUE},
    )

    assert result.verdict == AssessmentVerdict.PARTIALLY_DISCLOSED
    assert result.review_status == ReviewStatus.NEEDS_MANUAL_REVIEW
    assert "比率" in result.missing_items
```

- [ ] **Step 4: 写 418 guardrail 测试**

同文件增加：

```python
def test_customer_privacy_complaint_source_breakdown_stays_unknown_for_general_zero_privacy_event():
    result = evaluate_ontology_verdict(
        semantic_group=SemanticGroup.ZERO_EVENT_COMPLIANCE,
        facets={RequirementFacet.REQUIRES_COUNT, RequirementFacet.REQUIRES_COMPLAINT_SOURCE_BREAKDOWN},
        evidence_kinds={EvidenceKind.EXPLICIT_ZERO_STATEMENT},
    )

    assert result.verdict == AssessmentVerdict.UNKNOWN
    assert result.review_status == ReviewStatus.NEEDS_MANUAL_REVIEW
    assert "投诉来源分类" in result.missing_items
```

- [ ] **Step 5: 运行测试确认失败或确认已覆盖**

Run:

```powershell
cd backend
uv run --no-sync pytest --basetemp ../tmp/pytest-ontology-goldwind tests/standards/test_evidence_ontology.py -q
```

Expected: 若新增测试通过，记录为已有能力；若失败，按 Step 6 实现。

- [ ] **Step 6: 实现 semantic group 和 matrix**

在 `SemanticGroup` 增加：

```python
ANTI_CORRUPTION_RISK = "anti_corruption_risk"
```

在 `evaluate_ontology_verdict()` 增加：

```python
if semantic_group is SemanticGroup.ANTI_CORRUPTION_RISK:
    if EvidenceKind.MANAGEMENT_MECHANISM in evidence_kinds:
        return OntologyVerdictResult(
            verdict=AssessmentVerdict.PARTIALLY_DISCLOSED,
            review_status=ReviewStatus.NEEDS_MANUAL_REVIEW,
            rationale="Anti-corruption management evidence is directionally relevant, but it does not disclose the total number and percentage of operations assessed or the significant corruption risks identified.",
            missing_items=("运营点总数和百分比", "重大腐败风险识别结果"),
        )
```

在 supplier / OHS / zero-event 既有分支中增加同等保守规则：

```python
if semantic_group is SemanticGroup.SUPPLIER_ASSESSMENT:
    if RequirementFacet.REQUIRES_PERCENTAGE in facets and EvidenceKind.KPI_VALUE in evidence_kinds:
        return OntologyVerdictResult(
            verdict=AssessmentVerdict.PARTIALLY_DISCLOSED,
            review_status=ReviewStatus.NEEDS_MANUAL_REVIEW,
            rationale="Supplier assessment evidence is directionally relevant, but it does not directly disclose the required new-supplier percentage or denominator.",
            missing_items=("新供应商百分比", "新供应商分母"),
        )
```

- [ ] **Step 7: 给现有 contracts 补 metadata**

在 `backend/src/standards/evidence_contracts.py` 中只补 metadata，不新增 Goldwind 页码：

```python
"GRI 205-1-a": RequirementEvidenceContract(
    requirement_id="GRI 205-1-a",
    semantic_group=SemanticGroup.ANTI_CORRUPTION_RISK,
    facets=(RequirementFacet.REQUIRES_COUNT, RequirementFacet.REQUIRES_PERCENTAGE),
    evidence_kinds=(EvidenceKind.MANAGEMENT_MECHANISM,),
),
```

`GRI 205-1-b` 使用：

```python
semantic_group=SemanticGroup.ANTI_CORRUPTION_RISK,
facets=(RequirementFacet.REQUIRES_IMPACT_TYPE,),
evidence_kinds=(EvidenceKind.MANAGEMENT_MECHANISM,),
```

确认 `GRI 414-1-a`、`GRI 403-9-a-i`、`GRI 418-1-a` 已有或补齐对应 semantic metadata。

- [ ] **Step 8: 运行测试确认通过**

Run:

```powershell
cd backend
uv run --no-sync pytest --basetemp ../tmp/pytest-ontology-goldwind tests/standards/test_evidence_ontology.py tests/standards/test_evidence_contracts.py -q
```

Expected: PASS。

---

## Task 5: 重跑 Goldwind Holdout 并生成 Review Pack

**Files:**
- Read/Write: `tmp/review/holdout_goldwind_2024_first_pass.csv`
- Read/Write: `tmp/review/holdout_goldwind_2024_reviewed.csv`
- Read/Write: `tmp/review/holdout_goldwind_2024_route_improvement.csv`
- Read/Write: `tmp/review/holdout_goldwind_2024_review_pack.csv`
- Create: `tmp/review/holdout_goldwind_2024_evidence_hit_summary.json`

- [ ] **Step 1: 重跑 Goldwind holdout**

Run:

```powershell
cd backend
uv run --no-sync python ../tmp/goldwind_holdout_remediation.py
```

Expected:

- `global_fallback_count=0`
- `max_source_pdf_page <= 52`
- `max_candidate_pdf_page <= 52`
- `false_disclosed_count=0`

- [ ] **Step 2: 重建 route improvement 与 review pack**

Run:

```powershell
cd backend
@'
from pathlib import Path
from src.standards.gri import GRIAdapter
from src.tools.holdout_review_pack import (
    build_route_improvement_rows,
    write_route_improvement_rows,
    build_review_pack_rows,
    write_review_pack_rows,
)

review_dir = Path("../tmp/review")
adapter = GRIAdapter(Path("data/manifests/gri_requirement_checklist.json"))
requirement_texts = {
    requirement.requirement_id: requirement.requirement_text
    for requirement in adapter.load_requirements()
}
route_path = review_dir / "holdout_goldwind_2024_route_improvement.csv"
pack_path = review_dir / "holdout_goldwind_2024_review_pack.csv"
rows = build_route_improvement_rows(
    review_dir / "holdout_goldwind_2024_recall_diagnosis.csv",
    review_dir / "holdout_goldwind_2024_first_pass.csv",
    Path("data/reports/profiles/goldwind_2024.json"),
    requirement_texts=requirement_texts,
)
write_route_improvement_rows(rows, route_path)
pack = build_review_pack_rows(route_path)
write_review_pack_rows(pack, pack_path)
print(len(rows), len(pack))
'@ | uv run --no-sync python -
```

Expected: 输出 `5 5`。

- [ ] **Step 3: 生成 evidence hit summary**

Run:

```powershell
cd backend
@'
import csv
import json
from collections import Counter
from pathlib import Path

review_dir = Path("../tmp/review")
routes = list(csv.DictReader((review_dir / "holdout_goldwind_2024_route_improvement.csv").open(encoding="utf-8-sig", newline="")))
first_rows = list(csv.DictReader((review_dir / "holdout_goldwind_2024_first_pass.csv").open(encoding="utf-8-sig", newline="")))
target_ids = {"GRI 205-1-a", "GRI 205-1-b", "GRI 414-1-a", "GRI 403-9-a-i", "GRI 418-1-a"}
targets = [row for row in first_rows if row["requirement_id"] in target_ids]
summary = {
    "target_requirement_count": len(target_ids),
    "target_rows": len(targets),
    "target_verdict_counts": dict(Counter(row["verdict"] for row in targets)),
    "route_status_counts": dict(Counter(row["route_status"] for row in routes)),
    "source_pages_by_requirement": {
        rid: sorted({int(row["source_pdf_page"]) for row in targets if row["requirement_id"] == rid and row["source_pdf_page"]})
        for rid in sorted(target_ids)
    },
    "stop_at": "manual_review",
}
(review_dir / "holdout_goldwind_2024_evidence_hit_summary.json").write_text(
    json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
print(json.dumps(summary, ensure_ascii=False, indent=2))
'@ | uv run --no-sync python -
```

Expected:

- `target_requirement_count=5`
- `stop_at=manual_review`

- [ ] **Step 4: 跑 Goldwind audit**

Run:

```powershell
cd backend
@'
import json
from pathlib import Path
from src.tools.review_csv_audit import audit_review_csv

review_dir = Path("../tmp/review")
first = audit_review_csv(review_dir / "holdout_goldwind_2024_first_pass.csv", report_total_pages=52)
reviewed = audit_review_csv(review_dir / "holdout_goldwind_2024_reviewed.csv", report_total_pages=52)
audit = {
    "first_pass": {"ok": first.ok, "error_count": len(first.errors), "errors": first.errors},
    "reviewed": {"ok": reviewed.ok, "error_count": len(reviewed.errors), "errors": reviewed.errors},
}
(review_dir / "holdout_goldwind_2024_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(audit, ensure_ascii=False, indent=2))
'@ | uv run --no-sync python -
```

Expected: `first_pass.ok=true` 且 `reviewed.ok=true`。

---

## Task 6: Focused Tests 与 Envision 577 Gate

**Files:**
- Read: `tmp/review/current_577_review_after_profile_routing.csv`
- Write: `tmp/review/current_577_review_regenerated.csv`
- Write: `tmp/review/current_577_review_regenerated_audit.json`
- Write: `tmp/review/current_577_review_regeneration_diff_summary.json`
- Modify: `docs/DEVELOPMENT.md`

- [ ] **Step 1: 跑 focused tests**

Run:

```powershell
cd backend
uv run --no-sync pytest --basetemp ../tmp/pytest-goldwind-evidence-hit tests/tools/test_retrieval.py tests/tools/test_kpi_row_matcher.py tests/tools/test_evidence.py tests/tools/test_evidence_routing.py tests/tools/test_holdout_review_pack.py tests/standards/test_evidence_ontology.py tests/standards/test_evidence_contracts.py -q
```

Expected: PASS。

- [ ] **Step 2: 跑 Envision 577 regeneration gate**

Run:

```powershell
cd backend
uv run --no-sync python -m src.tools.regenerate_review_csv `
  --report-id envision_2024 `
  --pdf "data/reports/Envision Energy 2024-zh.pdf" `
  --profile data/reports/profiles/envision_2024.json `
  --output ../tmp/review/current_577_review_regenerated.csv `
  --baseline ../tmp/review/current_577_review_after_profile_routing.csv `
  --audit-output ../tmp/review/current_577_review_regenerated_audit.json `
  --diff-summary-output ../tmp/review/current_577_review_regeneration_diff_summary.json `
  --report-total-pages 78
```

Expected:

- unique requirements = 577
- compilation-like requirements = 0
- audit ok = true
- `after_rules_delta_disclosed=0`
- `after_rules_delta_partial=0`
- `after_rules_delta_unknown=0`
- strict source/evidence diff = 0

- [ ] **Step 3: 扫描 docs 绝对路径**

Run:

```powershell
$matches = rg '[A-Za-z]:\\' docs README.md 2>$null; if ($LASTEXITCODE -eq 0) { $matches; exit 1 } else { 'no absolute paths found' }
```

Expected: `no absolute paths found`。

- [ ] **Step 4: 更新开发记录**

在 `docs/DEVELOPMENT.md` 增加记录：

```markdown
- Goldwind evidence hit 改造完成：针对 `GRI 205-1-a`、`GRI 205-1-b`、`GRI 414-1-a`、`GRI 403-9-a-i`、`GRI 418-1-a` 生成新一轮 `tmp/review/holdout_goldwind_2024_review_pack.csv`。本轮目标是验证 profile route handoff、bounded retrieval、KPI/段落行级匹配和 partial matrix 边界；`GRI 418-1-a` 保持 unknown guardrail。Goldwind audit 通过，未出现 `global_fallback`、页码越界或 false disclosed；当前停止点为人工复核 review pack。Envision 577 regeneration gate 通过，577 requirement 数量不变，verdict/review/source/evidence/page/quality/OCR-VLM 字段无回退。
```

---

## 人工复核交付

执行完成后暂停，并请人工复核：

- `tmp/review/holdout_goldwind_2024_review_pack.csv`
- `tmp/review/holdout_goldwind_2024_evidence_hit_summary.json`

人工复核字段：

- `manual_label`
- `correct_source_pdf_pages`
- `suggested_verdict`
- `review_note`

复核重点：

- `GRI 205-1-a` 与 `GRI 205-1-b` 是否命中 PDF 第 21 页管理机制，并保持 partial。
- `GRI 414-1-a` 是否命中 PDF 第 31-32 页供应商社会责任审核证据，并保持 partial。
- `GRI 403-9-a-i` 是否命中 PDF 第 37 或 47 页工伤死亡人数证据，并保持 partial。
- `GRI 418-1-a` 是否保持 unknown，且没有把一般隐私/数据泄露零事件作为客户隐私投诉证据。
- 是否出现新的 wrong source page、false disclosed、preview 不可读。

## 验收标准

- Goldwind `global_fallback_count=0`。
- Goldwind `source_pdf_page` 和 `candidate_pdf_pages` 均不超过 52。
- Goldwind GRI index PDF 50/51 未作为 `substantive evidence`。
- `GRI 418-1-a` 保持 `unknown + needs_manual_review`。
- `GRI 205-1-a`、`GRI 205-1-b`、`GRI 414-1-a`、`GRI 403-9-a-i` 不自动升 `disclosed`。
- `tmp/review/holdout_goldwind_2024_review_pack.csv` 已生成且包含 5 个目标 requirement。
- `tmp/review/holdout_goldwind_2024_evidence_hit_summary.json` 已生成。
- Focused tests 通过。
- Envision 577 regeneration gate 通过且 strict diff 为 0。
- docs 不包含本机绝对路径。
- 最终停在人工作业点，不自动进入下一阶段。

## 执行建议

建议 inline 执行。原因是本计划会反复刷新同一批 Goldwind holdout 临时产物和 Envision 577 gate 产物，并且禁止新增 Goldwind per-ID contract；并行执行会增加状态冲突和误判风险。
