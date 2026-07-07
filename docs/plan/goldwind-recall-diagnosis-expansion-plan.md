# Goldwind Recall Diagnosis Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 扩充 Goldwind holdout recall 诊断表，并用 report-agnostic 的 KPI 表识别、章节路由和 preview 抽样机制继续提升召回能力。

**Architecture:** 先把人工复核结论结构化为可复用 gold case，区分 candidate route 缺失、关键词未命中、matrix 保守、source page 错误和 profile 映射问题。随后按上游到下游顺序增强 KPI 表自动识别、章节 route 精细化和 preview 抽样复核；每轮都用 Goldwind holdout 与 Envision 577 regression gate 验收。禁止新增 Goldwind per-ID contract，所有提升必须落在 profile builder、evidence routing、KPI row matcher、ontology/evidence kind 或 preview 层。

**Tech Stack:** Python 3.11、pytest、`ReportProfile`、`profile_builder`、`EvidenceRouter`、`kpi_row_matcher`、`holdout_recall_diagnosis`、`first_pass_quality`、`review_csv_audit`。

---

## 硬边界

- 不新增 Goldwind per-ID contract。
- 不把 Goldwind 固定 PDF 页码写进通用 GRI 标准规则。
- Goldwind `source_pdf_page` 是权威定位字段；`source_report_page` 只用于展示和人工阅读。
- GRI index page 只能作为 candidate route 来源，不能作为 `substantive evidence`。
- KPI 页召回必须依赖行标签、年份列、单位、数值和 evidence kind。
- 章节 route 只提供候选页和语义标签，不能直接触发 `disclosed`。
- 任意 `unknown/partial -> disclosed` 变化必须人工复核。
- 每轮优化都必须跑 Goldwind holdout audit 和 Envision 577 regression gate。

## 停止条件

触发任一条件即暂停并汇报原因：

- `false_disclosed_count > 0`。
- `wrong_source_page_count > 0`。
- `global_fallback_count > 0`。
- `source_pdf_page` 或 `candidate_pdf_pages` 超过 Goldwind 报告总页数。
- Goldwind GRI index PDF 50/51 被标为 `substantive evidence`。
- Envision 577 regression 出现 requirement 数量变化。
- Envision 577 regression 出现非预期 verdict / review_status / source page / evidence_type / quality_flags / OCR-VLM 字段变化。
- 为提升 recall 需要新增 Goldwind per-ID contract。
- focused tests 失败且不能用小范围修复解决。

## 影响文件

- Modify: `backend/src/tools/holdout_recall_diagnosis.py`
- Create: `backend/data/holdout/goldwind_2024_recall_gold.json`
- Modify: `backend/tests/tools/test_holdout_recall_diagnosis.py`
- Modify: `backend/src/tools/kpi_row_matcher.py`
- Modify: `backend/tests/tools/test_kpi_row_matcher.py`
- Modify: `backend/src/reports/profile_builder.py`
- Modify: `backend/tests/reports/test_profile_builder.py`
- Modify: `backend/src/tools/evidence_routing.py`
- Modify: `backend/tests/tools/test_evidence_routing.py`
- Modify: `backend/src/tools/evidence.py`
- Modify: `backend/tests/tools/test_evidence.py`
- Modify: `docs/DEVELOPMENT.md`

## 产物

- `backend/data/holdout/goldwind_2024_recall_gold.json`
- `tmp/review/holdout_goldwind_2024_recall_diagnosis.csv`
- `tmp/review/holdout_goldwind_2024_first_pass.csv`
- `tmp/review/holdout_goldwind_2024_reviewed.csv`
- `tmp/review/holdout_goldwind_2024_quality_summary.json`
- `tmp/review/holdout_goldwind_2024_audit.json`
- `tmp/review/current_577_review_after_profile_routing_regression.csv`
- `tmp/review/current_577_review_after_profile_routing_regression_audit.json`

---

### Task 1: 扩充 Goldwind Recall Gold 数据

**Files:**
- Create: `backend/data/holdout/goldwind_2024_recall_gold.json`
- Modify: `backend/src/tools/holdout_recall_diagnosis.py`
- Modify: `backend/tests/tools/test_holdout_recall_diagnosis.py`

- [ ] **Step 1: 写 gold JSON loader 测试**

在 `backend/tests/tools/test_holdout_recall_diagnosis.py` 增加：

```python
import json

from src.tools.holdout_recall_diagnosis import load_manual_gold


def test_load_manual_gold_indexes_cases_by_requirement_id(tmp_path):
    source = tmp_path / "gold.json"
    source.write_text(
        json.dumps(
            [
                {
                    "requirement_id": "GRI 414-1-a",
                    "issue_type": "unknown_leakage",
                    "correct_pdf_pages": [31, 32],
                    "evidence_kind": "kpi_value",
                    "route_failure_reason": "candidate_pages_present_keyword_miss",
                    "suggested_profile_route": [31, 32],
                    "review_note": "PDF 第 31-32 页包含供应商社会评价 KPI。",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    gold = load_manual_gold(source)

    assert gold["GRI 414-1-a"]["correct_pdf_pages"] == [31, 32]
    assert gold["GRI 414-1-a"]["evidence_kind"] == "kpi_value"
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```powershell
uv run --no-sync pytest --basetemp ..\tmp\pytest-recall-gold tests/tools/test_holdout_recall_diagnosis.py -q
```

Expected: FAIL，原因是 `load_manual_gold` 尚未存在。

- [ ] **Step 3: 实现 gold JSON loader**

在 `backend/src/tools/holdout_recall_diagnosis.py` 增加：

```python
def load_manual_gold(path: Path) -> dict[str, dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("manual gold must be a list of case objects")

    cases: dict[str, dict[str, Any]] = {}
    for item in raw:
        requirement_id = str(item.get("requirement_id", "")).strip()
        if not requirement_id:
            raise ValueError("manual gold case missing requirement_id")
        if requirement_id in cases:
            raise ValueError(f"duplicate manual gold case: {requirement_id}")
        pages = item.get("correct_pdf_pages", [])
        if not isinstance(pages, list) or not all(isinstance(page, int) for page in pages):
            raise ValueError(f"correct_pdf_pages must be integer list for {requirement_id}")
        cases[requirement_id] = dict(item)
    return cases
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```powershell
uv run --no-sync pytest --basetemp ..\tmp\pytest-recall-gold tests/tools/test_holdout_recall_diagnosis.py -q
```

Expected: PASS。

- [ ] **Step 5: 写入扩充版 gold case**

创建 `backend/data/holdout/goldwind_2024_recall_gold.json`。第一版至少包含人工复核中明确的三类样本：

```json
[
  {
    "requirement_id": "GRI 205-1-a",
    "issue_type": "unknown_leakage",
    "correct_pdf_pages": [21],
    "evidence_kind": "management_mechanism",
    "route_failure_reason": "wrong_source_page",
    "suggested_profile_route": [21],
    "review_note": "反腐败风险评估应回到实质披露页，不能停留在 GRI 索引或无关页。"
  },
  {
    "requirement_id": "GRI 205-1-b",
    "issue_type": "unknown_leakage",
    "correct_pdf_pages": [21],
    "evidence_kind": "management_mechanism",
    "route_failure_reason": "wrong_source_page",
    "suggested_profile_route": [21],
    "review_note": "腐败风险类型或管理机制需要实质披露页。"
  },
  {
    "requirement_id": "GRI 414-1-a",
    "issue_type": "unknown_leakage",
    "correct_pdf_pages": [31, 32],
    "evidence_kind": "kpi_value",
    "route_failure_reason": "candidate_pages_present_keyword_miss",
    "suggested_profile_route": [31, 32],
    "review_note": "供应商社会评价筛选比例应由 KPI 行标签匹配。"
  },
  {
    "requirement_id": "GRI 403-9-a-i",
    "issue_type": "unknown_leakage",
    "correct_pdf_pages": [47],
    "evidence_kind": "kpi_value",
    "route_failure_reason": "candidate_pages_present_keyword_miss",
    "suggested_profile_route": [47],
    "review_note": "工伤死亡数量和死亡率应由 KPI 行标签匹配。"
  },
  {
    "requirement_id": "GRI 418-1-a",
    "issue_type": "false_disclosed",
    "correct_pdf_pages": [],
    "evidence_kind": "explicit_zero_statement",
    "route_failure_reason": "wrong_source_page",
    "suggested_profile_route": [],
    "review_note": "Goldwind first-pass 曾将无关证据升为 disclosed，零投诉声明需要正确 source page 和分类边界。"
  }
]
```

允许在执行时继续补充人工复核中已明确的 case，但不得凭推测新增未复核 case。

- [ ] **Step 6: 生成诊断表**

Run:

```powershell
uv run --no-sync python - <<'PY'
from pathlib import Path
from src.tools.holdout_recall_diagnosis import (
    build_recall_diagnosis_rows,
    load_manual_gold,
    write_recall_diagnosis_csv,
)

gold = load_manual_gold(Path("data/holdout/goldwind_2024_recall_gold.json"))
rows = build_recall_diagnosis_rows(
    first_pass_csv=Path("../tmp/review/holdout_goldwind_2024_first_pass.csv"),
    manual_gold=gold,
)
write_recall_diagnosis_csv(rows, Path("../tmp/review/holdout_goldwind_2024_recall_diagnosis.csv"))
print(len(rows))
PY
```

Expected: 输出行数等于 `goldwind_2024_recall_gold.json` 中 case 数。

- [ ] **Step 7: 提交**

```powershell
git add backend/src/tools/holdout_recall_diagnosis.py backend/tests/tools/test_holdout_recall_diagnosis.py backend/data/holdout/goldwind_2024_recall_gold.json
git commit -m "test: expand Goldwind recall diagnosis cases"
```

---

### Task 2: 增强 KPI 表自动识别

**Files:**
- Modify: `backend/src/tools/kpi_row_matcher.py`
- Modify: `backend/tests/tools/test_kpi_row_matcher.py`

- [ ] **Step 1: 写多行 KPI 表自动匹配测试**

在 `backend/tests/tools/test_kpi_row_matcher.py` 增加：

```python
def test_kpi_row_matcher_matches_terms_without_exact_spacing():
    chunk = DocumentChunk(
        chunk_id="goldwind-p47",
        report_id="goldwind",
        text=(
            "指标 单位 2024年 2023年 2022年 "
            "员工可记录工伤事故率 次/百万工时 0.18 0.20 0.25 "
            "员工因工死亡人数 人 0 0 0 "
            "员工总工时 小时 87654321 81234567 79876543"
        ),
        source_page=47,
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        source_file_hash="hash",
        quality_flags=[PageQualityFlag.COMPLEX_TABLE],
    )

    matches = match_kpi_rows(
        [chunk],
        ["员工因工死亡人数", "员工总工时"],
        year_columns=["2024年", "2024"],
    )

    assert [match.row_label for match in matches] == ["员工因工死亡人数", "员工总工时"]
    assert matches[0].unit == "人"
    assert matches[0].value == "0"
    assert matches[1].unit == "小时"
    assert matches[1].value == "87654321"
```

- [ ] **Step 2: 运行测试确认失败或覆盖不足**

Run:

```powershell
uv run --no-sync pytest --basetemp ..\tmp\pytest-kpi-auto tests/tools/test_kpi_row_matcher.py -q
```

Expected: 当前实现若已通过，继续 Step 3 增加 negative case；若失败，则按 Step 3 修复。

- [ ] **Step 3: 增强 `_match_metric_line`**

在 `backend/src/tools/kpi_row_matcher.py` 中把 `_match_metric_line` 改成只在 metric 后的短窗口内取单位和第一个数值，并排除相邻指标名：

```python
def _match_metric_line(text: str, term: str, year_columns: list[str]) -> tuple[str | None, str | None, str | None] | None:
    index = text.find(term)
    if index < 0:
        return None
    window = text[index : index + 220]
    year = next((candidate for candidate in year_columns if candidate in text[:index] or candidate in window), None)
    after_term = window[len(term) :].strip()
    tokens = after_term.split()
    unit = tokens[0] if tokens else None
    value = None
    for token in tokens[1:8]:
        if re.fullmatch(r"-?\d[\d,]*(?:\.\d+)?%?", token):
            value = token
            break
    if value is None:
        return None
    return unit, value, year
```

- [ ] **Step 4: 增加 negative test**

在同一测试文件增加：

```python
def test_kpi_row_matcher_does_not_match_metric_when_no_numeric_value_nearby():
    chunk = DocumentChunk(
        chunk_id="goldwind-p47",
        report_id="goldwind",
        text="员工因工死亡人数 说明文字 无数据 员工总工时 小时 87654321",
        source_page=47,
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        source_file_hash="hash",
        quality_flags=[PageQualityFlag.COMPLEX_TABLE],
    )

    matches = match_kpi_rows([chunk], ["员工因工死亡人数"], year_columns=["2024年", "2024"])

    assert matches == []
```

- [ ] **Step 5: 运行测试**

Run:

```powershell
uv run --no-sync pytest --basetemp ..\tmp\pytest-kpi-auto tests/tools/test_kpi_row_matcher.py tests/tools/test_evidence.py -q
```

Expected: PASS。

- [ ] **Step 6: 重跑 Goldwind holdout 与 Envision regression**

Run:

```powershell
uv run --no-sync python ../tmp/goldwind_holdout_remediation.py
uv run --no-sync python -m src.tools.first_pass_quality ../tmp/review/holdout_goldwind_2024_first_pass.csv ../tmp/review/holdout_goldwind_2024_reviewed.csv
```

Expected:

- `false_disclosed_count=0`
- `wrong_source_page_count=0`
- `global_fallback_count=0`

随后按既有命令重跑 Envision 577 regression，Expected:

- 577 requirement 数量不变
- `after_rules_delta_disclosed=0`
- `after_rules_delta_partial=0`
- `after_rules_delta_unknown=0`

- [ ] **Step 7: 提交**

```powershell
git add backend/src/tools/kpi_row_matcher.py backend/tests/tools/test_kpi_row_matcher.py
git commit -m "feat: improve report-agnostic KPI row matching"
```

---

### Task 3: 细化章节 Route 诊断与匹配

**Files:**
- Modify: `backend/src/reports/profile_builder.py`
- Modify: `backend/src/tools/evidence_routing.py`
- Modify: `backend/tests/reports/test_profile_builder.py`
- Modify: `backend/tests/tools/test_evidence_routing.py`

- [ ] **Step 1: 写章节 route 不覆盖 requirement route 的测试**

在 `backend/tests/tools/test_evidence_routing.py` 增加：

```python
def test_requirement_route_has_priority_over_section_route_for_goldwind_profile():
    profile = load_report_profile(Path("data/reports/profiles/goldwind_2024.json"))
    router = EvidenceRouter(report_profile=profile)
    task = make_task("GRI 414-1-a", "GRI 414-1").model_copy(
        update={
            "requirement_text": "new suppliers screened using social criteria",
            "keywords": ["供应商", "社会评价", "筛选"],
        }
    )

    route = router.route(task)

    assert route.source == "report_profile"
    assert route.candidate_pdf_pages == [31, 32]
```

- [ ] **Step 2: 写章节 route 低优先级测试**

在同一测试文件增加：

```python
def test_section_route_only_provides_candidates_for_unrouted_topic():
    profile = load_report_profile(Path("data/reports/profiles/goldwind_2024.json"))
    router = EvidenceRouter(report_profile=profile)
    task = make_task("GRI 999-1-a", "GRI 999-1").model_copy(
        update={
            "requirement_text": "community engagement and public welfare program",
            "keywords": ["社区", "公益"],
        }
    )

    route = router.route(task)

    assert route.source == "report_profile_section"
    assert route.candidate_pdf_pages == [41, 42, 43, 44, 45]
    assert "和谐社区关系" in route.metric_terms
```

- [ ] **Step 3: 运行测试**

Run:

```powershell
uv run --no-sync pytest --basetemp ..\tmp\pytest-section-refine tests/tools/test_evidence_routing.py tests/reports/test_profile_builder.py -q
```

Expected: PASS。若失败，原因通常是 Goldwind profile 未刷新；先运行 `uv run --no-sync python ../tmp/goldwind_holdout_remediation.py` 刷新 profile，再重跑测试。

- [ ] **Step 4: 检查 section route 不制造 disclosed**

Run:

```powershell
uv run --no-sync python ../tmp/goldwind_holdout_remediation.py
uv run --no-sync python -m src.tools.first_pass_quality ../tmp/review/holdout_goldwind_2024_first_pass.csv ../tmp/review/holdout_goldwind_2024_reviewed.csv
```

Expected:

- `false_disclosed_count=0`
- `wrong_source_page_count=0`
- `global_fallback_count=0`

- [ ] **Step 5: 提交**

```powershell
git add backend/src/reports/profile_builder.py backend/src/tools/evidence_routing.py backend/tests/reports/test_profile_builder.py backend/tests/tools/test_evidence_routing.py backend/data/reports/profiles/goldwind_2024.json
git commit -m "test: lock Goldwind section route priorities"
```

---

### Task 4: Preview 抽样复核工具

**Files:**
- Create: `backend/src/tools/preview_sample_audit.py`
- Create: `backend/tests/tools/test_preview_sample_audit.py`

- [ ] **Step 1: 写 preview 抽样测试**

创建 `backend/tests/tools/test_preview_sample_audit.py`：

```python
from pathlib import Path

from src.tools.preview_sample_audit import build_preview_sample_rows


def test_preview_sample_rows_flag_missing_anchor(tmp_path: Path):
    source = tmp_path / "review.csv"
    source.write_text(
        "requirement_id,verdict,evidence_preview,source_pdf_page,candidate_page_source,evidence_type\n"
        "GRI 414-1-a,disclosed,页眉 目录 相邻表格,31,report_profile,substantive\n"
        "GRI 403-9-a-i,disclosed,员工因工死亡人数 人 0,47,report_profile,substantive\n",
        encoding="utf-8",
    )

    rows = build_preview_sample_rows(
        source,
        anchors={
            "GRI 414-1-a": ["供应商", "社会评价"],
            "GRI 403-9-a-i": ["死亡人数", "0"],
        },
    )

    assert rows[0]["preview_anchor_status"] == "missing_anchor"
    assert rows[1]["preview_anchor_status"] == "anchor_found"
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```powershell
uv run --no-sync pytest --basetemp ..\tmp\pytest-preview-audit tests/tools/test_preview_sample_audit.py -q
```

Expected: FAIL，原因是工具尚未存在。

- [ ] **Step 3: 实现 preview 抽样工具**

创建 `backend/src/tools/preview_sample_audit.py`：

```python
from __future__ import annotations

import csv
from pathlib import Path


PREVIEW_SAMPLE_COLUMNS = [
    "requirement_id",
    "verdict",
    "source_pdf_page",
    "candidate_page_source",
    "evidence_type",
    "preview_anchor_status",
    "expected_anchors",
    "evidence_preview",
]


def build_preview_sample_rows(source_csv: Path, anchors: dict[str, list[str]]) -> list[dict[str, str]]:
    with source_csv.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    sampled: list[dict[str, str]] = []
    for row in rows:
        requirement_id = row.get("requirement_id", "")
        expected = anchors.get(requirement_id)
        if expected is None:
            continue
        preview = row.get("evidence_preview", "")
        status = "anchor_found" if any(anchor in preview for anchor in expected) else "missing_anchor"
        sampled.append(
            {
                "requirement_id": requirement_id,
                "verdict": row.get("verdict", ""),
                "source_pdf_page": row.get("source_pdf_page", ""),
                "candidate_page_source": row.get("candidate_page_source", ""),
                "evidence_type": row.get("evidence_type", ""),
                "preview_anchor_status": status,
                "expected_anchors": "|".join(expected),
                "evidence_preview": preview,
            }
        )
    return sampled


def write_preview_sample_rows(rows: list[dict[str, str]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PREVIEW_SAMPLE_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
```

- [ ] **Step 4: 运行测试**

Run:

```powershell
uv run --no-sync pytest --basetemp ..\tmp\pytest-preview-audit tests/tools/test_preview_sample_audit.py -q
```

Expected: PASS。

- [ ] **Step 5: 生成 preview 抽样 CSV**

Run:

```powershell
uv run --no-sync python - <<'PY'
from pathlib import Path
from src.tools.preview_sample_audit import build_preview_sample_rows, write_preview_sample_rows

anchors = {
    "GRI 414-1-a": ["供应商", "社会评价"],
    "GRI 403-9-a-i": ["死亡", "0"],
    "GRI 205-1-a": ["反腐败", "风险"],
    "GRI 418-1-a": ["客户隐私", "投诉"],
}
rows = build_preview_sample_rows(Path("../tmp/review/holdout_goldwind_2024_first_pass.csv"), anchors)
write_preview_sample_rows(rows, Path("../tmp/review/holdout_goldwind_2024_preview_sample.csv"))
print(len(rows))
PY
```

Expected: 生成 `tmp/review/holdout_goldwind_2024_preview_sample.csv`。若有 `missing_anchor`，不得直接改 verdict；只允许改 preview 锚点或 evidence routing。

- [ ] **Step 6: 提交**

```powershell
git add backend/src/tools/preview_sample_audit.py backend/tests/tools/test_preview_sample_audit.py
git commit -m "feat: add holdout preview sample audit"
```

---

### Task 5: 最终 Gate 与开发记录

**Files:**
- Modify: `docs/DEVELOPMENT.md`
- Read: `tmp/review/holdout_goldwind_2024_quality_summary.json`
- Read: `tmp/review/holdout_goldwind_2024_audit.json`
- Read: `tmp/review/holdout_goldwind_2024_recall_diagnosis.csv`
- Read: `tmp/review/holdout_goldwind_2024_preview_sample.csv`

- [ ] **Step 1: 跑 Goldwind holdout**

Run:

```powershell
uv run --no-sync python ../tmp/goldwind_holdout_remediation.py
```

Expected:

- `global_fallback_count=0`
- `max_source_pdf_page <= 52`
- `max_candidate_pdf_page <= 52`

- [ ] **Step 2: 跑 Goldwind audit**

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
(review_dir / "holdout_goldwind_2024_audit.json").write_text(
    json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
print(json.dumps(audit, ensure_ascii=False, indent=2))
PY
```

Expected: `first_pass.ok=true` 且 `reviewed.ok=true`。

- [ ] **Step 3: 跑 Goldwind quality diff**

Run:

```powershell
uv run --no-sync python -m src.tools.first_pass_quality ../tmp/review/holdout_goldwind_2024_first_pass.csv ../tmp/review/holdout_goldwind_2024_reviewed.csv
```

Expected:

- `false_disclosed_count=0`
- `wrong_source_page_count=0`

- [ ] **Step 4: 跑 Envision 577 regression**

按当前项目已使用的 Envision regression 脚本重新生成：

```powershell
uv run --no-sync python -m src.tools.first_pass_quality ../tmp/review/current_577_review_after_profile_routing.csv ../tmp/review/current_577_review_after_profile_routing_regression.csv
```

Expected:

- `after_rules_delta_disclosed=0`
- `after_rules_delta_partial=0`
- `after_rules_delta_unknown=0`

- [ ] **Step 5: 跑 focused tests**

Run:

```powershell
uv run --no-sync pytest --basetemp ..\tmp\pytest-goldwind-recall-expanded tests/tools/test_holdout_recall_diagnosis.py tests/tools/test_kpi_row_matcher.py tests/tools/test_preview_sample_audit.py tests/tools/test_evidence.py tests/tools/test_evidence_routing.py tests/reports/test_profile_builder.py -q
```

Expected: PASS。

- [ ] **Step 6: 扫描 docs 本机绝对路径**

Run:

```powershell
$matches = rg '[A-Za-z]:\\' docs README.md 2>$null; if ($LASTEXITCODE -eq 0) { $matches; exit 1 } else { 'no absolute paths found' }
```

Expected: `no absolute paths found`。

- [ ] **Step 7: 更新开发记录**

在 `docs/DEVELOPMENT.md` 增加一条记录，包含：

- Goldwind recall gold case 数量。
- `profile_route_hit_count`、`global_no_index_count`、`false_disclosed_count`、`wrong_source_page_count`。
- preview sample 是否存在 `missing_anchor`。
- Envision 577 regression 是否无回退。

- [ ] **Step 8: 最终提交**

```powershell
git add docs/DEVELOPMENT.md tmp/review/holdout_goldwind_2024_recall_diagnosis.csv tmp/review/holdout_goldwind_2024_preview_sample.csv
git commit -m "feat: expand Goldwind recall diagnostics"
```

若 `tmp/review/` 被 `.gitignore` 忽略，提交只包含源码、测试、profile/gold 数据和文档；在最终汇报中列出未提交的临时产物路径。

---

## 验收标准

- `backend/data/holdout/goldwind_2024_recall_gold.json` 已创建，且不包含未复核推测 case。
- `tmp/review/holdout_goldwind_2024_recall_diagnosis.csv` 已生成，行数等于 gold case 数。
- `tmp/review/holdout_goldwind_2024_preview_sample.csv` 已生成。
- `false_disclosed_count=0`。
- `wrong_source_page_count=0`。
- `global_fallback_count=0`。
- `source_pdf_page` 和 `candidate_pdf_pages` 均未超过 52。
- Goldwind GRI index PDF 50/51 未作为 `substantive evidence`。
- Envision 577 regression 无 requirement 数量变化，无 verdict/review/source/evidence/page/quality/OCR-VLM 回退。
- 未新增 Goldwind per-ID contract。
- docs 不包含本机绝对路径。

## 执行建议

建议 inline 执行。原因是诊断表、Goldwind holdout、preview sample 和 Envision regression 共享同一批临时产物，拆并行任务会增加状态冲突风险。
