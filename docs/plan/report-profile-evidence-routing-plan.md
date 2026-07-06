# Report Profile 与 Evidence Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将当前 Envision 2024 的固定页码规则迁入 report profile，并建立基于 GRI 索引、章节语义、KPI 行标签、年份列、单位和 evidence kind 的 evidence routing。

**Architecture:** `report profile` 保存单份报告的实例画像，通用 routing 逻辑只读取 profile、GRI 索引、contract metadata 和 ontology metadata，不在通用代码中硬编码 Envision 页码。KPI 行级匹配先覆盖已经人工验证过的 Envision KPI 页 PDF 63-68，并通过 577 regression 确认 verdict、evidence、页码和质量标记不回退。

**Tech Stack:** Python 3.11、Pydantic、pytest、现有 `SingleReportWorkflow`、`DisclosureAgent`、`evidence_contracts.py`、`evidence_ontology.py`、review CSV audit、first-pass quality。

---

## 1. 背景与边界

当前系统已经完成 577 条 eligible requirement 的人工复核、ontology matrix 接入和 no-evidence guardrail 迁移。当前主要扩展性风险集中在三处：

- `evidence_contracts.py` 和 `SingleReportWorkflow._candidate_page_overrides()` 中仍有大量 Envision 2024 固定页码。
- KPI 证据主要以页级文本命中为主，`evidence_preview` 偶尔夹杂整页表格串行文本。
- 577 regression 证明 baseline 未被破坏，但还不能证明换报告或未见 requirement 的 first-pass recall 已经提高。

本计划只做 report profile、evidence routing 和 KPI 行级匹配的第一阶段实现。Holdout 本阶段只写接口和指标，不立刻执行跨报告 holdout。

### 已确认决策

- Report profile 存放路径：`backend/data/reports/profiles/envision_2024.json`。
- Holdout：先写接口和指标，不立刻执行 holdout。
- KPI 行级匹配首批范围：只覆盖已经验证过的 Envision KPI 页 PDF 63-68。
- 固定页码：只能存在于 `backend/data/reports/profiles/envision_2024.json` 或测试 fixture 中，不能作为跨报告通用规则。

### 非目标

- 本阶段不迁移现有 PDF 文件路径。
- 本阶段不把所有 report-specific contract 一次性删除。
- 本阶段不放宽 `disclosed` 门槛。
- 本阶段不调用外部模型。
- 本阶段不把 84 条 compilation requirement 作为独立 assessment。

---

## 2. 目标文件结构

### 新增文件

- `backend/data/reports/profiles/envision_2024.json`
  - Envision 2024 报告实例画像。
  - 保存 PDF 文件名、页码偏移、GRI 索引页、KPI 页、章节页、鉴证页、低文本页和已确认候选页。

- `backend/src/reports/profile.py`
  - 定义 `ReportProfile`、`ReportPageRange`、`ReportKpiTableProfile`、`ReportRequirementRoute`。
  - 提供 `load_report_profile(path)`。
  - 提供 PDF 页码与报告页码转换方法。

- `backend/src/reports/__init__.py`
  - 导出 profile 相关类型。

- `backend/src/tools/evidence_routing.py`
  - 统一合并 GRI 索引、report profile、contract candidate、ontology metadata。
  - 输出 `EvidenceRoute`，包含候选 PDF 页、候选报告页、来源、KPI 页和 routing reason。

- `backend/src/tools/kpi_row_matcher.py`
  - 从候选 KPI 页的文本块中抽取行级 KPI 证据。
  - 识别 row label、年份列、单位、数值、source page 和 quality flag。
  - 首批只面向 profile 中声明的 PDF 63-68。

- `backend/tests/reports/test_report_profile.py`
  - 验证 profile schema、页码转换、KPI 页配置。

- `backend/tests/tools/test_evidence_routing.py`
  - 验证 routing 合并顺序、profile 页码来源、避免 `global_no_index`。

- `backend/tests/tools/test_kpi_row_matcher.py`
  - 验证 KPI 行级匹配、preview 锚点和 `complex_table`。

### 修改文件

- `backend/src/workflows/single_report_workflow.py`
  - 增加可选 `report_profile_path`。
  - 使用 `EvidenceRouter` 替换 `_candidate_page_overrides()` 中的通用使用路径。
  - 保留 `_candidate_page_overrides()` 作为迁移期 fallback，并逐步缩小。

- `backend/src/tools/retrieval.py`
  - 支持 routing 传入的 `kpi_row_terms` 和 `kpi_table_pages`。
  - 保持已有 `index_page_bounded` 行为。

- `backend/src/tools/evidence.py`
  - KPI evidence preview 优先使用行级 KPI 片段。
  - 普通 evidence preview 逻辑不回退。

- `backend/src/domain/models.py`
  - 在 `DisclosureTask` metadata 中承载 routing 结果字段，优先复用现有字段。
  - 只有现有字段无法表达行级 KPI 信息时，才新增字段。

- `backend/src/api/routes/reports.py`
  - 为单报告 workflow 提供可选 profile path。
  - 默认 Envision 2024 仍能通过现有路径运行。

- `backend/tests/agents/test_disclosure_agent.py`
  - 保留已有行为测试。
  - 增加少量 route metadata 和 KPI row preview 断言。

- `docs/DEVELOPMENT.md`
  - 记录 report profile 路径、routing 优先级、577 regression 命令、holdout 当前状态。

---

## 3. Routing 优先级

固定顺序：

1. `omission_note` / `not_applicable` 短路，不进入 KPI 行级匹配。
2. GRI report index 提供基础候选页。
3. Report profile 提供报告实例候选页、KPI 表页、章节页和页码偏移。
4. Contract metadata 提供 requirement-specific guardrail、allowed/forbidden pages 和迁移期候选页。
5. Evidence routing 根据 `semantic_group + facet + evidence_kind` 收窄候选页。
6. KPI row matcher 在 profile 的 KPI 页内做行级匹配。
7. Ontology matrix 给默认 verdict。
8. Per-ID contract guardrail 做最终约束。

关键规则：

- profile 页码可以影响当前报告候选页。
- profile 页码不能写入 ontology matrix。
- contract 中仍可保留高风险 guardrail。
- 当 profile 和 contract 都有候选页时，先取交集；交集为空时使用 contract allowed pages 保护高风险条目。
- 无索引项时优先走 contract/profile candidate fallback，避免回到 `global_no_index`。

---

## 4. Task 1：新增 Report Profile Schema

**Files:**

- Create: `backend/src/reports/profile.py`
- Create: `backend/src/reports/__init__.py`
- Create: `backend/tests/reports/test_report_profile.py`
- Create: `backend/data/reports/profiles/envision_2024.json`

- [ ] **Step 1: 写 profile schema 测试**

创建 `backend/tests/reports/test_report_profile.py`：

```python
from pathlib import Path

from src.reports.profile import load_report_profile


def test_load_envision_2024_profile_maps_pdf_and_report_pages():
    profile = load_report_profile(Path("data/reports/profiles/envision_2024.json"))

    assert profile.report_id == "envision_2024"
    assert profile.pdf_file == "Envision Energy 2024-zh.pdf"
    assert profile.report_page_for_pdf_page(63) == 62
    assert profile.pdf_page_for_report_page(62) == 63


def test_envision_2024_profile_declares_verified_kpi_pages():
    profile = load_report_profile(Path("data/reports/profiles/envision_2024.json"))

    assert profile.kpi_pdf_pages == [63, 64, 65, 66, 67, 68]
    assert profile.is_kpi_page(67)
    assert not profile.is_kpi_page(62)


def test_profile_returns_requirement_route_without_global_logic():
    profile = load_report_profile(Path("data/reports/profiles/envision_2024.json"))

    route = profile.route_for_requirement("GRI 414-1-a")

    assert route is not None
    assert route.candidate_pdf_pages == [67]
    assert route.kpi_table_pages == [67]
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd backend
uv run --no-sync pytest tests/reports/test_report_profile.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'src.reports'
```

- [ ] **Step 3: 创建 profile JSON**

创建 `backend/data/reports/profiles/envision_2024.json`：

```json
{
  "report_id": "envision_2024",
  "company_name": "Envision Energy",
  "report_year": 2024,
  "pdf_file": "Envision Energy 2024-zh.pdf",
  "total_pdf_pages": 78,
  "page_numbering": {
    "report_index_pdf_page": 71,
    "report_index_report_page": 70
  },
  "gri_index": {
    "pdf_pages": [71, 72, 73, 74]
  },
  "kpi_tables": [
    {
      "name": "environment_kpi",
      "pdf_pages": [63, 64],
      "report_pages": [62, 63],
      "quality_flags": ["complex_table"],
      "year_columns": ["2024"],
      "known_metric_terms": [
        "能源使用总量",
        "总取水量",
        "总排水量",
        "范围一",
        "范围二",
        "范围三",
        "节能措施促成的碳减排总量",
        "危险废物总重",
        "非危险废物总重",
        "废弃物回收总量"
      ]
    },
    {
      "name": "social_kpi",
      "pdf_pages": [65, 66, 67],
      "report_pages": [64, 65, 66],
      "quality_flags": ["complex_table"],
      "year_columns": ["2024"],
      "known_metric_terms": [
        "新进员工",
        "离职员工",
        "员工培训总时数",
        "接受定期绩效和职业发展考核的员工比例",
        "员工因工伤死亡数量",
        "可记录工伤数量",
        "工作小时数",
        "职业病病例数量",
        "使用环境评价维度筛选的新供应商百分比",
        "使用社会评价维度筛选的新供应商百分比"
      ]
    },
    {
      "name": "governance_kpi",
      "pdf_pages": [68],
      "report_pages": [67],
      "quality_flags": ["complex_table"],
      "year_columns": ["2024"],
      "known_metric_terms": [
        "贪污腐败事件数量",
        "员工因腐败被开除或受到处分的事件数量",
        "反竞争行为事件数量",
        "信息安全事件",
        "客户隐私"
      ]
    }
  ],
  "assurance_pages": [
    {
      "pdf_page": 77,
      "report_page": 76,
      "requires_ocr": true,
      "requires_vlm": false,
      "quality_flags": ["short_text", "image_body_not_extracted", "assurance_page_text_too_short"]
    }
  ],
  "requirement_routes": {
    "GRI 302-1-e": {
      "candidate_pdf_pages": [63],
      "kpi_table_pages": [63],
      "metric_terms": ["能源使用总量", "总能耗"]
    },
    "GRI 305-3-a": {
      "candidate_pdf_pages": [20, 63],
      "kpi_table_pages": [63],
      "metric_terms": ["范围三", "Scope 3"]
    },
    "GRI 305-5-a": {
      "candidate_pdf_pages": [63],
      "kpi_table_pages": [63],
      "metric_terms": ["节能措施促成的碳减排总量"]
    },
    "GRI 308-1-a": {
      "candidate_pdf_pages": [67],
      "kpi_table_pages": [67],
      "metric_terms": ["使用环境评价维度筛选的新供应商百分比"]
    },
    "GRI 414-1-a": {
      "candidate_pdf_pages": [67],
      "kpi_table_pages": [67],
      "metric_terms": ["使用社会评价维度筛选的新供应商百分比"]
    },
    "GRI 418-1-b": {
      "candidate_pdf_pages": [60, 61, 68],
      "kpi_table_pages": [68],
      "metric_terms": ["客户隐私", "数据丢失", "信息安全事件"]
    }
  }
}
```

- [ ] **Step 4: 实现 profile loader**

创建 `backend/src/reports/profile.py`：

```python
import json
from pathlib import Path

from pydantic import BaseModel, Field


class PageNumbering(BaseModel):
    report_index_pdf_page: int
    report_index_report_page: int

    @property
    def offset(self) -> int:
        return self.report_index_pdf_page - self.report_index_report_page


class ReportKpiTableProfile(BaseModel):
    name: str
    pdf_pages: list[int]
    report_pages: list[int] = Field(default_factory=list)
    quality_flags: list[str] = Field(default_factory=list)
    year_columns: list[str] = Field(default_factory=list)
    known_metric_terms: list[str] = Field(default_factory=list)


class AssurancePageProfile(BaseModel):
    pdf_page: int
    report_page: int | None = None
    requires_ocr: bool = False
    requires_vlm: bool = False
    quality_flags: list[str] = Field(default_factory=list)


class ReportRequirementRoute(BaseModel):
    candidate_pdf_pages: list[int] = Field(default_factory=list)
    kpi_table_pages: list[int] = Field(default_factory=list)
    metric_terms: list[str] = Field(default_factory=list)


class ReportProfile(BaseModel):
    report_id: str
    company_name: str
    report_year: int
    pdf_file: str
    total_pdf_pages: int
    page_numbering: PageNumbering
    gri_index: dict = Field(default_factory=dict)
    kpi_tables: list[ReportKpiTableProfile] = Field(default_factory=list)
    assurance_pages: list[AssurancePageProfile] = Field(default_factory=list)
    requirement_routes: dict[str, ReportRequirementRoute] = Field(default_factory=dict)

    @property
    def kpi_pdf_pages(self) -> list[int]:
        return sorted({page for table in self.kpi_tables for page in table.pdf_pages})

    def report_page_for_pdf_page(self, pdf_page: int) -> int | None:
        report_page = pdf_page - self.page_numbering.offset
        return report_page if report_page > 0 else None

    def pdf_page_for_report_page(self, report_page: int) -> int:
        return report_page + self.page_numbering.offset

    def is_kpi_page(self, pdf_page: int) -> bool:
        return pdf_page in set(self.kpi_pdf_pages)

    def route_for_requirement(self, requirement_id: str) -> ReportRequirementRoute | None:
        return self.requirement_routes.get(requirement_id)


def load_report_profile(path: Path) -> ReportProfile:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return ReportProfile.model_validate(raw)
```

创建 `backend/src/reports/__init__.py`：

```python
from src.reports.profile import ReportProfile, ReportRequirementRoute, load_report_profile

__all__ = ["ReportProfile", "ReportRequirementRoute", "load_report_profile"]
```

- [ ] **Step 5: 运行测试确认通过**

Run:

```bash
cd backend
uv run --no-sync pytest tests/reports/test_report_profile.py -q
```

Expected:

```text
3 passed
```

---

## 5. Task 2：新增 Evidence Routing 模块

**Files:**

- Create: `backend/src/tools/evidence_routing.py`
- Create: `backend/tests/tools/test_evidence_routing.py`
- Modify: `backend/src/workflows/single_report_workflow.py`

- [ ] **Step 1: 写 routing 测试**

创建 `backend/tests/tools/test_evidence_routing.py`：

```python
from pathlib import Path

from src.domain.models import DisclosureTask
from src.reports.profile import load_report_profile
from src.tools.evidence_routing import EvidenceRouter


def make_task(requirement_id: str, disclosure_id: str | None = None) -> DisclosureTask:
    return DisclosureTask(
        task_id=f"task-{requirement_id}",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI",
        disclosure_id=disclosure_id or requirement_id.rsplit("-", 1)[0],
        requirement_id=requirement_id,
        requirement_text="test requirement",
        keywords=["test"],
    )


def test_router_uses_report_profile_route_before_global_fallback():
    profile = load_report_profile(Path("data/reports/profiles/envision_2024.json"))
    router = EvidenceRouter(report_profile=profile)

    route = router.route(make_task("GRI 414-1-a", "GRI 414-1"))

    assert route.candidate_pdf_pages == [67]
    assert route.candidate_report_pages == [66]
    assert route.kpi_table_pages == [67]
    assert route.source == "report_profile"
    assert "profile:envision_2024" in route.reasons


def test_router_keeps_empty_route_for_explicit_no_evidence_candidate():
    profile = load_report_profile(Path("data/reports/profiles/envision_2024.json"))
    router = EvidenceRouter(report_profile=profile)

    route = router.route(make_task("GRI 305-2-c", "GRI 305-2"))

    assert route.candidate_pdf_pages == []
    assert route.candidate_report_pages == []
    assert route.source in {"contract", "empty"}


def test_router_merges_index_pages_when_profile_has_no_requirement_route():
    profile = load_report_profile(Path("data/reports/profiles/envision_2024.json"))
    router = EvidenceRouter(report_profile=profile)

    task = make_task("GRI 2-3-d", "GRI 2-3").model_copy(
        update={
            "candidate_pages": [3],
            "candidate_pdf_pages": [3],
            "candidate_report_pages": [2],
            "candidate_page_source": "gri_report_index",
        }
    )

    route = router.route(task)

    assert route.candidate_pdf_pages == [3]
    assert route.candidate_report_pages == [2]
    assert route.source == "gri_report_index"
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd backend
uv run --no-sync pytest tests/tools/test_evidence_routing.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'src.tools.evidence_routing'
```

- [ ] **Step 3: 实现 router**

创建 `backend/src/tools/evidence_routing.py`：

```python
from dataclasses import dataclass, field

from src.domain.models import DisclosureTask
from src.reports.profile import ReportProfile
from src.standards.evidence_contracts import get_requirement_contract


@dataclass(frozen=True)
class EvidenceRoute:
    candidate_pdf_pages: list[int] = field(default_factory=list)
    candidate_report_pages: list[int | None] = field(default_factory=list)
    kpi_table_pages: list[int] = field(default_factory=list)
    metric_terms: list[str] = field(default_factory=list)
    source: str = "empty"
    reasons: list[str] = field(default_factory=list)


class EvidenceRouter:
    def __init__(self, report_profile: ReportProfile | None = None):
        self.report_profile = report_profile

    def route(self, task: DisclosureTask) -> EvidenceRoute:
        contract = get_requirement_contract(task.requirement_id)
        profile_route = self.report_profile.route_for_requirement(task.requirement_id) if self.report_profile else None

        if profile_route is not None:
            pages = self._valid_pages(profile_route.candidate_pdf_pages)
            return EvidenceRoute(
                candidate_pdf_pages=pages,
                candidate_report_pages=self._report_pages(pages),
                kpi_table_pages=self._valid_pages(profile_route.kpi_table_pages),
                metric_terms=list(profile_route.metric_terms),
                source="report_profile",
                reasons=[f"profile:{self.report_profile.report_id}"] if self.report_profile else [],
            )

        if contract is not None and contract.candidate_pages is not None:
            pages = self._valid_pages(list(contract.candidate_pages))
            return EvidenceRoute(
                candidate_pdf_pages=pages,
                candidate_report_pages=self._report_pages(pages),
                kpi_table_pages=list(contract.kpi_table_pages or ()),
                source="contract",
                reasons=["contract:candidate_pages"],
            )

        if task.candidate_pdf_pages:
            pages = self._valid_pages(task.candidate_pdf_pages)
            return EvidenceRoute(
                candidate_pdf_pages=pages,
                candidate_report_pages=task.candidate_report_pages,
                source=task.candidate_page_source or "gri_report_index",
                reasons=[task.candidate_page_source or "gri_report_index"],
            )

        if task.candidate_pages:
            pages = self._valid_pages(task.candidate_pages)
            return EvidenceRoute(
                candidate_pdf_pages=pages,
                candidate_report_pages=self._report_pages(pages),
                source=task.candidate_page_source or "candidate_pages",
                reasons=[task.candidate_page_source or "candidate_pages"],
            )

        return EvidenceRoute()

    def _valid_pages(self, pages: list[int]) -> list[int]:
        if self.report_profile is None:
            return sorted({page for page in pages if page > 0})
        return sorted({page for page in pages if 1 <= page <= self.report_profile.total_pdf_pages})

    def _report_pages(self, pdf_pages: list[int]) -> list[int | None]:
        if self.report_profile is None:
            return []
        return [self.report_profile.report_page_for_pdf_page(page) for page in pdf_pages]
```

- [ ] **Step 4: 接入 workflow 构造 routing**

修改 `backend/src/workflows/single_report_workflow.py`：

```python
from src.reports.profile import ReportProfile, load_report_profile
from src.tools.evidence_routing import EvidenceRouter
```

在 `SingleReportWorkflow.__init__` 增加参数：

```python
        report_profile_path: Path | None = None,
```

初始化：

```python
        self.report_profile: ReportProfile | None = (
            load_report_profile(report_profile_path) if report_profile_path is not None else None
        )
        self.evidence_router = EvidenceRouter(self.report_profile)
```

在 `_attach_report_index_candidates()` 中，构造完 report index entry 后调用 router；迁移期只在 profile 有 route 时覆盖：

```python
            route = self.evidence_router.route(task)
            if route.source == "report_profile":
                enriched_tasks.append(
                    task.model_copy(
                        update={
                            "candidate_pages": route.candidate_pdf_pages,
                            "candidate_pdf_pages": route.candidate_pdf_pages,
                            "candidate_report_pages": route.candidate_report_pages,
                            "candidate_page_source": route.source,
                        }
                    )
                )
                continue
```

注意：这一步只覆盖 profile 明确声明的 requirement。未声明的 requirement 继续走现有逻辑，避免大范围 diff。

- [ ] **Step 5: 运行 routing 测试**

Run:

```bash
cd backend
uv run --no-sync pytest tests/tools/test_evidence_routing.py tests/reports/test_report_profile.py -q
```

Expected:

```text
6 passed
```

---

## 6. Task 3：KPI 行级匹配与 preview 锚点

**Files:**

- Create: `backend/src/tools/kpi_row_matcher.py`
- Create: `backend/tests/tools/test_kpi_row_matcher.py`
- Modify: `backend/src/tools/evidence.py`
- Modify: `backend/src/tools/retrieval.py`

- [ ] **Step 1: 写 KPI 行级匹配测试**

创建 `backend/tests/tools/test_kpi_row_matcher.py`：

```python
from src.domain.enums import PageQualityFlag
from src.domain.models import DocumentChunk
from src.tools.kpi_row_matcher import match_kpi_rows


def test_match_kpi_row_extracts_metric_value_and_unit():
    chunk = DocumentChunk(
        chunk_id="chunk-63",
        report_id="report-1",
        source_page=63,
        source_text_hash="hash",
        source_file_hash="file-hash",
        text="环境绩效 指标 单位 2024 能源使用总量 kWh 177,478,406.50 绿色电力 kWh 1,000",
        source_method="pdfplumber",
        quality_flags=[PageQualityFlag.COMPLEX_TABLE],
    )

    matches = match_kpi_rows([chunk], ["能源使用总量"], year_columns=["2024"])

    assert len(matches) == 1
    assert matches[0].row_label == "能源使用总量"
    assert matches[0].unit == "kWh"
    assert matches[0].value == "177,478,406.50"
    assert matches[0].source_page == 63


def test_match_kpi_row_does_not_match_unrelated_metric():
    chunk = DocumentChunk(
        chunk_id="chunk-67",
        report_id="report-1",
        source_page=67,
        source_text_hash="hash",
        source_file_hash="file-hash",
        text="供应商绩效 指标 单位 2024 使用环境评价维度筛选的新供应商百分比 % 100",
        source_method="pdfplumber",
        quality_flags=[PageQualityFlag.COMPLEX_TABLE],
    )

    matches = match_kpi_rows([chunk], ["使用社会评价维度筛选的新供应商百分比"], year_columns=["2024"])

    assert matches == []
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd backend
uv run --no-sync pytest tests/tools/test_kpi_row_matcher.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'src.tools.kpi_row_matcher'
```

- [ ] **Step 3: 实现 KPI matcher**

创建 `backend/src/tools/kpi_row_matcher.py`：

```python
import re
from dataclasses import dataclass

from src.domain.models import DocumentChunk


@dataclass(frozen=True)
class KpiRowMatch:
    chunk: DocumentChunk
    row_label: str
    unit: str | None
    value: str | None
    year_column: str | None
    source_page: int
    preview: str


def match_kpi_rows(
    chunks: list[DocumentChunk],
    metric_terms: list[str],
    year_columns: list[str] | None = None,
) -> list[KpiRowMatch]:
    year_columns = year_columns or ["2024"]
    matches: list[KpiRowMatch] = []
    for chunk in chunks:
        normalized = " ".join(chunk.text.split())
        for term in metric_terms:
            term = term.strip()
            if not term or term not in normalized:
                continue
            match = _match_metric_line(normalized, term, year_columns)
            if match is None:
                continue
            unit, value, year = match
            matches.append(
                KpiRowMatch(
                    chunk=chunk,
                    row_label=term,
                    unit=unit,
                    value=value,
                    year_column=year,
                    source_page=chunk.source_page,
                    preview=_preview(normalized, term),
                )
            )
    return matches


def _match_metric_line(text: str, term: str, year_columns: list[str]) -> tuple[str | None, str | None, str | None] | None:
    index = text.find(term)
    if index < 0:
        return None
    window = text[index : index + 180]
    year = next((candidate for candidate in year_columns if candidate in text[:index] or candidate in window), None)
    after_term = window[len(term) :].strip()
    tokens = after_term.split()
    unit = tokens[0] if tokens else None
    value = None
    for token in tokens[1:]:
        if re.fullmatch(r"-?\d[\d,]*(?:\.\d+)?%?", token):
            value = token
            break
    return unit, value, year


def _preview(text: str, term: str) -> str:
    index = text.find(term)
    start = max(0, index - 20)
    end = min(len(text), index + len(term) + 120)
    preview = text[start:end].strip()
    if start > 0:
        preview = f"...{preview}"
    if end < len(text):
        preview = f"{preview}..."
    return preview
```

- [ ] **Step 4: 在 evidence preview 中使用 KPI row preview**

修改 `backend/src/tools/evidence.py` 的 `chunk_to_evidence()`，在 `retrieval_metadata` 中存在 `kpi_row_preview` 时优先使用：

```python
    evidence_preview = (
        str(metadata.get("kpi_row_preview"))
        if metadata.get("kpi_row_preview")
        else build_evidence_preview(chunk.text, task.keywords)
    )
```

并把 `EvidenceItem` 中的 `evidence_preview=` 改为：

```python
        evidence_preview=evidence_preview,
```

- [ ] **Step 5: 在 retrieval 中优先匹配 KPI 行**

修改 `backend/src/tools/retrieval.py`：

```python
from src.domain.enums import PageQualityFlag
from src.tools.kpi_row_matcher import match_kpi_rows
```

在 bounded retrieval 前加入：

```python
        kpi_terms = task.metadata.get("kpi_metric_terms", []) if hasattr(task, "metadata") else []
```

如果 `DisclosureTask` 没有 `metadata` 字段，改为通过 `retrieval_metadata` 传入 `metric_terms`，并在 workflow 更新 task 时把 metric terms 放进已有可用字段。优先避免新增数据库字段。

KPI 行匹配逻辑：

```python
        if retrieval_metadata.get("kpi_metric_terms"):
            kpi_chunks = [
                chunk
                for chunk in chunks
                if chunk.source_page in set(retrieval_metadata.get("kpi_table_pages", []))
                and PageQualityFlag.COMPLEX_TABLE in chunk.quality_flags
            ]
            row_matches = match_kpi_rows(
                kpi_chunks,
                list(retrieval_metadata["kpi_metric_terms"]),
                year_columns=list(retrieval_metadata.get("year_columns", ["2024"])),
            )
            if row_matches:
                return [
                    chunk_to_evidence(
                        task,
                        match.chunk,
                        retrieval_metadata={
                            **retrieval_metadata,
                            "kpi_row_label": match.row_label,
                            "kpi_row_unit": match.unit,
                            "kpi_row_value": match.value,
                            "kpi_year_column": match.year_column,
                            "kpi_row_preview": match.preview,
                        },
                    )
                    for match in row_matches[:limit]
                ]
```

- [ ] **Step 6: 运行 KPI matcher 测试**

Run:

```bash
cd backend
uv run --no-sync pytest tests/tools/test_kpi_row_matcher.py tests/tools/test_evidence.py -q
```

Expected:

```text
all tests passed
```

---

## 7. Task 4：Workflow 使用 Report Profile，但保持 577 输出不回退

**Files:**

- Modify: `backend/src/workflows/single_report_workflow.py`
- Modify: `backend/src/api/routes/reports.py`
- Modify: `backend/tests/agents/test_disclosure_agent.py`
- Modify: `backend/tests/tools/test_review_csv_audit.py`

- [ ] **Step 1: 增加 workflow profile path 测试**

在 `backend/tests/agents/test_disclosure_agent.py` 或新增 workflow 测试中验证：

```python
def test_workflow_profile_route_sets_candidate_pages_for_supplier_social_kpi():
    profile = load_report_profile(Path("data/reports/profiles/envision_2024.json"))
    router = EvidenceRouter(report_profile=profile)
    task = DisclosureTask(
        task_id="task-414",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI",
        disclosure_id="GRI 414-1",
        requirement_id="GRI 414-1-a",
        requirement_text="new suppliers screened using social criteria",
        keywords=["供应商", "社会评价"],
    )

    route = router.route(task)

    assert route.candidate_pdf_pages == [67]
    assert route.candidate_report_pages == [66]
```

- [ ] **Step 2: 将 profile path 接入 API**

修改 `backend/src/api/routes/reports.py` 中创建 `SingleReportWorkflow` 的地方，传入默认 profile path。只对 Envision 2024 当前样本使用：

```python
report_profile_path = Path("data/reports/profiles/envision_2024.json")
if not report_profile_path.exists():
    report_profile_path = None
```

然后：

```python
workflow = SingleReportWorkflow(
    ...,
    report_profile_path=report_profile_path,
)
```

- [ ] **Step 3: 在 workflow 中标记 route source**

当 profile route 命中时，`candidate_page_source` 必须为：

```python
"report_profile"
```

当 GRI 索引 + profile 共同参与时，使用：

```python
"gri_report_index+report_profile"
```

迁移期允许旧值继续存在，但新增 profile route 不能显示为 `global_fallback` 或 `global_no_index`。

- [ ] **Step 4: 跑相关测试**

Run:

```bash
cd backend
uv run --no-sync pytest tests/tools/test_evidence_routing.py tests/reports/test_report_profile.py tests/agents/test_disclosure_agent.py -q
```

Expected:

```text
all tests passed
```

---

## 8. Task 5：迁移 Envision KPI 页候选逻辑到 Profile

**Files:**

- Modify: `backend/src/standards/evidence_contracts.py`
- Modify: `backend/src/workflows/single_report_workflow.py`
- Modify: `backend/data/reports/profiles/envision_2024.json`
- Test: `backend/tests/standards/test_evidence_contracts.py`
- Test: `backend/tests/tools/test_evidence_routing.py`

- [ ] **Step 1: 先只迁移 KPI 页 63-68 的候选页**

迁移范围只包括这些已验证的 KPI 页：

```text
PDF 63: 环境 KPI
PDF 64: 环境/废弃物/温室气体方法与 KPI
PDF 65: 员工结构 KPI
PDF 66: 员工福利、培训、OHS KPI
PDF 67: OHS、供应商环境/社会评估 KPI
PDF 68: 治理、合规、信息安全 KPI
```

首批从 contract 中迁出这些纯 KPI candidate：

```text
GRI 302-1-e
GRI 305-3-a
GRI 305-5-a
GRI 308-1-a
GRI 414-1-a
GRI 418-1-b
```

保留 contract 中的 semantic group、facets、evidence_kinds 和 guardrail。

- [ ] **Step 2: 修改 contract 测试**

在 `backend/tests/standards/test_evidence_contracts.py` 中确认迁移后的 contract 不再拥有纯 profile 页码：

```python
def test_kpi_profile_owned_requirement_contract_keeps_semantic_metadata_without_candidate_page():
    contract = get_requirement_contract("GRI 414-1-a")

    assert contract is not None
    assert contract.candidate_pages is None or contract.candidate_pages == ()
    assert contract.semantic_group is not None
    assert contract.evidence_kinds
```

- [ ] **Step 3: 修改 routing 测试确认 profile 接管**

在 `backend/tests/tools/test_evidence_routing.py` 增加：

```python
def test_profile_takes_over_kpi_candidate_pages_after_contract_page_removal():
    profile = load_report_profile(Path("data/reports/profiles/envision_2024.json"))
    router = EvidenceRouter(report_profile=profile)

    route = router.route(make_task("GRI 308-1-a", "GRI 308-1"))

    assert route.candidate_pdf_pages == [67]
    assert route.source == "report_profile"
```

- [ ] **Step 4: 跑 contract 与 routing 测试**

Run:

```bash
cd backend
uv run --no-sync pytest tests/standards/test_evidence_contracts.py tests/tools/test_evidence_routing.py -q
```

Expected:

```text
all tests passed
```

---

## 9. Task 6：577 Regression Gate

**Files:**

- No source file change expected.
- Generated artifacts under `tmp/review/`.

- [ ] **Step 1: 重新生成 ontology 后 577 review CSV**

Run:

```bash
cd backend
uv run --no-sync python -m src.tools.review_csv_audit ../tmp/review/current_577_review_after_ontology.csv
```

如果 `review_csv_audit.py` CLI 不支持该命令，使用现有 Python inline 调用：

```bash
cd backend
uv run --no-sync python - <<'PY'
import json
from dataclasses import asdict
from pathlib import Path
from src.tools.review_csv_audit import audit_review_csv

result = audit_review_csv("../tmp/review/current_577_review_after_ontology.csv", report_total_pages=78)
Path("../tmp/review/current_577_review_after_profile_routing_audit.json").write_text(
    json.dumps(asdict(result), ensure_ascii=False, indent=2),
    encoding="utf-8",
)
print("ok=", result.ok)
print("errors=", result.errors)
print("warnings=", result.warnings)
PY
```

Expected:

```text
ok= True
errors= []
warnings= []
```

- [ ] **Step 2: 生成新 CSV**

沿用当前项目已有的 577 生成脚本或 inline workflow，输出：

```text
tmp/review/current_577_review_after_profile_routing.csv
```

要求：

```text
requirement_count = 577
global_fallback = 0
compilation_overlap = 0
```

- [ ] **Step 3: 对比 profile routing 前后 diff**

输出：

```text
tmp/review/current_577_review_profile_routing_diff.csv
tmp/review/current_577_review_profile_routing_diff_summary.json
```

硬性通过条件：

```json
{
  "added_requirements": [],
  "removed_requirements": [],
  "changed_by_field": {
    "verdict": 0,
    "review_status": 0,
    "source_pdf_page": 0,
    "source_report_page": 0,
    "evidence_type": 0,
    "retrieval_strategy": 0,
    "quality_flags": 0,
    "needs_ocr_or_vlm": 0,
    "requires_ocr": 0,
    "requires_vlm": 0
  }
}
```

允许差异：

```text
evidence_preview
rationale
missing_items
candidate_page_source
metadata 中的 kpi_row_label / kpi_row_value / kpi_row_unit / kpi_year_column
```

所有允许差异必须写入 diff summary。

- [ ] **Step 4: 跑 first-pass quality**

Run:

```bash
cd backend
uv run --no-sync python -m src.tools.first_pass_quality ../tmp/review/current_577_review_after_rules.csv ../tmp/review/current_577_review_after_profile_routing.csv
```

Expected:

```json
{
  "false_disclosed_count": 0,
  "wrong_source_page_count": 0,
  "unknown_leakage_count": 0,
  "after_rules_delta_disclosed": 0,
  "after_rules_delta_partial": 0,
  "after_rules_delta_unknown": 0
}
```

- [ ] **Step 5: 停止条件**

出现任一情况必须暂停：

- 新增 `disclosed`。
- `disclosed -> partial/unknown`。
- `unknown/partial -> disclosed`。
- source PDF page 变化。
- `complex_table` 丢失。
- PDF 第 77 页 OCR/VLM 风险标记丢失。
- `global_fallback` 大于 0。
- 577 requirement 数量变化。

处理方式：

1. 先定位是 profile route、KPI row matcher、contract fallback 还是 workflow 页码转换造成。
2. 若 routing 过宽，收窄 profile route 或 metric terms。
3. 若 contract guardrail 被绕过，恢复 contract final guardrail 优先级。
4. 若 KPI row preview 变化但 source 页不变，只记录为非阻塞差异。

---

## 10. Task 7：Holdout 接口与指标，不执行 Holdout

**Files:**

- Modify: `backend/src/tools/first_pass_quality.py`
- Create: `backend/tests/tools/test_holdout_quality_interface.py`
- Modify: `docs/DEVELOPMENT.md`

- [ ] **Step 1: 写 holdout 接口测试**

创建 `backend/tests/tools/test_holdout_quality_interface.py`：

```python
from src.tools.first_pass_quality import summarize_quality


def test_holdout_quality_accepts_empty_gold_fields_without_running_holdout():
    rows = [
        {
            "requirement_id": "HOLDOUT supplier screening percentage",
            "verdict": "disclosed",
            "source_pdf_page": "67",
            "manual_label": "",
            "correct_pdf_pages": "",
            "suggested_verdict": "",
            "issue_type": "",
        }
    ]

    summary = summarize_quality(rows, rows)

    assert summary.false_disclosed_count == 0
    assert summary.wrong_source_page_count == 0
```

- [ ] **Step 2: 实现或调整 first-pass quality helper**

如果 `first_pass_quality.py` 已有 `summarize_quality`，只补兼容空 gold 字段。没有该函数时，新增：

```python
def summarize_quality(first_rows: list[dict], reviewed_rows: list[dict]):
    ...
```

该函数不得要求 holdout 文件已经存在。

- [ ] **Step 3: 文档记录 holdout 状态**

在 `docs/DEVELOPMENT.md` 增加：

```markdown
### Holdout 状态

- 当前已实现 holdout quality 接口和指标字段。
- 本阶段暂不执行跨报告 holdout。
- 正式 holdout 需要先确定新报告资产、人工复核样本和禁止新增 per-ID contract 的验收边界。
```

- [ ] **Step 4: 跑测试**

Run:

```bash
cd backend
uv run --no-sync pytest tests/tools/test_first_pass_quality.py tests/tools/test_holdout_quality_interface.py -q
```

Expected:

```text
all tests passed
```

---

## 11. Task 8：文档与迁移记录

**Files:**

- Modify: `docs/DEVELOPMENT.md`
- Modify: `docs/plan/report-profile-evidence-routing-plan.md`

- [ ] **Step 1: 写开发记录**

在 `docs/DEVELOPMENT.md` 增加：

```markdown
### Report Profile 与 Evidence Routing

- 新增 `backend/data/reports/profiles/envision_2024.json`，保存 Envision 2024 报告实例画像。
- 固定 PDF 页码只作为当前报告 profile candidate，不作为跨报告通用规则。
- Evidence routing 优先级为 GRI 索引、report profile、contract metadata、ontology metadata、KPI row matcher、ontology matrix、contract guardrail。
- 首批 KPI 行级匹配只覆盖 PDF 63-68。
- 577 regression gate 要求 verdict、review_status、source page、evidence_type、quality_flags、OCR/VLM 字段不回退。
- Holdout 本阶段只实现接口和指标，不执行跨报告 holdout。
```

- [ ] **Step 2: 文档路径扫描**

Run:

```bash
python - <<'PY'
from pathlib import Path

for target in [Path("docs/DEVELOPMENT.md"), Path("docs/plan/report-profile-evidence-routing-plan.md")]:
    for number, line in enumerate(target.read_text(encoding="utf-8").splitlines(), start=1):
        for index in range(len(line) - 2):
            starts_path = index == 0 or line[index - 1] in {" ", "`", "'", '"', "(", "["}
            if starts_path and line[index].isalpha() and line[index + 1] == ":" and line[index + 2] in {"/", "\\"}:
                print(f"{target}:{number}:{line}")
                break
PY
```

Expected:

```text
no output
```

- [ ] **Step 3: 计划勾选**

执行任务时逐步勾选本计划 checklist。只在验证通过后勾选对应步骤。

---

## 12. 最小测试集

每个阶段至少运行对应测试。完整阶段收尾运行：

```bash
cd backend
uv run --no-sync pytest tests/reports/test_report_profile.py tests/tools/test_evidence_routing.py tests/tools/test_kpi_row_matcher.py tests/tools/test_evidence.py tests/tools/test_review_csv_audit.py tests/tools/test_first_pass_quality.py tests/standards/test_evidence_contracts.py tests/agents/test_disclosure_agent.py -q
```

预期：

```text
all tests passed
```

577 regression gate 必须额外运行：

```bash
cd backend
uv run --no-sync python -m src.tools.first_pass_quality ../tmp/review/current_577_review_after_rules.csv ../tmp/review/current_577_review_after_profile_routing.csv
```

预期：

```text
after_rules_delta_disclosed = 0
after_rules_delta_partial = 0
after_rules_delta_unknown = 0
false_disclosed_count = 0
wrong_source_page_count = 0
unknown_leakage_count = 0
```

---

## 13. 停止条件

执行本计划时，触发以下任一条件必须暂停，先汇报原因、影响范围和建议处理方式，不继续后续任务。

- 577 regression 重新生成后 requirement 数量不是 577。
- 出现新增 `disclosed`。
- verdict 或 review status 出现非预期变化，包括：
  - `unknown` 或 `partially_disclosed` 变为 `disclosed`
  - `disclosed` 变为 `partially_disclosed` 或 `unknown`
  - `disclosed` 未对应 `not_required`
  - `partially_disclosed` 或 `unknown` 未对应 `needs_manual_review`
- source page 发生非预期变化，包括 `source_pdf_page`、`source_report_page`、`page_label`。
- evidence type 发生非预期变化，包括 `omission_note`、`index_statement`、`substantive` 被误改。
- PDF 第 63-68 页 KPI evidence 丢失 `complex_table`。
- PDF 第 77 页鉴证页 OCR/VLM 风险标记回退，包括：
  - `requires_ocr=True`
  - `needs_ocr_or_vlm=True`
  - `short_text`
  - `image_body_not_extracted`
  - `assurance_page_text_too_short`
- `global_fallback` 大于 0。
- 出现页码越界、`page_label` 乱码或字面量 Unicode 转义。
- 84 条 compilation requirement 被当作独立 assessment 混入主 assessment。
- 关键测试失败且失败原因不是计划中明确要求的预期失败。

### 13.1 允许继续的差异

以下差异不触发停止，但必须记录到 diff summary 或开发记录：

- `evidence_preview` 变为更准确的 KPI 行级片段。
- `rationale` 或 `missing_items` 更具体。
- `candidate_page_source` 从 `requirement_contract` 变为 `report_profile` 或 `gri_report_index+report_profile`。
- evidence metadata 新增：
  - `kpi_row_label`
  - `kpi_row_value`
  - `kpi_row_unit`
  - `kpi_year_column`

---

## 14. 验收标准

### 机器验收

- `global_fallback=0`。
- 577 requirement 数量不变。
- `compilation_overlap=0`。
- `page_label` 无乱码，无字面量 Unicode 转义。
- `source_pdf_page` 和 `candidate_pdf_pages` 不越界。
- `disclosed` 全部为 `not_required`。
- `partially_disclosed / unknown` 全部为 `needs_manual_review`。
- `omission_note` 不升格。
- PDF 第 63-68 页 KPI evidence 保留 `complex_table`。
- PDF 第 77 页保留 OCR/VLM 风险标记。

### 业务验收

- Envision 2024 固定 KPI 页候选逻辑迁入 profile。
- 通用 routing 不直接写死 PDF 63-68。
- KPI preview 能优先显示命中行。
- 现有 577 baseline verdict 和 source page 不回退。
- Holdout 接口和指标可用，但不要求本阶段执行 holdout。

---

## 15. 提交建议

建议按阶段小提交：

```bash
git add backend/src/reports backend/tests/reports backend/data/reports/profiles/envision_2024.json
git commit -m "feat: add report profile schema"
```

```bash
git add backend/src/tools/evidence_routing.py backend/src/workflows/single_report_workflow.py backend/tests/tools/test_evidence_routing.py
git commit -m "feat: route evidence through report profile"
```

```bash
git add backend/src/tools/kpi_row_matcher.py backend/src/tools/evidence.py backend/src/tools/retrieval.py backend/tests/tools/test_kpi_row_matcher.py
git commit -m "feat: add KPI row evidence matching"
```

```bash
git add docs/DEVELOPMENT.md docs/plan/report-profile-evidence-routing-plan.md
git commit -m "docs: record report profile routing plan"
```

---

## 16. 后续阶段

本计划通过后，下一阶段再做：

1. 将更多 Envision 页码从 contract/workflow 迁入 profile。
2. 将 profile 生成自动化：从 GRI 索引、目录、表格标题和页脚页码生成初始 profile。
3. 执行正式 holdout：选择另一份 ESG 报告或保留样本，禁止新增 per-ID contract，评估 first-pass recall。
4. 将 `compilation_requirement_mapping_fixed.csv` 转为正式 sufficiency guardrail。
5. 继续收敛 ontology matrix，减少重复 missing_items 和 report-specific 口径。
