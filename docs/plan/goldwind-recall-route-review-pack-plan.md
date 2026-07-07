# Goldwind Recall Route Review Pack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 根据 Goldwind recall 诊断表完成自动 route 改进、回归验证和人工复核包生成，最终停在人工作业点。

**Architecture:** 以 `backend/data/holdout/goldwind_2024_recall_gold.json` 和 `tmp/review/holdout_goldwind_2024_recall_diagnosis.csv` 为输入，先提升已确认 route failure 的候选页与证据命中，再生成 route improvement 与 review pack CSV。所有提升必须落在 report profile、evidence routing、KPI row matcher、explicit zero statement routing 或 preview 层；禁止新增 Goldwind per-ID contract。完成自动 gate 后停下，由人工复核 route、preview、unknown leakage 和 false disclosed 风险。

**Tech Stack:** Python 3.11、pytest、`ReportProfile`、`profile_builder`、`EvidenceRouter`、`retrieve_evidence`、`kpi_row_matcher`、`holdout_recall_diagnosis`、`preview_sample_audit`、`first_pass_quality`、`review_csv_audit`。

---

## 硬边界

- 不新增 Goldwind per-ID contract。
- 不把 Goldwind 固定 PDF 页码写入通用 GRI 标准规则。
- Goldwind `source_pdf_page` 是权威定位字段；`source_report_page` 只用于展示。
- GRI index page 只能作为 candidate route 来源，不能作为 `substantive evidence`。
- KPI 召回必须依赖行标签、年份列、单位、数值和 evidence kind。
- explicit zero statement 只能支撑明确零事件或零投诉 leaf，不能传播到罚款、警告、来源分类或历史期间归属 leaf。
- 章节 route 只提供候选页，不直接触发 `disclosed`。
- 任意 `unknown/partial -> disclosed` 变化必须进入人工复核包。

## 停止条件

触发任一条件即暂停并汇报原因：

- `false_disclosed_count > 0`。
- `wrong_source_page_count > 0`。
- `global_fallback_count > 0`。
- `source_pdf_page` 或 `candidate_pdf_pages` 超过 Goldwind 报告总页数 52。
- Goldwind GRI index PDF 50/51 被标为 `substantive evidence`。
- Envision 577 regression 出现 requirement 数量变化。
- Envision 577 regression 出现非预期 verdict / review_status / source page / evidence_type / quality_flags / OCR-VLM 字段变化。
- 需要新增 Goldwind per-ID contract 才能继续提升 recall。
- 自动修复后仍无法判断证据是否有效，需要人工确认。
- focused tests 失败且不能用小范围修复解决。

## 当前目标样本

来自 `backend/data/holdout/goldwind_2024_recall_gold.json`：

- `GRI 205-1-a`：应路由到 PDF 第 21 页，evidence kind 为 `management_mechanism`。
- `GRI 205-1-b`：应路由到 PDF 第 21 页，evidence kind 为 `management_mechanism`。
- `GRI 414-1-a`：应路由到 PDF 第 31-32 页，evidence kind 为 `kpi_value`。
- `GRI 403-9-a-i`：应路由到 PDF 第 47 页，evidence kind 为 `kpi_value`。
- `GRI 418-1-a`：当前 source 错页，需要 route 到客户隐私零投诉实质页，evidence kind 为 `explicit_zero_statement`；若无法自动确认，则进入人工复核包。

## 影响文件

- Modify: `backend/src/reports/profile_builder.py`
- Modify: `backend/src/tools/evidence_routing.py`
- Modify: `backend/src/tools/retrieval.py`
- Modify: `backend/src/tools/kpi_row_matcher.py`
- Modify: `backend/src/tools/evidence.py`
- Create: `backend/src/tools/holdout_review_pack.py`
- Test: `backend/tests/reports/test_profile_builder.py`
- Test: `backend/tests/tools/test_evidence_routing.py`
- Test: `backend/tests/tools/test_retrieval.py`
- Test: `backend/tests/tools/test_kpi_row_matcher.py`
- Test: `backend/tests/tools/test_evidence.py`
- Test: `backend/tests/tools/test_holdout_review_pack.py`
- Modify: `docs/DEVELOPMENT.md`

## 产物

- `tmp/review/holdout_goldwind_2024_route_improvement.csv`
- `tmp/review/holdout_goldwind_2024_review_pack.csv`
- `tmp/review/holdout_goldwind_2024_route_improvement_summary.json`
- `tmp/review/holdout_goldwind_2024_first_pass.csv`
- `tmp/review/holdout_goldwind_2024_reviewed.csv`
- `tmp/review/holdout_goldwind_2024_audit.json`
- `tmp/review/current_577_review_after_profile_routing_regression.csv`
- `tmp/review/current_577_review_after_profile_routing_regression_audit.json`

---

### Task 1: 生成 Route Improvement 基线表

**Files:**
- Create: `backend/src/tools/holdout_review_pack.py`
- Create: `backend/tests/tools/test_holdout_review_pack.py`

- [ ] **Step 1: 写 route improvement 测试**

创建 `backend/tests/tools/test_holdout_review_pack.py`：

```python
from pathlib import Path

from src.tools.holdout_review_pack import build_route_improvement_rows


def test_build_route_improvement_rows_joins_gold_and_first_pass(tmp_path: Path):
    gold = tmp_path / "gold.csv"
    gold.write_text(
        "requirement_id,issue_type,correct_pdf_pages,evidence_kind,suggested_profile_route\n"
        "GRI 414-1-a,unknown_leakage,\"[31, 32]\",kpi_value,\"[31, 32]\"\n",
        encoding="utf-8",
    )
    first_pass = tmp_path / "first.csv"
    first_pass.write_text(
        "requirement_id,verdict,review_status,source_pdf_page,candidate_pdf_pages,evidence_preview\n"
        "GRI 414-1-a,unknown,needs_manual_review,,[],\n",
        encoding="utf-8",
    )

    rows = build_route_improvement_rows(gold, first_pass)

    assert rows[0]["requirement_id"] == "GRI 414-1-a"
    assert rows[0]["before_verdict"] == "unknown"
    assert rows[0]["correct_pdf_pages"] == "[31, 32]"
    assert rows[0]["route_status"] == "missing_candidate"
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```powershell
uv run --no-sync pytest --basetemp ..\tmp\pytest-review-pack tests/tools/test_holdout_review_pack.py -q
```

Expected: FAIL，原因是 `holdout_review_pack.py` 尚未存在。

- [ ] **Step 3: 实现 route improvement 生成函数**

创建 `backend/src/tools/holdout_review_pack.py`：

```python
from __future__ import annotations

import csv
import json
from pathlib import Path


ROUTE_IMPROVEMENT_COLUMNS = [
    "requirement_id",
    "issue_type",
    "evidence_kind",
    "correct_pdf_pages",
    "suggested_profile_route",
    "before_verdict",
    "before_review_status",
    "before_source_pdf_pages",
    "before_candidate_pdf_pages",
    "route_status",
    "evidence_preview",
]


def build_route_improvement_rows(diagnosis_csv: Path, first_pass_csv: Path) -> list[dict[str, str]]:
    diagnosis_rows = _read_csv(diagnosis_csv)
    first_rows = _group_by_requirement(_read_csv(first_pass_csv))
    output: list[dict[str, str]] = []
    for diagnosis in diagnosis_rows:
        requirement_id = diagnosis["requirement_id"]
        rows = first_rows.get(requirement_id, [])
        source_pages = sorted({row["source_pdf_page"] for row in rows if row.get("source_pdf_page")})
        candidate_pages = _first_non_empty(rows, "candidate_pdf_pages")
        correct_pages = diagnosis.get("correct_pdf_pages", "[]")
        output.append(
            {
                "requirement_id": requirement_id,
                "issue_type": diagnosis.get("issue_type", ""),
                "evidence_kind": diagnosis.get("evidence_kind", ""),
                "correct_pdf_pages": correct_pages,
                "suggested_profile_route": diagnosis.get("suggested_profile_route", correct_pages),
                "before_verdict": _first_non_empty(rows, "verdict") or "missing",
                "before_review_status": _first_non_empty(rows, "review_status") or "missing",
                "before_source_pdf_pages": json.dumps(source_pages, ensure_ascii=False),
                "before_candidate_pdf_pages": candidate_pages,
                "route_status": _route_status(candidate_pages, source_pages, correct_pages),
                "evidence_preview": _first_non_empty(rows, "evidence_preview"),
            }
        )
    return output


def write_route_improvement_rows(rows: list[dict[str, str]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ROUTE_IMPROVEMENT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _group_by_requirement(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        grouped.setdefault(row["requirement_id"], []).append(row)
    return grouped


def _first_non_empty(rows: list[dict[str, str]], field: str) -> str:
    for row in rows:
        value = row.get(field, "")
        if value:
            return value
    return ""


def _route_status(candidate_pages: str, source_pages: list[str], correct_pages: str) -> str:
    if not candidate_pages or candidate_pages == "[]":
        return "missing_candidate"
    if not source_pages:
        return "candidate_without_evidence"
    try:
        correct = {str(page) for page in json.loads(correct_pages or "[]")}
    except json.JSONDecodeError:
        correct = set()
    if correct and not correct.intersection(source_pages):
        return "wrong_source"
    return "candidate_with_evidence"
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```powershell
uv run --no-sync pytest --basetemp ..\tmp\pytest-review-pack tests/tools/test_holdout_review_pack.py -q
```

Expected: PASS。

- [ ] **Step 5: 生成 route improvement 基线表**

Run:

```powershell
uv run --no-sync python - <<'PY'
from pathlib import Path
from src.tools.holdout_review_pack import build_route_improvement_rows, write_route_improvement_rows

rows = build_route_improvement_rows(
    Path("../tmp/review/holdout_goldwind_2024_recall_diagnosis.csv"),
    Path("../tmp/review/holdout_goldwind_2024_first_pass.csv"),
)
write_route_improvement_rows(rows, Path("../tmp/review/holdout_goldwind_2024_route_improvement.csv"))
print(len(rows))
PY
```

Expected: 输出 `5`。

- [ ] **Step 6: 提交**

```powershell
git add backend/src/tools/holdout_review_pack.py backend/tests/tools/test_holdout_review_pack.py
git commit -m "feat: add Goldwind route improvement pack"
```

---

### Task 2: 强化 Goldwind Index Route 与 Topic Route

**Files:**
- Modify: `backend/src/reports/profile_builder.py`
- Modify: `backend/tests/reports/test_profile_builder.py`

- [ ] **Step 1: 写 topic route 覆盖 205 和 414 的测试**

在 `backend/tests/reports/test_profile_builder.py` 增加：

```python
def test_profile_builder_expands_goldwind_topic_routes_to_missing_leaf_requirements():
    pages = [
        PageExtraction(
            report_id="goldwind",
            page_number=50,
            text=(
                "GRI 205：反腐败 2016 205-1 已进行腐败风险评估的运营点 P38 "
                "GRI 414：供应商社会评估 2016 414-1 使用社会标准筛选的新供应商 P59-P60"
            ),
        )
    ]
    requirements = [
        DisclosureRequirement(
            standard_id="GRI",
            standard_version="2016",
            disclosure_id="GRI 205-1",
            requirement_id="GRI 205-1-a",
            requirement_text="operations assessed for risks related to corruption",
            keywords=["腐败", "风险评估"],
        ),
        DisclosureRequirement(
            standard_id="GRI",
            standard_version="2016",
            disclosure_id="GRI 414-1",
            requirement_id="GRI 414-1-a",
            requirement_text="new suppliers screened using social criteria",
            keywords=["供应商", "社会标准", "筛选"],
        ),
    ]

    profile = build_initial_profile(
        report_id="goldwind_2024",
        company_name="Goldwind",
        report_year=2024,
        pdf_file="goldwind.pdf",
        total_pdf_pages=52,
        pages=pages,
        report_index_pdf_page=50,
        report_index_report_page=96,
        requirements=requirements,
    )

    assert profile.requirement_routes["GRI 205-1-a"].candidate_pdf_pages == [21]
    assert profile.requirement_routes["GRI 414-1-a"].candidate_pdf_pages == [31, 32]
```

- [ ] **Step 2: 运行测试**

Run:

```powershell
uv run --no-sync pytest --basetemp ..\tmp\pytest-index-topic tests/reports/test_profile_builder.py -q
```

Expected: PASS。如果失败，优先修复 `_extract_disclosure_report_pages()` 或 topic inheritance，不能写 per-ID contract。

- [ ] **Step 3: 重跑 Goldwind holdout**

Run:

```powershell
uv run --no-sync python ../tmp/goldwind_holdout_remediation.py
```

Expected:

- `global_fallback_count=0`
- `max_source_pdf_page <= 52`
- `max_candidate_pdf_page <= 52`

- [ ] **Step 4: 重新生成 route improvement 表**

Run:

```powershell
uv run --no-sync python - <<'PY'
from pathlib import Path
from src.tools.holdout_review_pack import build_route_improvement_rows, write_route_improvement_rows

rows = build_route_improvement_rows(
    Path("../tmp/review/holdout_goldwind_2024_recall_diagnosis.csv"),
    Path("../tmp/review/holdout_goldwind_2024_first_pass.csv"),
)
write_route_improvement_rows(rows, Path("../tmp/review/holdout_goldwind_2024_route_improvement.csv"))
print(len(rows))
PY
```

Expected: 输出 `5`。人工复核前不要求全部 route_status 变为 `candidate_with_evidence`。

- [ ] **Step 5: 提交**

```powershell
git add backend/src/reports/profile_builder.py backend/tests/reports/test_profile_builder.py backend/data/reports/profiles/goldwind_2024.json
git commit -m "feat: improve Goldwind topic route expansion"
```

---

### Task 3: 强化 Explicit Zero Statement Routing

**Files:**
- Modify: `backend/src/tools/retrieval.py`
- Modify: `backend/src/tools/evidence.py`
- Modify: `backend/tests/tools/test_retrieval.py`
- Modify: `backend/tests/tools/test_evidence.py`

- [ ] **Step 1: 写零投诉证据检索测试**

在 `backend/tests/tools/test_retrieval.py` 增加：

```python
def test_retrieve_evidence_matches_explicit_zero_statement_terms():
    task = DisclosureTask(
        task_id="task-418-1-a",
        run_id="run-1",
        report_id="goldwind",
        standard_id="GRI",
        standard_version="2021",
        disclosure_id="GRI 418-1",
        requirement_id="GRI 418-1-a",
        requirement_text="substantiated complaints concerning breaches of customer privacy",
        keywords=["客户隐私", "投诉", "数据丢失"],
        candidate_pages=[30],
        candidate_pdf_pages=[30],
        candidate_report_pages=[56],
        candidate_page_source="report_profile_section",
    )
    chunks = [
        DocumentChunk(
            chunk_id="wrong",
            report_id="goldwind",
            text="员工福利和住房公积金。",
            source_page=40,
            source_method=EvidenceSourceMethod.PDFPLUMBER,
            source_file_hash="hash",
        ),
        DocumentChunk(
            chunk_id="privacy",
            report_id="goldwind",
            text="报告期内，公司未接到任何涉及侵犯客户隐私或数据丢失的投诉。",
            source_page=30,
            source_method=EvidenceSourceMethod.PDFPLUMBER,
            source_file_hash="hash",
        ),
    ]

    evidence = retrieve_evidence(task, chunks)

    assert [item.source_page for item in evidence] == [30]
    assert "客户隐私" in evidence[0].evidence_preview
```

- [ ] **Step 2: 运行测试**

Run:

```powershell
uv run --no-sync pytest --basetemp ..\tmp\pytest-zero-statement tests/tools/test_retrieval.py tests/tools/test_evidence.py -q
```

Expected: PASS。如果失败，只允许改关键词窗口、preview 或 retrieval metadata，不允许新增 per-ID contract。

- [ ] **Step 3: 重跑 Goldwind holdout 与 quality diff**

Run:

```powershell
uv run --no-sync python ../tmp/goldwind_holdout_remediation.py
uv run --no-sync python -m src.tools.first_pass_quality ../tmp/review/holdout_goldwind_2024_first_pass.csv ../tmp/review/holdout_goldwind_2024_reviewed.csv
```

Expected:

- `false_disclosed_count=0`
- `wrong_source_page_count=0`
- `global_fallback_count=0`

若 `GRI 418-1-a` 仍未自动找到正确 source，继续保留在 review pack，不得写 per-ID contract。

- [ ] **Step 4: 提交**

```powershell
git add backend/src/tools/retrieval.py backend/src/tools/evidence.py backend/tests/tools/test_retrieval.py backend/tests/tools/test_evidence.py
git commit -m "feat: improve explicit zero statement retrieval"
```

---

### Task 4: 生成 Review Pack

**Files:**
- Modify: `backend/src/tools/holdout_review_pack.py`
- Modify: `backend/tests/tools/test_holdout_review_pack.py`

- [ ] **Step 1: 写 review pack 测试**

在 `backend/tests/tools/test_holdout_review_pack.py` 增加：

```python
from src.tools.holdout_review_pack import build_review_pack_rows


def test_build_review_pack_rows_marks_manual_review_need(tmp_path: Path):
    route_improvement = tmp_path / "routes.csv"
    route_improvement.write_text(
        "requirement_id,issue_type,evidence_kind,correct_pdf_pages,suggested_profile_route,before_verdict,before_review_status,before_source_pdf_pages,before_candidate_pdf_pages,route_status,evidence_preview\n"
        "GRI 414-1-a,unknown_leakage,kpi_value,\"[31, 32]\",\"[31, 32]\",unknown,needs_manual_review,[],[],missing_candidate,\n",
        encoding="utf-8",
    )

    rows = build_review_pack_rows(route_improvement)

    assert rows[0]["manual_check_required"] == "true"
    assert rows[0]["manual_check_focus"] == "route_and_preview"
```

- [ ] **Step 2: 实现 review pack 生成函数**

在 `backend/src/tools/holdout_review_pack.py` 增加：

```python
REVIEW_PACK_COLUMNS = [
    "requirement_id",
    "issue_type",
    "evidence_kind",
    "correct_pdf_pages",
    "suggested_profile_route",
    "current_route_status",
    "manual_check_required",
    "manual_check_focus",
    "manual_label",
    "correct_source_pdf_pages",
    "suggested_verdict",
    "review_note",
    "evidence_preview",
]


def build_review_pack_rows(route_improvement_csv: Path) -> list[dict[str, str]]:
    rows = _read_csv(route_improvement_csv)
    output: list[dict[str, str]] = []
    for row in rows:
        focus = "route_and_preview"
        if row.get("issue_type") == "false_disclosed":
            focus = "false_disclosed_boundary"
        output.append(
            {
                "requirement_id": row["requirement_id"],
                "issue_type": row.get("issue_type", ""),
                "evidence_kind": row.get("evidence_kind", ""),
                "correct_pdf_pages": row.get("correct_pdf_pages", ""),
                "suggested_profile_route": row.get("suggested_profile_route", ""),
                "current_route_status": row.get("route_status", ""),
                "manual_check_required": "true",
                "manual_check_focus": focus,
                "manual_label": "",
                "correct_source_pdf_pages": "",
                "suggested_verdict": "",
                "review_note": "",
                "evidence_preview": row.get("evidence_preview", ""),
            }
        )
    return output


def write_review_pack_rows(rows: list[dict[str, str]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_PACK_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
```

- [ ] **Step 3: 运行测试**

Run:

```powershell
uv run --no-sync pytest --basetemp ..\tmp\pytest-review-pack tests/tools/test_holdout_review_pack.py -q
```

Expected: PASS。

- [ ] **Step 4: 生成 review pack**

Run:

```powershell
uv run --no-sync python - <<'PY'
from pathlib import Path
from src.tools.holdout_review_pack import build_review_pack_rows, write_review_pack_rows

rows = build_review_pack_rows(Path("../tmp/review/holdout_goldwind_2024_route_improvement.csv"))
write_review_pack_rows(rows, Path("../tmp/review/holdout_goldwind_2024_review_pack.csv"))
print(len(rows))
PY
```

Expected: 输出 `5`。

- [ ] **Step 5: 提交**

```powershell
git add backend/src/tools/holdout_review_pack.py backend/tests/tools/test_holdout_review_pack.py
git commit -m "feat: generate Goldwind recall review pack"
```

---

### Task 5: 最终 Gate 与人工核查交付

**Files:**
- Modify: `docs/DEVELOPMENT.md`
- Read: `tmp/review/holdout_goldwind_2024_route_improvement.csv`
- Read: `tmp/review/holdout_goldwind_2024_review_pack.csv`
- Read: `tmp/review/holdout_goldwind_2024_route_improvement_summary.json`

- [ ] **Step 1: 运行 focused tests**

Run:

```powershell
uv run --no-sync pytest --basetemp ..\tmp\pytest-goldwind-route-pack tests/tools/test_holdout_review_pack.py tests/tools/test_holdout_recall_diagnosis.py tests/tools/test_kpi_row_matcher.py tests/tools/test_preview_sample_audit.py tests/tools/test_retrieval.py tests/tools/test_evidence.py tests/tools/test_evidence_routing.py tests/reports/test_profile_builder.py -q
```

Expected: PASS。

- [ ] **Step 2: 跑 Goldwind holdout**

Run:

```powershell
uv run --no-sync python ../tmp/goldwind_holdout_remediation.py
```

Expected:

- `global_fallback_count=0`
- `max_source_pdf_page <= 52`
- `max_candidate_pdf_page <= 52`

- [ ] **Step 3: 跑 Goldwind audit 和 quality diff**

Run:

```powershell
uv run --no-sync python - <<'PY'
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
PY
uv run --no-sync python -m src.tools.first_pass_quality ../tmp/review/holdout_goldwind_2024_first_pass.csv ../tmp/review/holdout_goldwind_2024_reviewed.csv
```

Expected:

- audit `ok=true`
- `false_disclosed_count=0`
- `wrong_source_page_count=0`

- [ ] **Step 4: 跑 Envision 577 regression**

按当前项目已使用的 Envision regression 脚本重新生成 `tmp/review/current_577_review_after_profile_routing_regression.csv` 后运行：

```powershell
uv run --no-sync python -m src.tools.first_pass_quality ../tmp/review/current_577_review_after_profile_routing.csv ../tmp/review/current_577_review_after_profile_routing_regression.csv
```

Expected:

- 577 requirement 数量不变
- `after_rules_delta_disclosed=0`
- `after_rules_delta_partial=0`
- `after_rules_delta_unknown=0`

- [ ] **Step 5: 生成 summary JSON**

Run:

```powershell
uv run --no-sync python - <<'PY'
import csv
import json
from collections import Counter
from pathlib import Path

review_dir = Path("../tmp/review")
routes = list(csv.DictReader((review_dir / "holdout_goldwind_2024_route_improvement.csv").open(encoding="utf-8-sig", newline="")))
pack = list(csv.DictReader((review_dir / "holdout_goldwind_2024_review_pack.csv").open(encoding="utf-8-sig", newline="")))
summary = {
    "route_improvement_rows": len(routes),
    "review_pack_rows": len(pack),
    "route_status_counts": dict(Counter(row["route_status"] for row in routes)),
    "manual_check_required_count": sum(1 for row in pack if row["manual_check_required"] == "true"),
    "stop_at": "manual_review",
}
(review_dir / "holdout_goldwind_2024_route_improvement_summary.json").write_text(
    json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
print(json.dumps(summary, ensure_ascii=False, indent=2))
PY
```

Expected:

- `route_improvement_rows=5`
- `review_pack_rows=5`
- `stop_at=manual_review`

- [ ] **Step 6: 扫描 docs 本机绝对路径**

Run:

```powershell
$matches = rg '[A-Za-z]:\\' docs README.md 2>$null; if ($LASTEXITCODE -eq 0) { $matches; exit 1 } else { 'no absolute paths found' }
```

Expected: `no absolute paths found`。

- [ ] **Step 7: 更新开发记录**

在 `docs/DEVELOPMENT.md` 增加记录：

- route improvement rows 数量。
- review pack rows 数量。
- Goldwind gate 是否通过。
- Envision 577 regression 是否无回退。
- 当前停止点为人工核查 `tmp/review/holdout_goldwind_2024_review_pack.csv`。

- [ ] **Step 8: 提交**

```powershell
git add docs/DEVELOPMENT.md
git commit -m "docs: record Goldwind recall review pack"
```

若 `tmp/review/` 被 `.gitignore` 忽略，最终汇报必须列出未提交产物路径：

- `tmp/review/holdout_goldwind_2024_route_improvement.csv`
- `tmp/review/holdout_goldwind_2024_review_pack.csv`
- `tmp/review/holdout_goldwind_2024_route_improvement_summary.json`

---

## 人工核查交付要求

执行完成后暂停，并请人工复核：

- `tmp/review/holdout_goldwind_2024_review_pack.csv`

人工复核字段：

- `manual_label`
- `correct_source_pdf_pages`
- `suggested_verdict`
- `review_note`

人工复核重点：

- route 是否命中正确 PDF 页。
- preview 是否包含目标证据。
- unknown 是否仍有明显漏检。
- 是否出现新的 false disclosed。
- 是否允许进入下一轮 report profile builder 泛化。

## 验收标准

- `tmp/review/holdout_goldwind_2024_route_improvement.csv` 已生成。
- `tmp/review/holdout_goldwind_2024_review_pack.csv` 已生成。
- `tmp/review/holdout_goldwind_2024_route_improvement_summary.json` 已生成。
- Goldwind first-pass/reviewed audit 通过。
- `false_disclosed_count=0`。
- `wrong_source_page_count=0`。
- `global_fallback_count=0`。
- Goldwind PDF 页码不超过 52。
- Goldwind GRI index PDF 50/51 未作为 `substantive evidence`。
- Envision 577 regression 无回退。
- 未新增 Goldwind per-ID contract。
- docs 不包含本机绝对路径。
- 最终停在人工作业点，不自动进入下一阶段优化。

## 执行建议

建议 inline 执行。原因是该计划依赖同一批 Goldwind holdout 临时产物和 Envision regression gate，串行执行更容易保持状态一致。不要并行生成 review pack 与改 routing，避免使用过期 first-pass CSV。
