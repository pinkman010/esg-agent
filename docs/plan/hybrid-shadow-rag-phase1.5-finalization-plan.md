# 混合影子 RAG Phase 1.5 封版实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**目标：** 在不进入 Phase 2–3、不调用外部服务、不依赖新增 ESG 专家判断的前提下，对 Envision 499 条规则、向量和混合 Top 5 上下文进行自动工程验收，证明 Phase 1.5 的召回增益、结构确定性、正式业务零变化和可追溯性，并形成可提交的封版报告。

**架构：** 新增纯评估模块读取既有召回明细 CSV 和混合 context JSONL，统一计算规则、向量、混合三路 Top 1/3/5 指标与逐项差异；新增只读封版编排器在 PostgreSQL `REPEATABLE READ READ ONLY` 事务内读取指定报告 chunk 和正式表计数，重建两次混合 context 验证 hash 确定性，生成 CSV、JSON、Markdown 和输入指纹。所有诊断产物只写 `tmp/embedding/`，正式数据库、API、前端和分析工作流保持不变。

**技术栈：** Python 3.11、pytest、SQLAlchemy 2.0、PostgreSQL、现有 `evaluate_shadow_retrieval`、`build_shadow_rag_contexts`、`resolve_shadow_output` 和 Envision v3 regeneration gate。

**执行状态（2026-07-27）：** Task 1–10 已执行，本地提交已完成，未执行 `git push`。最终事实以 `docs/product/rag-phase1.5-acceptance-report.md` 为准。

---

## 1. 已确认边界

### 1.1 当前基线

- 当前 Git 基线：`0cf3cbc feat: add hybrid shadow RAG contexts`。
- 当前后端门禁：686 项测试通过。
- Envision v3 结构：`577/499/78/0`。
- Envision gate：global fallback 0、新增 false disclosed 0、新增 wrong source page 0、audit 0 error/0 warning。
- 当前混合参数：向量候选池 Top 10、RRF 规则权重 2、向量权重 1、常数 60、最终 context Top 5。
- 当前 demo 混合 context：499 条、499 个唯一 hash、同页重复 0、未解析规则页 0。
- 当前数据库 migration：代码、test、main、demo 均为 `0012_chunk_embeddings`。

### 1.2 本计划包含

- 对全部 499 个独立判断项执行规则、向量和混合 Top 5 自动对比。
- 使用既有人工工作簿 `correct_pdf_pages` 作为历史工程 gold。
- 对无 gold requirement 保留结构诊断，但不纳入 hit、recall 和 MRR 分母。
- 验证 context 数量、requirement 唯一性、报告隔离、页级去重、页码范围、shadow evidence ID、RRF 字段和 context hash。
- 同一输入连续构建两次，验证 499 个 context hash 完全一致。
- 在只读事务中验证封版工具不能执行数据库写操作。
- 比较封版前后正式业务表行数。
- 重跑 focused tests、后端全量测试和 Envision v3 gate。
- 生成 Phase 1.5 自动验收报告并更新项目文档。

### 1.3 本计划不包含

- 不新增人工复核包，不要求 ESG 专家作新判断。
- 不把历史 gold 描述为专家认证或最终合规结论。
- 不调用 SiliconFlow、DeepSeek、OCR 或 VLM。
- 不重新批量生成 embedding。
- 不写 `evidence_items`、`ai_assessment_suggestions`、assessment、risk、review snapshot、整改任务或 export。
- 不修改 `retrieve_evidence()`、`SingleReportWorkflow`、API、前端或正式输出门禁。
- 不进入 Phase 2；Phase 2 只保留为可选 AI suggestion 增强方向。
- 不进入 Phase 3；向量候选不得晋升为正式 evidence 或影响 assessment。
- 不推送远端。

## 2. 文件结构

### 新增

- `backend/src/tools/shadow_context_acceptance.py`
  - 只负责加载既有离线文件、建立三路逐项对比、计算指标、执行结构审计和渲染验收报告。
  - 不读取环境变量，不连接数据库，不调用外部服务。
- `backend/src/tools/finalize_shadow_rag_phase1.py`
  - 只负责 CLI 编排、输入指纹、只读数据库事务、两次 context 构建、正式表计数前后对比和输出落盘。
  - 强制 `EMBEDDING_ENABLED=false`。
- `backend/tests/tools/test_shadow_context_acceptance.py`
  - 覆盖三路指标、无 gold 排除、结构错误、增益/损失分类、报告生成和输出路径。
- `backend/tests/tools/test_finalize_shadow_rag_phase1.py`
  - 覆盖外部调用阻断、只读事务、确定性构建、输入指纹、正式表计数一致和 CLI 输出。
- `docs/product/rag-phase1.5-acceptance-report.md`
  - 保存最终自动工程验收结论、指标、限制、冻结边界和后续路线。

### 修改

- `README.md`
  - 将 RAG 状态更新为 Phase 1.5 已完成自动工程验收。
- `docs/DESIGN.md`
  - 固化 Phase 1.5 架构、工程 gold 口径、正式链路隔离和 Phase 2–3 边界。
- `docs/DEVELOPMENT.md`
  - 增加一条无外部调用的 Phase 1.5 封版命令及产物说明。
- `docs/plan/siliconflow-bge-m3-shadow-embedding-plan.md`
  - 将 Phase 1.5 标记为完成，将 Phase 2 记为可选增强，将 Phase 3 记为关闭。

### 不修改

- `backend/src/tools/evaluate_shadow_retrieval.py`
- `backend/src/tools/build_shadow_rag_contexts.py`
- `backend/src/tools/evaluate_shadow_rag.py`
- `backend/src/workflows/single_report_workflow.py`
- `backend/src/services/ai_assessment_service.py`
- 数据库 ORM、Alembic migration、API 和前端。

## 3. 输出契约

封版命令固定输出：

```text
tmp/embedding/envision_phase1_5_contexts.jsonl
tmp/embedding/envision_phase1_5_acceptance_cases.csv
tmp/embedding/envision_phase1_5_acceptance_summary.json
tmp/embedding/envision_phase1_5_input_manifest.json
tmp/embedding/envision_phase1_5_formal_state.json
tmp/embedding/envision_phase1_5_acceptance_report.md
```

逐项 CSV 至少包含：

```text
report_id
requirement_id
gold_pages
rule_pages
vector_pages
hybrid_pages
rule_first_hit_rank
vector_first_hit_rank
hybrid_first_hit_rank
rule_hit_at_1
rule_hit_at_3
rule_hit_at_5
vector_hit_at_1
vector_hit_at_3
vector_hit_at_5
hybrid_hit_at_1
hybrid_hit_at_3
hybrid_hit_at_5
rule_recall_at_1
rule_recall_at_3
rule_recall_at_5
vector_recall_at_1
vector_recall_at_3
vector_recall_at_5
hybrid_recall_at_1
hybrid_recall_at_3
hybrid_recall_at_5
comparison_bucket
context_hash
context_size
duplicate_page_count
unresolved_rule_pages
```

`comparison_bucket` 固定使用：

```text
hybrid_gain
hybrid_loss
both_hit
neither_hit
not_evaluated
```

汇总 JSON 至少包含：

```text
report_id
run_metadata
case_count
evaluated_case_count
no_gold_page_case_count
unique_requirement_count
context_count
unique_context_hash_count
duplicate_page_context_count
unresolved_rule_page_context_count
out_of_range_page_count
invalid_shadow_evidence_id_count
invalid_rrf_evidence_count
context_size_not_5_count
deterministic_hash_mismatch_count
rule_metrics
vector_metrics
hybrid_metrics
hybrid_gain_case_count
hybrid_loss_case_count
formal_table_counts_before
formal_table_counts_after
formal_table_counts_unchanged
gates
ok
limitations
```

## 4. 验收门禁

### 4.1 结构硬门禁

- `case_count == 499`
- `evaluated_case_count == 119`
- `unique_requirement_count == 499`
- `context_count == 499`
- `unique_context_hash_count == 499`
- `duplicate_page_context_count == 0`
- `unresolved_rule_page_context_count == 0`
- `out_of_range_page_count == 0`
- `invalid_shadow_evidence_id_count == 0`
- `invalid_rrf_evidence_count == 0`
- `context_size_not_5_count == 0`
- `deterministic_hash_mismatch_count == 0`
- `formal_table_counts_unchanged == true`
- `EMBEDDING_ENABLED == false`

### 4.2 相对质量门禁

- `hybrid.hit_at_5 >= rule.hit_at_5`
- `hybrid.recall_at_5 >= rule.recall_at_5`
- `hybrid.mrr >= rule.mrr`
- `hybrid_gain_case_count >= hybrid_loss_case_count`

### 4.3 正式业务门禁

- Envision v3 保持 `577/499/78/0`。
- global fallback 保持 0。
- 新增 false disclosed 保持 0。
- 新增 wrong source page 保持 0。
- 最终裁决 pending 保持 0。
- audit 保持 0 error、0 warning。
- 不新增 migration。
- 正式分析、风险、人工复核和输出相关表行数前后相同。

### 4.4 结论限制

验收报告必须明确：

- 历史 `correct_pdf_pages` 只作为现有工程 gold。
- 无 gold requirement 不进入召回指标分母。
- 候选命中历史页码不等于披露充分。
- 相似度与 RRF 分数不构成 GRI 合规判断。
- 本阶段不构成 GRI 专家认证、外部鉴证或最终合规结论。

---

## Task 1：建立三路指标纯函数

**Files:**

- Create: `backend/src/tools/shadow_context_acceptance.py`
- Create: `backend/tests/tools/test_shadow_context_acceptance.py`

- [ ] **Step 1：写规则、向量、混合三路指标失败测试**

在 `backend/tests/tools/test_shadow_context_acceptance.py` 创建：

```python
from src.tools.shadow_context_acceptance import (
    build_comparison_case,
    compute_method_metrics,
)


def test_comparison_metrics_use_only_cases_with_gold_pages():
    cases = [
        build_comparison_case(
            report_id="report-envision",
            requirement_id="GRI 305-1-a",
            gold_pages=[40, 41],
            rule_pages=[40, 8],
            vector_pages=[41, 9, 40],
            hybrid_pages=[40, 41, 9],
            context_hash="a" * 64,
            unresolved_rule_pages=[],
        ),
        build_comparison_case(
            report_id="report-envision",
            requirement_id="GRI 305-2-a",
            gold_pages=[],
            rule_pages=[42],
            vector_pages=[42],
            hybrid_pages=[42],
            context_hash="b" * 64,
            unresolved_rule_pages=[],
        ),
    ]

    rule = compute_method_metrics(cases, method="rule")
    vector = compute_method_metrics(cases, method="vector")
    hybrid = compute_method_metrics(cases, method="hybrid")

    assert rule["evaluated_case_count"] == 1
    assert rule["no_gold_page_case_count"] == 1
    assert rule["hit_at_1"] == 1.0
    assert rule["recall_at_1"] == 0.5
    assert vector["recall_at_3"] == 1.0
    assert hybrid["recall_at_3"] == 1.0
    assert hybrid["mrr"] == 1.0
```

- [ ] **Step 2：运行测试确认失败**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/tools/test_shadow_context_acceptance.py::test_comparison_metrics_use_only_cases_with_gold_pages -q --basetemp ../tmp/pytest-phase1-5-metrics-red
```

Expected: FAIL，`src.tools.shadow_context_acceptance` 尚不存在。

- [ ] **Step 3：实现页面规范化和单方法指标**

在 `backend/src/tools/shadow_context_acceptance.py` 实现以下接口，复用 `parse_page_list()`：

```python
from __future__ import annotations

from typing import Any, Literal

from src.tools.evaluate_shadow_retrieval import parse_page_list


MethodName = Literal["rule", "vector", "hybrid"]


def build_comparison_case(
    *,
    report_id: str,
    requirement_id: str,
    gold_pages: object,
    rule_pages: object,
    vector_pages: object,
    hybrid_pages: object,
    context_hash: str,
    unresolved_rule_pages: object,
) -> dict[str, Any]:
    if not report_id.strip():
        raise ValueError("report_id is required")
    if not requirement_id.strip():
        raise ValueError("requirement_id is required")
    if len(context_hash) != 64:
        raise ValueError("context_hash must be sha256")
    case: dict[str, Any] = {
        "report_id": report_id.strip(),
        "requirement_id": requirement_id.strip(),
        "gold_pages": parse_page_list(gold_pages),
        "rule_pages": parse_page_list(rule_pages)[:5],
        "vector_pages": parse_page_list(vector_pages)[:5],
        "hybrid_pages": parse_page_list(hybrid_pages)[:5],
        "context_hash": context_hash,
        "unresolved_rule_pages": parse_page_list(
            unresolved_rule_pages
        ),
    }
    gold = set(case["gold_pages"])
    for method in ("rule", "vector", "hybrid"):
        pages = case[f"{method}_pages"]
        first_hit_rank = next(
            (
                rank
                for rank, page in enumerate(pages, start=1)
                if page in gold
            ),
            None,
        )
        case[f"{method}_first_hit_rank"] = (
            first_hit_rank if gold else None
        )
        for k in (1, 3, 5):
            matched = set(pages[:k]) & gold
            case[f"{method}_hit_at_{k}"] = (
                int(bool(matched)) if gold else None
            )
            case[f"{method}_recall_at_{k}"] = (
                round(len(matched) / len(gold), 6)
                if gold
                else None
            )
    return case


def compute_method_metrics(
    cases: list[dict[str, Any]],
    *,
    method: MethodName,
    k_values: tuple[int, ...] = (1, 3, 5),
) -> dict[str, int | float]:
    if method not in {"rule", "vector", "hybrid"}:
        raise ValueError("unsupported method")
    if not k_values or any(k < 1 for k in k_values):
        raise ValueError("k_values must contain positive integers")
    page_field = f"{method}_pages"
    evaluated = [
        case for case in cases if parse_page_list(case["gold_pages"])
    ]
    denominator = len(evaluated)
    summary: dict[str, int | float] = {
        "case_count": len(cases),
        "evaluated_case_count": denominator,
        "no_gold_page_case_count": len(cases) - denominator,
    }
    reciprocal_rank_total = 0.0
    for k in sorted(set(k_values)):
        hit_total = 0
        recall_total = 0.0
        for case in evaluated:
            gold = set(parse_page_list(case["gold_pages"]))
            pages = parse_page_list(case[page_field])
            matched = set(pages[:k]) & gold
            hit_total += bool(matched)
            recall_total += len(matched) / len(gold)
        summary[f"hit_at_{k}"] = (
            round(hit_total / denominator, 6)
            if denominator
            else 0.0
        )
        summary[f"recall_at_{k}"] = (
            round(recall_total / denominator, 6)
            if denominator
            else 0.0
        )
    for case in evaluated:
        gold = set(parse_page_list(case["gold_pages"]))
        pages = parse_page_list(case[page_field])
        first_hit_rank = next(
            (
                rank
                for rank, page in enumerate(pages, start=1)
                if page in gold
            ),
            None,
        )
        if first_hit_rank is not None:
            reciprocal_rank_total += 1 / first_hit_rank
    summary["mrr"] = (
        round(reciprocal_rank_total / denominator, 6)
        if denominator
        else 0.0
    )
    return summary
```

- [ ] **Step 4：运行指标测试**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/tools/test_shadow_context_acceptance.py::test_comparison_metrics_use_only_cases_with_gold_pages -q --basetemp ../tmp/pytest-phase1-5-metrics-green
```

Expected: PASS。

## Task 2：建立逐项差异分类与结构审计

**Files:**

- Modify: `backend/src/tools/shadow_context_acceptance.py`
- Modify: `backend/tests/tools/test_shadow_context_acceptance.py`

- [ ] **Step 1：写增益、损失和结构错误失败测试**

追加：

```python
import pytest

from src.tools.shadow_context_acceptance import audit_contexts


def test_build_comparison_case_classifies_hybrid_gain_and_loss():
    gain = build_comparison_case(
        report_id="report-envision",
        requirement_id="GRI 305-1-a",
        gold_pages=[40],
        rule_pages=[8],
        vector_pages=[40],
        hybrid_pages=[40, 8],
        context_hash="a" * 64,
        unresolved_rule_pages=[],
    )
    loss = build_comparison_case(
        report_id="report-envision",
        requirement_id="GRI 305-2-a",
        gold_pages=[41],
        rule_pages=[41],
        vector_pages=[9],
        hybrid_pages=[9],
        context_hash="b" * 64,
        unresolved_rule_pages=[],
    )

    assert gain["comparison_bucket"] == "hybrid_gain"
    assert loss["comparison_bucket"] == "hybrid_loss"


def test_audit_contexts_rejects_duplicate_pages_and_foreign_report():
    contexts = [
        {
            "report_id": "report-other",
            "requirement_id": "GRI 305-1-a",
            "context_hash": "a" * 64,
            "top_k": 2,
            "unresolved_rule_pages": [],
            "evidence": [
                {
                    "shadow_evidence_id": "shadow-chunk:chunk-1",
                    "source_page": 40,
                },
                {
                    "shadow_evidence_id": "shadow-chunk:chunk-2",
                    "source_page": 40,
                },
            ],
        }
    ]

    with pytest.raises(ValueError, match="report_id"):
        audit_contexts(
            contexts,
            report_id="report-envision",
            report_total_pages=78,
            expected_count=1,
            require_exact_context_size=False,
        )
```

- [ ] **Step 2：运行测试确认失败**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/tools/test_shadow_context_acceptance.py -q --basetemp ../tmp/pytest-phase1-5-audit-red
```

Expected: FAIL，分类字段和 `audit_contexts()` 尚未实现。

- [ ] **Step 3：实现逐项分类**

在逐项指标循环之后、`return case` 之前增加：

```python
gold = set(case["gold_pages"])
if not gold:
    case["comparison_bucket"] = "not_evaluated"
else:
    rule_hit = bool(set(case["rule_pages"]) & gold)
    hybrid_hit = bool(set(case["hybrid_pages"]) & gold)
    if hybrid_hit and not rule_hit:
        case["comparison_bucket"] = "hybrid_gain"
    elif rule_hit and not hybrid_hit:
        case["comparison_bucket"] = "hybrid_loss"
    elif rule_hit and hybrid_hit:
        case["comparison_bucket"] = "both_hit"
    else:
        case["comparison_bucket"] = "neither_hit"
return case
```

其中 `case` 是原返回字典，禁止按向量命中结果替代规则—混合比较口径。

- [ ] **Step 4：实现结构审计**

实现：

```python
def audit_contexts(
    contexts: list[dict[str, Any]],
    *,
    report_id: str,
    report_total_pages: int,
    expected_count: int = 499,
    require_exact_context_size: bool = True,
) -> dict[str, int]:
    if len(contexts) != expected_count:
        raise ValueError("unexpected context count")
    requirement_ids: set[str] = set()
    context_hashes: set[str] = set()
    duplicate_page_context_count = 0
    unresolved_rule_page_context_count = 0
    out_of_range_page_count = 0
    invalid_shadow_evidence_id_count = 0
    context_size_not_5_count = 0
    expected_rrf_metadata = {
        "retrieval_mode": "hybrid_rrf",
        "provider": "siliconflow",
        "model": "BAAI/bge-m3",
        "vector_pool_k": 10,
        "context_k": 5,
        "top_k": 5,
        "rrf_rule_weight": 2.0,
        "rrf_vector_weight": 1.0,
        "rrf_constant": 60,
    }

    for context in contexts:
        if context.get("report_id") != report_id:
            raise ValueError("context report_id mismatch")
        if any(
            context.get(field) != value
            for field, value in expected_rrf_metadata.items()
        ):
            raise ValueError("context RRF metadata mismatch")
        requirement_id = str(
            context.get("requirement_id") or ""
        ).strip()
        if not requirement_id or requirement_id in requirement_ids:
            raise ValueError("duplicate or empty requirement_id")
        requirement_ids.add(requirement_id)
        context_hash = str(context.get("context_hash") or "")
        if len(context_hash) != 64 or context_hash in context_hashes:
            raise ValueError("duplicate or invalid context_hash")
        context_hashes.add(context_hash)
        evidence = list(context.get("evidence") or [])
        pages = [
            int(item.get("source_page") or 0)
            for item in evidence
        ]
        if len(pages) != len(set(pages)):
            duplicate_page_context_count += 1
        out_of_range_page_count += sum(
            page < 1 or page > report_total_pages
            for page in pages
        )
        invalid_shadow_evidence_id_count += sum(
            not str(
                item.get("shadow_evidence_id") or ""
            ).startswith("shadow-chunk:")
            for item in evidence
        )
        if len(evidence) != 5:
            context_size_not_5_count += 1
        if context.get("unresolved_rule_pages"):
            unresolved_rule_page_context_count += 1

    if duplicate_page_context_count:
        raise ValueError("duplicate source pages in context")
    if out_of_range_page_count:
        raise ValueError("context source page out of range")
    if invalid_shadow_evidence_id_count:
        raise ValueError("invalid shadow evidence id")
    if unresolved_rule_page_context_count:
        raise ValueError("unresolved rule pages remain")
    if require_exact_context_size and context_size_not_5_count:
        raise ValueError("context size must equal 5")
    return {
        "context_count": len(contexts),
        "unique_requirement_count": len(requirement_ids),
        "unique_context_hash_count": len(context_hashes),
        "duplicate_page_context_count": duplicate_page_context_count,
        "unresolved_rule_page_context_count": (
            unresolved_rule_page_context_count
        ),
        "out_of_range_page_count": out_of_range_page_count,
        "invalid_shadow_evidence_id_count": (
            invalid_shadow_evidence_id_count
        ),
        "context_size_not_5_count": context_size_not_5_count,
    }
```

实现时还必须逐条验证 `retrieval_sources`、`rule_rank`、`vector_rank`
和 `fusion_score`：来源组合只能为 rule、vector 或双路；vector rank
不得超过 10；融合分数必须按固定权重 2：1 和常数 60 重算一致。失败计入
`invalid_rrf_evidence_count` 并阻断验收。

- [ ] **Step 5：运行结构审计测试**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/tools/test_shadow_context_acceptance.py -q --basetemp ../tmp/pytest-phase1-5-audit-green
```

Expected: PASS。

## Task 3：加载既有召回明细与混合 context

**Files:**

- Modify: `backend/src/tools/shadow_context_acceptance.py`
- Modify: `backend/tests/tools/test_shadow_context_acceptance.py`

- [ ] **Step 1：写输入关联失败测试**

测试至少覆盖：

- retrieval CSV 和 context JSONL 必须各有唯一 499 个 requirement；
- 两边 requirement 集合必须完全相同；
- report ID 必须等于 CLI 指定报告；
- `hybrid_pages` 必须从 context evidence 的 `source_page` 顺序生成；
- 规则页取 `rule_pages[:5]`；
- 向量页优先读取 `vector_source_pages[:5]`，保留页级去重顺序；
- context JSONL 重复 requirement、空行或非法 JSON 立即失败。

示例：

```python
def test_load_comparison_cases_joins_by_requirement_id(tmp_path):
    retrieval_path = tmp_path / "cases.csv"
    contexts_path = tmp_path / "contexts.jsonl"
    retrieval_path.write_text(
        (
            "report_id,requirement_id,gold_pages,rule_pages,"
            "vector_source_pages\n"
            'report-envision,GRI 2-1-a,"[1,3]","[3,6]",'
            '"[1,8,3]"\n'
        ),
        encoding="utf-8",
    )
    contexts_path.write_text(
        (
            '{"report_id":"report-envision",'
            '"requirement_id":"GRI 2-1-a",'
            '"context_hash":"' + "a" * 64 + '",'
            '"unresolved_rule_pages":[],'
            '"evidence":[{"source_page":3},{"source_page":1}]}\n'
        ),
        encoding="utf-8",
    )

    cases, contexts = load_comparison_inputs(
        retrieval_path,
        contexts_path,
        report_id="report-envision",
        expected_count=1,
    )

    assert cases[0]["rule_pages"] == [3, 6]
    assert cases[0]["vector_pages"] == [1, 8, 3]
    assert cases[0]["hybrid_pages"] == [3, 1]
    assert len(contexts) == 1
```

- [ ] **Step 2：运行测试确认失败**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/tools/test_shadow_context_acceptance.py::test_load_comparison_cases_joins_by_requirement_id -q --basetemp ../tmp/pytest-phase1-5-load-red
```

Expected: FAIL，`load_comparison_inputs()` 尚未实现。

- [ ] **Step 3：实现输入加载**

实现接口
`load_comparison_inputs(retrieval_cases_path: Path, contexts_path: Path, *, report_id: str, expected_count: int = 499) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]`。

实现要求：

1. CSV 使用 `encoding="utf-8-sig"` 和 `csv.DictReader`。
2. JSONL 使用 `encoding="utf-8"`，逐行 `json.loads()`。
3. 空行忽略；非法 JSON 抛出包含行号的 `ValueError`。
4. 两边分别建立 `requirement_id -> row/context` 映射，发现重复立即失败。
5. 两边数量都必须等于 `expected_count`。
6. 两边 requirement ID 集合必须完全一致；错误信息输出缺失数量，不输出报告正文。
7. 使用 `build_comparison_case()` 生成按 requirement ID 排序的结果。
8. 从 context evidence 原始列表写入 `context_size`；用原始
   `source_page` 数量减唯一页数量写入 `duplicate_page_count`。
9. 逐项结果必须完整包含输出契约中的 first-hit、hit、recall、
   `comparison_bucket`、context hash 和结构诊断字段。
10. 不把 `manual_suggested_verdict` 当作本阶段质量门禁。

- [ ] **Step 4：运行加载与指标测试**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/tools/test_shadow_context_acceptance.py -q --basetemp ../tmp/pytest-phase1-5-load-green
```

Expected: PASS。

## Task 4：生成汇总、门禁和 Markdown 报告

**Files:**

- Modify: `backend/src/tools/shadow_context_acceptance.py`
- Modify: `backend/tests/tools/test_shadow_context_acceptance.py`

- [ ] **Step 1：写门禁失败和报告限制测试**

追加：

```python
def test_build_acceptance_summary_requires_hybrid_not_below_rule():
    cases = [
        build_comparison_case(
            report_id="report-envision",
            requirement_id="GRI 305-1-a",
            gold_pages=[40],
            rule_pages=[40],
            vector_pages=[8],
            hybrid_pages=[8],
            context_hash="a" * 64,
            unresolved_rule_pages=[],
        )
    ]

    summary = build_acceptance_summary(
        report_id="report-envision",
        run_metadata={
            "git_head": "0cf3cbc",
            "input_manifest_path": (
                "tmp/embedding/"
                "envision_phase1_5_input_manifest.json"
            ),
            "retrieval_mode": "hybrid_rrf",
        },
        cases=cases,
        context_audit={
            "context_count": 1,
            "unique_requirement_count": 1,
            "unique_context_hash_count": 1,
            "duplicate_page_context_count": 0,
            "unresolved_rule_page_context_count": 0,
            "out_of_range_page_count": 0,
            "invalid_shadow_evidence_id_count": 0,
            "context_size_not_5_count": 0,
        },
        deterministic_hash_mismatch_count=0,
        formal_table_counts_before={"assessments": 10},
        formal_table_counts_after={"assessments": 10},
        embedding_enabled=False,
        expected_count=1,
    )

    assert summary["gates"]["hybrid_hit_at_5_not_below_rule"] is False
    assert summary["ok"] is False
    report = render_acceptance_report(summary)
    assert "不构成 GRI 专家认证" in report
    assert "无 gold requirement 不进入召回指标分母" in report
```

- [ ] **Step 2：运行测试确认失败**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/tools/test_shadow_context_acceptance.py::test_build_acceptance_summary_requires_hybrid_not_below_rule -q --basetemp ../tmp/pytest-phase1-5-summary-red
```

Expected: FAIL，`build_acceptance_summary()` 和 `render_acceptance_report()` 尚未实现。

- [ ] **Step 3：实现汇总和门禁**

实现：

```python
def build_acceptance_summary(
    *,
    report_id: str,
    run_metadata: dict[str, Any],
    cases: list[dict[str, Any]],
    context_audit: dict[str, int],
    deterministic_hash_mismatch_count: int,
    formal_table_counts_before: dict[str, int],
    formal_table_counts_after: dict[str, int],
    embedding_enabled: bool,
    expected_count: int = 499,
) -> dict[str, Any]:
    rule = compute_method_metrics(cases, method="rule")
    vector = compute_method_metrics(cases, method="vector")
    hybrid = compute_method_metrics(cases, method="hybrid")
    gain_count = sum(
        case["comparison_bucket"] == "hybrid_gain"
        for case in cases
    )
    loss_count = sum(
        case["comparison_bucket"] == "hybrid_loss"
        for case in cases
    )
    counts_unchanged = (
        formal_table_counts_before == formal_table_counts_after
    )
    gates = {
        "case_count_499": len(cases) == expected_count,
        "context_count_499": (
            context_audit["context_count"] == expected_count
        ),
        "unique_requirement_count_499": (
            context_audit["unique_requirement_count"]
            == expected_count
        ),
        "unique_context_hash_count_499": (
            context_audit["unique_context_hash_count"]
            == expected_count
        ),
        "duplicate_page_context_count_zero": (
            context_audit["duplicate_page_context_count"] == 0
        ),
        "unresolved_rule_page_context_count_zero": (
            context_audit[
                "unresolved_rule_page_context_count"
            ]
            == 0
        ),
        "out_of_range_page_count_zero": (
            context_audit["out_of_range_page_count"] == 0
        ),
        "invalid_shadow_evidence_id_count_zero": (
            context_audit[
                "invalid_shadow_evidence_id_count"
            ]
            == 0
        ),
        "context_size_not_5_count_zero": (
            context_audit["context_size_not_5_count"] == 0
        ),
        "deterministic_hash_mismatch_count_zero": (
            deterministic_hash_mismatch_count == 0
        ),
        "formal_table_counts_unchanged": counts_unchanged,
        "embedding_disabled": not embedding_enabled,
        "hybrid_hit_at_5_not_below_rule": (
            hybrid["hit_at_5"] >= rule["hit_at_5"]
        ),
        "hybrid_recall_at_5_not_below_rule": (
            hybrid["recall_at_5"] >= rule["recall_at_5"]
        ),
        "hybrid_mrr_not_below_rule": (
            hybrid["mrr"] >= rule["mrr"]
        ),
        "hybrid_gain_not_below_loss": gain_count >= loss_count,
    }
    return {
        "report_id": report_id,
        "run_metadata": run_metadata,
        "case_count": len(cases),
        "evaluated_case_count": hybrid[
            "evaluated_case_count"
        ],
        "no_gold_page_case_count": hybrid[
            "no_gold_page_case_count"
        ],
        **context_audit,
        "deterministic_hash_mismatch_count": (
            deterministic_hash_mismatch_count
        ),
        "rule_metrics": rule,
        "vector_metrics": vector,
        "hybrid_metrics": hybrid,
        "hybrid_gain_case_count": gain_count,
        "hybrid_loss_case_count": loss_count,
        "formal_table_counts_before": formal_table_counts_before,
        "formal_table_counts_after": formal_table_counts_after,
        "formal_table_counts_unchanged": counts_unchanged,
        "gates": gates,
        "ok": all(gates.values()),
        "limitations": [
            "历史 correct_pdf_pages 只作为现有工程 gold。",
            "无 gold requirement 不进入召回指标分母。",
            "页码命中不等于披露充分。",
            "本结果不构成 GRI 专家认证、外部鉴证或最终合规结论。",
        ],
    }
```

- [ ] **Step 4：实现 Markdown 报告**

`render_acceptance_report(summary)` 必须输出：

1. 结论：通过或未通过。
2. 从 `summary["run_metadata"]` 读取当前 Git、报告 ID、输入 manifest
   相对路径和固定检索参数；缺少任一必填元数据时立即失败。
3. 规则、向量、混合三路 `hit@1/3/5`、`recall@1/3/5` 和 MRR 表格。
4. hybrid gain/loss 数量。
5. 18 项门禁逐项通过/失败。
6. 正式表前后计数。
7. 限制声明。
8. Phase 2 为可选增强、Phase 3 关闭。

函数只返回字符串，不直接写文件。

- [ ] **Step 5：运行全部纯评估测试**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/tools/test_shadow_context_acceptance.py -q --basetemp ../tmp/pytest-phase1-5-summary-green
```

Expected: PASS。

## Task 5：实现只读封版编排器

**Files:**

- Create: `backend/src/tools/finalize_shadow_rag_phase1.py`
- Create: `backend/tests/tools/test_finalize_shadow_rag_phase1.py`

- [ ] **Step 1：写外部调用阻断和正式表计数测试**

创建测试：

```python
import pytest

from src.tools.finalize_shadow_rag_phase1 import (
    FORMAL_TABLE_MODELS,
    capture_formal_table_counts,
    ensure_offline_phase1_5,
)


def test_phase1_5_finalizer_blocks_when_embedding_enabled():
    with pytest.raises(
        RuntimeError,
        match="EMBEDDING_ENABLED=false",
    ):
        ensure_offline_phase1_5(embedding_enabled=True)


def test_formal_table_model_set_excludes_shadow_embeddings():
    assert "document_chunk_embeddings" not in FORMAL_TABLE_MODELS
    assert {
        "reports",
        "analysis_runs",
        "analysis_stage_events",
        "document_pages",
        "document_chunks",
        "standard_requirements",
        "disclosure_tasks",
        "assessments",
        "ai_assessment_suggestions",
        "assessment_risks",
        "evidence_items",
        "recommendations",
        "review_decisions",
        "review_snapshots",
        "review_change_events",
        "improvement_actions",
        "export_versions",
        "audit_events",
    } == set(FORMAL_TABLE_MODELS)
```

- [ ] **Step 2：运行测试确认失败**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/tools/test_finalize_shadow_rag_phase1.py -q --basetemp ../tmp/pytest-phase1-5-finalizer-red
```

Expected: FAIL，封版编排器尚不存在。

- [ ] **Step 3：实现正式表映射和只读计数**

在 `backend/src/tools/finalize_shadow_rag_phase1.py` 导入以下 ORM：

```python
from sqlalchemy import func, select, text

from src.db.models import (
    AIAssessmentSuggestionRecord,
    AnalysisRunRecord,
    AnalysisStageEventRecord,
    AssessmentRecord,
    AssessmentRiskRecord,
    AuditEventRecord,
    DisclosureTaskRecord,
    DocumentChunkRecord,
    DocumentPageRecord,
    EvidenceItemRecord,
    ExportVersionRecord,
    ImprovementActionRecord,
    RecommendationRecord,
    ReportRecord,
    ReviewChangeEventRecord,
    ReviewDecisionRecord,
    ReviewSnapshotRecord,
    StandardRequirementRecord,
)
```

固定映射：

```python
FORMAL_TABLE_MODELS = {
    "reports": ReportRecord,
    "analysis_runs": AnalysisRunRecord,
    "analysis_stage_events": AnalysisStageEventRecord,
    "document_pages": DocumentPageRecord,
    "document_chunks": DocumentChunkRecord,
    "standard_requirements": StandardRequirementRecord,
    "disclosure_tasks": DisclosureTaskRecord,
    "assessments": AssessmentRecord,
    "ai_assessment_suggestions": (
        AIAssessmentSuggestionRecord
    ),
    "assessment_risks": AssessmentRiskRecord,
    "evidence_items": EvidenceItemRecord,
    "recommendations": RecommendationRecord,
    "review_decisions": ReviewDecisionRecord,
    "review_snapshots": ReviewSnapshotRecord,
    "review_change_events": ReviewChangeEventRecord,
    "improvement_actions": ImprovementActionRecord,
    "export_versions": ExportVersionRecord,
    "audit_events": AuditEventRecord,
}


def ensure_offline_phase1_5(*, embedding_enabled: bool) -> None:
    if embedding_enabled:
        raise RuntimeError(
            "Phase 1.5 finalization requires "
            "EMBEDDING_ENABLED=false"
        )


def capture_formal_table_counts(session) -> dict[str, int]:
    return {
        table_name: int(
            session.scalar(
                select(func.count()).select_from(model)
            )
            or 0
        )
        for table_name, model in FORMAL_TABLE_MODELS.items()
    }
```

- [ ] **Step 4：写只读事务和确定性构建测试**

测试使用 fake session、fake repository 和临时文件，必须断言：

- 第一条 SQL 为 `SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY`；
- 只调用 `list_document_chunks(report_id=...)`；
- 不调用 `add()`、`flush()`、`commit()` 或任何 repository 写方法；
- `load_shadow_contexts_from_cases()` 连续调用两次；
- 两次 `requirement_id -> context_hash` 映射完全一致；
- 正式表前后计数完全一致；
- `EMBEDDING_ENABLED=false` 时不创建 `EmbeddingClient`。

- [ ] **Step 5：实现输入指纹**

实现：

```python
def fingerprint_file(
    path: Path,
    *,
    project_root: Path,
) -> dict[str, str | int]:
    content = path.read_bytes()
    return {
        "path": path.resolve()
        .relative_to(project_root.resolve())
        .as_posix(),
        "sha256": hashlib.sha256(content).hexdigest(),
        "size_bytes": len(content),
    }
```

输入 manifest 必须包含：

- retrieval cases CSV；
- GRI v3 requirements manifest；
- Envision regeneration baseline CSV；
- Envision 人工工作簿；
- Envision 最终裁决 CSV；
- Envision PDF；
- context JSONL；
- Git HEAD；
- provider、model、向量池、context K、RRF 权重和常数。

manifest 只保存相对路径、hash 和大小，不复制原始报告或人工工作簿。

- [ ] **Step 6：实现封版编排**

实现接口
`finalize_phase1_5(*, report_id: str, retrieval_cases_path: Path, requirements_path: Path, baseline_path: Path, manual_review_path: Path, final_adjudications_path: Path, report_pdf_path: Path, context_output: str, output_prefix: str, report_total_pages: int, git_head: str) -> dict[str, Any]`。

执行顺序固定：

1. `settings = get_settings()`。
2. `ensure_offline_phase1_5(embedding_enabled=settings.embedding_enabled)`。
3. 验证 `report_total_pages == 78`、`report_id` 非空、所有输入存在。
4. 打开 `SessionLocal()`。
5. 在第一次查询前执行：

   ```python
   session.execute(
       text(
           "SET TRANSACTION ISOLATION LEVEL "
           "REPEATABLE READ READ ONLY"
       )
   )
   ```

6. 捕获正式表计数 before。
7. `Repository(session).list_document_chunks(report_id=report_id)`；空结果立即失败。
8. 使用固定参数调用 `load_shadow_contexts_from_cases()` 两次：

   ```text
   retrieval_mode=hybrid_rrf
   vector_pool_k=10
   context_k=5
   rrf_rule_weight=2
   rrf_vector_weight=1
   rrf_constant=60
   ```

9. 比较两次 `requirement_id -> context_hash`，记录 mismatch 数；非 0 时停止，不写最终报告。
10. 使用 `write_shadow_contexts()` 写第一次结果。
11. 捕获正式表计数 after。
12. 为全部输入及刚写出的 context 计算指纹，构造 input manifest；manifest
    的 `git_head` 必须等于 CLI 参数，检索参数必须等于第 8 步固定值。
13. 使用 `load_comparison_inputs()`、`audit_contexts()` 和
    `build_acceptance_summary()` 计算验收结果；将 Git、input manifest
    相对路径、provider、model 和固定检索参数放入 `run_metadata`。
14. 写逐项 CSV、summary JSON、input manifest、formal state JSON 和 Markdown。
    `output_prefix` 只派生
    `<prefix>_cases.csv`、`<prefix>_summary.json` 和
    `<prefix>_report.md`；input manifest 与 formal state 固定写到同目录的
    `envision_phase1_5_input_manifest.json` 和
    `envision_phase1_5_formal_state.json`，确保与第 3 节六类输出契约一致。
15. `summary["ok"]` 为 false 时 CLI 退出码为 1。
16. 关闭 session；不得 commit。

- [ ] **Step 7：实现 CLI**

CLI 参数固定为：

```text
--report-id                       required
--retrieval-cases                 required
--requirements                    default backend/data/manifests/gri_requirement_checklist_v3.json
--baseline                        default backend/data/review_inputs/envision_2024/baselines/current_577_review_regenerated.csv
--manual-review-workbook          default backend/data/review_inputs/envision_2024/manual/envision_2024_577_manual_review_second_review_Pro_20260719.xlsx
--final-adjudications             default backend/data/review_inputs/envision_2024/adjudication/envision_2024_result_adjudication_v1.csv
--report-pdf                      default backend/data/reports/Envision Energy 2024-zh.pdf
--context-output                  default tmp/embedding/envision_phase1_5_contexts.jsonl
--output-prefix                   default tmp/embedding/envision_phase1_5_acceptance
--report-total-pages              default 78
--git-head                        required
```

所有输出通过 `resolve_shadow_output()` 约束在 `tmp/embedding/`。

- [ ] **Step 8：运行封版编排器测试**

Run:

```powershell
cd backend
uv run --no-sync pytest tests/tools/test_finalize_shadow_rag_phase1.py -q --basetemp ../tmp/pytest-phase1-5-finalizer-green
```

Expected: PASS，测试不连接外部服务。

## Task 6：运行 focused tests 与静态检查

**Files:**

- No production changes.

- [ ] **Step 1：运行 Phase 1.5 focused tests**

Run:

```powershell
cd backend
uv run --no-sync pytest `
  tests/tools/test_shadow_context_acceptance.py `
  tests/tools/test_finalize_shadow_rag_phase1.py `
  tests/tools/test_shadow_retrieval.py `
  tests/tools/test_shadow_rag.py `
  tests/db/test_repositories.py `
  -q `
  --basetemp ../tmp/pytest-phase1-5-focused
```

Expected: PASS，0 failure；新增测试不得 skip。

- [ ] **Step 2：运行 Ruff**

Run:

```powershell
cd backend
uv run --no-sync ruff check `
  src/tools/shadow_context_acceptance.py `
  src/tools/finalize_shadow_rag_phase1.py `
  tests/tools/test_shadow_context_acceptance.py `
  tests/tools/test_finalize_shadow_rag_phase1.py
```

Expected: `All checks passed!`

- [ ] **Step 3：验证默认禁用**

Run:

```powershell
cd backend
$env:EMBEDDING_ENABLED="false"
uv run --no-sync pytest `
  tests/tools/test_embedding_client.py::test_embedding_client_blocks_when_disabled `
  -q `
  --basetemp ../tmp/pytest-phase1-5-disabled
```

Expected: PASS。

## Task 7：在 demo 数据库执行一次真实离线封版

**Files:**

- Generate only under: `tmp/embedding/`

- [ ] **Step 1：只读确认目标环境**

Run:

```powershell
cd backend
$env:APP_ENV="demo"
$env:DATABASE_URL="postgresql+psycopg://esg_agent:esg_agent@localhost:5432/esg_agent_demo"
$env:UPLOAD_DIR="backend/data/runtime/demo/uploads"
$env:DERIVED_DIR="backend/data/runtime/demo/derived"
$env:EMBEDDING_ENABLED="false"
uv run --no-sync python -c "from sqlalchemy.engine import make_url; from src.config.settings import get_settings; from src.db.session import engine; from sqlalchemy import text; s=get_settings(); print({'app_env': s.app_env, 'database': make_url(s.database_url).database, 'embedding_enabled': s.embedding_enabled}); print({'database': engine.connect().execute(text('select current_database()')).scalar_one()})"
```

Expected:

```text
app_env=demo
database=esg_agent_demo
embedding_enabled=False
```

若数据库不是 `esg_agent_demo` 或 embedding 为 true，立即停止。

- [ ] **Step 2：运行 Phase 1.5 封版命令**

Run:

```powershell
cd backend
$env:APP_ENV="demo"
$env:DATABASE_URL="postgresql+psycopg://esg_agent:esg_agent@localhost:5432/esg_agent_demo"
$env:UPLOAD_DIR="backend/data/runtime/demo/uploads"
$env:DERIVED_DIR="backend/data/runtime/demo/derived"
$env:EMBEDDING_ENABLED="false"
$phase15GitHead = git rev-parse HEAD
uv run --no-sync python -m src.tools.finalize_shadow_rag_phase1 `
  --report-id report-15401bb4334e40d4a0885730f2635b22 `
  --retrieval-cases ../tmp/embedding/envision_demo_bge_m3_shadow_retrieval_cases.csv `
  --context-output tmp/embedding/envision_phase1_5_contexts.jsonl `
  --output-prefix tmp/embedding/envision_phase1_5_acceptance `
  --report-total-pages 78 `
  --git-head $phase15GitHead
```

Expected:

- 进程退出码 0；
- summary `ok=true`；
- 499 cases；
- 499 unique requirements；
- 499 unique context hashes；
- context size 非 5 数量为 0；
- duplicate page、unresolved rule page、out-of-range page 和 invalid shadow evidence ID 均为 0；
- deterministic hash mismatch 为 0；
- 正式表 before/after 完全一致；
- hybrid Top 5 hit、recall 和 MRR 均不低于 rule Top 5；
- hybrid gain 不少于 hybrid loss。

- [ ] **Step 3：核对输出文件**

Run:

```powershell
Get-ChildItem ..\tmp\embedding\envision_phase1_5_* |
  Select-Object Name,Length,LastWriteTime
```

Expected: 六类约定输出均存在且大小大于 0。

- [ ] **Step 4：核对输入保护**

重新计算 manual workbook、baseline、final adjudications 和 PDF 的 SHA256，与 input manifest 比较。Expected: 全部一致。

## Task 8：运行后端全量测试与 Envision 冻结门禁

**Files:**

- No production changes.

- [ ] **Step 1：运行后端全量测试**

Run:

```powershell
cd backend
uv run --no-sync pytest -q --basetemp ../tmp/pytest-phase1-5-full
```

Expected: 不少于当前 686 项测试通过，0 failure；新增测试均被收集并通过。

- [ ] **Step 2：显式绑定测试库运行 Envision gate**

Run:

```powershell
cd backend
$env:APP_ENV="test"
$env:DATABASE_URL="postgresql+psycopg://esg_agent:esg_agent@localhost:5432/esg_agent_test"
uv run --no-sync python -m src.tools.regenerate_review_csv `
  --report-id envision_2024_v3 `
  --pdf "data/reports/Envision Energy 2024-zh.pdf" `
  --profile data/reports/profiles/envision_2024.json `
  --requirements data/manifests/gri_requirement_checklist_v3.json `
  --manual-review-workbook data/review_inputs/envision_2024/manual/envision_2024_577_manual_review_second_review_Pro_20260719.xlsx `
  --final-adjudications data/review_inputs/envision_2024/adjudication/envision_2024_result_adjudication_v1.csv `
  --output data/runtime/evaluations/envision_2024/current_499_review_regenerated.csv `
  --baseline data/review_inputs/envision_2024/baselines/current_577_review_regenerated.csv `
  --audit-output data/runtime/evaluations/envision_2024/current_499_review_regenerated_audit.json `
  --diff-summary-output data/runtime/evaluations/envision_2024/current_499_review_regeneration_diff_summary.json `
  --scope-summary-output data/runtime/evaluations/envision_2024/current_499_review_scope_summary.json `
  --report-total-pages 78
```

Expected:

```text
577/499/78/0
global_fallback=0
new_false_disclosed=0
new_wrong_source_page=0
final_adjudication_pending=0
audit_errors=0
audit_warnings=0
```

- [ ] **Step 3：确认正式链路没有 Phase 1.5 字段**

Run:

```powershell
rg -n "phase1_5|hybrid_rrf|fusion_score|shadow_evidence_id" `
  backend/src/api `
  backend/src/services `
  backend/src/workflows `
  frontend
```

Expected: 无新增正式消费者；现有影子工具目录之外不得出现本轮字段接入。

## Task 9：生成并写入产品级验收报告

**Files:**

- Create: `docs/product/rag-phase1.5-acceptance-report.md`
- Modify: `README.md`
- Modify: `docs/DESIGN.md`
- Modify: `docs/DEVELOPMENT.md`
- Modify: `docs/plan/siliconflow-bge-m3-shadow-embedding-plan.md`

- [ ] **Step 1：从自动报告提取已验证事实**

只从以下产物读取数字：

```text
tmp/embedding/envision_phase1_5_acceptance_summary.json
tmp/embedding/envision_phase1_5_input_manifest.json
tmp/embedding/envision_phase1_5_formal_state.json
backend/data/runtime/evaluations/envision_2024/current_499_review_scope_summary.json
backend/data/runtime/evaluations/envision_2024/current_499_review_regeneration_diff_summary.json
backend/data/runtime/evaluations/envision_2024/current_499_review_regenerated_audit.json
```

禁止从终端记忆手写指标。

- [ ] **Step 2：创建中文验收报告**

`docs/product/rag-phase1.5-acceptance-report.md` 固定包含：

1. 验收结论与冻结名称：`混合影子 RAG Phase 1.5 工程基线`。
2. Git、migration、报告 ID、provider、model、参数。
3. 输入资产相对路径与 SHA256。
4. 规则、向量、混合三路指标表。
5. gain/loss 和结构门禁。
6. 正式业务表 before/after。
7. Envision `577/499/78/0` 零回归。
8. 外部服务未调用说明。
9. 历史 gold 与无专家判断的限制。
10. Phase 2 可选、Phase 3 关闭。

- [ ] **Step 3：更新 README**

项目状态增加：

- Phase 1.5 已完成自动工程验收；
- 混合 RAG 仍是离线影子能力；
- 不构成 ESG 专家判断；
- 正式产品继续使用冻结规则 assessment。

- [ ] **Step 4：更新 DESIGN**

记录：

- Phase 1.5 参数与输出；
- 自动工程 gold 口径；
- 正式链路隔离；
- Phase 2 为可选 AI suggestion 增强；
- Phase 3 保持关闭。

- [ ] **Step 5：更新 DEVELOPMENT**

增加封版命令、输出说明、测试命令和故障停止条件。文档不得写本机绝对路径。

- [ ] **Step 6：更新总计划状态**

在 `docs/plan/siliconflow-bge-m3-shadow-embedding-plan.md` 中：

- 将 Phase 1.5 更新为“自动工程验收完成”；
- Phase 2 更新为“可选增强，未启动”；
- Phase 3 更新为“关闭，需要独立高质量 gold 或专家条件后重新决策”。

## Task 10：最终自检、审查和本地提交

**Files:**

- All files changed by Tasks 1–9.

- [ ] **Step 1：计划覆盖自检**

逐项确认：

- 499 三路比较已执行；
- 无 gold 已排除指标分母；
- 六类输出已生成；
- 结构、相对质量、正式业务和限制门禁均有结果；
- Phase 2–3 没有实现性改动。

- [ ] **Step 2：运行仓库卫生检查**

Run:

```powershell
git diff --check
rg -n -i "(EMBEDDING_API_KEY|SILICONFLOW_API_KEY)\s*=\s*(sk-|[A-Za-z0-9_-]{24,})" `
  README.md docs backend/.env.example
$drivePattern = "(?<![A-Za-z0-9_+.-])[A-Za-z]:[\\/]"
Select-String `
  -Path docs/plan/hybrid-shadow-rag-phase1.5-finalization-plan.md,docs/product/rag-phase1.5-acceptance-report.md `
  -Pattern $drivePattern
```

Expected:

- `git diff --check` 无错误；
- 无密钥值；
- 新增文档无本机绝对路径。

- [ ] **Step 3：独立代码审查**

审查重点：

- 指标分母是否只包含有 gold case；
- rule/vector/hybrid 是否都严格截取 Top 5；
- 页面是否按首次出现顺序去重；
- 汇总 gate 是否可能把失败误报为通过；
- read-only transaction 是否在第一次查询前设置；
- 正式表列表是否遗漏业务写表；
- 报告是否越过工程结论边界。

Critical 和 Important 必须修复并重跑相关测试。Minor 记录到验收报告或当轮修复。

- [ ] **Step 4：复核最终 Git 范围**

Run:

```powershell
git status --short --branch
git diff --stat
git diff --name-status
```

Expected: 只包含本计划列出的代码、测试和文档；`tmp/embedding/` 继续被 `.gitignore` 排除。

- [ ] **Step 5：本地提交**

在用户确认最终差异后执行：

```powershell
git add `
  backend/src/tools/shadow_context_acceptance.py `
  backend/src/tools/finalize_shadow_rag_phase1.py `
  backend/tests/tools/test_shadow_context_acceptance.py `
  backend/tests/tools/test_finalize_shadow_rag_phase1.py `
  README.md `
  docs/DESIGN.md `
  docs/DEVELOPMENT.md `
  docs/product/rag-phase1.5-acceptance-report.md `
  docs/plan/hybrid-shadow-rag-phase1.5-finalization-plan.md `
  docs/plan/siliconflow-bge-m3-shadow-embedding-plan.md
git commit -m "feat: finalize hybrid shadow RAG phase 1.5"
```

不执行 `git push`。

---

## 5. 停止条件

出现以下任一情况立即停止，不扩大修改范围：

1. 目标数据库不是 `esg_agent_demo`。
2. `EMBEDDING_ENABLED` 不是 false。
3. 封版工具试图创建 EmbeddingClient 或 LLMClient。
4. 指定报告没有 `document_chunks`。
5. retrieval CSV 与 context requirement 集合不一致。
6. context 数量、唯一 requirement 或唯一 hash 不是 499。
7. 发现重复页、越界页、非法 shadow evidence ID 或未解析规则页。
8. 两次构建 context hash 不一致。
9. 正式业务表 before/after 不一致。
10. hybrid Top 5 hit、recall 或 MRR 低于 rule Top 5。
11. hybrid loss 多于 hybrid gain。
12. Envision gate 出现结构、verdict、source page 或 audit 回归。
13. 需要新增 migration、修改 API、前端或正式工作流才能继续。
14. 发现输入文件 hash 与 manifest 不一致。
15. 发现真实外部调用、密钥输出或非公开响应进入日志。

## 6. 完成定义

Phase 1.5 只有同时满足以下条件才可标记完成：

- 新增纯评估模块和只读封版编排器均有 TDD 覆盖；
- 三路 499 条 Top 5 对比完成；
- 所有结构和相对质量门禁通过；
- 两次 context hash 完全一致；
- 正式表计数前后完全一致；
- 后端全量测试通过且不少于当前 686 项；
- Envision `577/499/78/0` 零回归门禁通过；
- 自动验收报告和项目文档完成；
- 文档明确没有 ESG 专家新判断；
- Phase 2 保持可选、Phase 3 保持关闭；
- 仓库无密钥、无本机绝对路径、无非公开外部响应；
- 本地提交完成，未推送。
