# Goldwind Recall Improvement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 提升 Goldwind 2024 holdout 的 first-pass evidence recall，同时保持 `false_disclosed_count=0` 和既有 Envision 577 baseline 不回退。

**Architecture:** 先建立 recall 诊断表，把漏检拆成 route 缺失、关键词未命中、verdict matrix 保守和 preview 不可读四类。随后按上游到下游顺序改造：GRI index route、KPI 行级匹配、章节 route、evidence preview。每轮只改一个层级，并用 Goldwind holdout audit 和 Envision 577 regression gate 验收。

**Tech Stack:** Python 3.11、pytest、`ReportProfile`、`profile_builder`、`EvidenceRouter`、`retrieve_evidence`、`kpi_row_matcher`、`first_pass_quality`、`review_csv_audit`。

---

## 硬边界

- 不新增 Goldwind per-ID contract。
- 不把 Goldwind PDF 固定页码写进通用 GRI 标准规则。
- Goldwind `source_pdf_page` 是权威定位字段；`source_report_page` 只用于展示和人工阅读。
- GRI index page 只能作为 candidate route 来源，不能作为 `substantive evidence`。
- KPI 页召回必须依赖行标签、年份列、单位、数值和 evidence kind，不能只靠页码命中。
- 任何 `unknown/partial -> disclosed` 变化必须人工复核。
- 每轮优化都必须跑 Goldwind holdout audit 和 Envision 577 regression gate。

## 停止条件

触发任一条件即暂停并汇报原因：

- `false_disclosed_count > 0`。
- `wrong_source_page_count > 0`。
- `global_fallback_count > 0`。
- `source_pdf_page` 或 `candidate_pdf_pages` 超过报告总页数。
- Goldwind GRI index PDF 50/51 被标为 `substantive evidence`。
- Envision 577 regression 出现 requirement 数量变化。
- Envision 577 regression 出现非预期 verdict / review_status / source page / evidence_type / quality_flags / OCR-VLM 字段变化。
- 为提升 recall 需要新增 Goldwind per-ID contract。
- 测试失败且不能用小范围修复解决。

## 指标口径

每轮记录以下指标，来源为 `tmp/review/holdout_goldwind_2024_quality_summary.json` 和 recall 诊断表：

- `profile_route_hit_count`
- `global_no_index_count`
- `unknown_leakage_count`
- `wrong_source_page_count`
- `false_disclosed_count`

优先级：

1. `false_disclosed_count = 0`
2. `wrong_source_page_count = 0`
3. `profile_route_hit_count` 上升
4. `global_no_index_count` 下降
5. `unknown_leakage_count` 下降

## 影响文件

- Modify: `backend/src/reports/profile_builder.py`
- Modify: `backend/src/tools/evidence_routing.py`
- Modify: `backend/src/tools/kpi_row_matcher.py`
- Modify: `backend/src/tools/evidence.py`
- Modify: `backend/src/tools/first_pass_quality.py`
- Modify: `backend/src/workflows/single_report_workflow.py`
- Create: `backend/src/tools/holdout_recall_diagnosis.py`
- Test: `backend/tests/reports/test_profile_builder.py`
- Test: `backend/tests/tools/test_evidence_routing.py`
- Test: `backend/tests/tools/test_kpi_row_matcher.py`
- Test: `backend/tests/tools/test_evidence.py`
- Test: `backend/tests/tools/test_first_pass_quality.py`
- Create: `backend/tests/tools/test_holdout_recall_diagnosis.py`
- Update: `docs/DEVELOPMENT.md`

## 产物

- `tmp/review/holdout_goldwind_2024_recall_diagnosis.csv`
- `tmp/review/holdout_goldwind_2024_first_pass.csv`
- `tmp/review/holdout_goldwind_2024_reviewed.csv`
- `tmp/review/holdout_goldwind_2024_quality_summary.json`
- `tmp/review/holdout_goldwind_2024_audit.json`
- `tmp/review/current_577_review_after_profile_routing_regression.csv`
- `tmp/review/current_577_review_after_profile_routing_regression_audit.json`

---

### Task 1: 建立 Recall 诊断表

**Files:**
- Create: `backend/src/tools/holdout_recall_diagnosis.py`
- Create: `backend/tests/tools/test_holdout_recall_diagnosis.py`
- Modify: `backend/src/tools/first_pass_quality.py`

- [ ] **Step 1: 写诊断表测试**

新增测试覆盖三类行：

```python
def test_recall_diagnosis_classifies_route_missing(tmp_path: Path):
    source = tmp_path / "first_pass.csv"
    source.write_text(
        "requirement_id,verdict,review_status,candidate_pdf_pages,source_pdf_page,retrieval_strategy,evidence_type,evidence_preview\n"
        "GRI 205-1-a,unknown,needs_manual_review,[],10,global_no_index,substantive,policy text\n",
        encoding="utf-8",
    )

    rows = build_recall_diagnosis_rows(
        first_pass_csv=source,
        manual_gold={
            "GRI 205-1-a": {
                "issue_type": "unknown_leakage",
                "correct_pdf_pages": [21],
                "evidence_kind": "management_mechanism",
            }
        },
    )

    assert rows[0]["route_failure_reason"] == "candidate_pages_missing"
    assert rows[0]["suggested_profile_route"] == "[21]"
```

同一测试文件再覆盖：

```python
def test_recall_diagnosis_classifies_keyword_miss(tmp_path: Path):
    source = tmp_path / "first_pass.csv"
    source.write_text(
        "requirement_id,verdict,review_status,candidate_pdf_pages,source_pdf_page,retrieval_strategy,evidence_type,evidence_preview\n"
        "GRI 414-1-a,unknown,needs_manual_review,\"[31, 32]\",,index_page_bounded,,\n",
        encoding="utf-8",
    )

    rows = build_recall_diagnosis_rows(
        first_pass_csv=source,
        manual_gold={
            "GRI 414-1-a": {
                "issue_type": "unknown_leakage",
                "correct_pdf_pages": [31, 32],
                "evidence_kind": "kpi_value",
            }
        },
    )

    assert rows[0]["route_failure_reason"] == "candidate_pages_present_keyword_miss"
```

```python
def test_recall_diagnosis_classifies_matrix_conservative(tmp_path: Path):
    source = tmp_path / "first_pass.csv"
    source.write_text(
        "requirement_id,verdict,review_status,candidate_pdf_pages,source_pdf_page,retrieval_strategy,evidence_type,evidence_preview\n"
        "GRI 403-9-a-i,unknown,needs_manual_review,[47],47,index_page_bounded,substantive,death rate 0\n",
        encoding="utf-8",
    )

    rows = build_recall_diagnosis_rows(
        first_pass_csv=source,
        manual_gold={
            "GRI 403-9-a-i": {
                "issue_type": "unknown_leakage",
                "correct_pdf_pages": [47],
                "evidence_kind": "kpi_value",
            }
        },
    )

    assert rows[0]["route_failure_reason"] == "evidence_found_matrix_conservative"
```

- [ ] **Step 2: 运行测试并确认失败**

Run:

```powershell
uv run --no-sync pytest tests/tools/test_holdout_recall_diagnosis.py -q
```

Expected: FAIL，原因是 `holdout_recall_diagnosis.py` 或 `build_recall_diagnosis_rows` 尚未存在。

- [ ] **Step 3: 实现诊断工具**

实现 `backend/src/tools/holdout_recall_diagnosis.py`：

```python
import csv
import json
from pathlib import Path
from typing import Any


DIAGNOSIS_COLUMNS = [
    "requirement_id",
    "verdict",
    "review_status",
    "issue_type",
    "correct_pdf_pages",
    "evidence_kind",
    "current_source_pdf_pages",
    "current_candidate_pdf_pages",
    "current_retrieval_strategy",
    "route_failure_reason",
    "suggested_profile_route",
    "evidence_preview",
]


def build_recall_diagnosis_rows(
    first_pass_csv: Path,
    manual_gold: dict[str, dict[str, Any]],
) -> list[dict[str, str]]:
    with first_pass_csv.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        grouped.setdefault(row["requirement_id"], []).append(row)

    diagnosis_rows: list[dict[str, str]] = []
    for requirement_id, gold in manual_gold.items():
        source_rows = grouped.get(requirement_id, [])
        current_sources = sorted(
            {
                int(float(row["source_pdf_page"]))
                for row in source_rows
                if row.get("source_pdf_page")
            }
        )
        candidate_pages = _first_non_empty(source_rows, "candidate_pdf_pages")
        retrieval_strategy = _first_non_empty(source_rows, "retrieval_strategy")
        evidence_preview = _first_non_empty(source_rows, "evidence_preview")
        verdict = _first_non_empty(source_rows, "verdict") or "missing"
        review_status = _first_non_empty(source_rows, "review_status") or "missing"

        diagnosis_rows.append(
            {
                "requirement_id": requirement_id,
                "verdict": verdict,
                "review_status": review_status,
                "issue_type": str(gold.get("issue_type", "")),
                "correct_pdf_pages": json.dumps(gold.get("correct_pdf_pages", []), ensure_ascii=False),
                "evidence_kind": str(gold.get("evidence_kind", "")),
                "current_source_pdf_pages": json.dumps(current_sources, ensure_ascii=False),
                "current_candidate_pdf_pages": candidate_pages,
                "current_retrieval_strategy": retrieval_strategy,
                "route_failure_reason": _route_failure_reason(candidate_pages, current_sources, gold),
                "suggested_profile_route": json.dumps(gold.get("correct_pdf_pages", []), ensure_ascii=False),
                "evidence_preview": evidence_preview,
            }
        )
    return diagnosis_rows


def write_recall_diagnosis_csv(rows: list[dict[str, str]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=DIAGNOSIS_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _first_non_empty(rows: list[dict[str, str]], field: str) -> str:
    for row in rows:
        value = row.get(field, "")
        if value:
            return value
    return ""


def _route_failure_reason(
    candidate_pages_text: str,
    current_sources: list[int],
    gold: dict[str, Any],
) -> str:
    correct_pages = set(gold.get("correct_pdf_pages", []))
    if not candidate_pages_text or candidate_pages_text in {"[]", ""}:
        return "candidate_pages_missing"
    if not current_sources:
        return "candidate_pages_present_keyword_miss"
    if current_sources and not correct_pages.intersection(current_sources):
        return "wrong_source_page"
    return "evidence_found_matrix_conservative"
```

- [ ] **Step 4: 运行测试并确认通过**

Run:

```powershell
uv run --no-sync pytest tests/tools/test_holdout_recall_diagnosis.py -q
```

Expected: PASS。

- [ ] **Step 5: 生成 Goldwind 诊断表**

先手工建立一个最小 gold seed，覆盖人工复核已确认的 unknown leakage 样本。初版可以只包含人工已明确指出的条目，后续人工复核再扩展。

Run:

```powershell
uv run --no-sync python - <<'PY'
from pathlib import Path
from src.tools.holdout_recall_diagnosis import build_recall_diagnosis_rows, write_recall_diagnosis_csv

manual_gold = {
    "GRI 205-1-a": {"issue_type": "unknown_leakage", "correct_pdf_pages": [21], "evidence_kind": "management_mechanism"},
    "GRI 205-1-b": {"issue_type": "unknown_leakage", "correct_pdf_pages": [21], "evidence_kind": "management_mechanism"},
    "GRI 414-1-a": {"issue_type": "unknown_leakage", "correct_pdf_pages": [31, 32], "evidence_kind": "kpi_value"},
    "GRI 403-9-a-i": {"issue_type": "unknown_leakage", "correct_pdf_pages": [47], "evidence_kind": "kpi_value"},
}

rows = build_recall_diagnosis_rows(
    first_pass_csv=Path("../tmp/review/holdout_goldwind_2024_first_pass.csv"),
    manual_gold=manual_gold,
)
write_recall_diagnosis_csv(rows, Path("../tmp/review/holdout_goldwind_2024_recall_diagnosis.csv"))
print(len(rows))
PY
```

Expected: 输出行数为 `4`，生成 `tmp/review/holdout_goldwind_2024_recall_diagnosis.csv`。

---

### Task 2: 提升 Goldwind GRI Index Routing

**Files:**
- Modify: `backend/src/reports/profile_builder.py`
- Modify: `backend/tests/reports/test_profile_builder.py`

- [ ] **Step 1: 写 profile builder route 测试**

新增测试覆盖 Goldwind 索引中的双栏和跨主题行：

```python
def test_profile_builder_extracts_goldwind_index_routes_for_adjacent_disclosures():
    pages = [
        PageExtraction(
            report_id="goldwind",
            page_number=50,
            text=(
                "2-6 活动、价值链和其他业务关系 P08-P09, P58-P61 GRI 205：反腐败 2016 "
                "2-8 员工之外的工作者 P58-P61 SDG8 205-2 反腐败政策和程序的传达及培训 P38 "
                "管治 205-3 经确认的腐败事件和采取的行动 P38 "
                "GRI 305：排放 2016 305-1 直接（范畴1）温室气体排放 P46 "
                "305-2 能源间接（范畴2）温室气体排放 P46"
            ),
        ),
    ]
    requirements = [
        DisclosureRequirement(
            standard_id="GRI",
            standard_version="2016",
            disclosure_id="GRI 205-2",
            requirement_id="GRI 205-2-b",
            requirement_text="anti-corruption training",
            keywords=["反腐败", "培训"],
        ),
        DisclosureRequirement(
            standard_id="GRI",
            standard_version="2016",
            disclosure_id="GRI 305-1",
            requirement_id="GRI 305-1-a",
            requirement_text="scope 1 emissions",
            keywords=["范围一"],
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

    assert profile.requirement_routes["GRI 205-2-b"].candidate_pdf_pages == [21]
    assert profile.requirement_routes["GRI 305-1-a"].candidate_pdf_pages == [25]
```

- [ ] **Step 2: 运行测试并确认失败**

Run:

```powershell
uv run --no-sync pytest tests/reports/test_profile_builder.py -q
```

Expected: FAIL，原因是当前解析不能覆盖相邻 disclosure 或 prefix 继承场景。

- [ ] **Step 3: 改造 GRI index row parser**

实现要求：

- 对全文规范化后，识别 `\d+-\d+` disclosure token。
- token 后向前读取到下一个 disclosure token 或 `GRI \d+` 标题。
- 在 row 内解析 `Pxx`、`Pxx-Pyy`、`Pxx, Pyy`。
- 对 Goldwind 双页拼版使用 profile page numbering 推断 PDF 页。
- 输出 `requirement_routes` 时只写 candidate pages，不写 verdict。

- [ ] **Step 4: 运行测试并确认通过**

Run:

```powershell
uv run --no-sync pytest tests/reports/test_profile_builder.py -q
```

Expected: PASS。

- [ ] **Step 5: 重跑 Goldwind holdout**

Run:

```powershell
uv run --no-sync python ../tmp/goldwind_holdout_remediation.py
```

Expected:

- `profile_route_hit_count` 高于上一轮 `40`。
- `global_no_index_count` 低于上一轮 `53`。
- `false_disclosed_count = 0`。
- `wrong_source_page_count = 0`。

- [ ] **Step 6: 跑 Envision 577 regression**

Run:

```powershell
uv run --no-sync python -m src.tools.first_pass_quality ../tmp/review/current_577_review_after_profile_routing.csv ../tmp/review/current_577_review_after_profile_routing_regression.csv
```

Expected:

- `after_rules_delta_disclosed = 0`
- `after_rules_delta_partial = 0`
- `after_rules_delta_unknown = 0`

- [ ] **Step 7: 提交**

Commit message:

```text
feat: improve Goldwind GRI index routing
```

---

### Task 3: 增强 Goldwind KPI 行级匹配

**Files:**
- Modify: `backend/src/tools/kpi_row_matcher.py`
- Modify: `backend/src/reports/profile_builder.py`
- Modify: `backend/tests/tools/test_kpi_row_matcher.py`
- Modify: `backend/tests/reports/test_profile_builder.py`

- [ ] **Step 1: 写 KPI 表结构识别测试**

测试目标：识别页内包含 `指标 / 单位 / 2024年 / 2023年 / 2022年` 的表格文本，并抽出行标签、单位、年份值。

```python
def test_kpi_row_matcher_extracts_goldwind_year_value_unit():
    chunk = DocumentChunk(
        chunk_id="goldwind-p47",
        report_id="goldwind",
        text="指标 单位 2024年 2023年 2022年\n职业病发病次数 次 0 0 0\n重大安全事故 次 0 0 0",
        source_page=47,
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        source_file_hash="hash",
        quality_flags=[PageQualityFlag.COMPLEX_TABLE],
    )

    matches = match_kpi_rows([chunk], ["职业病发病次数"], year_columns=["2024年", "2024"])

    assert matches[0].row_label == "职业病发病次数"
    assert matches[0].unit == "次"
    assert matches[0].value == "0"
```

- [ ] **Step 2: 运行测试并确认失败**

Run:

```powershell
uv run --no-sync pytest tests/tools/test_kpi_row_matcher.py -q
```

Expected: FAIL，原因是当前 matcher 对 Goldwind 年份列或单位解析不足。

- [ ] **Step 3: 实现 KPI 行级增强**

实现要求：

- 支持 `2024` 和 `2024年` 两类年份列。
- 支持中文单位列。
- 支持 Goldwind 双页拼版文本中表格行被空格切分的情况。
- `kpi_row_preview` 必须以行标签开头。
- KPI evidence 自动追加 `complex_table`。

- [ ] **Step 4: 重跑测试**

Run:

```powershell
uv run --no-sync pytest tests/tools/test_kpi_row_matcher.py tests/tools/test_evidence.py -q
```

Expected: PASS。

- [ ] **Step 5: 重跑 Goldwind holdout 并比较指标**

Run:

```powershell
uv run --no-sync python ../tmp/goldwind_holdout_remediation.py
```

Expected:

- `profile_route_hit_count` 不下降。
- `global_no_index_count` 下降或不变。
- `unknown_leakage_count` 下降。
- `false_disclosed_count = 0`。
- `wrong_source_page_count = 0`。

- [ ] **Step 6: 提交**

Commit message:

```text
feat: improve Goldwind KPI row matching
```

---

### Task 4: 增强章节 Route

**Files:**
- Modify: `backend/src/reports/profile_builder.py`
- Modify: `backend/src/tools/evidence_routing.py`
- Modify: `backend/tests/reports/test_profile_builder.py`
- Modify: `backend/tests/tools/test_evidence_routing.py`

- [ ] **Step 1: 写章节 route 测试**

覆盖以下章节名：

- `可持续发展管理`
- `诚信合规经营`
- `绿色环保运营`
- `公平健康工作环境`
- `可持续产业链`
- `和谐社区关系`

测试要求：章节 route 只提供 candidate pages 和 semantic terms，不直接给 verdict。

- [ ] **Step 2: 运行测试并确认失败**

Run:

```powershell
uv run --no-sync pytest tests/reports/test_profile_builder.py tests/tools/test_evidence_routing.py -q
```

Expected: FAIL，原因是章节 route 尚未生成或未被 router 使用。

- [ ] **Step 3: 实现章节 route**

实现要求：

- 从目录和 GRI index 中提取章节候选页。
- 章节 route 的优先级低于 requirement route，高于 `global_no_index`。
- 章节 route metadata 标注 `candidate_page_source=report_profile_section`。
- 章节 route 不能直接触发 `disclosed`。

- [ ] **Step 4: 重跑 Goldwind holdout**

Run:

```powershell
uv run --no-sync python ../tmp/goldwind_holdout_remediation.py
```

Expected:

- `global_no_index_count` 下降。
- `false_disclosed_count = 0`。
- `wrong_source_page_count = 0`。

- [ ] **Step 5: 提交**

Commit message:

```text
feat: improve Goldwind section routing
```

---

### Task 5: 改善 Evidence Preview 锚点

**Files:**
- Modify: `backend/src/tools/evidence.py`
- Modify: `backend/tests/tools/test_evidence.py`

- [ ] **Step 1: 写 preview 锚点测试**

测试优先级：

1. `kpi_row_preview`
2. requirement keyword
3. GRI index row
4. section heading

示例：

```python
def test_evidence_preview_prefers_kpi_row_preview():
    task = DisclosureTask(
        task_id="task",
        run_id="run",
        report_id="goldwind",
        standard_id="GRI",
        standard_version="2018",
        disclosure_id="GRI 403-9",
        requirement_id="GRI 403-9-a-i",
        requirement_text="fatalities",
        keywords=["死亡", "工伤"],
    )
    chunk = DocumentChunk(
        chunk_id="chunk",
        report_id="goldwind",
        text="页眉 目录 相邻表格 职业病发病次数 次 0 0 0",
        source_page=47,
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        source_file_hash="hash",
    )

    evidence = chunk_to_evidence(
        task,
        chunk,
        retrieval_metadata={"kpi_row_preview": "职业病发病次数 次 0"},
    )

    assert evidence.evidence_preview == "职业病发病次数 次 0"
```

- [ ] **Step 2: 运行测试并确认失败**

Run:

```powershell
uv run --no-sync pytest tests/tools/test_evidence.py -q
```

Expected: FAIL，原因是 preview 未按新锚点优先级生成。

- [ ] **Step 3: 实现 preview 锚点**

实现要求：

- 有 `kpi_row_preview` 时直接使用。
- 无 KPI 行时围绕命中 keyword 截取窗口。
- GRI index row 只用于 `index_statement` / `omission_note` / route debug，不标为 substantive。
- 双栏文本不得只显示页眉、目录或相邻表格。

- [ ] **Step 4: 重跑测试和 holdout**

Run:

```powershell
uv run --no-sync pytest tests/tools/test_evidence.py -q
uv run --no-sync python ../tmp/goldwind_holdout_remediation.py
```

Expected:

- `false_disclosed_count = 0`
- `wrong_source_page_count = 0`
- 人工检查抽样 preview 时，目标行或目标关键词出现在 preview 前半段。

- [ ] **Step 5: 提交**

Commit message:

```text
feat: improve holdout evidence previews
```

---

### Task 6: 最终回归和记录

**Files:**
- Modify: `docs/DEVELOPMENT.md`
- Read: `tmp/review/holdout_goldwind_2024_quality_summary.json`
- Read: `tmp/review/holdout_goldwind_2024_audit.json`

- [ ] **Step 1: 跑 Goldwind holdout audit**

Run:

```powershell
uv run --no-sync python ../tmp/goldwind_holdout_remediation.py
```

Expected:

- `holdout_gate_status = passed`
- `false_disclosed_count = 0`
- `wrong_source_page_count = 0`
- `global_fallback_count = 0`

- [ ] **Step 2: 跑 Envision 577 regression**

Run:

```powershell
uv run --no-sync python -m src.tools.first_pass_quality ../tmp/review/current_577_review_after_profile_routing.csv ../tmp/review/current_577_review_after_profile_routing_regression.csv
```

Expected:

- `after_rules_delta_disclosed = 0`
- `after_rules_delta_partial = 0`
- `after_rules_delta_unknown = 0`

- [ ] **Step 3: 跑 focused tests**

Run:

```powershell
uv run --no-sync pytest tests/reports/test_profile_builder.py tests/tools/test_evidence_routing.py tests/tools/test_kpi_row_matcher.py tests/tools/test_evidence.py tests/tools/test_first_pass_quality.py tests/tools/test_holdout_recall_diagnosis.py -q
```

Expected: PASS。

- [ ] **Step 4: 更新开发记录**

在 `docs/DEVELOPMENT.md` 增加一条记录，包含：

- Goldwind route 命中变化。
- `global_no_index_count` 变化。
- `unknown_leakage_count` 变化。
- 是否保持 `false_disclosed_count = 0`。
- 是否保持 Envision 577 regression 无回退。

- [ ] **Step 5: 最终提交**

Commit message:

```text
feat: improve Goldwind holdout recall
```

---

## 验收标准

- `tmp/review/holdout_goldwind_2024_recall_diagnosis.csv` 已生成。
- `profile_route_hit_count` 高于当前基线 `40`。
- `global_no_index_count` 低于当前基线 `53`。
- `false_disclosed_count = 0`。
- `wrong_source_page_count = 0`。
- `global_fallback_count = 0`。
- Goldwind first-pass 和 reviewed CSV 均通过 `review_csv_audit`。
- Envision 577 regression audit 通过。
- Envision 577 requirement 数量不变。
- 未新增 Goldwind per-ID contract。
- 文档不包含本机绝对路径。

## 执行建议

建议 inline 执行。原因是当前任务链路强依赖同一套 holdout 产物和 regression gate，拆成并行子任务会增加状态冲突风险。

