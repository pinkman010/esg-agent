# Report Profile Routing Generalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将当前 profile/routing 第一阶段固化为提交点，并继续把 Envision 固定页码、profile 生成、holdout 指标和 compilation guardrail 产品化为可复用链路。

**Architecture:** 以已通过 577 regression 的 profile/routing 第一阶段为基线，后续每批迁移都通过 report profile 承载报告实例页码，通过 evidence routing 和 ontology/guardrail 执行通用判断。Profile 自动生成先覆盖 GRI 索引和目录/章节范围；holdout 本计划只定义规则和输出格式；compilation requirement guardrail 采用 JSON manifest 存规则数据、Python 模块加载执行。

**Tech Stack:** Python 3.11、Pydantic、pytest、现有 `SingleReportWorkflow`、`EvidenceRouter`、`ReportProfile`、`review_csv_audit`、`first_pass_quality`、577 review CSV baseline。

---

## 1. 已确认决策

- 先提交当前 profile/routing 第一阶段，再继续扩大迁移范围。
- 固定页码迁移采用分批策略：先 KPI 页，再章节页，再 no-evidence / empty route。
- Profile 自动生成第一版只覆盖 GRI 索引和目录/章节范围；表格标题、页脚和 KPI 行识别留到后续阶段。
- Holdout 本计划只定义规则和输出格式，不立刻执行。
- Compilation guardrail 使用 JSON + Python：JSON 存 84 条映射修复后的规则数据，Python 负责加载、执行和测试。

---

## 2. 非目标

- 不移动现有 PDF 原始文件。
- 不把固定页码写回 ontology matrix。
- 不把 holdout 变成 per-ID 补丁任务。
- 不把 84 条 `compilation_requirement` 当作独立 assessment。
- 不放宽 `disclosed` 门槛。
- 不调用外部模型。

---

## 3. 停止条件

触发以下任一条件必须暂停：

- 577 regression requirement 数量不是 577。
- 出现新增 `disclosed`。
- verdict 或 review status 非预期变化。
- source page、evidence type、quality flags、OCR/VLM 字段非预期变化。
- `global_fallback > 0`。
- PDF 第 63-68 页 KPI evidence 丢失 `complex_table`。
- PDF 第 77 页鉴证页 OCR/VLM 风险标记回退。
- `compilation_requirement` 混入主 assessment。
- 关键测试失败且不是计划中预期失败。

允许继续但必须记录的差异：

- `candidate_page_source` 从 contract 切到 profile。
- `evidence_preview` 变为行级或章节级更准确片段。
- `rationale` / `missing_items` 更具体。
- metadata 新增 profile/routing/guardrail 字段。

---

## 4. Task 1：提交当前 Profile/Routing 第一阶段

**Files:**

- Existing modified files from current working tree.

- [ ] **Step 1: 审阅当前 diff**

Run:

```powershell
git status --short
git diff --stat
git diff --check
```

Expected:

```text
git diff --check 无错误
```

- [ ] **Step 2: 跑完整阶段测试**

Run:

```powershell
cd backend
uv run --no-sync pytest --basetemp ..\tmp\pytest-profile-routing-final tests/reports/test_report_profile.py tests/tools/test_evidence_routing.py tests/tools/test_kpi_row_matcher.py tests/tools/test_evidence.py tests/tools/test_review_csv_audit.py tests/tools/test_first_pass_quality.py tests/tools/test_holdout_quality_interface.py tests/standards/test_evidence_contracts.py tests/agents/test_disclosure_agent.py -q
```

Expected:

```text
all tests passed
```

- [ ] **Step 3: 确认 577 gate 产物存在**

Run:

```powershell
Test-Path tmp\review\current_577_review_after_profile_routing.csv
Test-Path tmp\review\current_577_review_profile_routing_diff_summary.json
Get-Content tmp\review\current_577_review_profile_routing_diff_summary.json
```

Expected:

```text
before_count = 577
after_count = 577
changed_by_field.verdict = 0
changed_by_field.source_pdf_page = 0
changed_by_field.quality_flags = 0
new_disclosed = []
```

- [ ] **Step 4: 提交当前阶段**

Run:

```powershell
git add backend/src backend/tests backend/data/reports/profiles/envision_2024.json docs/DEVELOPMENT.md docs/plan/report-profile-evidence-routing-plan.md
git commit -m "feat: add report profile evidence routing"
```

Expected:

```text
commit created
```

---

## 5. Task 2：盘点剩余固定页码

**Files:**

- Create: `tmp/review/envision_fixed_page_inventory.csv`
- Modify: `docs/DEVELOPMENT.md`

- [ ] **Step 1: 导出固定页码清单**

Run:

```powershell
@'
import ast
import csv
import re
from pathlib import Path

sources = [
    Path("backend/src/standards/evidence_contracts.py"),
    Path("backend/src/workflows/single_report_workflow.py"),
]
rows = []
for source in sources:
    text = source.read_text(encoding="utf-8")
    for match in re.finditer(r'"(GRI [^"]+)":\s*(?:RequirementEvidenceContract\(|\[)', text):
        requirement_id = match.group(1)
        block = text[match.start(): text.find("\n    \"GRI ", match.start() + 1)]
        if not block:
            block = text[match.start(): match.start() + 800]
        pages = sorted({int(value) for value in re.findall(r"\b(?:candidate_pages|allowed_pages|kpi_table_pages)\s*=\s*\(([^)]*)\)", block) for value in re.findall(r"\d+", value)})
        if pages:
            rows.append({
                "source_file": str(source),
                "requirement_id": requirement_id,
                "pages": pages,
                "category": "unclassified",
                "migration_batch": "",
                "note": "",
            })

output = Path("tmp/review/envision_fixed_page_inventory.csv")
output.parent.mkdir(parents=True, exist_ok=True)
with output.open("w", encoding="utf-8-sig", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=["source_file", "requirement_id", "pages", "category", "migration_batch", "note"])
    writer.writeheader()
    writer.writerows(rows)
print("rows=", len(rows))
print(output)
'@ | python -
```

Expected:

```text
tmp/review/envision_fixed_page_inventory.csv created
```

- [ ] **Step 2: 分类迁移批次**

编辑生成的 CSV 或用脚本分类：

```text
batch_1_kpi_pages: PDF 63-68 纯 KPI 页
batch_2_section_pages: 章节正文页，例如 14、17-25、32-41、42-44、52-61
batch_3_index_omission_pages: 71-74 索引/从略页
batch_4_empty_routes: candidate_pages=() 的 no-evidence / empty route
```

- [ ] **Step 3: 记录清单结果**

在 `docs/DEVELOPMENT.md` 记录：

```markdown
### Envision 固定页码清单

- 固定页码清单输出到 `tmp/review/envision_fixed_page_inventory.csv`。
- 迁移顺序为 KPI 页、章节页、索引/从略页、empty routes。
- 每批迁移必须跑 577 regression gate。
```

---

## 6. Task 3：批量迁移剩余 KPI 页 Candidate

**Files:**

- Modify: `backend/data/reports/profiles/envision_2024.json`
- Modify: `backend/src/standards/evidence_contracts.py`
- Test: `backend/tests/tools/test_evidence_routing.py`
- Test: `backend/tests/standards/test_evidence_contracts.py`

- [ ] **Step 1: 选择 batch_1_kpi_pages**

从 `tmp/review/envision_fixed_page_inventory.csv` 选择：

```text
pages 只包含 63、64、65、66、67、68
且 candidate_pages 与 kpi_table_pages 高度一致
且不依赖章节背景页
```

禁止纳入：

```text
同时依赖正文页和 KPI 页的 partial 条目
omission_note
empty route
```

- [ ] **Step 2: 写 routing 测试**

在 `backend/tests/tools/test_evidence_routing.py` 为每个迁移 requirement 增加：

```python
def test_profile_owns_more_kpi_page_routes():
    profile = load_report_profile(Path("data/reports/profiles/envision_2024.json"))
    router = EvidenceRouter(report_profile=profile)

    cases = {
        "GRI 302-1-a": [63],
        "GRI 302-1-c": [63],
        "GRI 205-3-b": [68],
    }
    for requirement_id, expected_pages in cases.items():
        route = router.route(make_task(requirement_id, requirement_id.rsplit("-", 1)[0]))
        assert route.candidate_pdf_pages == expected_pages
        assert route.source == "report_profile"
```

- [ ] **Step 3: 更新 profile**

在 `backend/data/reports/profiles/envision_2024.json` 的 `requirement_routes` 增加对应 requirement：

```json
"GRI 302-1-a": {
  "candidate_pdf_pages": [63],
  "kpi_table_pages": [63],
  "metric_terms": ["不可再生能源", "燃料", "能源"]
}
```

每个 route 必须包含：

```text
candidate_pdf_pages
kpi_table_pages
metric_terms
```

- [ ] **Step 4: 从 contract 移除 candidate_pages**

对已迁移 requirement：

- 移除 `candidate_pages`
- 保留 `allowed_pages`
- 保留 `kpi_table_pages`
- 保留 `facets`
- 保留 `evidence_kinds`
- 保留 `semantic_group`
- 保留 `missing_items`

- [ ] **Step 5: 跑测试**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/tools/test_evidence_routing.py tests/standards/test_evidence_contracts.py tests/agents/test_disclosure_agent.py -q
```

Expected:

```text
all tests passed
```

- [ ] **Step 6: 跑 577 regression gate**

重新生成：

```text
tmp/review/current_577_review_after_profile_routing.csv
tmp/review/current_577_review_profile_routing_diff_summary.json
```

Expected:

```text
verdict diff = 0
source page diff = 0
quality_flags diff = 0
new_disclosed = []
candidate_page_source 允许增加 profile 差异
```

---

## 7. Task 4：迁移章节页 Candidate

**Files:**

- Modify: `backend/data/reports/profiles/envision_2024.json`
- Modify: `backend/src/standards/evidence_contracts.py`
- Modify: `backend/src/workflows/single_report_workflow.py`
- Test: `backend/tests/tools/test_evidence_routing.py`

- [ ] **Step 1: 在 profile 增加章节范围**

在 `backend/data/reports/profiles/envision_2024.json` 增加：

```json
"sections": [
  {
    "name": "stakeholder_engagement",
    "pdf_pages": [14, 15],
    "report_pages": [13, 14],
    "terms": ["利益相关方", "关注议题", "沟通渠道"]
  },
  {
    "name": "ohs_management",
    "pdf_pages": [38, 39, 40, 41],
    "report_pages": [37, 38, 39, 40],
    "terms": ["EHS", "职业健康安全", "隐患排查", "事故管理"]
  }
]
```

- [ ] **Step 2: 扩展 `ReportProfile` schema**

在 `backend/src/reports/profile.py` 增加：

```python
class ReportSectionProfile(BaseModel):
    name: str
    pdf_pages: list[int]
    report_pages: list[int] = Field(default_factory=list)
    terms: list[str] = Field(default_factory=list)
```

并在 `ReportProfile` 增加：

```python
sections: list[ReportSectionProfile] = Field(default_factory=list)
```

- [ ] **Step 3: 只迁移稳定章节页**

首批章节页只迁移已多轮复核稳定的条目：

```text
GRI 2-29 / GRI 3-1: PDF 14-15
GRI 403 management: PDF 38-41
GRI 413 community: PDF 14, 42-44
```

不迁移：

```text
需要索引从略说明的条目
no-evidence empty route
仍存在人工争议的条目
```

- [ ] **Step 4: 跑 577 regression gate**

同 Task 3 Step 6。

---

## 8. Task 5：迁移索引/从略页 Candidate

**Files:**

- Modify: `backend/data/reports/profiles/envision_2024.json`
- Modify: `backend/src/standards/evidence_contracts.py`
- Test: `backend/tests/agents/test_disclosure_agent.py`
- Test: `backend/tests/tools/test_review_csv_audit.py`

- [ ] **Step 1: 在 profile 增加 GRI index note pages**

在 profile 中补充：

```json
"index_note_pages": [
  {
    "pdf_page": 71,
    "report_page": 70,
    "note_types": ["omission_note", "index_statement"]
  },
  {
    "pdf_page": 72,
    "report_page": 71,
    "note_types": ["omission_note", "index_statement"]
  },
  {
    "pdf_page": 73,
    "report_page": 72,
    "note_types": ["omission_note"]
  },
  {
    "pdf_page": 74,
    "report_page": 73,
    "note_types": ["omission_note"]
  }
]
```

- [ ] **Step 2: 迁移 omission / index statement 候选页**

只迁移已经审定的：

```text
omission_note
index_statement
not_applicable omission
```

保持规则：

```text
omission_note 只作为缺口解释，不得升 partial/disclosed
index_statement 只能作用于明确零事件或索引声明允许的 leaf
```

- [ ] **Step 3: 跑 audit 和 577 gate**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/tools/test_review_csv_audit.py tests/agents/test_disclosure_agent.py -q
```

再跑 577 regression gate。

---

## 9. Task 6：Profile 自动生成第一版

**Files:**

- Create: `backend/src/reports/profile_builder.py`
- Create: `backend/tests/reports/test_profile_builder.py`

- [ ] **Step 1: 写 profile builder 测试**

创建 `backend/tests/reports/test_profile_builder.py`：

```python
from src.domain.models import PageExtraction
from src.reports.profile_builder import build_initial_profile


def test_profile_builder_uses_gri_index_and_page_offset():
    pages = [
        PageExtraction(report_id="r1", page_number=71, text="GRI 2-4 信息重述 无信息重述 70"),
        PageExtraction(report_id="r1", page_number=72, text="GRI 204-1 向当地供应商采购的支出比例 因商业保密限制从略披露"),
    ]

    profile = build_initial_profile(
        report_id="sample",
        company_name="Sample",
        report_year=2024,
        pdf_file="sample.pdf",
        total_pdf_pages=78,
        pages=pages,
        report_index_pdf_page=71,
        report_index_report_page=70,
    )

    assert profile.report_page_for_pdf_page(72) == 71
    assert profile.gri_index["pdf_pages"] == [71, 72]
```

- [ ] **Step 2: 实现 builder**

创建 `backend/src/reports/profile_builder.py`：

```python
from src.domain.models import PageExtraction
from src.reports.profile import PageNumbering, ReportProfile


def build_initial_profile(
    report_id: str,
    company_name: str,
    report_year: int,
    pdf_file: str,
    total_pdf_pages: int,
    pages: list[PageExtraction],
    report_index_pdf_page: int,
    report_index_report_page: int,
) -> ReportProfile:
    index_pages = [
        page.page_number
        for page in pages
        if "GRI" in page.text and ("披露项" in page.text or "从略披露" in page.text or "信息重述" in page.text)
    ]
    return ReportProfile(
        report_id=report_id,
        company_name=company_name,
        report_year=report_year,
        pdf_file=pdf_file,
        total_pdf_pages=total_pdf_pages,
        page_numbering=PageNumbering(
            report_index_pdf_page=report_index_pdf_page,
            report_index_report_page=report_index_report_page,
        ),
        gri_index={"pdf_pages": sorted(set(index_pages))},
    )
```

- [ ] **Step 3: 跑测试**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/reports/test_profile_builder.py tests/reports/test_report_profile.py -q
```

Expected:

```text
all tests passed
```

---

## 10. Task 7：Holdout 规则和输出格式

**Files:**

- Create: `docs/plan/holdout-validation-protocol.md`
- Modify: `backend/src/tools/first_pass_quality.py`
- Test: `backend/tests/tools/test_holdout_quality_interface.py`

- [ ] **Step 1: 写 holdout 协议文档**

创建 `docs/plan/holdout-validation-protocol.md`：

```markdown
# Holdout Validation Protocol

## 目标

验证 report profile、evidence routing、ontology matrix 和 guardrail 对未见样本的 first-pass recall 是否提高。

## 规则

- 不得针对 holdout 新增 per-ID contract。
- 不得针对 holdout 写固定页码到通用代码。
- 允许生成 holdout report profile。
- 允许扩展通用 evidence kind、facet、routing rule。

## 输出

- first-pass recall
- false disclosed
- wrong source page
- unknown leakage
- disclosed precision review list
```

- [ ] **Step 2: first-pass quality 输出 holdout 字段**

在 `FirstPassQualityResult` 中不新增破坏性字段；需要新增时只追加可选字段，并保持 CLI JSON 向后兼容。

- [ ] **Step 3: 跑测试**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/tools/test_first_pass_quality.py tests/tools/test_holdout_quality_interface.py -q
```

Expected:

```text
all tests passed
```

---

## 11. Task 8：Compilation Guardrail 产品化

**Files:**

- Create: `backend/data/manifests/compilation_guardrails.json`
- Modify: `backend/src/standards/compilation_guardrails.py`
- Test: `backend/tests/standards/test_compilation_guardrails.py`

- [ ] **Step 1: 生成 JSON manifest**

从 `tmp/review/compilation_requirement_mapping_fixed.csv` 生成：

```json
{
  "rules": [
    {
      "compilation_requirement_id": "GRI 401-1-2.1",
      "target_requirement_ids": ["GRI 401-1-a", "GRI 401-1-b"],
      "facets": ["requires_rate_basis"],
      "missing_item_template": "员工流失率和新进员工率需要说明分母口径。",
      "guardrail_effect": "不能在缺少分母口径时判定完整 disclosed。"
    }
  ]
}
```

Remove 行不得进入 manifest。

- [ ] **Step 2: 加载 manifest**

在 `backend/src/standards/compilation_guardrails.py` 增加：

```python
def load_compilation_guardrail_manifest(path: Path) -> CompilationGuardrailManifest:
    ...
```

保留现有 Python guardrail 行为，manifest 先作为数据来源，不改变 verdict。

- [ ] **Step 3: 测试 compilation 不生成 assessment**

测试要求：

```text
manifest 中的 compilation_requirement_id 不出现在 577 assessment requirement_id 中
target_requirement_ids 均非空
remove 行不存在
```

- [ ] **Step 4: 跑 577 regression gate**

Expected:

```text
verdict/source page/quality/OCR 无变化
允许 missing_items 更具体
```

---

## 12. 总体验收

完整收尾命令：

```powershell
cd backend
uv run --no-sync pytest --basetemp ..\tmp\pytest-profile-generalization tests/reports tests/tools tests/standards tests/agents/test_disclosure_agent.py -q
```

577 gate：

```powershell
cd backend
uv run --no-sync python -m src.tools.first_pass_quality ../tmp/review/current_577_review_after_rules.csv ../tmp/review/current_577_review_after_profile_routing.csv
```

必须满足：

```text
577 requirement 不变
global_fallback=0
new_disclosed=[]
verdict diff=0
source page diff=0
quality_flags diff=0
OCR/VLM diff=0
compilation_overlap=0
```

---

## 13. 后续计划

完成本计划后，下一阶段再做：

1. 表格标题、页脚页码和 KPI 行识别驱动的 profile 自动生成。
2. 正式跨报告 holdout。
3. 将 holdout 复核结果反向沉淀到 evidence routing 和 ontology matrix。
4. 清理迁移后不再需要的 `SingleReportWorkflow._candidate_page_overrides()` 条目。
5. 将 report profile 导入/导出接入前端或管理工具。

