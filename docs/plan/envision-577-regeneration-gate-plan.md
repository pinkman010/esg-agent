# Envision 577 重生成 Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立一个可重复执行的 Envision 2024 577 条主 assessment 重生成入口，用当前代码从源报告、profile 和 GRI requirements 生成 review CSV，并用 audit + diff 证明没有回退。

**Architecture:** 新增一个只负责 orchestration 的 CLI，把现有 `SingleReportWorkflow`、profile routing、review CSV export、`review_csv_audit` 和 `first_pass_quality` 串成可执行 gate。577 条 eligible assessment 作为主输出，84 条 compilation requirement 只进入 guardrail / missing item / sufficiency 校验，不作为独立 assessment 行输出。所有产物写入 `tmp/review/`，提交范围只包含工具、测试和文档。

**Tech Stack:** Python 3.11、pytest、`SingleReportWorkflow`、report profile、`review_csv_audit`、`first_pass_quality`、CSV/JSON 标准库。

---

## 背景

当前已经有可用于回归的静态 CSV：

- `tmp/review/current_577_review_after_profile_routing.csv`
- `tmp/review/current_577_review_after_profile_routing_regression.csv`
- `tmp/review/current_577_review_profile_routing_diff_summary.json`

这些文件可以比较两份 CSV 的差异，但还不能证明当前代码能从源报告重新生成同等质量的 577 条结果。后续继续做 Goldwind recall、profile route、ontology matrix 和 compilation guardrail 时，需要一个固定 gate 判断 Envision baseline 是否回退。

本计划要补齐这个缺口：从 `backend/data/reports/Envision Energy 2024-zh.pdf`、`backend/data/reports/profiles/envision_2024.json` 和当前标准数据重新生成 577 review CSV，再执行审计和 baseline diff。

## 硬边界

- 不调用外部模型；CLI 必须默认 `--confirm-llm false`。
- 不启用 OCR/VLM；CLI 必须默认 `--enable-ocr false`。
- 不覆盖、删改原始 PDF、标准文件、profile 或人工复核 CSV。
- 不新增 Envision per-ID contract，不修改 verdict 规则，只建立重生成入口和 gate。
- `tmp/review/` 下生成物不提交。
- 84 条 compilation requirement 不输出为独立 assessment requirement。
- `docs/` 中只写相对路径，不写本机绝对路径。

## 停止条件

触发任一条件即暂停并汇报：

- 重生成结果唯一 eligible requirement 数量不是 577。
- 输出中出现 compilation requirement 作为独立 assessment 行。
- `review_csv_audit` 返回 error。
- `global_fallback_count > 0`。
- `source_pdf_page` 或 `candidate_pdf_pages` 超过 Envision 2024 报告总 PDF 页数 78。
- `disclosed` 搭配 `needs_manual_review`。
- `partially_disclosed` 或 `unknown` 未搭配 `needs_manual_review`。
- `omission_note` 被判为 `partially_disclosed` 或 `disclosed`。
- PDF 第 63、65、66、67、68 页 KPI evidence 丢失 `complex_table`。
- PDF 第 77 页鉴证页丢失 OCR/VLM 风险标记。
- 和 baseline 比较出现非预期 verdict、review_status、source page、evidence_type、quality_flags、OCR/VLM 字段变化。
- 实现过程中需要修改 Envision verdict contract 才能通过 gate。

## 文件职责

- Create: `backend/src/tools/regenerate_review_csv.py`
  - CLI 入口。读取 report/profile/requirements 参数，调用现有 workflow，导出 review CSV，生成 audit 和 diff summary。
- Create: `backend/src/tools/review_csv_export.py`
  - 纯函数导出层。把 workflow result / assessment rows 转成当前 review CSV 字段，避免在 CLI 中堆积字段拼装逻辑。
- Modify: `backend/src/tools/review_csv_audit.py`
  - 增加 CLI 入口，保留现有 `audit_review_csv()` API。
- Modify: `backend/src/tools/first_pass_quality.py`
  - 保持现有 CLI；如需 diff 输出文件，增加 `--json-output` 参数。
- Test: `backend/tests/tools/test_regenerate_review_csv.py`
  - 覆盖 CLI 参数、577 过滤、compilation 排除、禁止模型调用默认值。
- Test: `backend/tests/tools/test_review_csv_export.py`
  - 覆盖 CSV 字段契约、页码双轨字段、quality flags、OCR/VLM 字段。
- Modify: `backend/tests/tools/test_review_csv_audit.py`
  - 覆盖新增 CLI。
- Modify: `docs/DEVELOPMENT.md`
  - 记录重生成命令、产物、验收指标和停止条件。
- Create: `tmp/review/current_577_review_regenerated.csv`
  - 执行产物，不提交。
- Create: `tmp/review/current_577_review_regenerated_audit.json`
  - 执行产物，不提交。
- Create: `tmp/review/current_577_review_regeneration_diff_summary.json`
  - 执行产物，不提交。

## Task 1: 盘点现有数据和入口

**Files:**
- Read: `backend/data/reports/Envision Energy 2024-zh.pdf`
- Read: `backend/data/reports/profiles/envision_2024.json`
- Read: `tmp/review/current_577_review_after_profile_routing.csv`
- Read: `backend/src/workflows/single_report_workflow.py`
- Read: `backend/src/tools/first_pass_quality.py`
- Read: `backend/src/tools/review_csv_audit.py`

- [ ] **Step 1: 确认 baseline 文件存在**

Run:

```powershell
Test-Path tmp/review/current_577_review_after_profile_routing.csv
Test-Path backend/data/reports/profiles/envision_2024.json
Test-Path "backend/data/reports/Envision Energy 2024-zh.pdf"
```

Expected:

```text
True
True
True
```

- [ ] **Step 2: 确认 baseline 唯一 requirement 数**

Run:

```powershell
@'
import csv
from pathlib import Path

path = Path("tmp/review/current_577_review_after_profile_routing.csv")
with path.open(encoding="utf-8-sig", newline="") as handle:
    rows = list(csv.DictReader(handle))
ids = {row["requirement_id"] for row in rows if row.get("requirement_id")}
print(len(ids))
print(len(rows))
'@ | python -
```

Expected:

```text
577
```

第二行是 evidence 行数，不要求固定为 577。

- [ ] **Step 3: 记录现有 workflow 构造参数**

Run:

```powershell
rg -n "class SingleReportWorkflow|def __init__|def run|profile|confirm_llm|ocr" backend/src/workflows/single_report_workflow.py backend/src/api/routes/reports.py
```

Expected:

```text
输出包含 SingleReportWorkflow 构造参数、API 调用方式、profile_path 或等价字段。
```

## Task 2: 增加 review CSV export 纯函数

**Files:**
- Create: `backend/src/tools/review_csv_export.py`
- Test: `backend/tests/tools/test_review_csv_export.py`

- [ ] **Step 1: 写失败测试，覆盖 review CSV 必需字段**

Create `backend/tests/tools/test_review_csv_export.py`:

```python
from src.tools.review_csv_export import export_review_rows


def test_export_review_rows_preserves_contract_fields():
    assessments = [
        {
            "requirement_id": "GRI 2-1-a",
            "verdict": "disclosed",
            "review_status": "not_required",
            "evidence": [
                {
                    "source_pdf_page": 1,
                    "source_report_page": None,
                    "candidate_pdf_pages": [1, 3],
                    "candidate_report_pages": [None, 2],
                    "page_label": "PDF 第 1 页",
                    "retrieval_strategy": "index_page_bounded",
                    "evidence_type": "substantive",
                    "quality_flags": ["digital_text"],
                    "requires_ocr": False,
                    "requires_vlm": False,
                    "needs_ocr_or_vlm": False,
                    "evidence_preview": "金风科技股份有限公司",
                    "source_text": "金风科技股份有限公司",
                }
            ],
        }
    ]

    rows = export_review_rows(assessments)

    assert rows == [
        {
            "requirement_id": "GRI 2-1-a",
            "verdict": "disclosed",
            "review_status": "not_required",
            "source_pdf_page": "1",
            "source_report_page": "",
            "candidate_pdf_pages": "[1, 3]",
            "candidate_report_pages": "[null, 2]",
            "page_label": "PDF 第 1 页",
            "retrieval_strategy": "index_page_bounded",
            "evidence_type": "substantive",
            "quality_flags": '["digital_text"]',
            "requires_ocr": "False",
            "requires_vlm": "False",
            "needs_ocr_or_vlm": "False",
            "evidence_preview": "金风科技股份有限公司",
            "source_text": "金风科技股份有限公司",
        }
    ]
```

- [ ] **Step 2: 运行失败测试**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/tools/test_review_csv_export.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'src.tools.review_csv_export'
```

- [ ] **Step 3: 实现最小 export 函数**

Create `backend/src/tools/review_csv_export.py`:

```python
from __future__ import annotations

import json
from typing import Any


REVIEW_CSV_FIELDS = [
    "requirement_id",
    "verdict",
    "review_status",
    "source_pdf_page",
    "source_report_page",
    "candidate_pdf_pages",
    "candidate_report_pages",
    "page_label",
    "retrieval_strategy",
    "evidence_type",
    "quality_flags",
    "requires_ocr",
    "requires_vlm",
    "needs_ocr_or_vlm",
    "evidence_preview",
    "source_text",
]


def export_review_rows(assessments: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for assessment in assessments:
        evidence_items = assessment.get("evidence") or [{}]
        for evidence in evidence_items:
            rows.append(_row_from_assessment(assessment, evidence))
    return rows


def _row_from_assessment(assessment: dict[str, Any], evidence: dict[str, Any]) -> dict[str, str]:
    row = {
        "requirement_id": _string(assessment.get("requirement_id")),
        "verdict": _string(assessment.get("verdict")),
        "review_status": _string(assessment.get("review_status")),
        "source_pdf_page": _string(evidence.get("source_pdf_page")),
        "source_report_page": _string(evidence.get("source_report_page")),
        "candidate_pdf_pages": _json(evidence.get("candidate_pdf_pages", [])),
        "candidate_report_pages": _json(evidence.get("candidate_report_pages", [])),
        "page_label": _string(evidence.get("page_label")),
        "retrieval_strategy": _string(evidence.get("retrieval_strategy")),
        "evidence_type": _string(evidence.get("evidence_type")),
        "quality_flags": _json(evidence.get("quality_flags", [])),
        "requires_ocr": _bool_string(evidence.get("requires_ocr", False)),
        "requires_vlm": _bool_string(evidence.get("requires_vlm", False)),
        "needs_ocr_or_vlm": _bool_string(evidence.get("needs_ocr_or_vlm", False)),
        "evidence_preview": _string(evidence.get("evidence_preview")),
        "source_text": _string(evidence.get("source_text")),
    }
    return {field: row.get(field, "") for field in REVIEW_CSV_FIELDS}


def _json(value: Any) -> str:
    return json.dumps(value or [], ensure_ascii=False)


def _string(value: Any) -> str:
    return "" if value is None else str(value)


def _bool_string(value: Any) -> str:
    return "True" if bool(value) else "False"
```

- [ ] **Step 4: 运行 export 测试**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/tools/test_review_csv_export.py -q
```

Expected:

```text
1 passed
```

## Task 3: 给 review_csv_audit 增加 CLI

**Files:**
- Modify: `backend/src/tools/review_csv_audit.py`
- Modify: `backend/tests/tools/test_review_csv_audit.py`

- [ ] **Step 1: 写 CLI 测试**

Append to `backend/tests/tools/test_review_csv_audit.py`:

```python
import json
import subprocess
import sys
from pathlib import Path


def test_review_csv_audit_cli_writes_json(tmp_path: Path):
    csv_path = tmp_path / "review.csv"
    csv_path.write_text(
        "requirement_id,verdict,review_status,retrieval_strategy,evidence_type,source_pdf_page,page_label,quality_flags,candidate_pdf_pages,requires_ocr,needs_ocr_or_vlm\n"
        'GRI 2-1-a,disclosed,not_required,index_page_bounded,substantive,1,PDF 第 1 页,"[]","[1]",False,False\n',
        encoding="utf-8",
    )
    output_path = tmp_path / "audit.json"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.tools.review_csv_audit",
            str(csv_path),
            "--report-total-pages",
            "78",
            "--json-output",
            str(output_path),
        ],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["errors"] == []
```

- [ ] **Step 2: 运行失败测试**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/tools/test_review_csv_audit.py::test_review_csv_audit_cli_writes_json -q
```

Expected:

```text
FAIL，原因是 review_csv_audit 缺少 CLI 入口。
```

- [ ] **Step 3: 添加 CLI 入口**

Modify `backend/src/tools/review_csv_audit.py`，保留现有函数，在文件末尾增加：

```python
def _to_dict(result: ReviewCsvAuditResult) -> dict:
    return {"ok": result.ok, "errors": result.errors, "warnings": result.warnings}


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Audit review CSV hard gates.")
    parser.add_argument("review_csv", type=Path)
    parser.add_argument("--report-total-pages", type=int, required=True)
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args()

    result = audit_review_csv(args.review_csv, report_total_pages=args.report_total_pages)
    payload = _to_dict(result)
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.json_output:
        args.json_output.write_text(text + "\n", encoding="utf-8")
    print(text)
    raise SystemExit(0 if result.ok else 1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 运行 audit 测试**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/tools/test_review_csv_audit.py -q
```

Expected:

```text
全部通过。
```

## Task 4: 增加 Envision 重生成 CLI

**Files:**
- Create: `backend/src/tools/regenerate_review_csv.py`
- Test: `backend/tests/tools/test_regenerate_review_csv.py`

- [ ] **Step 1: 写 CLI 参数和过滤测试**

Create `backend/tests/tools/test_regenerate_review_csv.py`:

```python
from pathlib import Path

from src.tools.regenerate_review_csv import filter_eligible_assessments, parse_args


def test_parse_args_defaults_disable_llm_and_ocr(tmp_path: Path):
    args = parse_args(
        [
            "--report-id",
            "envision_2024",
            "--pdf",
            "backend/data/reports/Envision Energy 2024-zh.pdf",
            "--profile",
            "backend/data/reports/profiles/envision_2024.json",
            "--output",
            str(tmp_path / "out.csv"),
        ]
    )

    assert args.confirm_llm is False
    assert args.enable_ocr is False


def test_filter_eligible_assessments_removes_compilation_requirements():
    assessments = [
        {"requirement_id": "GRI 2-1-a", "requirement_type": "assessment"},
        {"requirement_id": "GRI 305-2-2.3", "requirement_type": "compilation_requirement"},
    ]

    filtered = filter_eligible_assessments(assessments)

    assert filtered == [{"requirement_id": "GRI 2-1-a", "requirement_type": "assessment"}]
```

- [ ] **Step 2: 运行失败测试**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/tools/test_regenerate_review_csv.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'src.tools.regenerate_review_csv'
```

- [ ] **Step 3: 实现参数解析和 eligible 过滤**

Create `backend/src/tools/regenerate_review_csv.py`:

```python
from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

from src.tools.review_csv_export import REVIEW_CSV_FIELDS, export_review_rows


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Regenerate review CSV for a single ESG report.")
    parser.add_argument("--report-id", required=True)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--confirm-llm", action="store_true", default=False)
    parser.add_argument("--enable-ocr", action="store_true", default=False)
    parser.add_argument("--audit-output", type=Path)
    parser.add_argument("--report-total-pages", type=int, default=78)
    return parser.parse_args(argv)


def filter_eligible_assessments(assessments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        assessment
        for assessment in assessments
        if assessment.get("requirement_type") != "compilation_requirement"
        and not _looks_like_compilation_requirement(str(assessment.get("requirement_id", "")))
    ]


def _looks_like_compilation_requirement(requirement_id: str) -> bool:
    parts = requirement_id.replace("GRI ", "").split("-")
    return len(parts) >= 4 and any(part.count(".") for part in parts)


def write_review_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    assessments = run_single_report_regeneration(args)
    eligible = filter_eligible_assessments(assessments)
    rows = export_review_rows(eligible)
    write_review_csv(args.output, rows)


def run_single_report_regeneration(args: argparse.Namespace) -> list[dict[str, Any]]:
    raise NotImplementedError("Task 5 wires this function to SingleReportWorkflow.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 运行参数和过滤测试**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/tools/test_regenerate_review_csv.py -q
```

Expected:

```text
2 passed
```

## Task 5: 接入 SingleReportWorkflow

**Files:**
- Modify: `backend/src/tools/regenerate_review_csv.py`
- Test: `backend/tests/tools/test_regenerate_review_csv.py`

- [ ] **Step 1: 写 workflow adapter 测试**

Append to `backend/tests/tools/test_regenerate_review_csv.py`:

```python
from argparse import Namespace

import src.tools.regenerate_review_csv as module


def test_run_single_report_regeneration_uses_workflow_without_llm_or_ocr(monkeypatch, tmp_path):
    calls = {}

    class FakeWorkflow:
        def __init__(self, *, profile_path, confirm_llm, enable_ocr):
            calls["profile_path"] = profile_path
            calls["confirm_llm"] = confirm_llm
            calls["enable_ocr"] = enable_ocr

        def run(self, pdf_path, report_id):
            calls["pdf_path"] = pdf_path
            calls["report_id"] = report_id
            return [{"requirement_id": "GRI 2-1-a", "requirement_type": "assessment"}]

    monkeypatch.setattr(module, "build_workflow", lambda args: FakeWorkflow(
        profile_path=args.profile,
        confirm_llm=args.confirm_llm,
        enable_ocr=args.enable_ocr,
    ))

    args = Namespace(
        report_id="envision_2024",
        pdf=tmp_path / "report.pdf",
        profile=tmp_path / "profile.json",
        confirm_llm=False,
        enable_ocr=False,
    )

    result = module.run_single_report_regeneration(args)

    assert result == [{"requirement_id": "GRI 2-1-a", "requirement_type": "assessment"}]
    assert calls["confirm_llm"] is False
    assert calls["enable_ocr"] is False
    assert calls["report_id"] == "envision_2024"
```

- [ ] **Step 2: 实现 workflow builder**

Modify `backend/src/tools/regenerate_review_csv.py`:

```python
def build_workflow(args: argparse.Namespace):
    from src.agents.disclosure_agent import DisclosureAgent
    from src.adapters.gri_adapter import GriAdapter
    from src.parsers.pdf_parser import PdfParser
    from src.repositories.report_repository import ReportRepository
    from src.workflows.single_report_workflow import SingleReportWorkflow

    return SingleReportWorkflow(
        ReportRepository(),
        PdfParser(enable_ocr=args.enable_ocr),
        GriAdapter(),
        DisclosureAgent(confirm_llm=args.confirm_llm),
        profile_path=args.profile,
    )


def run_single_report_regeneration(args: argparse.Namespace) -> list[dict[str, Any]]:
    workflow = build_workflow(args)
    result = workflow.run(args.pdf, report_id=args.report_id)
    if isinstance(result, list):
        return result
    if hasattr(result, "assessments"):
        return list(result.assessments)
    if isinstance(result, dict) and "assessments" in result:
        return list(result["assessments"])
    raise TypeError(f"Unsupported workflow result type: {type(result)!r}")
```

如果实际类名或构造参数不同，以 `backend/src/api/routes/reports.py` 当前调用方式为准调整，但保留 `confirm_llm=False` 和 `enable_ocr=False` 默认值。

- [ ] **Step 3: 运行工具测试**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/tools/test_regenerate_review_csv.py tests/tools/test_review_csv_export.py -q
```

Expected:

```text
全部通过。
```

## Task 6: 增加 audit + diff wrapper 输出

**Files:**
- Modify: `backend/src/tools/regenerate_review_csv.py`
- Modify: `backend/tests/tools/test_regenerate_review_csv.py`

- [ ] **Step 1: 增加 CLI 参数测试**

Append to `backend/tests/tools/test_regenerate_review_csv.py`:

```python
def test_parse_args_accepts_baseline_and_diff_outputs(tmp_path: Path):
    args = parse_args(
        [
            "--report-id",
            "envision_2024",
            "--pdf",
            "backend/data/reports/Envision Energy 2024-zh.pdf",
            "--profile",
            "backend/data/reports/profiles/envision_2024.json",
            "--output",
            str(tmp_path / "out.csv"),
            "--baseline",
            "tmp/review/current_577_review_after_profile_routing.csv",
            "--audit-output",
            str(tmp_path / "audit.json"),
            "--diff-summary-output",
            str(tmp_path / "diff.json"),
        ]
    )

    assert str(args.baseline).endswith("current_577_review_after_profile_routing.csv")
    assert args.audit_output.name == "audit.json"
    assert args.diff_summary_output.name == "diff.json"
```

- [ ] **Step 2: 增加参数和输出函数**

Modify `parse_args()` in `backend/src/tools/regenerate_review_csv.py`:

```python
parser.add_argument("--baseline", type=Path)
parser.add_argument("--diff-summary-output", type=Path)
```

Add helper:

```python
def write_audit(path: Path, review_csv: Path, report_total_pages: int) -> None:
    from dataclasses import asdict
    from src.tools.review_csv_audit import audit_review_csv

    result = audit_review_csv(review_csv, report_total_pages=report_total_pages)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(result), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not result.ok:
        raise SystemExit(1)


def write_diff_summary(path: Path, baseline: Path, regenerated: Path) -> None:
    from dataclasses import asdict
    from src.tools.first_pass_quality import compare_first_pass_to_after_rules

    result = compare_first_pass_to_after_rules(baseline, regenerated)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(result), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
```

Also add `import json`.

Update `main()`:

```python
if args.audit_output:
    write_audit(args.audit_output, args.output, args.report_total_pages)
if args.baseline and args.diff_summary_output:
    write_diff_summary(args.diff_summary_output, args.baseline, args.output)
```

- [ ] **Step 3: 运行工具测试**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/tools/test_regenerate_review_csv.py tests/tools/test_review_csv_audit.py tests/tools/test_first_pass_quality.py -q
```

Expected:

```text
全部通过。
```

## Task 7: 执行 Envision 577 重生成 gate

**Files:**
- Generate: `tmp/review/current_577_review_regenerated.csv`
- Generate: `tmp/review/current_577_review_regenerated_audit.json`
- Generate: `tmp/review/current_577_review_regeneration_diff_summary.json`

- [ ] **Step 1: 执行重生成命令**

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

```text
命令退出码为 0。
生成 3 个 tmp/review 产物。
```

- [ ] **Step 2: 检查 577 数量**

Run:

```powershell
@'
import csv
from pathlib import Path

path = Path("tmp/review/current_577_review_regenerated.csv")
with path.open(encoding="utf-8-sig", newline="") as handle:
    rows = list(csv.DictReader(handle))
ids = {row["requirement_id"] for row in rows if row.get("requirement_id")}
compilation = [rid for rid in ids if rid.count(".") >= 1 and len(rid.split("-")) >= 4]
print({"unique_requirements": len(ids), "rows": len(rows), "compilation_like": len(compilation)})
'@ | python -
```

Expected:

```text
{'unique_requirements': 577, 'rows': <非固定行数>, 'compilation_like': 0}
```

- [ ] **Step 3: 检查 audit JSON**

Run:

```powershell
Get-Content tmp/review/current_577_review_regenerated_audit.json
```

Expected:

```json
{
  "ok": true,
  "errors": [],
  "warnings": []
}
```

- [ ] **Step 4: 检查 diff summary**

Run:

```powershell
Get-Content tmp/review/current_577_review_regeneration_diff_summary.json
```

Expected:

```text
确认 first_pass_disclosed_count、first_pass_partial_count、first_pass_unknown_count 与 baseline 对齐。
after_rules_delta_disclosed、after_rules_delta_partial、after_rules_delta_unknown 为 0，或列出人工批准的预期差异。
```

## Task 8: 更新开发文档

**Files:**
- Modify: `docs/DEVELOPMENT.md`

- [ ] **Step 1: 添加 Envision 577 重生成命令**

Append a section to `docs/DEVELOPMENT.md`:

```markdown
## Envision 577 Review CSV Regeneration Gate

用途：从 Envision 2024 源报告和 report profile 重新生成 577 条 eligible GRI assessment review CSV，并与已批准 baseline 比较。

命令：

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

通过标准：

- 唯一 eligible requirement 数为 577。
- compilation requirement 不作为独立 assessment 输出。
- `review_csv_audit` 通过。
- `global_fallback=0`。
- `omission_note` 不升格。
- disclosed 全部为 `not_required`。
- partial/unknown 全部为 `needs_manual_review`。
- 和 baseline 的 verdict、review_status、source page、evidence_type、quality_flags、OCR/VLM 字段无非预期变化。

产物写入 `tmp/review/`，不提交。
```

- [ ] **Step 2: 检查文档路径**

Run:

```powershell
@'
from pathlib import Path

for file_name in ["docs/DEVELOPMENT.md", "docs/plan/envision-577-regeneration-gate-plan.md"]:
    for line_number, line in enumerate(Path(file_name).read_text(encoding="utf-8").splitlines(), start=1):
        if len(line) >= 3 and line[1] == ":" and line[0].isalpha() and line[2] in {"\\", "/"}:
            print(f"{file_name}:{line_number}:{line}")
'@ | python -
```

Expected:

```text
无输出。
```

## Task 9: 最小验证和提交

**Files:**
- Read: `git diff`
- Commit after user approval

- [ ] **Step 1: 运行相关单测**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/tools/test_regenerate_review_csv.py tests/tools/test_review_csv_export.py tests/tools/test_review_csv_audit.py tests/tools/test_first_pass_quality.py -q
```

Expected:

```text
全部通过。
```

- [ ] **Step 2: 运行 workflow 相关回归**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/workflows/test_single_report_workflow.py tests/agents/test_disclosure_agent.py -q
```

Expected:

```text
全部通过。
```

- [ ] **Step 3: 检查 git diff**

Run:

```powershell
git diff -- backend/src/tools/regenerate_review_csv.py backend/src/tools/review_csv_export.py backend/src/tools/review_csv_audit.py backend/src/tools/first_pass_quality.py backend/tests/tools/test_regenerate_review_csv.py backend/tests/tools/test_review_csv_export.py backend/tests/tools/test_review_csv_audit.py docs/DEVELOPMENT.md docs/plan/envision-577-regeneration-gate-plan.md
git status --short
```

Expected:

```text
只出现本计划列出的代码、测试和文档文件。
tmp/review 产物不进入 git status。
```

- [ ] **Step 4: 提交**

Run after user approval:

```powershell
git add backend/src/tools/regenerate_review_csv.py backend/src/tools/review_csv_export.py backend/src/tools/review_csv_audit.py backend/src/tools/first_pass_quality.py backend/tests/tools/test_regenerate_review_csv.py backend/tests/tools/test_review_csv_export.py backend/tests/tools/test_review_csv_audit.py docs/DEVELOPMENT.md docs/plan/envision-577-regeneration-gate-plan.md
git commit -m "feat: add Envision 577 regeneration gate"
```

Expected:

```text
提交成功。
```

## 验收标准

- 可以用一条命令从源报告重生成 `tmp/review/current_577_review_regenerated.csv`。
- 重生成结果唯一 eligible requirement 数为 577。
- 84 条 compilation requirement 没有作为独立 assessment 输出。
- `review_csv_audit` 通过。
- diff summary 显示无非预期 verdict/review/source/evidence/quality/OCR 字段变化。
- 工具默认不调用外部模型，不启用 OCR/VLM。
- 文档只包含相对路径。

## 后续计划

完成本计划后，再继续 Goldwind recall 提升：

- 优先修 profile route 到 first-pass 候选页保留链路。
- 继续增强 KPI 行级 evidence 命中。
- 继续保持不新增 Goldwind per-ID contract。
- 每次 recall 改造后运行 Envision 577 重生成 gate，防止 baseline 回退。
