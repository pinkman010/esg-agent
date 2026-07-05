# Ontology Regression Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 requirement/evidence ontology refactor 后，重跑 577 条 eligible requirement，验证 verdict、evidence、页码字段和 hard gate 没有回退，并只对差异项做人工复核。

**Architecture:** 以 `current_577_review_after_rules.csv` 作为基准，生成 ontology 后的新 review CSV，再通过 review audit、diff 和 first-pass quality 工具做机器验收。84 条 `compilation_requirement` 不作为独立 assessment 重跑，只用于 guardrail、`missing_items` 和充分性规则校验。

**Tech Stack:** Python 3.11、pytest、现有 `SingleReportWorkflow`、`review_csv_audit`、`first_pass_quality`、review CSV artifacts。

---

## 1. 背景

当前 checklist 总数为 661 条，其中独立 evidence assessment 口径下实际进入核查的是 577 条 eligible requirement。剩余 84 条为 `compilation_requirement`，已通过 `tmp/review/compilation_requirement_mapping_fixed.csv` 映射为充分性规则、`missing_items` 和 guardrail，不应生成独立 `disclosed` / `partially_disclosed` / `unknown` assessment。

本次 ontology refactor 已引入 requirement facet、evidence kind、semantic group 和 verdict matrix。下一步需要确认这次抽象没有改变已经人工复核通过的 577 条结果，尤其不能引入 disclosed 误升、`omission_note` 升格、KPI 表质量标记缺失或页码双轨字段回退。

## 2. 不做范围

- 不把 84 条 `compilation_requirement` 作为独立 assessment 执行。
- 不调用外部模型。
- 不新增 OCR/VLM 实调用。
- 不继续逐 ID 补业务规则，除非 regression diff 暴露明确 bug。
- 不以固定 PDF 页码作为跨报告通用逻辑；页码只用于当前报告回归样本。
- 不重新人工复核 577 条全量结果，只复核机器 diff 标出的变化项。

## 3. 输入与输出

输入文件：

- `tmp/review/current_577_review_after_rules.csv`
- `tmp/review/compilation_requirement_mapping_fixed.csv`
- 当前已导入数据库或 workflow 可读取的 Envision 2024 报告与 GRI checklist。

输出文件：

- `tmp/review/current_577_review_after_ontology.csv`
- `tmp/review/current_577_review_after_ontology_audit.json`
- `tmp/review/current_577_review_ontology_diff.csv`
- `tmp/review/current_577_review_ontology_diff_summary.json`

## 4. 验收标准

硬门禁：

- `global_fallback=0`。
- `page_label` 无 `?` 乱码，也无字面量 `\u`。
- `source_pdf_page` 和 `candidate_pdf_pages` 不超过报告总页数。
- `omission_note` 不得升为 `disclosed` 或 `partially_disclosed`。
- KPI 表 evidence 必须包含 `complex_table`。
- PDF 第 77 页鉴证页 OCR/VLM 风险标记不得回退。
- `disclosed` 必须对应 `not_required`。
- `partially_disclosed` 和 `unknown` 必须对应 `needs_manual_review`。

差异验收：

- `disclosed` 数量不得异常增加；任何新增 `disclosed` 必须进入人工复核。
- `unknown` 数量减少必须能被 evidence kind 和 semantic group 解释。
- evidence 页码变化必须保留正确 `source_pdf_page` / `source_report_page` / `page_label`。
- `compilation_requirement` 不得出现在独立 assessment 输出中。
- 84 条 compilation mapping 只作为 guardrail / missing item 来源，不得产生新 assessment 行。

## 5. 文件职责

- `backend/src/agents/single_report_workflow.py`
  - 用于重新生成 577 条 review CSV。若已有命令或脚本可生成 review CSV，优先复用现有入口。
- `backend/src/tools/review_csv_audit.py`
  - 对 ontology 后 CSV 执行 hard gate。
- `backend/src/tools/first_pass_quality.py`
  - 输出 first-pass / after-rules delta；本次用于确认工具能处理真实 CSV。
- `tmp/review/current_577_review_ontology_diff.csv`
  - 只保存变化行，供人工复核。
- `tmp/review/current_577_review_ontology_diff_summary.json`
  - 保存 verdict、review_status、evidence page、evidence type、quality flag 变化统计。

## 6. Task 1：确认基准文件和环境

**Files:**
- Read: `tmp/review/current_577_review_after_rules.csv`
- Read: `tmp/review/compilation_requirement_mapping_fixed.csv`
- Read: `docs/DEVELOPMENT.md`

- [ ] **Step 1: 检查基准文件存在**

Run:

```powershell
Test-Path tmp/review/current_577_review_after_rules.csv
Test-Path tmp/review/compilation_requirement_mapping_fixed.csv
```

Expected:

```text
True
True
```

- [ ] **Step 2: 统计基准唯一 requirement**

Run:

```powershell
cd backend
@'
import csv
from pathlib import Path

path = Path("../tmp/review/current_577_review_after_rules.csv")
with path.open("r", encoding="utf-8-sig", newline="") as handle:
    rows = list(csv.DictReader(handle))
ids = {row["requirement_id"] for row in rows if row.get("requirement_id")}
print("rows=", len(rows))
print("unique_requirements=", len(ids))
'@ | uv run --no-sync python -
```

Expected:

```text
unique_requirements= 577
```

若输出不是 577，停止执行，先确认当前基准文件是否命名或生成口径变化。

## 7. Task 2：生成 ontology 后 577 条 review CSV

**Files:**
- Create: `tmp/review/current_577_review_after_ontology.csv`

- [ ] **Step 1: 使用现有 workflow 重新生成 review CSV**

优先复用项目当前生成 review CSV 的入口。若当前没有封装命令，使用现有脚本或 Python inline 调用 `SingleReportWorkflow`，保持以下约束：

- `confirm_llm=false`
- 不调用外部模型
- 输出路径为 `tmp/review/current_577_review_after_ontology.csv`
- requirement 过滤口径保持：`assessment_mode=current_gap`、`requirement_type=requirement`、`is_mandatory=True`、`scoring_role=hard_score`

Expected:

```text
生成 tmp/review/current_577_review_after_ontology.csv
唯一 requirement 数为 577
```

- [ ] **Step 2: 检查 84 条 compilation requirement 未进入独立 assessment**

Run:

```powershell
cd backend
@'
import csv
from pathlib import Path

review_path = Path("../tmp/review/current_577_review_after_ontology.csv")
mapping_path = Path("../tmp/review/compilation_requirement_mapping_fixed.csv")

with review_path.open("r", encoding="utf-8-sig", newline="") as handle:
    review_ids = {row["requirement_id"] for row in csv.DictReader(handle) if row.get("requirement_id")}

with mapping_path.open("r", encoding="utf-8-sig", newline="") as handle:
    compilation_ids = {
        row["compilation_requirement_id"]
        for row in csv.DictReader(handle)
        if row.get("compilation_requirement_id") and row.get("mapping_status") != "remove"
    }

overlap = sorted(review_ids & compilation_ids)
print("compilation_overlap=", len(overlap))
print(overlap[:20])
'@ | uv run --no-sync python -
```

Expected:

```text
compilation_overlap= 0
```

## 8. Task 3：执行 review CSV hard gate

**Files:**
- Create: `tmp/review/current_577_review_after_ontology_audit.json`

- [ ] **Step 1: 运行 audit**

Run:

```powershell
cd backend
@'
import json
from dataclasses import asdict
from pathlib import Path
from src.tools.review_csv_audit import audit_review_csv

result = audit_review_csv("../tmp/review/current_577_review_after_ontology.csv", report_total_pages=78)
payload = asdict(result)
Path("../tmp/review/current_577_review_after_ontology_audit.json").write_text(
    json.dumps(payload, ensure_ascii=False, indent=2),
    encoding="utf-8",
)
print("ok=", result.ok)
print("errors=", result.errors)
print("warnings=", result.warnings)
'@ | uv run --no-sync python -
```

Expected:

```text
ok= True
errors= []
```

若 `errors` 非空，停止执行并先修 hard gate 问题。

## 9. Task 4：生成 ontology diff

**Files:**
- Create: `tmp/review/current_577_review_ontology_diff.csv`
- Create: `tmp/review/current_577_review_ontology_diff_summary.json`

- [ ] **Step 1: 对比基准和 ontology 后 CSV**

Run:

```powershell
cd backend
@'
import csv
import json
from pathlib import Path

before_path = Path("../tmp/review/current_577_review_after_rules.csv")
after_path = Path("../tmp/review/current_577_review_after_ontology.csv")
diff_path = Path("../tmp/review/current_577_review_ontology_diff.csv")
summary_path = Path("../tmp/review/current_577_review_ontology_diff_summary.json")

KEY_FIELDS = [
    "verdict",
    "review_status",
    "source_pdf_page",
    "source_report_page",
    "page_label",
    "evidence_type",
    "retrieval_strategy",
    "quality_flags",
    "needs_ocr_or_vlm",
    "requires_ocr",
    "requires_vlm",
    "evidence_preview",
    "missing_items",
]

def read_first_rows(path):
    rows = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            requirement_id = row.get("requirement_id", "")
            if requirement_id and requirement_id not in rows:
                rows[requirement_id] = row
    return rows

before = read_first_rows(before_path)
after = read_first_rows(after_path)
all_ids = sorted(set(before) | set(after))

diff_rows = []
summary = {
    "before_count": len(before),
    "after_count": len(after),
    "added_requirements": [],
    "removed_requirements": [],
    "changed_requirements": 0,
    "changed_by_field": {field: 0 for field in KEY_FIELDS},
    "new_disclosed": [],
}

for requirement_id in all_ids:
    before_row = before.get(requirement_id)
    after_row = after.get(requirement_id)
    if before_row is None:
        summary["added_requirements"].append(requirement_id)
        continue
    if after_row is None:
        summary["removed_requirements"].append(requirement_id)
        continue

    changed_fields = [
        field
        for field in KEY_FIELDS
        if (before_row.get(field) or "") != (after_row.get(field) or "")
    ]
    if not changed_fields:
        continue

    summary["changed_requirements"] += 1
    for field in changed_fields:
        summary["changed_by_field"][field] += 1
    if before_row.get("verdict") != "disclosed" and after_row.get("verdict") == "disclosed":
        summary["new_disclosed"].append(requirement_id)

    diff_rows.append({
        "requirement_id": requirement_id,
        "changed_fields": ";".join(changed_fields),
        "before_verdict": before_row.get("verdict", ""),
        "after_verdict": after_row.get("verdict", ""),
        "before_review_status": before_row.get("review_status", ""),
        "after_review_status": after_row.get("review_status", ""),
        "before_source_pdf_page": before_row.get("source_pdf_page", ""),
        "after_source_pdf_page": after_row.get("source_pdf_page", ""),
        "before_page_label": before_row.get("page_label", ""),
        "after_page_label": after_row.get("page_label", ""),
        "before_evidence_preview": before_row.get("evidence_preview", ""),
        "after_evidence_preview": after_row.get("evidence_preview", ""),
        "manual_review_required": "yes",
    })

fieldnames = [
    "requirement_id",
    "changed_fields",
    "before_verdict",
    "after_verdict",
    "before_review_status",
    "after_review_status",
    "before_source_pdf_page",
    "after_source_pdf_page",
    "before_page_label",
    "after_page_label",
    "before_evidence_preview",
    "after_evidence_preview",
    "manual_review_required",
]
with diff_path.open("w", encoding="utf-8-sig", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(diff_rows)

summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=2))
'@ | uv run --no-sync python -
```

Expected:

```text
"before_count": 577
"after_count": 577
"added_requirements": []
"removed_requirements": []
```

若出现新增或删除 requirement，停止执行，先查过滤口径。

## 10. Task 5：运行 first-pass quality 工具

**Files:**
- Read: `tmp/review/current_577_review_after_rules.csv`
- Read: `tmp/review/current_577_review_after_ontology.csv`

- [ ] **Step 1: 运行 CLI**

Run:

```powershell
cd backend
uv run --no-sync python -m src.tools.first_pass_quality ../tmp/review/current_577_review_after_rules.csv ../tmp/review/current_577_review_after_ontology.csv
```

Expected:

```text
输出 JSON，包含 first_pass_recall、false_disclosed_count、wrong_source_page_count、unknown_leakage_count、after_rules_delta_disclosed
```

说明：基准 CSV 若没有人工 gold 字段，`false_disclosed_count`、`wrong_source_page_count` 和 `unknown_leakage_count` 可以为 0；本步骤主要确认工具可处理真实 CSV，并观察 verdict delta。

## 11. Task 6：人工复核 diff

**Files:**
- Read: `tmp/review/current_577_review_ontology_diff.csv`
- Update: `tmp/review/current_577_review_ontology_diff.csv`

- [ ] **Step 1: 复核新增 disclosed**

打开 `tmp/review/current_577_review_ontology_diff.csv`，优先筛选：

```text
before_verdict != disclosed
after_verdict == disclosed
```

每一条新增 `disclosed` 必须确认：

- evidence 页码正确。
- evidence preview 直接覆盖 leaf requirement。
- 无 `omission_note` 或 `index_statement` 误升。
- 若来自 KPI，`quality_flags` 包含 `complex_table`。
- `review_status=not_required` 合理。

- [ ] **Step 2: 复核 evidence 页码变化**

筛选 `changed_fields` 包含：

```text
source_pdf_page
source_report_page
page_label
evidence_preview
```

人工确认：

- 页码双轨映射正确。
- preview 变化来自 KPI 行级锚点或 evidence kind 改进。
- 没有用页首截断替代目标证据。

- [ ] **Step 3: 复核 unknown 减少**

筛选：

```text
before_verdict == unknown
after_verdict in disclosed / partially_disclosed
```

人工确认：

- `partially_disclosed` 的 `missing_items` 能解释缺口。
- `disclosed` 只用于 leaf 要求被直接覆盖的情形。
- 政策、机制、案例没有替代具体数量、比例、拆分或风险结果。

## 12. Task 7：结论与提交

**Files:**
- Read: `tmp/review/current_577_review_ontology_diff_summary.json`
- Read: `tmp/review/current_577_review_after_ontology_audit.json`

- [ ] **Step 1: 形成验收结论**

在最终回复中报告：

- `review_csv_audit` 是否通过。
- 577 条 requirement 是否保持 577。
- 新增/删除 requirement 是否为 0。
- diff 行数。
- 新增 disclosed 数量。
- 是否需要人工复核阻塞项。

- [ ] **Step 2: 若无阻塞，提交**

Run:

```powershell
git status --short
git add backend/src/standards/evidence_ontology.py backend/src/standards/evidence_contracts.py backend/src/agents/disclosure_agent.py backend/src/tools/first_pass_quality.py backend/tests/standards/test_evidence_ontology.py backend/tests/standards/test_evidence_contracts.py backend/tests/agents/test_disclosure_agent.py backend/tests/tools/test_first_pass_quality.py docs/DEVELOPMENT.md docs/plan/ontology-regression-validation-plan.md
git commit -m "feat: add requirement evidence ontology matrix"
```

Expected:

```text
提交成功
```

若 diff 人工复核发现阻塞问题，先修复并重新执行 Task 2 至 Task 6。

## 13. 最小测试命令

执行本计划前后至少运行：

```powershell
cd backend
uv run --no-sync pytest tests/standards/test_evidence_ontology.py tests/standards/test_evidence_contracts.py tests/tools/test_evidence.py tests/tools/test_review_csv_audit.py tests/tools/test_first_pass_quality.py tests/agents/test_disclosure_agent.py -q
```

Expected:

```text
全部通过
```

## 14. 自查清单

- [ ] 计划文件未写入本机绝对路径。
- [ ] 84 条 `compilation_requirement` 未作为独立 assessment。
- [ ] 所有命令使用相对路径。
- [ ] 未要求调用外部模型。
- [ ] 未把固定页码写成跨报告通用规则。
- [ ] diff 只作为人工复核入口，不自动确认 ontology 后结果全部正确。
