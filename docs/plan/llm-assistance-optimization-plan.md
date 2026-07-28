# LLM 辅助建议层优化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**目标：** 在保持 Envision v1.1、GRI `577/499/78/0`、规则 assessment、人工 snapshot 和正式输出边界不变的前提下，先完成 LLM 辅助建议层的文档冻结、风险定义和验收口径；只有取得独立批准后，才分阶段改进前端状态表达、只读观测能力或后端 AI 状态语义。

**架构：** 计划分为四个互不自动解锁的范围：A 为纯文档收口，默认可执行；B 为不改变 API 的前端派生展示，需前端范围批准；C 为只读离线观测工具，需后端非产品工具范围批准；D 为 `needs_human_review` 等正式状态语义调整，必须解除后端冻结并执行完整门禁。所有范围继续以 `confirm_llm` 为外部调用硬开关，AI suggestion 只追加保存，最终有效结论只来自人工 snapshot。

**技术栈：** Python 3.11、FastAPI、Pydantic v2、SQLAlchemy 2.0、PostgreSQL、pytest、Next.js、TypeScript、Vitest、OpenAPI、现有 DeepSeek OpenAI-compatible client。

---

## 1. 执行状态与默认范围

**执行状态（2026-07-28）：** Task 1–3 已执行；Task 7 已完成文档、后端、前端、Phase 1.5 封版和 Envision v3 收尾复验。Task 4–6 未执行，后端未解冻，真实模型调用为 0。

| Task | 状态 | 授权 |
| --- | --- | --- |
| Task 1：文档基线纠偏 | 已完成 | 默认范围 A |
| Task 2：产品验收与风险清单 | 已完成 | 默认范围 A |
| Task 3：前端派生展示 | 已完成（含低复核优先级文案修复） | 需单独批准范围 B |
| Task 4：离线观测工具 | 未执行 | 需单独批准范围 C |
| Task 5：正式状态语义 | 未执行 | 需解除冻结并批准范围 D |
| Task 6：显式候选边界测试 | 未执行 | 需单独批准范围 C 或 D |
| Task 7：最终门禁 | 已完成（收尾复验） | 随实际范围执行 |

收尾基线：

```text
Git commit：570a996d42143e8ffde1bfc6b2693f4c3c3ad2d0
真实模型调用：无
后端是否解冻：否
前端是否变更：是，仅修改既有 API 数据的展示分类与中文文案
RAG 是否进入正式链路：否
Task 4–6：未执行
```

收尾门禁：

```text
Phase 1.5：499 context，119 条工程 gold，gain 11，loss 0，18 张正式表计数不变
后端：709 tests pass
Ruff：src 与 tests pass
前端：28 test files / 105 tests / typecheck / production build pass
Envision v3：577/499/78/0
global fallback / new false disclosed / new wrong source page：0 / 0 / 0
final adjudication pending：0
audit：0 error / 0 warning
```

完整事实见 `docs/product/phase1.5-closeout-report.md`。

默认批准范围只包含：

- Task 1：冻结内文档基线纠偏。
- Task 2：产品验收说明和风险清单。
- Task 7 中与已执行范围对应的文档检查。

以下范围不得因本计划存在而自动执行：

- Task 3：前端 AI 状态派生展示。
- Task 4：离线 AI 观测工具。
- Task 5：正式 `needs_human_review` 状态。
- Task 6：代码级调用边界测试。
- 任何真实 DeepSeek 调用。

## 2. 已确认当前基线

### 2.1 产品与工程基线

- 产品对外口径为单报告 577 项 GRI 核查。
- 内部结构固定为 `577/499/78/0`：
  - 577 个标准单元；
  - 499 个独立判断项；
  - 78 个上下文项；
  - 0 个 method pending。
- 当前 migration head 为 `0012_chunk_embeddings`。
- 当前门禁为：
  - 后端 709 项测试通过；
  - 前端 28 个测试文件、105 项测试通过；
  - frontend typecheck 通过；
  - frontend production build 通过；
  - Envision v3 global fallback、新增 false disclosed、新增 wrong source page 均为 0；
  - Envision audit 为 0 error、0 warning。
- `docs/DESIGN.md` 当前实现状态仍记录后端 686 项测试，属于需要纠正的当前状态数字。
- `docs/DEVELOPMENT.md` 历史日志中的 651、626、627 等数字属于对应日期的历史事实，不得批量替换。

### 2.2 LLM 调用边界

- `backend/src/tools/llm_client.py` 在 `confirm_llm=false` 时抛出 `ModelCallBlocked`，不会创建真实请求。
- `backend/src/workflows/single_report_workflow.py` 在 `confirm_llm=false` 时直接把 `ai_assistance` stage 记为 `skipped`，不会调用 `AIAssessmentService`。
- `confirm_llm=true` 时，默认产品路径只调用：
  - `structure_status` 为 `verified` 或 `normalized`；
  - `review_priority` 为 high 或 medium；
  - 至少存在一条实质证据；
  - 未超过单 run 调用预算的候选。
- AI suggestion 使用 `ai_assessment_suggestions` 追加保存。
- AI suggestion 不设置适用性、风险优先级、人工复核状态或正式输出状态。
- 模型或 guardrail 失败只影响 AI stage，不使规则分析 run 失败。

### 2.3 三层权威关系

固定顺序为：

```text
规则 assessment
  -> AI 辅助 suggestion
  -> 人工 review snapshot
```

约束如下：

- 规则层读取不可变 `system_*` 字段。
- AI 建议只作为人工输入候选。
- 采纳、修改、拒绝 AI 建议都必须追加人工 snapshot。
- 当前有效结论来自最新有效人工 snapshot；没有人工 snapshot 时使用规则结果。
- AI 不能覆盖规则 assessment，也不能直接进入最终合规结论。

### 2.4 DeepSeek 工程基线

- 225 条真实 DeepSeek 评估只作为工程质量基线。
- 可比较样本为 224 条，一致 162 条，一致率 72.32%。
- applicability exception 为 1。
- targeted reruns 为 18。
- guardrail 后 false disclosed、证据 ID 越界、可比错页、schema failure、model failure 均为 0。
- 当前没有独立 ESG 专家 gold 可以证明规则或模型差异中的哪一方正确。
- 上述指标不得用于宣称 GRI 认证、最终合规结论或模型优于人工。

### 2.5 RAG 边界

- 混合影子 RAG Phase 1.5 已完成工程验收。
- Phase 1.5 不进入 `SingleReportWorkflow`、正式 evidence、AI suggestion、assessment、risk、API 或前端。
- 本计划不启动 RAG Phase 2，不使用影子 context 修改当前 DeepSeek suggestion。
- RAG Phase 3 保持关闭。

## 3. 必要性判断与冻结决策

| 项目 | 当前决策 | 理由 |
| --- | --- | --- |
| 新增中文优化计划 | 执行 | 固定边界、解冻条件和验收范围 |
| 更新当前门禁数字 | 执行 | DESIGN 的 686 已落后于当前 709 |
| 产品验收说明与风险清单 | 执行 | 当前规则分散在设计、开发和代码中 |
| 前端状态派生展示 | 待单独批准 | 可改善语义，但属于用户可见行为变化 |
| 离线观测工具 | 待单独批准 | 有价值，但新增后端代码和测试 |
| 正式 `needs_human_review` 状态 | 暂缓 | 会改变枚举、API、统计和工作流语义 |
| `confirm_llm=false` 逐项保存 skipped | 不实施 | run 级授权和 stage 已足够，逐项记录会产生大量噪声 |
| 修改 Prompt | 不实施 | 缺少独立专家 gold 和明确失败假设 |
| 修改模型或默认参数 | 不实施 | 当前安全门禁无失败证据 |
| 修改候选筛选 | 不实施 | 会改变调用范围、成本和对比基线 |
| 修改数据库结构 | 不实施 | 当前字段足以记录 suggestion、guardrail 和人工来源 |
| 修改导出口径 | 不实施 | AI 不应进入正式结论层 |
| 将 RAG 接入 AI suggestion | 不实施 | 属于独立 Phase 2 决策 |

## 4. 指标定义

后续观测必须使用以下固定定义，禁止先展示图表再反推口径。

### 4.1 运行指标

```text
eligible_count
  = AI stage 进入 should_call=true 的 assessment 数

attempted_count
  = status in {succeeded, failed, needs_human_review} 的 suggestion 数
  = 当前版本中 status in {succeeded, failed} 的 suggestion 数

succeeded_count
  = status=succeeded 的 suggestion 数

guardrail_blocked_count
  = status=failed 且 guardrail_codes 包含业务/证据护栏码的 suggestion 数

technical_failed_count
  = status=failed 且 error_code 属于连接、限流、服务、JSON 或 schema 技术失败的 suggestion 数

skipped_count
  = 已实际进入 suggestion 生成编排但因预算或候选边界跳过的记录数
```

`confirm_llm=false` 的 run 不创建逐项 suggestion，因此：

```text
run_not_authorized_count
  = analysis_runs.confirm_llm=false 的 run 数
```

不得用 `skipped_count=0` 推导“所有条目均调用成功”。

### 4.2 人工处置指标

基于 `review_snapshots.reason_code`：

```text
accepted_count
  = reason_code=ai_suggestion_accepted

modified_count
  = reason_code=ai_suggestion_modified

rejected_count
  = reason_code=ai_suggestion_rejected

resolved_ai_suggestion_count
  = accepted_count + modified_count + rejected_count

acceptance_rate
  = accepted_count / resolved_ai_suggestion_count

modification_rate
  = modified_count / resolved_ai_suggestion_count

rejection_rate
  = rejected_count / resolved_ai_suggestion_count
```

限制：

- 没有人工处置的 suggestion 不进入三个 rate 的分母。
- rate 描述产品使用行为，不代表模型正确率。
- 同一 assessment 多次追加 snapshot 时，只统计与指定 suggestion 或指定时间窗口对应的有效处置。
- 当前 reviewer note 使用 `AI suggestion_id=` 前缀保存真实 suggestion ID；离线统计必须解析并验证该 ID 确实属于同一 assessment。

### 4.3 Guardrail 分类

业务/证据护栏：

```text
evidence_page_cardinality_mismatch
duplicate_evidence_reference
evidence_reference_out_of_scope
evidence_page_mismatch
disclosed_without_substantive_evidence
verdict_upgrade_requires_human_review
partial_without_missing_items
```

技术失败：

```text
response_schema_invalid
llm_empty_content
llm_response_truncated
llm_invalid_json
llm_connection_error
llm_rate_limited
llm_server_error
llm_request_rejected
llm_call_failed
ai_service_unexpected_error
```

跳过原因：

```text
external_model_not_confirmed
structure_not_independent
low_review_priority
no_substantive_evidence
call_budget_exhausted
```

`verdict_upgrade_requires_human_review` 属于安全拦截，不得计入技术故障率。

## 5. 分阶段执行路线

```text
范围 A：纯文档
  -> 停止并确认

范围 B：前端派生展示
  -> 停止并确认

范围 C：只读离线观测
  -> 停止并确认

范围 D：正式状态语义
  -> 完整解冻和全部门禁
```

任一范围通过，不自动批准下一范围。

---

## Task 1：冻结内文档基线纠偏

**授权级别：** 默认范围 A。

**Files:**

- Modify: `docs/DESIGN.md`
- Modify: `docs/DEVELOPMENT.md`

- [x] **Step 1：更新 DESIGN 当前门禁数字**

在 `docs/DESIGN.md` 的“当前实现与验收状态”中，把当前状态段落的：

```text
后端 686 项测试
```

更新为：

```text
后端 709 项测试
```

不得修改 `docs/DEVELOPMENT.md` 历史日期段落中的 651、626、627 等数字。

- [x] **Step 2：在 DEVELOPMENT 当前状态中记录 LLM 决策**

在最新开发日志中增加：

```markdown
- LLM 辅助层继续保持 `confirm_llm` 显式授权、规则/AI/人工三层隔离和追加式 suggestion；当前不修改 DeepSeek 模型、Prompt、候选筛选、数据库、API、导出或 RAG 接入。
- `confirm_llm=false` 只记录 run 级授权状态和 AI stage skipped，不写 499 条逐项 skipped suggestion。
- `assess_explicit_candidates()` 只允许离线评估工具和测试使用，不进入默认产品工作流。
```

- [x] **Step 3：检查当前状态与历史日志没有混写**

Run:

```powershell
rg -n "后端 (709|686|651|627|626) 项|confirm_llm=false|assess_explicit_candidates" `
  README.md docs/DESIGN.md docs/DEVELOPMENT.md
```

Expected:

- README 和 DESIGN 当前状态为 709；
- DEVELOPMENT 最新当前门禁为 709；
- 651、627、626 只出现在对应历史日志；
- 新增 LLM 决策只描述当前边界。

- [x] **Step 4：提交文档纠偏**

```powershell
git add docs/DESIGN.md docs/DEVELOPMENT.md
git commit -m "docs: align frozen LLM assistance baseline"
```

---

## Task 2：建立 LLM 产品验收说明与风险清单

**授权级别：** 默认范围 A。

**Files:**

- Create: `docs/product/llm-assistance-acceptance.md`
- Modify: `README.md`

- [x] **Step 1：创建产品验收说明**

创建 `docs/product/llm-assistance-acceptance.md`，固定包含以下内容：

```markdown
# LLM 辅助建议层产品验收说明

## 1. 验收结论

当前 DeepSeek 接入只属于辅助复核建议层。外部模型默认关闭，只有分析请求显式传入 `confirm_llm=true` 时才允许调用。AI suggestion 不覆盖规则 assessment，用户采纳、修改或拒绝后均形成追加式人工 snapshot。

## 2. 权威层级

1. 规则 assessment：系统确定性基线。
2. AI suggestion：可选辅助建议。
3. 人工 snapshot：最终有效人工结论。

## 3. 外部调用边界

- `confirm_llm=false`：不调用模型，只记录 run 级 AI stage skipped。
- `confirm_llm=true`：只调用独立结构、高/中复核优先级且具有实质证据的候选。
- 测试不得真实调用外部模型。
- 每次真实模型评估需要当次用户批准。

## 4. 状态说明

- `succeeded`：建议通过 schema 和证据 guardrail。
- `failed`：当前版本同时包含技术失败和安全拦截，必须结合 `error_code` 与 `guardrail_codes` 判断。
- `skipped`：进入编排后因候选边界或预算未调用。
- 没有 suggestion：可能是 run 未授权、服务未配置或该项没有进入候选集合。

## 5. DeepSeek 工程基线

225 条评估只作为工程基线；可比较样本 224 条，一致 162 条，一致率 72.32%，applicability exception 1，targeted reruns 18。该结果不构成 GRI 专家认证或最终合规结论。

## 6. 风险

- `failed` 混合技术失败和安全拦截，可能影响运营判断。
- assessment 详情没有 run 授权状态，前端无法精确拆分所有空态。
- 采纳率、修改率和拒绝率尚未形成正式观测指标。
- 当前缺少独立专家 gold，不能用规则—AI 一致率指导 Prompt 调优。
- `assess_explicit_candidates()` 会绕过默认候选筛选，只能用于评估工具和测试。

## 7. 当前冻结决策

- 不保存 `confirm_llm=false` 的逐项 skipped suggestion。
- 不修改模型、Prompt、参数、候选筛选、数据库、API、导出或三层优先级。
- 不把影子 RAG 接入正式 AI suggestion。
- `needs_human_review` 只作为后续可选语义调整。
```

- [x] **Step 2：在 README 增加入口**

在“核心文档”中增加：

```markdown
- LLM 辅助建议层验收：`docs/product/llm-assistance-acceptance.md`
```

- [x] **Step 3：检查边界措辞**

Run:

```powershell
rg -n "最终合规结论|confirm_llm|规则 assessment|人工 snapshot|assess_explicit_candidates|影子 RAG" `
  docs/product/llm-assistance-acceptance.md README.md
```

Expected: 六类边界均有明确说明，不出现“AI 自动确认合规”“模型结论覆盖规则”等表述。

- [x] **Step 4：提交验收说明**

```powershell
git add README.md docs/product/llm-assistance-acceptance.md
git commit -m "docs: add LLM assistance acceptance boundary"
```

- [x] **Step 5：停止并请求范围确认**

完成 Task 1–2 后停止。未取得新批准时，不执行 Task 3–6。

---

## Task 3：前端派生“需人工复核”展示

**授权级别：** 范围 B，需单独批准。

**边界：** 只改变前端展示分类，不新增后端状态，不改变 API，不允许采纳或直接使用被 guardrail 拦截的 suggestion。

**Files:**

- Modify: `frontend/lib/ai-presentation.ts`
- Modify: `frontend/lib/ai-presentation.test.ts`
- Modify: `frontend/components/review/ai-suggestion-panel.tsx`
- Modify: `frontend/components/review/review-editor.test.tsx`

- [x] **Step 1：写前端派生状态失败测试**

在 `frontend/lib/ai-presentation.test.ts` 的 import 中增加 `aiPresentationState`，并追加：

```typescript
it("separates guardrail review from technical failure without changing API status", () => {
  expect(aiPresentationState({
    ...suggestion,
    status: "failed",
    guardrail_codes: ["verdict_upgrade_requires_human_review"],
    error_code: "ai_response_guardrail_failed",
  })).toBe("needs_human_review");

  expect(aiPresentationState({
    ...suggestion,
    status: "failed",
    guardrail_codes: ["llm_connection_error"],
    error_code: "llm_connection_error",
  })).toBe("technical_failed");
});
```

- [x] **Step 2：运行测试确认失败**

Run:

```powershell
cd frontend
pnpm test -- --run lib/ai-presentation.test.ts
```

Expected: FAIL，`aiPresentationState` 尚不存在。

- [x] **Step 3：实现纯前端派生状态**

在 `frontend/lib/ai-presentation.ts` 增加：

```typescript
export type AIPresentationState =
  | "not_available"
  | "succeeded"
  | "needs_human_review"
  | "skipped"
  | "technical_failed";

const reviewGuardrails = new Set([
  "evidence_page_cardinality_mismatch",
  "duplicate_evidence_reference",
  "evidence_reference_out_of_scope",
  "evidence_page_mismatch",
  "disclosed_without_substantive_evidence",
  "verdict_upgrade_requires_human_review",
  "partial_without_missing_items",
]);

export function aiPresentationState(
  suggestion: AIAssessmentSuggestion | null | undefined,
): AIPresentationState {
  if (!suggestion) return "not_available";
  if (suggestion.status === "succeeded") return "succeeded";
  if (suggestion.status === "skipped") return "skipped";
  if ((suggestion.guardrail_codes ?? []).some((code) => reviewGuardrails.has(code))) {
    return "needs_human_review";
  }
  return "technical_failed";
}
```

- [x] **Step 4：调整面板文案但保持操作禁用**

`frontend/components/review/ai-suggestion-panel.tsx` 使用派生状态显示：

```text
not_available       -> 本次分析未启用 AI，或该项未进入 AI 候选范围
succeeded           -> AI 建议已生成
needs_human_review  -> AI 建议触发安全校验，需人工独立判断
skipped             -> 该项未调用 AI
technical_failed    -> AI 辅助未完成，规则结果仍有效
```

必须继续使用：

```typescript
const usable = isUsableAISuggestion(suggestion);
```

只有 `status=succeeded` 才显示采纳、载入修改和拒绝按钮。不得让 `needs_human_review` 进入 `usable`。

- [x] **Step 5：运行前端相关测试**

Run:

```powershell
cd frontend
pnpm test -- --run `
  lib/ai-presentation.test.ts `
  components/review/review-editor.test.tsx `
  components/review/assessment-detail.test.tsx
```

Expected: PASS。

- [x] **Step 6：运行完整前端门禁**

```powershell
cd frontend
pnpm test -- --run
pnpm typecheck
pnpm build
```

Expected:

- 28 个或更多测试文件通过；
- 103 项或更多测试通过；
- typecheck 通过；
- production build 通过。

- [x] **Step 7：提交前端展示调整**

```powershell
git add `
  frontend/lib/ai-presentation.ts `
  frontend/lib/ai-presentation.test.ts `
  frontend/components/review/ai-suggestion-panel.tsx `
  frontend/components/review/review-editor.test.tsx
git commit -m "feat: clarify AI assistance presentation states"
```

---

## Task 4：增加只读离线 AI 观测工具

**授权级别：** 范围 C，需单独批准。

**边界：** 工具只读数据库，只向 `tmp/ai/` 写 JSON/CSV；不增加 API，不修改 schema，不调用外部模型，不写 suggestion、assessment、risk、review 或 export。

**Files:**

- Create: `backend/src/tools/report_ai_assistance_metrics.py`
- Create: `backend/tests/tools/test_report_ai_assistance_metrics.py`
- Modify: `docs/DEVELOPMENT.md`

- [ ] **Step 1：写指标纯函数失败测试**

在 `backend/tests/tools/test_report_ai_assistance_metrics.py` 创建测试，至少覆盖：

```python
from src.tools.report_ai_assistance_metrics import summarize_ai_suggestions


def suggestion(
    *,
    suggestion_id: str,
    status: str,
    guardrail_codes: list[str] | None = None,
    error_code: str | None = None,
) -> dict[str, object]:
    return {
        "suggestion_id": suggestion_id,
        "assessment_id": "assessment-1",
        "status": status,
        "guardrail_codes": guardrail_codes or [],
        "error_code": error_code,
    }


def snapshot(
    *,
    suggestion_id: str,
    reason_code: str,
    created_at: str,
) -> dict[str, object]:
    return {
        "assessment_id": "assessment-1",
        "reason_code": reason_code,
        "reviewer_note": f"人工处置；AI suggestion_id={suggestion_id}",
        "created_at": created_at,
    }


def test_metrics_separate_guardrail_blocks_from_technical_failures():
    summary = summarize_ai_suggestions(
        suggestions=[
            suggestion(
                suggestion_id="suggestion-guardrail",
                status="failed",
                guardrail_codes=["verdict_upgrade_requires_human_review"],
                error_code="ai_response_guardrail_failed",
            ),
            suggestion(
                suggestion_id="suggestion-connection",
                status="failed",
                guardrail_codes=["llm_connection_error"],
                error_code="llm_connection_error",
            ),
            suggestion(
                suggestion_id="suggestion-success",
                status="succeeded",
            ),
        ],
        snapshots=[],
    )

    assert summary["succeeded_count"] == 1
    assert summary["guardrail_blocked_count"] == 1
    assert summary["technical_failed_count"] == 1
```

以及：

```python
def test_human_rates_use_only_resolved_ai_suggestions():
    summary = summarize_ai_suggestions(
        suggestions=[
            suggestion(suggestion_id=f"suggestion-{index}", status="succeeded")
            for index in range(4)
        ],
        snapshots=[
            snapshot(
                suggestion_id="suggestion-0",
                reason_code="ai_suggestion_accepted",
                created_at="2026-07-27T10:00:00Z",
            ),
            snapshot(
                suggestion_id="suggestion-1",
                reason_code="ai_suggestion_modified",
                created_at="2026-07-27T10:01:00Z",
            ),
            snapshot(
                suggestion_id="suggestion-2",
                reason_code="ai_suggestion_rejected",
                created_at="2026-07-27T10:02:00Z",
            ),
            {
                "assessment_id": "assessment-other",
                "reason_code": "ai_suggestion_accepted",
                "reviewer_note": "AI suggestion_id=suggestion-3",
                "created_at": "2026-07-27T10:03:00Z",
            },
        ],
    )

    assert summary["resolved_ai_suggestion_count"] == 3
    assert summary["acceptance_rate"] == 1 / 3
    assert summary["modification_rate"] == 1 / 3
    assert summary["rejection_rate"] == 1 / 3
```

- [ ] **Step 2：运行测试确认失败**

```powershell
cd backend
uv run --no-sync pytest `
  tests/tools/test_report_ai_assistance_metrics.py `
  -q `
  --basetemp ../tmp/pytest-ai-observability-red
```

Expected: FAIL，模块尚不存在。

- [ ] **Step 3：实现指标分类常量和纯函数**

`backend/src/tools/report_ai_assistance_metrics.py` 必须定义：

```python
REVIEW_GUARDRAILS = frozenset({
    "evidence_page_cardinality_mismatch",
    "duplicate_evidence_reference",
    "evidence_reference_out_of_scope",
    "evidence_page_mismatch",
    "disclosed_without_substantive_evidence",
    "verdict_upgrade_requires_human_review",
    "partial_without_missing_items",
})

AI_REVIEW_REASON_CODES = frozenset({
    "ai_suggestion_accepted",
    "ai_suggestion_modified",
    "ai_suggestion_rejected",
})
```

并实现：

```python
from collections import Counter
import re


SUGGESTION_ID_PATTERN = re.compile(
    r"(?:^|[；;]\s*)AI suggestion_id=([A-Za-z0-9-]+)(?:$|[；;])"
)


def summarize_ai_suggestions(
    *,
    suggestions: list[dict[str, object]],
    snapshots: list[dict[str, object]],
) -> dict[str, object]:
    guardrail_code_counts: Counter[str] = Counter()
    error_code_counts: Counter[str] = Counter()
    succeeded_count = 0
    guardrail_blocked_count = 0
    technical_failed_count = 0
    skipped_count = 0

    for suggestion in suggestions:
        status = str(suggestion.get("status") or "")
        guardrail_codes_value = suggestion.get("guardrail_codes")
        guardrail_codes = [
            str(code)
            for code in (
                guardrail_codes_value
                if isinstance(guardrail_codes_value, list)
                else []
            )
        ]
        error_code = str(suggestion.get("error_code") or "")
        guardrail_code_counts.update(guardrail_codes)
        if error_code:
            error_code_counts.update([error_code])
        if status == "succeeded":
            succeeded_count += 1
        elif status == "skipped":
            skipped_count += 1
        elif status == "failed" and REVIEW_GUARDRAILS.intersection(
            guardrail_codes
        ):
            guardrail_blocked_count += 1
        elif status == "failed":
            technical_failed_count += 1

    suggestions_by_id = {
        str(suggestion.get("suggestion_id")): suggestion
        for suggestion in suggestions
        if str(suggestion.get("suggestion_id") or "")
    }
    resolved_by_suggestion: dict[str, str] = {}
    for snapshot in sorted(
        snapshots,
        key=lambda item: str(item.get("created_at") or ""),
    ):
        reason_code = str(snapshot.get("reason_code") or "")
        if reason_code not in AI_REVIEW_REASON_CODES:
            continue
        note = str(snapshot.get("reviewer_note") or "")
        match = SUGGESTION_ID_PATTERN.search(note)
        if match is None:
            continue
        suggestion_id = match.group(1)
        suggestion = suggestions_by_id.get(suggestion_id)
        if suggestion is None:
            continue
        if str(suggestion.get("assessment_id") or "") != str(
            snapshot.get("assessment_id") or ""
        ):
            continue
        resolved_by_suggestion[suggestion_id] = reason_code

    reason_code_counts = Counter(resolved_by_suggestion.values())
    accepted_count = reason_code_counts["ai_suggestion_accepted"]
    modified_count = reason_code_counts["ai_suggestion_modified"]
    rejected_count = reason_code_counts["ai_suggestion_rejected"]
    resolved_count = accepted_count + modified_count + rejected_count

    def rate(count: int) -> float | None:
        return count / resolved_count if resolved_count else None

    return {
        "suggestion_count": len(suggestions),
        "succeeded_count": succeeded_count,
        "guardrail_blocked_count": guardrail_blocked_count,
        "technical_failed_count": technical_failed_count,
        "skipped_count": skipped_count,
        "guardrail_code_counts": dict(sorted(guardrail_code_counts.items())),
        "error_code_counts": dict(sorted(error_code_counts.items())),
        "accepted_count": accepted_count,
        "modified_count": modified_count,
        "rejected_count": rejected_count,
        "resolved_ai_suggestion_count": resolved_count,
        "acceptance_rate": rate(accepted_count),
        "modification_rate": rate(modified_count),
        "rejection_rate": rate(rejected_count),
    }
```

输出必须包含：

```text
suggestion_count
succeeded_count
guardrail_blocked_count
technical_failed_count
skipped_count
guardrail_code_counts
error_code_counts
accepted_count
modified_count
rejected_count
resolved_ai_suggestion_count
acceptance_rate
modification_rate
rejection_rate
```

rate 分母为 0 时返回 `null`，不得返回 0 伪装成真实 0%。

- [ ] **Step 4：实现只读 CLI**

CLI 固定参数：

```text
--run-id
--output-prefix
```

运行前执行：

```sql
SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY
```

输出：

```text
tmp/ai/{prefix}_summary.json
tmp/ai/{prefix}_guardrails.csv
```

禁止：

- 创建 `LLMClient`；
- 调用 `AIAssessmentService`；
- 修改任何数据库记录；
- 输出 raw_response；
- 输出 API key、数据库 URL、完整 Prompt 或非公开模型响应。

- [ ] **Step 5：测试只读事务与输出保护**

增加测试验证：

```python
assert "READ ONLY" in first_statement.upper()
assert "raw_response" not in json.dumps(summary)
assert "api_key" not in json.dumps(summary).lower()
```

- [ ] **Step 6：增加 DEVELOPMENT 运行说明**

记录：

```powershell
cd backend
uv run --no-sync python -m src.tools.report_ai_assistance_metrics `
  --run-id run-526bd97aef5d4b9baa14618b719081c9 `
  --output-prefix tmp/ai/envision_llm_baseline
```

文档必须说明该工具不调用模型，输出不构成模型正确率或 GRI 认证。

- [ ] **Step 7：运行 focused tests 和 Ruff**

```powershell
cd backend
uv run --no-sync pytest `
  tests/tools/test_report_ai_assistance_metrics.py `
  tests/services/test_ai_assessment_service.py `
  tests/workflows/test_single_report_workflow.py `
  tests/api/test_runs_api.py `
  -q `
  --basetemp ../tmp/pytest-ai-observability-focused
uv run --no-sync ruff check `
  src/tools/report_ai_assistance_metrics.py `
  tests/tools/test_report_ai_assistance_metrics.py
```

Expected: 全部通过。

- [ ] **Step 8：提交离线观测工具**

```powershell
git add `
  backend/src/tools/report_ai_assistance_metrics.py `
  backend/tests/tools/test_report_ai_assistance_metrics.py `
  docs/DEVELOPMENT.md
git commit -m "feat: add read-only AI assistance metrics"
```

---

## Task 5：正式增加 `needs_human_review` 状态

**授权级别：** 范围 D，默认不执行。执行即解除后端和 API 状态语义冻结。

**前置条件：**

- Task 1–2 已完成；
- 已确认前端派生展示不足以满足运营需求；
- 已确认历史 `failed + verdict_upgrade_requires_human_review` 的迁移或兼容口径；
- 用户明确批准修改后端枚举、API 和工作流语义；
- 明确是否需要历史数据回填。本计划默认不回填历史记录。

**Files:**

- Modify: `backend/src/domain/enums.py`
- Modify: `backend/src/services/ai_assessment_service.py`
- Modify: `backend/src/workflows/single_report_workflow.py`
- Modify: `backend/src/api/schemas.py`
- Modify: `backend/src/api/routes/runs.py`
- Modify: `backend/tests/services/test_ai_assessment_service.py`
- Modify: `backend/tests/workflows/test_single_report_workflow.py`
- Modify: `backend/tests/api/test_runs_api.py`
- Modify: `backend/tests/api/test_openapi_contract.py`
- Modify: `frontend/lib/ai-presentation.ts`
- Modify: `frontend/components/review/ai-suggestion-panel.tsx`
- Modify: `frontend/lib/generated/api-types.ts`（通过 OpenAPI 生成命令更新）
- Modify: relevant frontend tests

数据库 `ai_assessment_suggestions.status` 当前为 `String(32)` 且没有 AI status check constraint，因此新增枚举值本身不要求 migration。若实施时数据库结构已变化，必须重新检查，不得沿用本结论。

- [ ] **Step 1：写后端状态失败测试**

在 `backend/tests/services/test_ai_assessment_service.py` 中修改 guardrail 测试：

```python
assert suggestion.status is AISuggestionStatus.NEEDS_HUMAN_REVIEW
assert suggestion.error_code == "ai_response_guardrail_blocked"
assert "verdict_upgrade_requires_human_review" in suggestion.guardrail_codes
```

技术失败继续断言：

```python
assert suggestion.status is AISuggestionStatus.FAILED
```

- [ ] **Step 2：运行服务测试确认失败**

```powershell
cd backend
uv run --no-sync pytest `
  tests/services/test_ai_assessment_service.py `
  -q `
  --basetemp ../tmp/pytest-ai-needs-review-red
```

Expected: FAIL，枚举值尚不存在。

- [ ] **Step 3：新增枚举**

在 `backend/src/domain/enums.py`：

```python
class AISuggestionStatus(StrEnum):
    SUCCEEDED = "succeeded"
    NEEDS_HUMAN_REVIEW = "needs_human_review"
    FAILED = "failed"
    SKIPPED = "skipped"
```

- [ ] **Step 4：拆分 guardrail 和技术失败**

`validate_response()` 中：

- Pydantic schema 失败继续使用 `FAILED`；
- evidence/verdict guardrail 使用 `NEEDS_HUMAN_REVIEW`；
- 连接、限流、服务和意外错误继续使用 `FAILED`。

新增专用构造函数：

```python
def _review_required_suggestion(
    self,
    candidate: AIAssessmentCandidate,
    *,
    input_hash: str,
    guardrail_codes: list[str],
    raw_response: dict,
    completion: LLMCompletionResult | None,
    parsed: AIAssessmentResponse,
) -> AIAssessmentSuggestion:
    return self._suggestion_from_response(
        candidate,
        parsed,
        input_hash=input_hash,
        status=AISuggestionStatus.NEEDS_HUMAN_REVIEW,
        raw_response=raw_response,
        completion=completion,
        guardrail_codes=guardrail_codes,
        error_code="ai_response_guardrail_blocked",
    )
```

- [ ] **Step 5：修改 AI stage 汇总语义**

`needs_human_review` 不计入技术 `failed_count`。run AI summary 增加：

```text
needs_human_review
```

stage 状态规则：

```text
所有实际调用均为技术失败 -> failed
部分实际调用为技术失败 -> partially_failed
没有技术失败，存在 needs_human_review -> completed
全部成功 -> completed
```

`needs_human_review` 表示护栏正常工作，不能把确定性 run 标记为失败。

- [ ] **Step 6：更新 OpenAPI 和前端**

前端状态标签增加：

```typescript
needs_human_review: "AI 建议需人工独立判断"
```

仍保持：

```typescript
isUsableAISuggestion(suggestion) {
  return suggestion?.status === "succeeded" && Boolean(suggestion.suggested_verdict);
}
```

`needs_human_review` 不显示采纳、载入修改和拒绝按钮；只显示 guardrail 原因和“请依据规则结果及原始证据独立复核”。

从项目根目录按 `docs/DEVELOPMENT.md` 的 OpenAPI 生成命令更新：

```text
frontend/lib/generated/api-types.ts
```

禁止手工编辑生成类型。

- [ ] **Step 7：运行后端 focused tests**

```powershell
cd backend
uv run --no-sync pytest `
  tests/services/test_ai_assessment_service.py `
  tests/workflows/test_single_report_workflow.py `
  tests/api/test_runs_api.py `
  tests/api/test_assessments_api.py `
  tests/api/test_openapi_contract.py `
  -q `
  --basetemp ../tmp/pytest-ai-needs-review-focused
```

Expected: 全部通过。

- [ ] **Step 8：运行前端 focused tests**

```powershell
cd frontend
pnpm test -- --run `
  lib/ai-presentation.test.ts `
  components/review/review-editor.test.tsx `
  components/review/assessment-detail.test.tsx
pnpm typecheck
```

Expected: 全部通过。

- [ ] **Step 9：提交状态语义调整**

```powershell
git add backend frontend docs
git commit -m "feat: separate guarded AI suggestions from failures"
```

该提交前必须用 `git diff --name-status` 确认没有 migration、规则、risk、export、RAG 或 checklist 改动。

---

## Task 6：固化 `assess_explicit_candidates` 调用边界

**授权级别：** 范围 C 或 D，需单独批准。

**Files:**

- Create: `backend/tests/architecture/test_ai_explicit_candidate_boundary.py`
- Modify: `backend/src/services/ai_assessment_service.py`

- [ ] **Step 1：增加方法说明**

在 `assess_explicit_candidates()` 上增加 docstring：

```python
"""Evaluate caller-selected candidates outside the default product path.

Only offline evaluation tools and tests may call this method. Product
workflows must call assess_candidates() so should_call() remains enforced.
"""
```

- [ ] **Step 2：写架构边界测试**

创建 `backend/tests/architecture/test_ai_explicit_candidate_boundary.py`：

```python
from pathlib import Path


PROJECT_SRC = Path(__file__).resolve().parents[2] / "src"
ALLOWED = {
    Path("services/ai_assessment_service.py"),
    Path("tools/evaluate_deepseek_against_manual_review.py"),
}


def test_explicit_candidate_assessment_is_not_used_by_product_runtime():
    offenders = []
    for path in PROJECT_SRC.rglob("*.py"):
        relative = path.relative_to(PROJECT_SRC)
        if relative in ALLOWED:
            continue
        if "assess_explicit_candidates(" in path.read_text(encoding="utf-8"):
            offenders.append(relative.as_posix())

    assert offenders == []
```

- [ ] **Step 3：运行边界测试**

```powershell
cd backend
uv run --no-sync pytest `
  tests/architecture/test_ai_explicit_candidate_boundary.py `
  tests/services/test_ai_assessment_service.py `
  -q `
  --basetemp ../tmp/pytest-ai-explicit-boundary
```

Expected: PASS；默认 workflow、API、service runner 均没有调用显式候选方法。

- [ ] **Step 4：提交边界测试**

```powershell
git add `
  backend/src/services/ai_assessment_service.py `
  backend/tests/architecture/test_ai_explicit_candidate_boundary.py
git commit -m "test: lock explicit AI evaluation boundary"
```

---

## Task 7：最终门禁与文档收口

**授权级别：** 按实际执行范围决定。

- [x] **Step 1：确认没有真实外部调用**

Run:

```powershell
rg -n "OPENAI_COMPATIBLE_API_KEY|api_key|raw_response" `
  README.md docs backend/.env.example
```

Expected:

- 文档只出现环境变量名；
- 不出现密钥值；
- 产品验收文档不包含 raw response；
- 测试继续使用 mock completion factory。

- [x] **Step 2：运行仓库卫生检查**

```powershell
git diff --check
$drivePattern = "(?<![A-Za-z0-9_+.-])[A-Za-z]:[\\/]"
Select-String `
  -Path docs/plan/llm-assistance-optimization-plan.md,docs/product/llm-assistance-acceptance.md `
  -Pattern $drivePattern
```

Expected:

- `git diff --check` 无错误；
- 新文档没有本机绝对路径。

- [x] **Step 3：按范围运行门禁**

只执行 Task 1–2：

```powershell
git diff --check
rg -n "confirm_llm|最终合规结论|人工 snapshot" `
  docs/plan/llm-assistance-optimization-plan.md `
  docs/product/llm-assistance-acceptance.md
```

执行 Task 3：

```powershell
cd frontend
pnpm test -- --run
pnpm typecheck
pnpm build
```

执行 Task 4、5 或 6：

```powershell
cd backend
uv run --no-sync pytest -q --basetemp ../tmp/pytest-llm-optimization-full
uv run --no-sync ruff check src tests
```

执行 Task 5 时还必须运行：

```powershell
cd frontend
pnpm test -- --run
pnpm typecheck
pnpm build
```

- [x] **Step 4：执行 Envision v3 regression**

只要执行 Task 4、5 或 6，必须显式绑定测试库运行：

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

- [x] **Step 5：确认正式层级未改变**

Run:

```powershell
rg -n "latest_ai_suggestion|system_verdict|reviewed_verdict|effective_verdict" `
  backend/src/api/routes/assessments.py `
  backend/src/services/export_service.py `
  frontend/components/review
```

人工复核和导出必须继续使用既有 effective verdict 规则。不得出现 AI suggestion 直接写入 assessment、risk 或 export verdict 的新路径。

- [x] **Step 6：记录实际执行范围**

在本计划顶部的 Task 状态表中逐项勾选实际完成的 Task，并写入：

```text
真实模型调用：无
后端是否解冻：是/否
前端是否变更：是/否
```

不得把未批准、未执行的 Task 标记为完成。

## 6. 停止条件

出现以下任一情况立即停止：

1. 需要真实 DeepSeek 调用但没有当次用户批准。
2. 需要修改 Prompt、模型或候选筛选，但没有独立专家 gold 或明确失败假设。
3. 需要新增 migration、修改 checklist、证据规则、risk-v2.1 或导出口径。
4. 发现 AI suggestion 可以直接改变规则 assessment 或 effective verdict。
5. 发现 `assess_explicit_candidates()` 被默认产品 workflow、API 或后台 runner 调用。
6. 前端展示尝试把 guardrail 拦截 suggestion 变为可采纳状态。
7. `confirm_llm=false` 产生真实外部请求。
8. 新观测工具尝试写数据库或输出 raw response、密钥、数据库 URL、完整 Prompt。
9. 后端全量测试、前端门禁或 Envision v3 gate 出现回归。
10. 需要把 RAG Phase 1.5 数据接入正式 AI suggestion。

## 7. 完成定义

### 范围 A 完成

- 当前门禁数字一致；
- LLM 产品验收说明完成；
- 风险、指标、冻结决策和解冻条件完整；
- 没有代码、API、Prompt、模型、数据库或导出改动；
- 没有真实外部调用。

### 范围 B 完成

- 前端能区分安全拦截和技术失败；
- 空态不虚构后端没有提供的原因；
- guardrail 拦截 suggestion 仍不可采纳；
- frontend tests、typecheck、build 全部通过。

### 范围 C 完成

- 观测工具只读数据库；
- 指标分母和分类固定；
- 输出不包含 raw response、密钥、数据库 URL 或完整 Prompt；
- focused tests、后端全量测试、Ruff 和 Envision gate 全部通过。

### 范围 D 完成

- `needs_human_review` 与技术 `failed` 在 domain、API、workflow、OpenAPI 和前端一致；
- 历史记录兼容策略明确；
- AI stage 不把正常 guardrail 拦截误报为技术失败；
- 三层权威关系和正式输出口径不变；
- 后端、前端、Envision 和 audit 全部门禁通过；
- 没有真实外部模型调用，除非另有明确批准和独立评估计划。
