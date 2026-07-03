# 页码双轨字段与鉴证页解析预留 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 evidence 增加 PDF 页码和报告角标页码双轨字段，并为低文本鉴证页预留 OCR/VLM 路由标记。

**Architecture:** 保留现有 `source_page` 作为兼容字段，并明确其语义等同 `source_pdf_page`。新增 `source_pdf_page` 用于程序打开 PDF、截图和定位，新增 `source_report_page` 用于人工阅读、目录和 GRI 索引展示；鉴证页正文不足时只打标，不在本阶段调用外部模型。

**Tech Stack:** Python 3.11、FastAPI、Pydantic v2、SQLAlchemy 2.0、pytest、PostgreSQL、当前 PDF 解析与 GRI 索引管线。

---

## 1. 背景与约束

当前 `source_page` 实际存储 PDF 物理页码。人工复核时还需要报告角标页码，例如“PDF 第 77 页 / 报告页 76”。如果只展示一个页码，后续证据定位、截图、GRI 索引和人工阅读会出现混用风险。

本计划只做两件事：

- 固定 evidence 页码字段语义：`source_pdf_page`、`source_report_page`、`source_page`。
- 对 PDF 第 77 页这类低文本鉴证页增加 `needs_ocr_or_vlm` 标记和原因字段。

本计划暂不做：

- 不删除 `source_page`。
- 不新增 `not_applicable` 或 `condition_not_triggered` 枚举。
- 不调用 OCRmyPDF、Tesseract 或外部 VLM。
- 不改变 API 默认前 10 条 requirement 限制。
- 不改变本轮已经通过人工复核的 verdict/review_status 分布。

## 2. 字段定义

| 字段 | 类型 | 语义 | 用途 |
| --- | --- | --- | --- |
| `source_page` | `int` | 兼容字段，等同 PDF 物理页码 | 旧 API、旧测试、旧导出兼容 |
| `source_pdf_page` | `int` | PDF 物理页码，从 1 开始 | 程序打开 PDF、截图、证据定位 |
| `source_report_page` | `int | None` | 报告角标页码，从目录或 GRI 索引换算 | 人工阅读、前端展示、CSV 展示 |
| `page_label` | 导出层字符串 | `PDF 第 77 页 / 报告页 76` | 前端和 CSV 可读展示 |
| `needs_ocr_or_vlm` | `bool` | 当前证据页文本不足，需要 OCR/VLM 补正文 | 后续鉴证页、关键 KPI 页路由 |
| `ocr_or_vlm_reason` | `str | None` | 触发 OCR/VLM 预留的原因 | 人工复核和后续任务排队 |

`source_report_page` 计算规则：

```python
source_report_page = source_pdf_page - (report_index_pdf_page - report_index_report_page)
```

只有存在可靠的 `report_index_pdf_page` 和 `report_index_report_page` 时才计算；否则保持 `None`。

## 3. 影响文件

- Modify: `backend/src/domain/models.py`
  - 为 `EvidenceItem` 增加 `source_pdf_page`、`source_report_page`、`needs_ocr_or_vlm`、`ocr_or_vlm_reason`。
  - 增加 Pydantic 兼容逻辑：未传 `source_pdf_page` 时使用 `source_page`。
- Modify: `backend/src/db/models.py`
  - 为 evidence 表增加 nullable 字段。
- Modify: `backend/src/db/repositories.py`
  - 保存和读取新增 evidence 字段。
- Create: `backend/alembic/versions/0002_add_evidence_page_fields.py`
  - 添加 nullable columns，避免破坏已有数据。
- Modify: `backend/src/standards/gri_report_index.py`
  - 暴露 PDF 页码与报告页码换算能力。
- Modify: `backend/src/workflows/single_report_workflow.py`
  - 将 GRI 索引 offset 写入 evidence metadata，并填充 `source_report_page`。
- Modify: `backend/src/tools/evidence.py`
  - 从 chunk 生成 evidence 时填充 `source_pdf_page`。
- Modify: `backend/src/tools/guardrails.py`
  - 针对鉴证页低文本 evidence 打 `needs_ocr_or_vlm`。
- Modify: `backend/src/services/exports.py` 或当前导出所在文件
  - CSV/JSON 导出新增双轨页码字段和 `page_label`。
- Modify: `backend/tests/**`
  - 覆盖 domain、repository、workflow、guardrails、exports、API 兼容。
- Modify: `docs/DEVELOPMENT.md`
  - 记录字段语义和本次验证结果。

## 4. 验收标准

- 旧字段 `source_page` 仍存在，旧 API 测试继续通过。
- 所有新 evidence 都有 `source_pdf_page`，并且等于旧 `source_page`。
- 有 GRI 索引 offset 的 evidence 可生成 `source_report_page`。
- CSV 导出包含 `source_pdf_page`、`source_report_page`、`page_label`。
- PDF 第 77 页鉴证 evidence 在正文偏薄时标记 `needs_ocr_or_vlm=true`。
- 重新生成 `tmp/review/current_20_review_after_page_fields.csv`。
- 新 CSV 中 `GRI 2-5-b` 展示为 `PDF 第 77 页 / 报告页 76`。
- 后端全量测试通过。
- `docs/` 不写入本机绝对路径。

## 5. 实施任务

### Task 1: Domain 字段兼容

**Files:**
- Modify: `backend/src/domain/models.py`
- Modify: `backend/tests/domain/test_models.py`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/domain/test_models.py` 增加：

```python
def test_evidence_item_defaults_source_pdf_page_from_legacy_source_page():
    evidence = EvidenceItem(
        evidence_id="evidence-1",
        run_id="run-1",
        report_id="report-1",
        source_text="独立有限鉴证报告",
        source_page=77,
        source_file_hash="hash-1",
        source_method=EvidenceSourceMethod.PDFPLUMBER,
    )

    assert evidence.source_page == 77
    assert evidence.source_pdf_page == 77
    assert evidence.source_report_page is None
    assert evidence.needs_ocr_or_vlm is False
    assert evidence.ocr_or_vlm_reason is None
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/domain/test_models.py::test_evidence_item_defaults_source_pdf_page_from_legacy_source_page -q
```

Expected: FAIL，提示 `EvidenceItem` 没有 `source_pdf_page` 或相关字段。

- [ ] **Step 3: 最小实现**

在 `EvidenceItem` 中加入：

```python
source_pdf_page: int | None = Field(default=None, ge=1)
source_report_page: int | None = Field(default=None, ge=1)
needs_ocr_or_vlm: bool = False
ocr_or_vlm_reason: str | None = None

@model_validator(mode="after")
def default_source_pdf_page(self) -> "EvidenceItem":
    if self.source_pdf_page is None:
        self.source_pdf_page = self.source_page
    return self
```

如果文件尚未导入 `model_validator`，同步从 `pydantic` 导入。

- [ ] **Step 4: 运行测试确认通过**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/domain/test_models.py -q
```

Expected: PASS。

### Task 2: DB 持久化字段

**Files:**
- Modify: `backend/src/db/models.py`
- Modify: `backend/src/db/repositories.py`
- Create: `backend/alembic/versions/0002_add_evidence_page_fields.py`
- Modify: `backend/tests/db/test_repositories.py`

- [ ] **Step 1: 写失败测试**

在 evidence repository 测试中保存并读取：

```python
evidence = EvidenceItem(
    evidence_id="evidence-page-fields",
    run_id=run.run_id,
    report_id=report.report_id,
    source_text="独立有限鉴证报告",
    source_page=77,
    source_pdf_page=77,
    source_report_page=76,
    source_file_hash="hash-1",
    source_method=EvidenceSourceMethod.PDFPLUMBER,
    needs_ocr_or_vlm=True,
    ocr_or_vlm_reason="assurance_page_text_too_short",
)

repository.save_assessment(... evidence=[evidence] ...)
saved = repository.list_assessments(run.run_id)[0].evidence[0]

assert saved.source_page == 77
assert saved.source_pdf_page == 77
assert saved.source_report_page == 76
assert saved.needs_ocr_or_vlm is True
assert saved.ocr_or_vlm_reason == "assurance_page_text_too_short"
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/db/test_repositories.py -q
```

Expected: FAIL，提示 DB model 或 repository 未映射新增字段。

- [ ] **Step 3: 最小实现**

在 evidence SQLAlchemy model 增加 nullable columns：

```python
source_pdf_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
source_report_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
needs_ocr_or_vlm: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
ocr_or_vlm_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
```

在 repository 保存 evidence 时写入新增字段；读取时传回 `EvidenceItem`。

Alembic migration 使用 nullable column：

```python
op.add_column("evidence_items", sa.Column("source_pdf_page", sa.Integer(), nullable=True))
op.add_column("evidence_items", sa.Column("source_report_page", sa.Integer(), nullable=True))
op.add_column("evidence_items", sa.Column("needs_ocr_or_vlm", sa.Boolean(), nullable=False, server_default=sa.false()))
op.add_column("evidence_items", sa.Column("ocr_or_vlm_reason", sa.String(length=255), nullable=True))
```

- [ ] **Step 4: 运行 repository 测试**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/db/test_repositories.py -q
```

Expected: PASS。

### Task 3: GRI 索引页码换算

**Files:**
- Modify: `backend/src/standards/gri_report_index.py`
- Modify: `backend/tests/standards/test_gri_report_index.py`

- [ ] **Step 1: 写失败测试**

新增测试：

```python
def test_report_index_entry_can_convert_pdf_page_to_report_page():
    index = build_report_index(
        rows=[{"disclosure": "2-5", "page": "附录三：鉴证报告 76"}],
        index_pdf_page=71,
        index_report_page=70,
    )

    entry = index["2-5"]

    assert entry.candidate_pages == [77]
    assert entry.to_report_page(77) == 76
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/standards/test_gri_report_index.py::test_report_index_entry_can_convert_pdf_page_to_report_page -q
```

Expected: FAIL，提示 `to_report_page` 不存在。

- [ ] **Step 3: 最小实现**

为 `ReportIndexEntry` 增加 offset 或转换方法：

```python
report_index_pdf_page: int
report_index_report_page: int

def to_report_page(self, pdf_page: int) -> int:
    return pdf_page - (self.report_index_pdf_page - self.report_index_report_page)
```

构建 entry 时填入两个索引页字段。

- [ ] **Step 4: 运行标准测试**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/standards/test_gri_report_index.py -q
```

Expected: PASS。

### Task 4: Workflow 填充双轨页码

**Files:**
- Modify: `backend/src/workflows/single_report_workflow.py`
- Modify: `backend/tests/workflows/test_single_report_workflow.py`

- [ ] **Step 1: 写失败测试**

在现有 GRI index candidate pages 测试中补充：

```python
assert evidence.source_page == 77
assert evidence.source_pdf_page == 77
assert evidence.source_report_page == 76
assert evidence.evidence_metadata["source_pdf_page"] == 77
assert evidence.evidence_metadata["source_report_page"] == 76
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/workflows/test_single_report_workflow.py -q
```

Expected: FAIL，提示 workflow 未填充 report page 字段。

- [ ] **Step 3: 最小实现**

在 workflow 绑定 `ReportIndexEntry` 后，根据 evidence 的 `source_pdf_page` 或 `source_page` 计算：

```python
source_pdf_page = evidence.source_pdf_page or evidence.source_page
evidence.source_pdf_page = source_pdf_page
evidence.source_report_page = entry.to_report_page(source_pdf_page)
evidence.evidence_metadata["source_pdf_page"] = source_pdf_page
evidence.evidence_metadata["source_report_page"] = evidence.source_report_page
```

只在 entry 存在且转换结果大于 0 时写入 `source_report_page`。

- [ ] **Step 4: 运行 workflow 测试**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/workflows/test_single_report_workflow.py -q
```

Expected: PASS。

### Task 5: 鉴证页低文本标记

**Files:**
- Modify: `backend/src/tools/guardrails.py`
- Modify: `backend/tests/tools/test_guardrails.py`

- [ ] **Step 1: 写失败测试**

新增测试：

```python
def test_guardrails_marks_low_text_assurance_page_for_ocr_or_vlm():
    evidence = EvidenceItem(
        evidence_id="evidence-assurance",
        run_id="run-1",
        report_id="report-1",
        source_text="独立有限鉴证报告",
        source_page=77,
        source_pdf_page=77,
        source_report_page=76,
        source_file_hash="hash-1",
        source_method=EvidenceSourceMethod.PDFPLUMBER,
    )

    result = apply_evidence_guardrails("GRI 2-5-b", [evidence])

    assert result[0].needs_ocr_or_vlm is True
    assert result[0].ocr_or_vlm_reason == "assurance_page_text_too_short"
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/tools/test_guardrails.py::test_guardrails_marks_low_text_assurance_page_for_ocr_or_vlm -q
```

Expected: FAIL，提示未设置 `needs_ocr_or_vlm`。

- [ ] **Step 3: 最小实现**

在 guardrails 中增加规则：

```python
assurance_terms = ("鉴证报告", "独立有限鉴证", "有限保证", "assurance")
if disclosure_id.startswith("GRI 2-5") and any(term in evidence.source_text for term in assurance_terms):
    if len(evidence.source_text.strip()) < 120:
        evidence.needs_ocr_or_vlm = True
        evidence.ocr_or_vlm_reason = "assurance_page_text_too_short"
```

阈值先用 120 字符，后续按真实 OCR 结果调整。

- [ ] **Step 4: 运行 guardrails 测试**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/tools/test_guardrails.py -q
```

Expected: PASS。

### Task 6: CSV/JSON 导出字段

**Files:**
- Modify: `backend/src/services/exports.py` 或当前导出实现文件
- Modify: `backend/tests/api/test_exports_api.py`

- [ ] **Step 1: 写失败测试**

在导出测试中断言 CSV header 和 row：

```python
assert "source_pdf_page" in csv_text
assert "source_report_page" in csv_text
assert "page_label" in csv_text
assert "PDF 第 77 页 / 报告页 76" in csv_text
assert "needs_ocr_or_vlm" in csv_text
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/api/test_exports_api.py -q
```

Expected: FAIL，提示导出缺少新增字段。

- [ ] **Step 3: 最小实现**

导出 row 增加：

```python
"source_pdf_page": evidence.source_pdf_page,
"source_report_page": evidence.source_report_page,
"page_label": format_page_label(evidence.source_pdf_page, evidence.source_report_page),
"needs_ocr_or_vlm": evidence.needs_ocr_or_vlm,
"ocr_or_vlm_reason": evidence.ocr_or_vlm_reason,
```

新增格式化函数：

```python
def format_page_label(source_pdf_page: int | None, source_report_page: int | None) -> str:
    if source_pdf_page and source_report_page:
        return f"PDF 第 {source_pdf_page} 页 / 报告页 {source_report_page}"
    if source_pdf_page:
        return f"PDF 第 {source_pdf_page} 页"
    return ""
```

- [ ] **Step 4: 运行导出测试**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/api/test_exports_api.py -q
```

Expected: PASS。

### Task 7: 生成新复核 CSV

**Files:**
- Create: `tmp/review/current_20_review_after_page_fields.csv`
- Modify: `docs/DEVELOPMENT.md`

- [ ] **Step 1: 运行真实 PDF 非模型验收**

Run:

```powershell
cd backend
uv run --no-sync python scripts/run_real_pdf_validation.py --limit 20 --confirm-llm false --output ../tmp/review/current_20_review_after_page_fields.csv
```

如果当前项目没有该脚本，使用现有生成 `current_20_review_after_rules.csv` 的命令或测试 helper，不新增外部模型调用。

Expected:

- `model_called=false`
- requirement count 为 20
- `global_fallback` 为 0
- 生成 `tmp/review/current_20_review_after_page_fields.csv`

- [ ] **Step 2: 抽查关键行**

Run:

```powershell
Import-Csv ..\tmp\review\current_20_review_after_page_fields.csv |
  Where-Object { $_.requirement_id -like 'GRI 2-5*' } |
  Select-Object requirement_id,verdict,source_pdf_page,source_report_page,page_label,needs_ocr_or_vlm,ocr_or_vlm_reason |
  Format-Table -AutoSize
```

Expected:

- `GRI 2-5-a`、`GRI 2-5-b`、`GRI 2-5-b-i` 有 `source_pdf_page=77`。
- 有索引 offset 时 `source_report_page=76`。
- `page_label` 为 `PDF 第 77 页 / 报告页 76`。
- 低文本鉴证页 evidence 标记 `needs_ocr_or_vlm=true`。

- [ ] **Step 3: 更新开发日志**

在 `docs/DEVELOPMENT.md` 的 `2026-07-03` 下增加：

```markdown
- 增加 evidence 页码双轨字段：`source_pdf_page` 用于程序定位，`source_report_page` 用于人工阅读和 GRI 索引展示；保留 `source_page` 兼容旧 API，并在 CSV 导出中增加 `page_label`。
- 对低文本鉴证页增加 `needs_ocr_or_vlm` 和 `ocr_or_vlm_reason` 标记；本阶段只做路由预留，不调用 OCR/VLM。
```

### Task 8: 全量验证

**Files:**
- Read-only verification

- [ ] **Step 1: 后端全量测试**

Run:

```powershell
cd backend
uv run --no-sync pytest
```

Expected: 全部通过。

- [ ] **Step 2: docs 路径扫描**

Run:

```powershell
rg "(?i)[a-z]:[\\/]" docs README.md .env.example
```

Expected: 无输出，exit code 可以是 1。

- [ ] **Step 3: 查看变更范围**

Run:

```powershell
git status --short
git diff --stat
```

Expected: 变更只集中在后端字段、导出、测试和开发日志；`tmp/` 文件不进入 git。

## 6. 执行顺序建议

1. 先做 Task 1-2，固定 domain 与 DB 契约。
2. 再做 Task 3-4，打通 GRI 索引页码换算到 workflow。
3. 再做 Task 5-6，补鉴证页路由标记和导出。
4. 最后做 Task 7-8，生成新 CSV 并验证。

## 7. 风险与回滚

- `source_page` 继续保留，回滚时可忽略新增字段读取，不影响旧逻辑。
- DB 新增 nullable columns，历史数据不会被清空。
- `needs_ocr_or_vlm` 只影响标记和导出，不改变 verdict。
- 若 `source_report_page` 换算缺少可靠 offset，保持空值，不能猜测。

## 8. 自检清单

- [ ] 计划覆盖页码双轨字段。
- [ ] 计划覆盖鉴证页低文本标记。
- [ ] 计划保留 `source_page` 兼容。
- [ ] 计划未要求调用外部模型。
- [ ] 计划未要求删除或覆盖原始 PDF。
- [ ] 计划中的路径均为相对路径。
