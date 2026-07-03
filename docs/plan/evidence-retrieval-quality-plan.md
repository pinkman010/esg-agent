# 证据定位质量改造 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 evidence retrieval 从“全报告关键词检索”改造成“先用 GRI 索引页限定候选页，再检索证据，必要时 fallback 并进入人工复核”的确定性基线。

**Architecture:** 在 PDF 解析完成后，从报告 GRI 指标索引页提取 disclosure 到报告页码的映射，并换算成 PDF 页码。`DisclosureTask` 携带候选页信息，`retrieve_evidence()` 优先在候选页检索；fallback、低质量页、复杂表格页通过 evidence metadata 和 guardrails 进入人工复核。

**Tech Stack:** Python 3.11、FastAPI、Pydantic v2、SQLAlchemy、pytest、pdfplumber、现有 GRI manifest。

---

## 1. 背景与目标

当前系统已经能用真实 ESG 报告跑通：

- 输入报告：`backend/data/reports/Envision Energy 2024-zh.pdf`
- GRI checklist：`backend/data/manifests/gri_requirement_checklist.json`
- GRI pack：`backend/data/manifests/gri_requirement_pack.json`
- 当前启用：前 10 条 `current_gap`、mandatory、`hard_score` requirement

当前主要问题：

- `retrieve_evidence()` 在所有 chunk 里做关键词检索。
- 对 `GRI 2-1-a` 这类条款，关键词过于泛化，容易命中目录、前言、无关章节。
- 真实报告的 GRI 指标索引页已经给出 disclosure 对应章节和页码，当前没有利用。

改造目标：

- 对每个 disclosure 建立候选 PDF 页码。
- 在候选页内优先检索 evidence。
- fallback 到全局检索时明确标记并进入人工复核。
- evidence metadata 记录检索方式、候选页、索引页来源。
- 真实 PDF 验收仍保持 `confirm_llm=false`，不调用外部模型。

## 2. 不做范围

- 不接 OCR/VLM 实调用。
- 不启用向量检索。
- 不一次性打开 577 条 requirement。
- 不把关键词命中结果写成最终合规结论。
- 不改前端 UI，除非后端响应字段已经暴露并需要展示。

## 3. 影响文件

- Modify: `backend/src/domain/models.py`
  - 给 `DisclosureTask` 增加候选页和检索上下文字段。
- Create: `backend/src/standards/gri_report_index.py`
  - 解析报告 GRI 指标索引页，输出 disclosure 到候选 PDF 页的映射。
- Modify: `backend/src/api/routes/reports.py`
  - 增加 `GRI_REQUIREMENT_PACK_PATH`，传给 workflow。
- Modify: `backend/src/workflows/single_report_workflow.py`
  - 在解析 PDF 后构建索引映射，并给 tasks 注入候选页。
- Modify: `backend/src/tools/retrieval.py`
  - 候选页优先检索，失败后全局 fallback。
- Modify: `backend/src/tools/evidence.py`
  - 写入 retrieval metadata。
- Modify: `backend/src/tools/guardrails.py`
  - fallback、低质量页、复杂表格页进入人工复核。
- Test: `backend/tests/standards/test_gri_report_index.py`
- Test: `backend/tests/tools/test_retrieval.py`
- Test: `backend/tests/tools/test_guardrails.py`
- Test: `backend/tests/workflows/test_single_report_workflow.py`
- Test: `backend/tests/api/test_reports_api.py`
- Docs: `docs/DEVELOPMENT.md`

## 4. 设计口径

### 4.1 页码换算

报告 GRI 指标索引页文本中的页码是报告页码，不是 PDF 文件页码。根据 `gri_requirement_pack.json`：

- `report_index_pdf_page`
- `report_index_report_page`

换算方式：

```text
pdf_page = report_page + (report_index_pdf_page - report_index_report_page)
```

以当前报告为例，索引页 PDF 页 71 对应报告页 70，因此正文报告页 5 对应 PDF 页 6。

### 4.2 检索策略

检索顺序：

```text
candidate_pages 非空
  -> 只在 candidate_pages 的 chunks 内关键词检索
  -> 命中：metadata.retrieval_strategy = index_page_bounded
  -> 未命中：全局关键词 fallback
  -> fallback 命中：metadata.retrieval_strategy = global_fallback

candidate_pages 为空
  -> 全局关键词检索
  -> metadata.retrieval_strategy = global_no_index
```

### 4.3 复核规则

进入人工复核的情况：

- 没有 evidence。
- evidence 来自 `global_fallback` 或 `global_no_index`。
- evidence 所在 chunk 带 `low_text_density`、`scanned`、`complex_table`。
- evidence 来自 OCR/VLM 且是 KPI。

## 5. Task 1: 增加任务候选页模型字段

**Files:**
- Modify: `backend/src/domain/models.py`
- Test: `backend/tests/domain/test_models.py`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/domain/test_models.py` 增加：

```python
def test_disclosure_task_can_carry_report_index_candidate_pages():
    task = DisclosureTask(
        task_id="run-1:GRI 2-1-a",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI 2",
        standard_version="2021",
        disclosure_id="GRI 2-1",
        requirement_id="GRI 2-1-a",
        requirement_text="report its legal name;",
        keywords=["legal", "name"],
        candidate_pages=[6],
        candidate_page_source="gri_report_index",
        index_page=71,
    )

    assert task.candidate_pages == [6]
    assert task.candidate_page_source == "gri_report_index"
    assert task.index_page == 71
```

- [ ] **Step 2: 运行失败测试**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/domain/test_models.py -k candidate_pages
```

Expected: FAIL，因为 `DisclosureTask` 还没有 `candidate_pages`、`candidate_page_source`、`index_page` 字段。

- [ ] **Step 3: 最小实现**

修改 `backend/src/domain/models.py` 中的 `DisclosureTask`：

```python
class DisclosureTask(BaseModel):
    task_id: str
    run_id: str
    report_id: str
    standard_id: str
    standard_version: str
    disclosure_id: str
    requirement_id: str
    requirement_text: str
    keywords: list[str] = Field(default_factory=list)
    candidate_pages: list[int] = Field(default_factory=list)
    candidate_page_source: str | None = None
    index_page: int | None = None
```

- [ ] **Step 4: 运行通过测试**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/domain/test_models.py -k candidate_pages
```

Expected: PASS。

## 6. Task 2: 解析 GRI 指标索引页

**Files:**
- Create: `backend/src/standards/gri_report_index.py`
- Test: `backend/tests/standards/test_gri_report_index.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/standards/test_gri_report_index.py`：

```python
from src.domain.models import PageExtraction
from src.standards.gri_report_index import build_report_index


def test_build_report_index_extracts_candidate_pdf_pages_from_index_text():
    pages = [
        PageExtraction(
            report_id="report-1",
            page_number=71,
            text=(
                "GRI标准 披露项 章节索引 页码/备注\n"
                "2-1 组织详细情况 关于远景能源 5\n"
                "2-2 纳入组织可持续发展报告的实体 关于本报告 2\n"
                "2-5 外部鉴证 附录三：鉴证报告 76\n"
            ),
        )
    ]
    pack_items = [
        {
            "canonical_disclosure_id": "2-1",
            "report_index_pdf_page": 71,
            "report_index_report_page": 70,
        },
        {
            "canonical_disclosure_id": "2-2",
            "report_index_pdf_page": 71,
            "report_index_report_page": 70,
        },
        {
            "canonical_disclosure_id": "2-5",
            "report_index_pdf_page": 71,
            "report_index_report_page": 70,
        },
    ]

    index = build_report_index(pages, pack_items)

    assert index["2-1"].candidate_pages == [6]
    assert index["2-2"].candidate_pages == [3]
    assert index["2-5"].candidate_pages == [77]
    assert index["2-1"].index_page == 71
```

- [ ] **Step 2: 运行失败测试**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/standards/test_gri_report_index.py
```

Expected: FAIL，因为 `gri_report_index.py` 尚不存在。

- [ ] **Step 3: 最小实现**

创建 `backend/src/standards/gri_report_index.py`：

```python
from dataclasses import dataclass
import re
from typing import Any

from src.domain.models import PageExtraction


@dataclass(frozen=True)
class GRIReportIndexEntry:
    disclosure_id: str
    candidate_pages: list[int]
    index_page: int
    source: str = "gri_report_index"


def build_report_index(
    pages: list[PageExtraction],
    pack_items: list[dict[str, Any]],
) -> dict[str, GRIReportIndexEntry]:
    page_by_number = {page.page_number: page for page in pages}
    result: dict[str, GRIReportIndexEntry] = {}

    for item in pack_items:
        disclosure_id = str(item.get("canonical_disclosure_id") or "").strip()
        index_pdf_page = item.get("report_index_pdf_page")
        index_report_page = item.get("report_index_report_page")
        if not disclosure_id or not isinstance(index_pdf_page, int) or not isinstance(index_report_page, int):
            continue

        page = page_by_number.get(index_pdf_page)
        if page is None:
            continue

        report_pages = _extract_report_pages_for_disclosure(disclosure_id, page.text)
        if not report_pages:
            continue

        offset = index_pdf_page - index_report_page
        candidate_pages = sorted({report_page + offset for report_page in report_pages if report_page > 0})
        result[disclosure_id] = GRIReportIndexEntry(
            disclosure_id=disclosure_id,
            candidate_pages=candidate_pages,
            index_page=index_pdf_page,
        )

    return result


def _extract_report_pages_for_disclosure(disclosure_id: str, text: str) -> list[int]:
    pattern = re.compile(rf"(?<![\d-]){re.escape(disclosure_id)}(?![\d-])(?P<body>.*?)(?=\n\d{{1,3}}-\d{{1,3}}|\nGRI\s+\d+|$)", re.S)
    match = pattern.search(text)
    if match is None:
        return []
    body = match.group("body")
    if "/" in body and not re.search(r"\d", body):
        return []
    return [int(value) for value in re.findall(r"(?<!\d)(\d{1,3})(?!\d)", body)]
```

- [ ] **Step 4: 运行通过测试**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/standards/test_gri_report_index.py
```

Expected: PASS。

## 7. Task 3: 给 workflow 注入候选页

**Files:**
- Modify: `backend/src/api/routes/reports.py`
- Modify: `backend/src/workflows/single_report_workflow.py`
- Test: `backend/tests/workflows/test_single_report_workflow.py`
- Test: `backend/tests/api/test_reports_api.py`

- [ ] **Step 1: 写 workflow 失败测试**

在 `backend/tests/workflows/test_single_report_workflow.py` 增加断言：workflow 生成的 task 会带候选页，并且 evidence metadata 记录 `candidate_pages`。

测试数据中让 fake parser 返回：

```python
PageExtraction(report_id=report_id, page_number=71, text="2-1 组织详细情况 关于远景能源 5")
DocumentChunk(
    chunk_id="chunk-page-6",
    report_id=report_id,
    text="Legal name: Envision Energy Co., Ltd.",
    source_page=6,
    source_method=EvidenceSourceMethod.PDFPLUMBER,
    source_file_hash=source_file_hash,
)
```

断言：

```python
evidence = repo_session.scalar(select(EvidenceItemRecord).where(EvidenceItemRecord.run_id == run.run_id))
assert evidence.source_page == 6
assert evidence.evidence_metadata["retrieval_strategy"] == "index_page_bounded"
assert evidence.evidence_metadata["candidate_pages"] == [6]
assert evidence.evidence_metadata["index_page"] == 71
```

- [ ] **Step 2: 运行失败测试**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/workflows/test_single_report_workflow.py -k index
```

Expected: FAIL，因为 workflow 尚未注入候选页。

- [ ] **Step 3: 修改 workflow 构造参数**

修改 `backend/src/workflows/single_report_workflow.py`：

```python
class SingleReportWorkflow:
    def __init__(self, repository: Repository, parser, standard_adapter, disclosure_agent: DisclosureAgent, requirement_pack_path: Path | None = None):
        self.repository = repository
        self.parser = parser
        self.standard_adapter = standard_adapter
        self.disclosure_agent = disclosure_agent
        self.requirement_pack_path = requirement_pack_path
```

在 `run()` 中，解析 PDF 后、`build_tasks()` 后加入：

```python
tasks = self.standard_adapter.build_tasks(run_id=run_id, report_id=report_id)
tasks = self._attach_report_index_candidates(parsed.pages, tasks)
```

新增私有方法：

```python
def _attach_report_index_candidates(self, pages, tasks):
    if self.requirement_pack_path is None:
        return tasks
    import json
    from src.standards.gri_report_index import build_report_index

    raw = json.loads(self.requirement_pack_path.read_text(encoding="utf-8"))
    report_index = build_report_index(pages, raw.get("requirements", []))
    enriched = []
    for task in tasks:
        disclosure_id = task.disclosure_id.removeprefix("GRI ").strip()
        entry = report_index.get(disclosure_id)
        if entry is None:
            enriched.append(task)
            continue
        enriched.append(
            task.model_copy(
                update={
                    "candidate_pages": entry.candidate_pages,
                    "candidate_page_source": entry.source,
                    "index_page": entry.index_page,
                }
            )
        )
    return enriched
```

- [ ] **Step 4: 修改 API 入口**

修改 `backend/src/api/routes/reports.py`：

```python
GRI_REQUIREMENT_PACK_PATH = Path(__file__).resolve().parents[3] / "data" / "manifests" / "gri_requirement_pack.json"
```

workflow 构造时传入：

```python
SingleReportWorkflow(
    repo,
    DocumentParser(),
    GRIAdapter(GRI_REQUIREMENTS_PATH, max_requirements=GRI_REQUIREMENTS_LIMIT),
    DisclosureAgent(),
    requirement_pack_path=GRI_REQUIREMENT_PACK_PATH,
)
```

- [ ] **Step 5: 运行通过测试**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/workflows/test_single_report_workflow.py tests/api/test_reports_api.py
```

Expected: PASS。

## 8. Task 4: 改造 retrieval 为候选页优先

**Files:**
- Modify: `backend/src/tools/retrieval.py`
- Modify: `backend/src/tools/evidence.py`
- Test: `backend/tests/tools/test_retrieval.py`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/tools/test_retrieval.py` 增加：

```python
def test_retrieve_evidence_prefers_candidate_pages_and_records_strategy():
    task = DisclosureTask(
        task_id="run-1:GRI 2-1-a",
        run_id="run-1",
        report_id="report-1",
        standard_id="GRI 2",
        standard_version="2021",
        disclosure_id="GRI 2-1",
        requirement_id="GRI 2-1-a",
        requirement_text="report its legal name;",
        keywords=["legal", "name"],
        candidate_pages=[6],
        candidate_page_source="gri_report_index",
        index_page=71,
    )
    chunks = [
        DocumentChunk(chunk_id="global", report_id="report-1", text="legal name appears in unrelated page", source_page=1, source_method=EvidenceSourceMethod.PDFPLUMBER, source_file_hash="hash-1"),
        DocumentChunk(chunk_id="bounded", report_id="report-1", text="legal name Envision Energy", source_page=6, source_method=EvidenceSourceMethod.PDFPLUMBER, source_file_hash="hash-1"),
    ]

    evidence = retrieve_evidence(task, chunks)

    assert [item.source_page for item in evidence] == [6]
    assert evidence[0].metadata["retrieval_strategy"] == "index_page_bounded"
    assert evidence[0].metadata["candidate_pages"] == [6]
```

再增加 fallback 测试：

```python
def test_retrieve_evidence_falls_back_globally_when_candidate_pages_do_not_match():
    task = make_task()
    task = task.model_copy(update={"candidate_pages": [6], "candidate_page_source": "gri_report_index", "index_page": 71})
    chunks = [
        DocumentChunk(chunk_id="global", report_id="report-1", text="Energy consumption is disclosed.", source_page=22, source_method=EvidenceSourceMethod.PDFPLUMBER, source_file_hash="hash-1")
    ]

    evidence = retrieve_evidence(task, chunks)

    assert evidence[0].source_page == 22
    assert evidence[0].metadata["retrieval_strategy"] == "global_fallback"
```

- [ ] **Step 2: 运行失败测试**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/tools/test_retrieval.py -k "candidate_pages or falls_back"
```

Expected: FAIL，因为当前 retrieval 不使用候选页。

- [ ] **Step 3: 修改 evidence metadata 支持 retrieval context**

修改 `backend/src/tools/evidence.py`：

```python
def chunk_to_evidence(task: DisclosureTask, chunk: DocumentChunk, retrieval_metadata: dict | None = None) -> EvidenceItem:
    metadata = {
        **chunk.metadata,
        "task_id": task.task_id,
        "chunk_id": chunk.chunk_id,
    }
    if retrieval_metadata:
        metadata.update(retrieval_metadata)
    return EvidenceItem(
        evidence_id=evidence_id_for(task.task_id, chunk.chunk_id),
        run_id=task.run_id,
        report_id=task.report_id,
        source_text=chunk.text,
        source_page=chunk.source_page,
        source_file_hash=chunk.source_file_hash,
        source_method=chunk.source_method,
        bbox=chunk.bbox,
        quality_flags=chunk.quality_flags,
        metadata=metadata,
    )
```

- [ ] **Step 4: 修改 retrieval**

修改 `backend/src/tools/retrieval.py`：

```python
def retrieve_evidence(task: DisclosureTask, chunks: list[DocumentChunk], limit: int = 5) -> list[EvidenceItem]:
    if task.candidate_pages:
        bounded = _keyword_matches(
            task,
            [chunk for chunk in chunks if chunk.source_page in set(task.candidate_pages)],
            limit,
            {
                "retrieval_strategy": "index_page_bounded",
                "candidate_pages": task.candidate_pages,
                "candidate_page_source": task.candidate_page_source,
                "index_page": task.index_page,
            },
        )
        if bounded:
            return bounded
        return _keyword_matches(
            task,
            chunks,
            limit,
            {
                "retrieval_strategy": "global_fallback",
                "candidate_pages": task.candidate_pages,
                "candidate_page_source": task.candidate_page_source,
                "index_page": task.index_page,
            },
        )

    return _keyword_matches(task, chunks, limit, {"retrieval_strategy": "global_no_index"})


def _keyword_matches(task: DisclosureTask, chunks: list[DocumentChunk], limit: int, metadata: dict) -> list[EvidenceItem]:
    keywords = [keyword.lower() for keyword in task.keywords]
    matches: list[EvidenceItem] = []
    for chunk in chunks:
        text = chunk.text.lower()
        if keywords and not any(keyword in text for keyword in keywords):
            continue
        matches.append(chunk_to_evidence(task, chunk, retrieval_metadata=metadata))
        if len(matches) >= limit:
            break
    return matches
```

- [ ] **Step 5: 运行通过测试**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/tools/test_retrieval.py
```

Expected: PASS。

## 9. Task 5: fallback 和低质量页进入人工复核

**Files:**
- Modify: `backend/src/tools/guardrails.py`
- Test: `backend/tests/tools/test_guardrails.py`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/tools/test_guardrails.py` 增加：

```python
def test_global_fallback_evidence_forces_manual_review():
    evidence = EvidenceItem(
        evidence_id="evidence-1",
        run_id="run-1",
        report_id="report-1",
        source_text="Legal name appears outside candidate pages.",
        source_page=10,
        source_file_hash="hash-1",
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        metadata={"retrieval_strategy": "global_fallback"},
    )

    assessment = build_guarded_assessment(make_task(), evidence=[evidence], model_called=False)

    assert assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
```

再增加复杂表格页测试：

```python
def test_complex_table_evidence_forces_manual_review():
    evidence = EvidenceItem(
        evidence_id="evidence-1",
        run_id="run-1",
        report_id="report-1",
        source_text="KPI table text.",
        source_page=64,
        source_file_hash="hash-1",
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        quality_flags=[PageQualityFlag.COMPLEX_TABLE],
    )

    assessment = build_guarded_assessment(make_task(), evidence=[evidence], model_called=False)

    assert assessment.review_status is ReviewStatus.NEEDS_MANUAL_REVIEW
```

- [ ] **Step 2: 运行失败测试**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/tools/test_guardrails.py -k "fallback or complex_table"
```

Expected: FAIL，因为 guardrails 尚未处理 retrieval metadata 和复杂表格标记。

- [ ] **Step 3: 修改 guardrails**

修改 `backend/src/tools/guardrails.py`：

```python
from src.domain.enums import AssessmentVerdict, EvidenceSourceMethod, PageQualityFlag, ReviewStatus
```

在有 evidence 分支中加入：

```python
manual_review_strategies = {"global_fallback", "global_no_index"}
manual_review_flags = {
    PageQualityFlag.LOW_TEXT_DENSITY,
    PageQualityFlag.SCANNED,
    PageQualityFlag.COMPLEX_TABLE,
}

if any(item.metadata.get("retrieval_strategy") in manual_review_strategies for item in evidence):
    review_status = ReviewStatus.NEEDS_MANUAL_REVIEW

if any(any(flag in manual_review_flags for flag in item.quality_flags) for item in evidence):
    review_status = ReviewStatus.NEEDS_MANUAL_REVIEW
```

- [ ] **Step 4: 运行通过测试**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/tools/test_guardrails.py
```

Expected: PASS。

## 10. Task 6: 真实 PDF 验收

**Files:**
- Modify: `docs/DEVELOPMENT.md`

- [ ] **Step 1: 启动数据库**

Run:

```powershell
docker compose up -d postgres
```

Expected: PostgreSQL container running。

- [ ] **Step 2: 重建验证库**

Run:

```powershell
cd backend
$env:DATABASE_URL = 'postgresql+psycopg://esg_agent:esg_agent@localhost:5432/esg_agent_validation'
uv run --no-sync alembic upgrade head
```

Expected: Alembic upgrade succeeds。

- [ ] **Step 3: 跑真实 PDF `confirm_llm=false` 验收脚本**

使用 ASGI client 调用：

```text
GET  /api/health
POST /api/reports/upload
POST /api/reports/{report_id}/analyze {"confirm_llm": false}
GET  /api/runs/{run_id}
GET  /api/runs/{run_id}/assessments
GET  /api/runs/{run_id}/recommendations
GET  /api/review/runs/{run_id}/assessments
POST /api/review/runs/{run_id}/decisions
GET  /api/exports/runs/{run_id}/assessments.json
GET  /api/exports/runs/{run_id}/assessments.csv
GET  /api/exports/runs/{run_id}/review.json
GET  /api/exports/runs/{run_id}/review.csv
GET  /api/audit/runs
```

Expected:

- `analyze.status == "completed"`
- `confirm_llm == false`
- `assessment_count == 10`
- `model_called_values == [false]`
- evidence metadata 至少包含一种 `index_page_bounded`
- fallback evidence 的 assessment 进入 `needs_manual_review`
- exports 四个接口均返回 `200`

- [ ] **Step 4: 更新开发日志**

在 `docs/DEVELOPMENT.md` 的 `2026-07-03` 或当前日期小节记录：

```markdown
- 完成 evidence retrieval 质量改造：从 GRI 指标索引页提取 disclosure 候选页，检索优先限定在候选页，fallback 和低质量页进入人工复核。
- 真实 PDF `confirm_llm=false` 验收通过：记录 assessment 数、evidence 数、`index_page_bounded` 数、`global_fallback` 数、review 数。
```

## 11. Task 7: 全量回归

**Files:**
- No production file changes.

- [ ] **Step 1: 后端全量测试**

Run:

```powershell
cd backend
uv run --no-sync pytest
```

Expected: all tests pass。

- [ ] **Step 2: 文档路径检查**

Run:

```powershell
rg -n -P "(?<![A-Za-z+])\b[A-Za-z]:[\\/]" docs README.md .env.example backend/.env.example
```

Expected: no matches。

- [ ] **Step 3: 旧运行路径检查**

Run:

```powershell
$legacyPattern = "backend/data/knowledge" + "_base|source" + "_assets"
rg -n $legacyPattern docs README.md backend/src backend/tests
```

Expected: no matches。

## 12. 验收标准

- 后端测试通过。
- 文档中没有本机绝对路径。
- 真实 PDF `confirm_llm=false` 端到端通过。
- 前 10 条真实 GRI requirement 仍然生成 10 个 assessment。
- evidence metadata 能区分 `index_page_bounded`、`global_fallback`、`global_no_index`。
- fallback 或低质量 evidence 自动进入人工复核。
- 不调用外部模型。

## 13. 风险与限制

- GRI 索引页是中文报告中的表格文本，pdfplumber 抽取顺序可能不稳定；第一版只对当前真实报告和前 10 条做确定性验收。
- 索引页给出的页码是报告页码，需要转换为 PDF 页码；转换依赖 `report_index_pdf_page - report_index_report_page`。
- `3-3_generic` 仍是 disclosure 级占位，不在当前 checklist 叶子 requirement 中直接启用。
- 复杂表格页先进入人工复核，不在本计划中做 KPI 表格结构化抽取。
