# Evidence Contract 与 KPI 证据审计 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将当前分散的 GRI evidence 规则升级为可审计的 leaf-level evidence contract，并为 KPI 表、omission note、index statement 和 review CSV 建立硬性校验。

**Architecture:** 先增加 review CSV 自查工具，把现有人工复核硬规则固化成可重复执行的 gate；再抽出 leaf requirement 级 evidence contract，逐步替代 `DisclosureAgent` 与 workflow 中不断增长的硬编码映射。KPI 表先做轻量行级 anchor，不更换 PDF parser，不引入 OCR/VLM 实调用。

**Tech Stack:** Python 3.11、pytest、Pydantic v2、现有 FastAPI 后端、pdfplumber 抽取结果、当前 GRI checklist/pack、CSV review artifact。

---

## 1. 背景

截至 `tmp/review/current_350_review_after_rules.csv`，系统已经能处理前 350 条 GRI requirement，并且已固化大量人工复核规则。当前主要问题不在 PDF 文本抽取本身，而在以下几处：

- 证据规则分散在 `backend/src/standards/gri.py`、`backend/src/workflows/single_report_workflow.py`、`backend/src/agents/disclosure_agent.py`。
- KPI 表页 PDF 第 63、65、68 页虽然能作为证据，但 preview 仍以关键词窗口为主，未稳定定位目标 KPI 行。
- `omission_note` 与 `index_statement` 已有基础语义，但触发词和类型抽象还不完整。
- 每次生成 review CSV 后的硬检查主要靠临时脚本和人工口径，没有固定为可运行工具。
- 少数质量标记仍有缺口，例如 PDF 第 68 页 `GRI 205-3-b` 缺 `complex_table`。

本计划的目标是提高可审计准确率，不追求提高 `disclosed` 数量。

## 2. 不做范围

- 不更换 PDF parser。
- 不启用真实 OCR、Docling 或 VLM 调用。
- 不新增 LLM 判断。
- 不一次性迁移全部 661 条 requirement 的完整 contract。
- 不改变现有数据库 schema，除非后续单独评估字段升列。
- 不改前端 UI。

## 3. 影响文件

- Create: `backend/src/tools/review_csv_audit.py`
  - 读取 review CSV，执行 fallback、页码、review_status、omission、KPI quality flag、OCR/VLM 风险等硬检查。
- Test: `backend/tests/tools/test_review_csv_audit.py`
  - 覆盖自查规则，防止 CSV gate 回退。
- Create: `backend/src/standards/evidence_contracts.py`
  - 定义 leaf-level contract 数据结构和首批 302/303/305/205 规则。
- Test: `backend/tests/standards/test_evidence_contracts.py`
  - 覆盖 allowed pages、forbidden pages、KPI table pages、unknown-only 子项。
- Modify: `backend/src/agents/disclosure_agent.py`
  - 从 contract 读取 allowed pages、unknown-only requirements、quality flags 和 verdict 规则。
- Modify: `backend/src/workflows/single_report_workflow.py`
  - 从 contract 读取 candidate page overrides，减少 workflow 内硬编码。
- Modify: `backend/src/tools/evidence.py`
  - 增加 KPI 行级 preview helper。
- Test: `backend/tests/tools/test_retrieval.py`
  - 或新增 `backend/tests/tools/test_evidence.py`，覆盖 KPI 行级 preview。
- Modify: `backend/src/standards/gri.py`
  - 保留中文关键词入口，后续只承载关键词，不再承载充分性规则。
- Modify: `docs/DEVELOPMENT.md`
  - 记录新增审计命令和本轮设计边界。

## 4. 设计口径

### 4.1 CSV hard gates

review CSV 自查必须能发现以下问题：

- `global_fallback` 证据存在。
- `page_label` 出现 `?` 乱码。
- `source_pdf_page` 或 `candidate_pdf_pages` 超过报告总页数。
- `omission_note` 被判为 `disclosed` 或 `partially_disclosed`。
- `disclosed` 的 `review_status` 不是 `not_required`。
- `partially_disclosed` 或 `unknown` 的 `review_status` 不是 `needs_manual_review`。
- PDF 第 63、65、68 页作为 KPI evidence 时缺少 `complex_table`。
- PDF 第 77 页鉴证 evidence 缺少 OCR/VLM 风险标记。
- GRI 305 evidence 使用 PDF 第 3 页。

### 4.2 leaf-level evidence contract

首批 contract 不覆盖全部 GRI，只覆盖已反复出问题的 topic-specific 子集：

- GRI 205：PDF 第 68 页治理 KPI。
- GRI 302：PDF 第 63 页能源 KPI，PDF 第 23 页节能案例。
- GRI 303：PDF 第 22、25、63 页水资源与废水。
- GRI 305：PDF 第 20、63、64 页温室气体 KPI 与核算方法。

contract 字段建议：

```python
from dataclasses import dataclass, field
from src.domain.enums import AssessmentVerdict, ReviewStatus


@dataclass(frozen=True)
class RequirementEvidenceContract:
    requirement_id: str
    allowed_pages: tuple[int, ...] = ()
    forbidden_pages: tuple[int, ...] = ()
    candidate_pages: tuple[int, ...] | None = None
    kpi_table_pages: tuple[int, ...] = ()
    verdict: AssessmentVerdict | None = None
    review_status: ReviewStatus | None = None
    missing_items: tuple[str, ...] = ()
    rationale: str | None = None
    evidence_type: str = "substantive"
    required_preview_terms: tuple[str, ...] = ()
```

### 4.3 KPI 行级 preview

先做轻量规则，不做完整表格结构还原：

- 对 PDF 第 63、65、68 页，从目标 KPI 名附近截取窗口。
- 如果目标 KPI 名在同一页多次出现，优先选择同时包含数值、单位和年份的窗口。
- 不把相邻 KPI 行作为充分证据。

示例目标：

```text
GRI 305-2-a -> 范围二 - 基于位置(tCO2e)
GRI 305-2-b -> 范围二 - 基于市场(tCO2e)
GRI 205-3-b -> 员工因腐败被开除或受到处分的事件数量（件）
GRI 303-3-a-i -> 地表水总量
GRI 302-1-e -> 能源使用总量
```

### 4.4 omission_note 与 index_statement

`omission_note` 触发词扩展为：

```text
因商业保密限制从略披露
因不适用而从略披露
不适用从略披露
confidentiality constraints
not applicable
```

输出固定为：

```text
evidence_type=omission_note
verdict=unknown
review_status=needs_manual_review
```

`index_statement` 保留为独立 evidence type，优先覆盖：

- `2-4` 无信息重述。
- `2-27` 报告期内未发生违法违规事件。

## 5. 任务拆分

### Task 1: 增加 review CSV 自查工具

**Files:**
- Create: `backend/src/tools/review_csv_audit.py`
- Create: `backend/tests/tools/test_review_csv_audit.py`

- [ ] **Step 1: 写失败测试，覆盖 CSV hard gate**

在 `backend/tests/tools/test_review_csv_audit.py` 写入：

```python
import csv
from pathlib import Path

from src.tools.review_csv_audit import audit_review_csv


def write_csv(path: Path, rows: list[dict]) -> None:
    fieldnames = [
        "requirement_id",
        "verdict",
        "review_status",
        "retrieval_strategy",
        "evidence_type",
        "source_pdf_page",
        "source_report_page",
        "page_label",
        "candidate_pdf_pages",
        "quality_flags",
        "requires_ocr",
        "needs_ocr_or_vlm",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_review_csv_audit_reports_hard_gate_failures(tmp_path):
    path = tmp_path / "review.csv"
    write_csv(
        path,
        [
            {
                "requirement_id": "GRI 305-2-a",
                "verdict": "disclosed",
                "review_status": "not_required",
                "retrieval_strategy": "index_page_bounded",
                "evidence_type": "substantive",
                "source_pdf_page": "3",
                "source_report_page": "2",
                "page_label": "PDF 第 3 页 / 报告页 2",
                "candidate_pdf_pages": "[20, 63]",
                "quality_flags": "[\"digital_text\"]",
                "requires_ocr": "False",
                "needs_ocr_or_vlm": "False",
            },
            {
                "requirement_id": "GRI 304-4-a",
                "verdict": "partially_disclosed",
                "review_status": "needs_manual_review",
                "retrieval_strategy": "index_page_bounded",
                "evidence_type": "omission_note",
                "source_pdf_page": "74",
                "source_report_page": "73",
                "page_label": "PDF 第 74 页 / 报告页 73",
                "candidate_pdf_pages": "[74]",
                "quality_flags": "[\"digital_text\"]",
                "requires_ocr": "False",
                "needs_ocr_or_vlm": "False",
            },
            {
                "requirement_id": "GRI 205-3-b",
                "verdict": "disclosed",
                "review_status": "not_required",
                "retrieval_strategy": "index_page_bounded",
                "evidence_type": "substantive",
                "source_pdf_page": "68",
                "source_report_page": "67",
                "page_label": "PDF 第 68 页 / 报告页 67",
                "candidate_pdf_pages": "[68]",
                "quality_flags": "[\"digital_text\"]",
                "requires_ocr": "False",
                "needs_ocr_or_vlm": "False",
            },
        ],
    )

    result = audit_review_csv(path, report_total_pages=78)

    assert "GRI 305-2-a uses forbidden PDF page 3" in result.errors
    assert "GRI 304-4-a omission_note cannot be partially_disclosed" in result.errors
    assert "GRI 205-3-b KPI page 68 missing complex_table" in result.errors
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/tools/test_review_csv_audit.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'src.tools.review_csv_audit'
```

- [ ] **Step 3: 实现最小自查工具**

创建 `backend/src/tools/review_csv_audit.py`：

```python
import csv
import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ReviewCsvAuditResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _loads_list(raw: str) -> list:
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return value if isinstance(value, list) else []


def audit_review_csv(path: str | Path, report_total_pages: int) -> ReviewCsvAuditResult:
    result = ReviewCsvAuditResult()
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    for row in rows:
        requirement_id = row.get("requirement_id", "")
        verdict = row.get("verdict", "")
        review_status = row.get("review_status", "")
        retrieval_strategy = row.get("retrieval_strategy", "")
        evidence_type = row.get("evidence_type", "")
        source_pdf_page = row.get("source_pdf_page", "")
        page_label = row.get("page_label", "")
        quality_flags = _loads_list(row.get("quality_flags", ""))
        candidate_pdf_pages = _loads_list(row.get("candidate_pdf_pages", ""))

        if retrieval_strategy == "global_fallback":
            result.errors.append(f"{requirement_id} uses global_fallback")

        if "?" in page_label:
            result.errors.append(f"{requirement_id} page_label contains '?'")

        for candidate_page in candidate_pdf_pages:
            if isinstance(candidate_page, int) and candidate_page > report_total_pages:
                result.errors.append(f"{requirement_id} candidate page {candidate_page} exceeds report total pages")

        if source_pdf_page:
            source_page_int = int(source_pdf_page)
            if source_page_int > report_total_pages:
                result.errors.append(f"{requirement_id} source page {source_page_int} exceeds report total pages")
            if requirement_id.startswith("GRI 305") and source_page_int == 3:
                result.errors.append(f"{requirement_id} uses forbidden PDF page 3")
            if source_page_int in {63, 65, 68} and "complex_table" not in quality_flags:
                result.errors.append(f"{requirement_id} KPI page {source_page_int} missing complex_table")
            if source_page_int == 77:
                requires_ocr = row.get("requires_ocr", "").lower() == "true"
                needs_ocr_or_vlm = row.get("needs_ocr_or_vlm", "").lower() == "true"
                if not (requires_ocr or needs_ocr_or_vlm):
                    result.errors.append(f"{requirement_id} assurance page 77 missing OCR/VLM risk flag")

        if evidence_type == "omission_note" and verdict != "unknown":
            result.errors.append(f"{requirement_id} omission_note cannot be {verdict}")

        if verdict == "disclosed" and review_status != "not_required":
            result.errors.append(f"{requirement_id} disclosed must be not_required")
        if verdict in {"partially_disclosed", "unknown"} and review_status != "needs_manual_review":
            result.errors.append(f"{requirement_id} {verdict} must be needs_manual_review")

    return result
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/tools/test_review_csv_audit.py -q
```

Expected:

```text
1 passed
```

- [ ] **Step 5: 用真实 CSV 跑自查**

Run:

```powershell
cd backend
@'
from src.tools.review_csv_audit import audit_review_csv
result = audit_review_csv("../tmp/review/current_350_review_after_rules.csv", report_total_pages=78)
print("ok=", result.ok)
print("errors=", result.errors)
print("warnings=", result.warnings)
'@ | uv run --no-sync python -
```

Expected before Task 2:

```text
ok= False
errors= ['GRI 205-3-b KPI page 68 missing complex_table']
```

### Task 2: 修复 KPI 页 quality flag gate

**Files:**
- Modify: `backend/src/agents/disclosure_agent.py`
- Test: `backend/tests/agents/test_disclosure_agent.py`
- Test: `backend/tests/tools/test_review_csv_audit.py`

- [ ] **Step 1: 写失败测试，覆盖 PDF 第 68 页所有治理 KPI evidence**

在 `backend/tests/agents/test_disclosure_agent.py` 增加：

```python
def test_disclosure_agent_marks_all_governance_kpi_page_68_as_complex_table():
    task = DisclosureTask(
        task_id="task-205-3-b",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI 205",
        standard_version="2016",
        disclosure_id="GRI 205-3",
        requirement_id="GRI 205-3-b",
        requirement_text="total number of confirmed incidents in which employees were dismissed or disciplined for corruption.",
        keywords=["员工因腐败被开除或受到处分的事件数量"],
        candidate_pages=[68],
        candidate_page_source="gri_report_index+requirement_supplement",
        index_page=73,
    )
    chunk = DocumentChunk(
        chunk_id="chunk-205-3-b-68",
        report_id="report-1",
        text="员工因腐败被开除或受到处分的事件数量（件） 2 2 1",
        source_page=68,
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        source_file_hash="hash-1",
    )

    result = DisclosureAgent().analyze(task, [chunk], confirm_llm=False)

    assert result.assessment.verdict is AssessmentVerdict.DISCLOSED
    assert result.assessment.review_status is ReviewStatus.NOT_REQUIRED
    assert PageQualityFlag.COMPLEX_TABLE in result.assessment.evidence[0].quality_flags
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/agents/test_disclosure_agent.py::test_disclosure_agent_marks_all_governance_kpi_page_68_as_complex_table -q
```

Expected:

```text
AssertionError: PageQualityFlag.COMPLEX_TABLE not in [...]
```

- [ ] **Step 3: 修改质量标记规则**

在 `backend/src/agents/disclosure_agent.py` 的 `_mark_requirement_specific_quality_flags()` 中，将 PDF 第 68 页规则从排除 `GRI 205-3-b` 改为全部治理 KPI：

```python
is_complex_table_page = (
    (task.disclosure_id == "GRI 2-7" and item.source_page == 65)
    or (
        task.disclosure_id in {"GRI 205-1", "GRI 205-2", "GRI 205-3", "GRI 206-1"}
        and item.source_page == 68
    )
    or (task.disclosure_id.startswith("GRI 302") and item.source_page == 63)
    or (task.disclosure_id.startswith("GRI 303") and item.source_page == 63)
    or (task.disclosure_id.startswith("GRI 305") and item.source_page == 63)
)
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/agents/test_disclosure_agent.py::test_disclosure_agent_marks_all_governance_kpi_page_68_as_complex_table -q
```

Expected:

```text
1 passed
```

- [ ] **Step 5: 重新生成 `current_350_review_after_rules.csv` 并跑 audit**

Run 现有生成命令，输出到：

```text
tmp/review/current_350_review_after_rules.csv
```

然后运行：

```powershell
cd backend
@'
from src.tools.review_csv_audit import audit_review_csv
result = audit_review_csv("../tmp/review/current_350_review_after_rules.csv", report_total_pages=78)
print("ok=", result.ok)
print("errors=", result.errors)
'@ | uv run --no-sync python -
```

Expected:

```text
ok= True
errors= []
```

### Task 3: 抽出首批 leaf-level evidence contract

**Files:**
- Create: `backend/src/standards/evidence_contracts.py`
- Create: `backend/tests/standards/test_evidence_contracts.py`
- Modify: `backend/src/workflows/single_report_workflow.py`
- Modify: `backend/src/agents/disclosure_agent.py`

- [ ] **Step 1: 写 contract 查询测试**

创建 `backend/tests/standards/test_evidence_contracts.py`：

```python
from src.domain.enums import AssessmentVerdict, ReviewStatus
from src.standards.evidence_contracts import get_requirement_contract


def test_evidence_contract_returns_305_2_allowed_and_forbidden_pages():
    contract = get_requirement_contract("GRI 305-2-a")

    assert contract.requirement_id == "GRI 305-2-a"
    assert contract.allowed_pages == (20, 63)
    assert contract.forbidden_pages == (3,)
    assert contract.candidate_pages == (20, 63)
    assert contract.kpi_table_pages == (63,)
    assert contract.verdict is AssessmentVerdict.DISCLOSED
    assert contract.review_status is ReviewStatus.NOT_REQUIRED


def test_evidence_contract_returns_unknown_only_305_2_c():
    contract = get_requirement_contract("GRI 305-2-c")

    assert contract.requirement_id == "GRI 305-2-c"
    assert contract.allowed_pages == ()
    assert contract.candidate_pages == ()
    assert contract.verdict is AssessmentVerdict.UNKNOWN
    assert contract.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/standards/test_evidence_contracts.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'src.standards.evidence_contracts'
```

- [ ] **Step 3: 创建 evidence contract 模块**

创建 `backend/src/standards/evidence_contracts.py`：

```python
from dataclasses import dataclass

from src.domain.enums import AssessmentVerdict, ReviewStatus


@dataclass(frozen=True)
class RequirementEvidenceContract:
    requirement_id: str
    allowed_pages: tuple[int, ...] = ()
    forbidden_pages: tuple[int, ...] = ()
    candidate_pages: tuple[int, ...] | None = None
    kpi_table_pages: tuple[int, ...] = ()
    verdict: AssessmentVerdict | None = None
    review_status: ReviewStatus | None = None
    rationale: str | None = None
    missing_items: tuple[str, ...] = ()


_CONTRACTS: dict[str, RequirementEvidenceContract] = {
    "GRI 305-1-a": RequirementEvidenceContract(
        requirement_id="GRI 305-1-a",
        allowed_pages=(20, 63),
        forbidden_pages=(3,),
        candidate_pages=(20, 63),
        kpi_table_pages=(63,),
        verdict=AssessmentVerdict.DISCLOSED,
        review_status=ReviewStatus.NOT_REQUIRED,
        rationale="Bounded evidence directly discloses Scope 1 GHG emissions.",
    ),
    "GRI 305-1-e": RequirementEvidenceContract(
        requirement_id="GRI 305-1-e",
        allowed_pages=(64,),
        candidate_pages=(64,),
        verdict=AssessmentVerdict.PARTIALLY_DISCLOSED,
        review_status=ReviewStatus.NEEDS_MANUAL_REVIEW,
        rationale="Bounded evidence describes GHG emission factors and GWP sources, but requires manual sufficiency review.",
        missing_items=("温室气体种类", "完整排放因子来源", "完整 GWP 来源"),
    ),
    "GRI 305-1-g": RequirementEvidenceContract(
        requirement_id="GRI 305-1-g",
        allowed_pages=(64,),
        candidate_pages=(64,),
        verdict=AssessmentVerdict.PARTIALLY_DISCLOSED,
        review_status=ReviewStatus.NEEDS_MANUAL_REVIEW,
        rationale="Bounded evidence describes GHG calculation methods or standards, but does not fully establish all methodology details.",
        missing_items=("完整核算标准", "完整方法说明"),
    ),
    "GRI 305-2-a": RequirementEvidenceContract(
        requirement_id="GRI 305-2-a",
        allowed_pages=(20, 63),
        forbidden_pages=(3,),
        candidate_pages=(20, 63),
        kpi_table_pages=(63,),
        verdict=AssessmentVerdict.DISCLOSED,
        review_status=ReviewStatus.NOT_REQUIRED,
        rationale="Bounded evidence directly discloses location-based Scope 2 GHG emissions.",
    ),
    "GRI 305-2-b": RequirementEvidenceContract(
        requirement_id="GRI 305-2-b",
        allowed_pages=(20, 63),
        forbidden_pages=(3,),
        candidate_pages=(20, 63),
        kpi_table_pages=(63,),
        verdict=AssessmentVerdict.DISCLOSED,
        review_status=ReviewStatus.NOT_REQUIRED,
        rationale="Bounded evidence directly discloses market-based Scope 2 GHG emissions.",
    ),
    "GRI 305-2-c": RequirementEvidenceContract(
        requirement_id="GRI 305-2-c",
        candidate_pages=(),
        verdict=AssessmentVerdict.UNKNOWN,
        review_status=ReviewStatus.NEEDS_MANUAL_REVIEW,
        rationale="The report does not explicitly list gases included in Scope 2 calculation.",
        missing_items=("温室气体种类",),
    ),
    "GRI 305-2-d": RequirementEvidenceContract(
        requirement_id="GRI 305-2-d",
        candidate_pages=(),
        verdict=AssessmentVerdict.UNKNOWN,
        review_status=ReviewStatus.NEEDS_MANUAL_REVIEW,
        rationale="The report does not disclose Scope 2 base year and rationale.",
        missing_items=("基准年", "选择基准年的理由"),
    ),
    "GRI 305-2-d-i": RequirementEvidenceContract(
        requirement_id="GRI 305-2-d-i",
        candidate_pages=(),
        verdict=AssessmentVerdict.UNKNOWN,
        review_status=ReviewStatus.NEEDS_MANUAL_REVIEW,
        rationale="The report does not disclose Scope 2 base year emissions.",
        missing_items=("基准年排放量",),
    ),
}


def get_requirement_contract(requirement_id: str) -> RequirementEvidenceContract | None:
    return _CONTRACTS.get(requirement_id)
```

- [ ] **Step 4: 运行 contract 测试确认通过**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/standards/test_evidence_contracts.py -q
```

Expected:

```text
2 passed
```

- [ ] **Step 5: 在 workflow 中读取 contract candidate pages**

在 `backend/src/workflows/single_report_workflow.py` 引入：

```python
from src.standards.evidence_contracts import get_requirement_contract
```

在 `_candidate_page_overrides()` 开头增加：

```python
        contract = get_requirement_contract(task.requirement_id)
        if contract is not None and contract.candidate_pages is not None:
            return list(contract.candidate_pages)
```

- [ ] **Step 6: 在 agent 中读取 contract allowed pages 与 verdict**

在 `backend/src/agents/disclosure_agent.py` 引入：

```python
from src.standards.evidence_contracts import get_requirement_contract
```

在 `_filter_requirement_specific_pages()` 中，优先使用 contract：

```python
        contract = get_requirement_contract(task.requirement_id)
        if contract is not None:
            if contract.verdict is AssessmentVerdict.UNKNOWN and not contract.allowed_pages:
                return []
            evidence = [
                item
                for item in evidence
                if item.source_page not in contract.forbidden_pages
            ]
            if contract.allowed_pages and task.candidate_pages:
                return [item for item in evidence if item.source_page in contract.allowed_pages]
```

在 `_classify_rule_based()` 中，`omission_note` 判断之后增加：

```python
        contract = get_requirement_contract(task.requirement_id)
        if contract is not None and contract.verdict is not None:
            return (
                contract.verdict,
                contract.rationale,
                list(contract.missing_items),
            )
```

在 `analyze()` 的 `disclosed_not_required_overrides` 后续改造为读取 contract：

```python
        contract = get_requirement_contract(task.requirement_id)
        if (
            contract is not None
            and contract.review_status is ReviewStatus.NOT_REQUIRED
            and assessment.verdict is AssessmentVerdict.DISCLOSED
        ):
            assessment.review_status = ReviewStatus.NOT_REQUIRED
```

- [ ] **Step 7: 跑现有 305 测试确认行为不变**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/agents/test_disclosure_agent.py::test_disclosure_agent_handles_305_1_scope_1_and_method_rules tests/agents/test_disclosure_agent.py::test_disclosure_agent_replaces_invalid_305_2_page_3_with_scope_2_kpi_pages tests/agents/test_disclosure_agent.py::test_disclosure_agent_keeps_unreported_305_1_and_305_2_subitems_unknown tests/workflows/test_single_report_workflow.py::test_single_report_workflow_supplements_candidate_pages_for_ghg_350_rules -q
```

Expected:

```text
4 passed
```

### Task 4: 增加 KPI 行级 preview helper

**Files:**
- Modify: `backend/src/tools/evidence.py`
- Test: `backend/tests/tools/test_retrieval.py` 或 `backend/tests/tools/test_evidence.py`
- Modify: `backend/src/agents/disclosure_agent.py`

- [ ] **Step 1: 写失败测试，目标 KPI 行优先**

在 `backend/tests/tools/test_evidence.py` 创建：

```python
from src.tools.evidence import build_kpi_evidence_preview


def test_build_kpi_evidence_preview_prefers_target_metric_row():
    text = (
        "总耗水量(t) 277,323.60 177,280.10 69,292.00 "
        "范围一(tCO2e) 4,728.96 4,251.21 3,757.00 "
        "范围二 - 基于市场(tCO2e) 2,359.23 2,114.54 883.00 "
        "污染物排放总量 "
        "范围二 - 基于位置(tCO2e) 57,897.05 42,929.76 19,524.00 "
        "化学需氧量(kg) 11,973.00 31,053.57 20,558.83"
    )

    preview = build_kpi_evidence_preview(text, ["范围二 - 基于位置"])

    assert "范围二 - 基于位置(tCO2e) 57,897.05" in preview
    assert "总耗水量" not in preview
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/tools/test_evidence.py -q
```

Expected:

```text
ImportError: cannot import name 'build_kpi_evidence_preview'
```

- [ ] **Step 3: 实现 KPI preview helper**

在 `backend/src/tools/evidence.py` 增加：

```python
def build_kpi_evidence_preview(text: str, metric_terms: list[str], window_before: int = 20, window_after: int = 120) -> str:
    normalized = " ".join(text.split())
    if not normalized:
        return ""

    lower = normalized.lower()
    candidates: list[str] = []
    for term in metric_terms:
        term_lower = term.strip().lower()
        if not term_lower:
            continue
        index = lower.find(term_lower)
        if index < 0:
            continue
        start = max(0, index - window_before)
        end = min(len(normalized), index + len(term) + window_after)
        preview = normalized[start:end].strip()
        if start > 0:
            preview = f"...{preview}"
        if end < len(normalized):
            preview = f"{preview}..."
        candidates.append(preview)

    if not candidates:
        return build_evidence_preview(normalized, metric_terms)

    return max(candidates, key=lambda candidate: (sum(char.isdigit() for char in candidate), len(candidate)))
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/tools/test_evidence.py -q
```

Expected:

```text
1 passed
```

- [ ] **Step 5: 在 agent 中对 KPI 页应用 preview helper**

在 `backend/src/agents/disclosure_agent.py` 引入：

```python
from src.tools.evidence import build_kpi_evidence_preview
```

在 `_mark_requirement_specific_quality_flags()` 中，给 PDF 第 63、65、68 页 evidence 追加：

```python
            if is_complex_table_page:
                item.evidence_preview = build_kpi_evidence_preview(item.source_text, task.keywords)
```

- [ ] **Step 6: 用 305 preview 回归测试确认行级 anchor 改善**

在 `backend/tests/agents/test_disclosure_agent.py` 增加断言：

```python
assert "范围二" in result.assessment.evidence[-1].evidence_preview
assert "总耗水量" not in result.assessment.evidence[-1].evidence_preview
```

Run:

```powershell
cd backend
uv run --no-sync pytest tests/agents/test_disclosure_agent.py::test_disclosure_agent_replaces_invalid_305_2_page_3_with_scope_2_kpi_pages -q
```

Expected:

```text
1 passed
```

### Task 5: 扩展 omission_note 与 index_statement 语义

**Files:**
- Modify: `backend/src/agents/disclosure_agent.py`
- Test: `backend/tests/agents/test_disclosure_agent.py`

- [ ] **Step 1: 写 omission 触发词测试**

在 `backend/tests/agents/test_disclosure_agent.py` 增加：

```python
def test_disclosure_agent_marks_english_and_short_omission_terms():
    cases = [
        ("GRI 304-4-a", "304-4 Species affected not applicable", "not_applicable"),
        ("GRI 201-1-a", "201-1 Direct economic value generated confidentiality constraints", "confidentiality"),
        ("GRI 304-4-a", "304-4 受运营影响的栖息地中已被列入 不适用从略披露", "not_applicable"),
    ]
    for requirement_id, text, reason in cases:
        disclosure_id = "GRI " + requirement_id.removeprefix("GRI ").rsplit("-", 1)[0]
        task = DisclosureTask(
            task_id=f"task-{requirement_id}",
            run_id="run-1",
            report_id="report-1",
            standard_id=disclosure_id.split("-")[0],
            standard_version="2021",
            disclosure_id=disclosure_id,
            requirement_id=requirement_id,
            requirement_text="omitted disclosure.",
            keywords=["从略披露", "not applicable", "confidentiality"],
            candidate_pages=[74],
            candidate_page_source="gri_report_index_omission_note",
            index_page=74,
        )
        chunk = DocumentChunk(
            chunk_id=f"chunk-{requirement_id}",
            report_id="report-1",
            text=text,
            source_page=74,
            source_method=EvidenceSourceMethod.PDFPLUMBER,
            source_file_hash="hash-1",
        )

        result = DisclosureAgent().analyze(task, [chunk], confirm_llm=False)

        assert result.assessment.verdict is AssessmentVerdict.UNKNOWN
        assert result.assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
        assert result.assessment.evidence[0].metadata["evidence_type"] == "omission_note"
        assert result.assessment.evidence[0].metadata["omission_reason"] == reason
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/agents/test_disclosure_agent.py::test_disclosure_agent_marks_english_and_short_omission_terms -q
```

Expected:

```text
AssertionError or KeyError for omission_reason
```

- [ ] **Step 3: 扩展 omission 识别**

在 `_mark_omission_note_evidence()` 中使用大小写归一化：

```python
        omission_terms = (
            "从略披露",
            "因商业保密限制从略披露",
            "因不适用而从略披露",
            "不适用从略披露",
            "confidentiality constraints",
            "not applicable",
        )
```

并增加原因判断：

```python
                target_row_lower = target_row.lower()
                if "因商业保密限制从略披露" in target_row or "confidentiality constraints" in target_row_lower:
                    item.metadata["omission_reason"] = "confidentiality"
                elif "因不适用而从略披露" in target_row or "不适用从略披露" in target_row or "not applicable" in target_row_lower:
                    item.metadata["omission_reason"] = "not_applicable"
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/agents/test_disclosure_agent.py::test_disclosure_agent_marks_english_and_short_omission_terms -q
```

Expected:

```text
1 passed
```

## 6. 验证命令

完成全部任务后运行：

```powershell
cd backend
uv run --no-sync pytest tests/standards/test_evidence_contracts.py tests/tools/test_review_csv_audit.py tests/tools/test_evidence.py tests/agents/test_disclosure_agent.py tests/standards/test_gri_adapter.py tests/workflows/test_single_report_workflow.py::test_single_report_workflow_supplements_candidate_pages_for_energy_and_water_300_rules tests/workflows/test_single_report_workflow.py::test_single_report_workflow_supplements_candidate_pages_for_ghg_350_rules -q
```

预期：

```text
全部通过
```

重新生成：

```text
tmp/review/current_350_review_after_rules.csv
```

然后运行：

```powershell
cd backend
@'
from src.tools.review_csv_audit import audit_review_csv
result = audit_review_csv("../tmp/review/current_350_review_after_rules.csv", report_total_pages=78)
print("ok=", result.ok)
print("errors=", result.errors)
print("warnings=", result.warnings)
'@ | uv run --no-sync python -
```

预期：

```text
ok= True
errors= []
```

最后运行：

```powershell
git diff --check
rg -n "(?i)\b[a-z]:[\\/]" docs README.md .env.example backend/.env.example frontend/.env.example
```

预期：

```text
git diff --check 无错误
路径扫描无 docs/README 绝对路径命中
```

## 7. 提交建议

建议分三次提交：

```powershell
git add backend/src/tools/review_csv_audit.py backend/tests/tools/test_review_csv_audit.py
git commit -m "test: add review CSV evidence audit gates"

git add backend/src/agents/disclosure_agent.py backend/tests/agents/test_disclosure_agent.py
git commit -m "fix: enforce KPI table quality flags"

git add backend/src/standards/evidence_contracts.py backend/tests/standards/test_evidence_contracts.py backend/src/workflows/single_report_workflow.py backend/src/agents/disclosure_agent.py backend/src/tools/evidence.py backend/tests/tools/test_evidence.py docs/DEVELOPMENT.md
git commit -m "feat: add leaf evidence contracts and KPI previews"
```

## 8. 自查清单

- [ ] `review_csv_audit` 能发现 PDF 第 3 页误挂 GRI 305。
- [ ] `review_csv_audit` 能发现 `omission_note` 被升格。
- [ ] `review_csv_audit` 能发现 PDF 第 63、65、68 页缺 `complex_table`。
- [ ] `GRI 205-3-b` PDF 第 68 页 evidence 已带 `complex_table`。
- [ ] `GRI 305-2-a/b` 不再使用 PDF 第 3 页。
- [ ] `GRI 305-2-a/b` 仍为 `disclosed + not_required`。
- [ ] `GRI 304-4-a` 仍为 `omission_note + not_applicable + unknown`。
- [ ] PDF 第 77 页鉴证页仍保留 OCR/VLM 风险标记。
- [ ] docs 中没有新增本机绝对路径。
