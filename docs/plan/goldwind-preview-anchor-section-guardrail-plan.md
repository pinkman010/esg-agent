# Goldwind Preview Anchor and Section Guardrail Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 Goldwind holdout 中 4 条有效 partial 的 preview 锚点问题，并阻断 `GRI 418-1-a` 的产品服务章节误命中。

**Architecture:** 本阶段只改 preview anchor、section route guardrail 和现有诊断输出，不新增字段，不新增 Goldwind per-ID contract，不调整 ontology matrix。`evidence_preview` 负责展示目标句或 KPI 行；guardrail 负责把不满足客户隐私投诉口径的 section evidence 过滤为无效 evidence。

**Tech Stack:** Python 3.11、pytest、`retrieve_evidence`、`kpi_row_matcher`、`build_kpi_evidence_preview`、`DisclosureAgent`、`review_csv_audit`、`regenerate_review_csv`。

---

## 背景

人工复核 `tmp/review/holdout_goldwind_2024_review_pack.csv` 后结论：

- `GRI 205-1-a`：PDF 第 21 页 source 正确，verdict 为 partial 合理，但 preview 未锚定“业务单位 / 风险程度 / 审计策略 / 商业道德问题”。
- `GRI 205-1-b`：PDF 第 21 页 source 正确，verdict 为 partial 合理，但 preview 偏到举报渠道和信息安全。
- `GRI 414-1-a`：PDF 第 31 页是核心 evidence，PDF 第 32 页只能作为补充；preview 未稳定显示“供应商社会责任审核 / 85 家 / A 级 / B 级 / 审核率”。
- `GRI 403-9-a-i`：PDF 第 47 页 source 正确，verdict 为 partial 合理，但 preview 先显示第三方审验声明和相邻表格，未锚定“员工因工死亡人数”KPI 行。
- `GRI 418-1-a`：PDF 第 13-17 页为产品服务章节，不应作为客户隐私投诉 evidence；当前 verdict 保持 unknown 合理，但存在 wrong source page / section over-route 风险。

## 硬边界

- 不新增 Goldwind per-ID contract。
- 不调整 ontology matrix。
- 不新增主 review CSV 顶层字段。
- 不把 Goldwind 固定页码写入通用 GRI 标准规则。
- Goldwind GRI index PDF 50/51 只能作为 candidate route 来源，不能成为 `substantive evidence`。
- `GRI 418-1-a` 必须保持 `unknown + needs_manual_review`。
- `GRI 205-1-a`、`GRI 205-1-b`、`GRI 414-1-a`、`GRI 403-9-a-i` 本阶段最多允许 `partially_disclosed`，不得自动升为 `disclosed`。
- 新增诊断信息只能进入 `*_diagnosis.csv`、`*_review_pack.csv` 或 `*_quality_summary.json`。

## 停止条件

触发任一条件即暂停并汇报：

- `false_disclosed_count > 0`。
- `wrong_source_page_count > 0`，除非仅来自已知且待人工确认的 review pack 样本。
- `global_fallback_count > 0`。
- Goldwind `source_pdf_page` 或 `candidate_pdf_pages` 超过 52。
- Goldwind GRI index PDF 50/51 被标为 `substantive evidence`。
- `GRI 418-1-a` 出现 substantive source evidence。
- `GRI 418-1-a` 从 `unknown` 升为 `partially_disclosed` 或 `disclosed`。
- `GRI 205-1-a`、`GRI 205-1-b`、`GRI 414-1-a`、`GRI 403-9-a-i` 任一条被自动升为 `disclosed`。
- Envision 577 regeneration gate 出现 requirement 数量变化。
- Envision 577 regeneration gate 出现非预期 verdict、review_status、source page、evidence_type、quality_flags、OCR/VLM 字段变化。
- 需要新增 Goldwind per-ID contract 才能继续。

## 文件职责

- `backend/src/tools/evidence.py`：增强 preview anchor，优先返回目标关键词附近窗口。
- `backend/src/tools/kpi_row_matcher.py`：增强 KPI 行级 preview，避免整页表格或审验声明抢占 preview。
- `backend/src/tools/retrieval.py`：在 bounded retrieval 中优先使用 anchor terms 生成 evidence preview。
- `backend/src/agents/disclosure_agent.py`：为客户隐私投诉 scope 增加 section evidence guardrail，过滤产品服务章节误命中。
- `backend/tests/tools/test_evidence.py`：覆盖 preview anchor。
- `backend/tests/tools/test_kpi_row_matcher.py`：覆盖 Goldwind KPI 行 preview。
- `backend/tests/tools/test_retrieval.py`：覆盖管理机制 preview。
- `backend/tests/agents/test_disclosure_agent.py`：覆盖 `GRI 418-1-a` 不接受产品服务章节 evidence。
- `docs/DEVELOPMENT.md`：记录本轮结果和字段分层约束。

## Task 1: 增强管理机制 Preview Anchor

**Files:**
- Modify: `backend/src/tools/evidence.py`
- Test: `backend/tests/tools/test_evidence.py`

- [ ] **Step 1: 写 205 preview anchor 测试**

在 `backend/tests/tools/test_evidence.py` 增加：

```python
def test_build_preview_prefers_anti_corruption_audit_strategy_anchor():
    text = (
        "金风科技反腐败 举报电话：+86（0）10-67511888-1127 电子邮箱：audit@goldwind.com.cn。"
        "公司根据不同业务单位的业务特点、重要性、风险程度制定相应审计策略，"
        "并在审计中重点关注商业道德问题。"
    )

    preview = build_evidence_preview(
        text,
        ["业务单位", "风险程度", "审计策略", "商业道德问题"],
    )

    assert "风险程度" in preview
    assert "审计策略" in preview
    assert "商业道德问题" in preview
```

- [ ] **Step 2: 运行测试**

```powershell
cd backend
uv run --no-sync pytest --basetemp ../tmp/pytest-preview-anchor tests/tools/test_evidence.py::test_build_preview_prefers_anti_corruption_audit_strategy_anchor -q
```

Expected: 若失败，说明 preview 仍偏页首或错误关键词；按 Step 3 修复。

- [ ] **Step 3: 实现 anchor terms 优先窗口**

在 `backend/src/tools/evidence.py` 中确保 preview 逻辑：

```python
def build_evidence_preview(text: str, keywords: list[str], window: int = 120) -> str:
    normalized = " ".join(text.split())
    anchor = _best_anchor_index(normalized, keywords)
    if anchor is None:
        return normalized[: min(len(normalized), window * 2)]
    start = max(0, anchor - window)
    end = min(len(normalized), anchor + window)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(normalized) else ""
    return f"{prefix}{normalized[start:end]}{suffix}"
```

`_best_anchor_index()` 应优先选择命中关键词数量最多的窗口。

- [ ] **Step 4: 运行测试通过**

```powershell
cd backend
uv run --no-sync pytest --basetemp ../tmp/pytest-preview-anchor tests/tools/test_evidence.py -q
```

Expected: PASS。

## Task 2: 增强 KPI 行级 Preview

**Files:**
- Modify: `backend/src/tools/kpi_row_matcher.py`
- Test: `backend/tests/tools/test_kpi_row_matcher.py`

- [ ] **Step 1: 写 414 KPI preview 测试**

在 `backend/tests/tools/test_kpi_row_matcher.py` 增加：

```python
def test_supplier_social_audit_preview_contains_target_kpi_row():
    chunk = DocumentChunk(
        chunk_id="p31",
        report_id="goldwind",
        text="2024年，公司完成85家风电机组零部件供应商社会责任审核，其中A级83家、B级2家，主要零部件制造商社会责任审核率100%。",
        source_page=31,
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        source_file_hash="hash",
    )

    matches = match_kpi_rows([chunk], ["供应商社会责任审核", "社会责任审核率"], year_columns=["2024"])

    assert matches
    assert "85家" in matches[0].preview
    assert "审核率100%" in matches[0].preview or "审核率 100%" in matches[0].preview
```

- [ ] **Step 2: 写 403-9 KPI preview 测试**

同文件增加：

```python
def test_ohs_fatality_preview_contains_employee_fatality_count():
    chunk = DocumentChunk(
        chunk_id="p47",
        report_id="goldwind",
        text="第三方审验声明 指标 单位 2024年 2023年 2022年 职业健康安全 员工因工死亡人数 人 1 0 0 因工伤损失工作日数 天 170 120 80 安全培训时数 小时 441630 300000 250000",
        source_page=47,
        source_method=EvidenceSourceMethod.PDFPLUMBER,
        source_file_hash="hash",
    )

    matches = match_kpi_rows([chunk], ["员工因工死亡人数", "因工死亡人数"], year_columns=["2024"])

    assert matches
    assert "员工因工死亡人数" in matches[0].preview
    assert "1" in matches[0].preview
```

- [ ] **Step 3: 运行测试**

```powershell
cd backend
uv run --no-sync pytest --basetemp ../tmp/pytest-kpi-preview tests/tools/test_kpi_row_matcher.py -q
```

Expected: PASS 或按 Step 4 修复。

- [ ] **Step 4: 调整 KPI preview 生成**

确保匹配到 metric term 后，preview 从 term 所在窗口生成，不从页首生成：

```python
preview = _window_around(text, term, before=80, after=180)
```

## Task 3: 增加 418 Section Route Guardrail

**Files:**
- Modify: `backend/src/agents/disclosure_agent.py`
- Test: `backend/tests/agents/test_disclosure_agent.py`

- [ ] **Step 1: 写 418 产品服务章节无效 evidence 测试**

在 `backend/tests/agents/test_disclosure_agent.py` 增加：

```python
def test_disclosure_agent_rejects_product_section_for_customer_privacy_complaints():
    agent = DisclosureAgent()
    task = DisclosureTask(
        task_id="task-418-1-a",
        run_id="run-1",
        report_id="goldwind",
        standard_id="GRI",
        standard_version="2016",
        disclosure_id="GRI 418-1",
        requirement_id="GRI 418-1-a",
        requirement_text="total number of substantiated complaints concerning breaches of customer privacy",
        keywords=["customer privacy", "complaints"],
        candidate_pages=[13, 14, 15, 16, 17],
        candidate_pdf_pages=[13, 14, 15, 16, 17],
        candidate_page_source="report_profile_section",
    )
    evidence = [
        EvidenceItem(
            evidence_id="ev-1",
            task_id=task.task_id,
            chunk_id="chunk-1",
            source_text="产品服务与研发创新 产品质量与安全 客户反馈 智慧运维",
            source_page=15,
            source_method=EvidenceSourceMethod.PDFPLUMBER,
            confidence=0.5,
        )
    ]

    assessment = agent.assess(task, evidence, confirm_llm=False)

    assert assessment.verdict == AssessmentVerdict.UNKNOWN
    assert assessment.review_status == ReviewStatus.NEEDS_MANUAL_REVIEW
    assert assessment.evidence == []
```

- [ ] **Step 2: 运行测试**

```powershell
cd backend
uv run --no-sync pytest --basetemp ../tmp/pytest-418-guardrail tests/agents/test_disclosure_agent.py::test_disclosure_agent_rejects_product_section_for_customer_privacy_complaints -q
```

Expected: 若失败，按 Step 3 修复。

- [ ] **Step 3: 实现客户隐私投诉 evidence 过滤**

在 `DisclosureAgent` evidence filtering 阶段增加：

```python
if task.requirement_id == "GRI 418-1-a":
    evidence = [
        item for item in evidence
        if self._has_customer_privacy_complaint_evidence(item.source_text)
    ]
```

保留现有 zero-event guardrail，不把一般信息安全、数据泄露或产品服务章节当作投诉 evidence。

## Task 4: 重跑 Goldwind Review Pack

**Files:**
- Write: `tmp/review/holdout_goldwind_2024_first_pass.csv`
- Write: `tmp/review/holdout_goldwind_2024_review_pack.csv`
- Write: `tmp/review/holdout_goldwind_2024_evidence_hit_summary.json`
- Write: `tmp/review/holdout_goldwind_2024_audit.json`

- [ ] **Step 1: 重跑 Goldwind holdout**

```powershell
cd backend
uv run --no-sync python ../tmp/goldwind_holdout_remediation.py
```

Expected:

- `global_fallback_count=0`
- `false_disclosed_count=0`
- `max_source_pdf_page <= 52`
- `max_candidate_pdf_page <= 52`

- [ ] **Step 2: 重建 review pack 和 summary**

复用 `src.tools.holdout_review_pack` 生成：

- `tmp/review/holdout_goldwind_2024_route_improvement.csv`
- `tmp/review/holdout_goldwind_2024_review_pack.csv`
- `tmp/review/holdout_goldwind_2024_evidence_hit_summary.json`

Expected:

- review pack 包含 5 个目标 requirement。
- `GRI 418-1-a` 不再出现 PDF 13-17 substantive source evidence。
- 4 条 partial 的 preview 包含目标句或 KPI 行。

## Task 5: Envision Gate 与文档记录

**Files:**
- Write: `tmp/review/current_577_review_regenerated.csv`
- Write: `tmp/review/current_577_review_regenerated_audit.json`
- Write: `tmp/review/current_577_review_regeneration_diff_summary.json`
- Modify: `docs/DEVELOPMENT.md`

- [ ] **Step 1: 跑 focused tests**

```powershell
cd backend
uv run --no-sync pytest --basetemp ../tmp/pytest-goldwind-preview-guardrail tests/tools/test_evidence.py tests/tools/test_kpi_row_matcher.py tests/tools/test_retrieval.py tests/agents/test_disclosure_agent.py tests/tools/test_holdout_review_pack.py -q
```

Expected: PASS。

- [ ] **Step 2: 跑 Envision 577 regeneration gate**

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

- unique requirements = 577
- compilation-like requirements = 0
- audit ok = true
- strict source/evidence diff = 0

- [ ] **Step 3: 更新开发记录**

在 `docs/DEVELOPMENT.md` 增加：

```markdown
- Goldwind preview anchor 与 section guardrail 改造完成：`GRI 205-1-a/b`、`GRI 414-1-a`、`GRI 403-9-a-i` 的 preview 已锚定目标句或 KPI 行；`GRI 418-1-a` 不再接受产品服务章节作为客户隐私投诉 evidence。Goldwind audit 通过，Envision 577 regeneration gate 通过，当前停止点为人工复核 `tmp/review/holdout_goldwind_2024_review_pack.csv`。
```

## 人工复核交付

执行完成后暂停，并请人工复核：

- `tmp/review/holdout_goldwind_2024_review_pack.csv`
- `tmp/review/holdout_goldwind_2024_evidence_hit_summary.json`

复核重点：

- `GRI 205-1-a/b` preview 是否显示“业务单位 / 风险程度 / 审计策略 / 商业道德问题”。
- `GRI 414-1-a` preview 是否显示“供应商社会责任审核 / 85 家 / A 级 / B 级 / 审核率”。
- `GRI 403-9-a-i` preview 是否显示“员工因工死亡人数”KPI 行。
- `GRI 418-1-a` 是否无 substantive evidence，并保持 `unknown + needs_manual_review`。

## 验收标准

- 不新增主 review CSV 顶层字段。
- 不新增 Goldwind per-ID contract。
- Goldwind `false_disclosed_count=0`。
- Goldwind `global_fallback_count=0`。
- Goldwind `wrong_source_page_count=0` 或只剩人工确认的无效候选记录。
- `GRI 418-1-a` 保持 unknown，且不含 PDF 13-17 substantive evidence。
- Envision 577 regeneration gate strict diff 为 0。
- docs 不包含本机绝对路径。
