# AI 候选路由与证据类型治理 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**目标：** 修复缺少 `evidence_type` 的弱证据被误判为实质证据、进而触发外部模型的问题；在不改变规则结论、人工复核、适用性、风险、GRI 范围和正式导出的前提下，使 AI 调用范围可解释、可观测、可回归。

**架构：** 在规则 assessment 与 `AIAssessmentService` 之间增加一个只供 AI 使用的证据资格分类器。分类器只读取既有 evidence、metadata 和质量标记，不修改 evidence，不回写规则层。产品默认路径继续由 `confirm_llm` 控制外部调用；已授权运行保存候选和跳过原因，未授权运行维持 run 级 skipped。观测能力通过只读离线工具实现，不新增产品 API 或数据库字段。

**技术栈：** FastAPI、Pydantic、SQLAlchemy、pytest、Ruff、Next.js、React、TypeScript、Vitest、pnpm。

---

## 0. 计划状态与决策

**计划状态：** Task 1–8 已完成；Task 9 未授权且未执行。真实 DeepSeek、SiliconFlow、OCR 和 VLM 新调用均为 0。

**推荐执行方式：** 用户确认本计划后，在当前窗口连续完成 Task 1–8；按工作包分批 commit，全部验证完成后统一汇报。真实 DeepSeek 对比属于 Task 9 的独立授权门禁，不随代码实施自动获得授权。

### 0.1 与现有计划的关系

- `docs/plan/llm-assistance-optimization-plan.md` 保留为 LLM 辅助层历史总计划和边界来源。
- 该文件中未执行的“只读离线 AI 观测工具”被本计划吸收；实现时以本计划的指标和验收口径为准。
- 本计划是一次范围受控的后端解冻候选，不解锁 `needs_human_review` 新数据库状态、Prompt 调整、模型切换、OCR/VLM 或 RAG Phase 2。
- 历史运行和历史 suggestion 只读保留，不回填、不重算、不覆盖。

### 0.2 第一性原理判断

AI 置信度只能在输入证据能够回答 requirement 时才有意义。当前问题包含两个不同层次：

1. **候选精度问题：** 页面正文未提取、只有目录或索引文字的 evidence 不应触发模型。修复后会减少无效调用和低置信度噪声。
2. **证据召回问题：** 报告若存在可用正文但当前解析未提取，后续需要 OCR/VLM 或更强的 evidence routing；该能力不在本次范围。

因此，本计划的成功标准是“弱证据不再进入默认 AI 调用范围，原因可解释”，不承诺把 0%/10%/20% 人为提高，也不以高置信度作为优化目标。

---

## 1. 当前基线与已确认缺陷

### 1.1 产品基线

| 项目 | 当前口径 |
|---|---|
| GRI 范围 | `577/499/78/0` |
| 外部模型开关 | 仅 `confirm_llm=true` 允许调用 |
| 默认产品运行 | `confirm_llm=false`，AI stage skipped，零外部调用 |
| AI 数据层 | `ai_assessment_suggestions` 追加保存 |
| 最终有效结论 | 人工 review snapshot |
| 当前后端门禁 | 774 项测试和 Ruff 通过 |
| 当前前端门禁 | lint 通过，39 个测试文件、146 项测试、typecheck、production build 通过 |
| Envision v3 安全门禁 | 新增 false disclosed、wrong source page、global fallback 均为 0；audit 0 error、0 warning |

门禁数字是实施前基线。新增测试后，最终数量允许增加，但不得减少测试发现范围或放宽断言。

### 1.2 本次缺陷样本

最新一次已授权 Envision 运行共处理 499 个独立判断项：

| 结果 | 数量 |
|---|---:|
| `low_review_priority` | 436 |
| `no_substantive_evidence` | 59 |
| 实际调用并 succeeded | 4 |
| 模型失败 | 0 |

4 个实际调用项为：

- `GRI 2-5-a`
- `GRI 2-5-b-i`
- `GRI 2-5-b-ii`
- `GRI 2-5-b-iii`

它们共同引用 PDF 第 77 页。该页主要是“目录/独立有限鉴证报告”相关短文本，质量标记包含 `short_text`、`image_body_not_extracted`，metadata 未显式提供 `evidence_type`。模型返回 `unknown`，置信度为 0%、0%、10%、20%。

根因在 `AIAssessmentService._evidence_type()`：缺少 `evidence_type` 时默认返回 `substantive_report_evidence`。该兼容默认值没有结合 `image_body_not_extracted`，导致正文未提取的 evidence 通过 `should_call()`。

### 1.3 需要保留的正确行为

- 4 次模型响应均为 `unknown`，没有错误升级规则 verdict，模型侧安全护栏有效。
- `confirm_llm=false` 时不创建 499 条逐项 skipped suggestion，避免未授权运行产生记录噪声。
- `assess_explicit_candidates()` 可绕过默认候选筛选，但只能用于离线评估和定向测试。
- `index_page_bounded` 仅代表候选页由索引限定，不能单独推导“该 evidence 是目录或索引证据”；正文页也可能通过该路由得到。

---

## 2. 范围、非目标与影响面

### 2.1 本次实施范围

1. 增加 AI 本地证据资格分类器，识别显式非实质证据和“图片正文未提取”证据。
2. 让 `AIAssessmentService.should_call()`、response guardrail 和 skip reason 使用同一分类口径。
3. 规范 `confirm_llm=true` 且合格候选为 0 时的记录行为：不调用模型，但保存逐项 skipped 原因，AI stage 显示 skipped。
4. 前端补齐 `structure_not_independent` 和 `no_substantive_evidence` 的中文解释，内部字段名不得暴露给用户。
5. 增加只读离线 AI 观测工具，输出调用、跳过、失败、护栏、置信度和人工处置分布。
6. 固化 `assess_explicit_candidates()` 只用于评估/测试的调用边界。
7. 运行后端、前端、Envision v3 和 AI 安全审计完整 gates。
8. 更新设计、开发和验收文档，分批 commit，不自动 push。

### 2.2 明确非目标

- 不修改 DeepSeek 模型、endpoint、默认参数或 Prompt 文本。
- 不引入置信度阈值，不对低置信度做数值放大或重标定。
- 不接入 OCR、VLM、Docling 或 PaddleOCR。
- 不把 RAG Phase 1.5 结果接入默认 AI 产品路径，不进入 RAG Phase 2。
- 不修改 requirement checklist、规则 verdict、适用性、风险优先级、人工 snapshot 或正式导出。
- 不修改 `577/499/78/0` 结构口径。
- 不新增数据库迁移、API 字段、AI status 枚举或 `needs_human_review` 状态。
- 不重写历史 suggestion，不把 DeepSeek 工程评估写成 GRI 认证或专家正确率。
- 不强制调用 `assess_explicit_candidates()` 来制造高置信度结果。

### 2.3 预计影响范围

| 层级 | 影响 | 风险 |
|---|---|---|
| AI 候选路由 | 调用集合会减少；弱证据转为 skipped | 中 |
| AI suggestion 记录 | 已授权且零候选时会保存逐项跳过原因 | 中 |
| AI stage 展示 | 已授权零候选显示 skipped，保持零调用 | 低 |
| 前端文案 | 增加跳过原因中文映射 | 低 |
| 离线观测 | 新增只读 JSON/CSV 工具 | 低 |
| 规则、风险、人工、导出 | 必须保持字节级或字段级语义不变 | 高风险保护区 |

---

## 3. 目标架构与固定语义

### 3.1 AI 本地证据分类

新增纯函数模块：

```text
EvidenceItem
  -> classify_ai_evidence()
      -> substantive
      -> explicit_non_substantive
      -> unresolved_image_body
```

分类优先级固定为：

1. `evidence_type` 属于 `omission_note/index_statement/chapter_cover/candidate_page`：`explicit_non_substantive`。
2. `quality_flags` 包含 `image_body_not_extracted`：`unresolved_image_body`，即使 `evidence_type` 缺失或错误标为 substantive，也不得触发 AI。
3. 其余 evidence：`substantive`，保持现有兼容行为。

以下信息只用于诊断，不单独决定非实质分类：

- `retrieval_strategy=index_page_bounded`
- `candidate_page_source=gri_report_index`
- `short_text`

理由：候选页由索引路由得到，不等于候选页本身是索引；`short_text` 也可能是有效 KPI 或零事件披露。`image_body_not_extracted` 明确表示当前文本没有覆盖主要正文，因此具有足够强的拦截依据。

### 3.2 调用与记录语义

| 条件 | 外部调用 | suggestion 记录 | AI stage |
|---|---:|---|---|
| `confirm_llm=false` | 0 | 不写逐项记录 | skipped `0/0` |
| `confirm_llm=true`，服务未配置 | 0 | 不写逐项记录 | skipped `0/0`，给出配置原因 |
| `confirm_llm=true`，合格候选为 0 | 0 | 为输入 candidates 保存 skipped 原因 | skipped `0/0` |
| `confirm_llm=true`，存在合格候选 | 仅调用合格候选 | 保存 succeeded/failed/skipped | completed/partially_failed/failed |

本次继续复用已有 skip code：

```text
structure_not_independent
low_review_priority
no_substantive_evidence
call_budget_exhausted
external_model_not_confirmed
```

`unresolved_image_body` 只作为分类器内部诊断类别，对外映射到既有 `no_substantive_evidence`，避免扩大 API 和持久化状态语义。

### 3.3 不变量

- `confirm_llm=false` 的任何路径都不能创建 `LLMClient.complete_json()` 请求。
- `model_called=true` 只允许写给 `succeeded` 或 `failed` 的真实 attempted assessment，skipped 必须保持 false。
- AI suggestion 只能追加，不能 update 规则 assessment。
- AI response 引用证据仍需通过 evidence ID、页码、数量和 verdict upgrade 护栏。
- 新分类器只读取 evidence，不改变 metadata、quality flags、source page 或 evidence preview。
- 正式 conclusion 仍来自人工 snapshot；AI confidence 不参与规则、风险或导出排序。

---

## 4. 文件清单

### 后端

- Create: `backend/src/services/ai_evidence_eligibility.py`
- Modify: `backend/src/services/ai_assessment_service.py`
- Modify: `backend/src/workflows/single_report_workflow.py`
- Modify: `backend/tests/services/test_ai_assessment_service.py`
- Modify: `backend/tests/workflows/test_single_report_workflow.py`
- Create: `backend/src/tools/report_ai_assistance_metrics.py`
- Create: `backend/tests/tools/test_report_ai_assistance_metrics.py`
- Modify: `backend/tests/tools/test_evaluate_deepseek_against_manual_review.py`

### 前端

- Modify: `frontend/lib/ai-presentation.ts`
- Modify: `frontend/lib/ai-presentation.test.ts`
- Modify only if focused test proves necessary: `frontend/components/review/ai-suggestion-panel.tsx`
- Modify only if focused test proves necessary: `frontend/components/review/review-editor.test.tsx`

### 文档

- Modify: `README.md`
- Modify: `docs/DESIGN.md`
- Modify: `docs/DEVELOPMENT.md`
- Create: `docs/product/ai-candidate-routing-acceptance.md`

### 禁止修改

- `backend/src/domain/ai_models.py`
- `backend/src/config/settings.py`
- Alembic migration 和数据库表结构
- GRI manifest、evidence contracts、risk rules、report profile
- export schema 和前端生成 API 类型

若实施中确认必须修改“禁止修改”文件，立即停止并重新评估范围，不得顺手扩大解冻面。

---

## Task 1：冻结实施前基线与差异保护

**Files:**

- Read: `README.md`
- Read: `docs/DESIGN.md`
- Read: `docs/DEVELOPMENT.md`
- Read: `backend/src/services/ai_assessment_service.py`
- Read: `backend/src/workflows/single_report_workflow.py`
- Create during execution: `docs/product/ai-candidate-routing-acceptance.md`

- [x] **Step 1：检查工作区和提交基线**

```powershell
git status -sb
git log -5 --oneline
```

Expected:

- 记录 main 与 origin/main 的 ahead/behind 状态；
- 区分本计划文件和用户已有改动；
- 不回退、不暂存、不格式化无关文件；
- 不 push。

- [x] **Step 2：记录实施前 AI 基线**

在验收文档中记录：

```text
499 = 436 low_review_priority + 59 no_substantive_evidence + 4 succeeded
actual_calls = 4
confidence = [0.0, 0.0, 0.1, 0.2]
suggested_verdict = unknown x 4
target requirements = GRI 2-5-a / GRI 2-5-b-i / GRI 2-5-b-ii / GRI 2-5-b-iii
target page = PDF 77
quality flags include short_text + image_body_not_extracted
```

不得把 API key、完整模型 raw response 或本机绝对路径写入文档。

- [x] **Step 3：执行实施前 focused baseline**

```powershell
cd backend
uv run --no-sync pytest `
  tests/services/test_ai_assessment_service.py `
  tests/workflows/test_single_report_workflow.py `
  tests/tools/test_evaluate_deepseek_against_manual_review.py `
  -q `
  --basetemp ../tmp/pytest-ai-routing-baseline
```

Expected: PASS。若基线本身失败，停止实施，先区分已有失败与本计划缺陷。

---

## Task 2：用失败测试固定证据资格边界

**Files:**

- Modify: `backend/tests/services/test_ai_assessment_service.py`
- Create: `backend/src/services/ai_evidence_eligibility.py`

- [x] **Step 1：扩展测试 fixture，不改变默认样本**

让 `_evidence()` 支持显式传入：

```python
metadata: dict[str, object] | None = None
quality_flags: list[PageQualityFlag] | None = None
```

默认仍生成：

```python
metadata={"evidence_type": "substantive_report_evidence"}
quality_flags=[]
```

- [x] **Step 2：增加分类器失败测试**

至少覆盖：

```python
@pytest.mark.parametrize(
    ("metadata", "quality_flags", "expected"),
    [
        ({"evidence_type": "substantive_report_evidence"}, [], True),
        ({}, [], True),
        ({"evidence_type": "index_statement"}, [], False),
        ({"evidence_type": "omission_note"}, [], False),
        ({}, [PageQualityFlag.IMAGE_BODY_NOT_EXTRACTED], False),
        (
            {"evidence_type": "substantive_report_evidence"},
            [PageQualityFlag.IMAGE_BODY_NOT_EXTRACTED],
            False,
        ),
        (
            {
                "retrieval_strategy": "index_page_bounded",
                "candidate_page_source": "gri_report_index",
            },
            [PageQualityFlag.DIGITAL_TEXT],
            True,
        ),
    ],
)
def test_ai_evidence_eligibility_is_conservative_without_treating_routes_as_types(...):
    ...
```

关键断言：`index_page_bounded` 和 `gri_report_index` 不能单独导致跳过；`image_body_not_extracted` 必须阻止默认产品调用。

- [x] **Step 3：增加 GRI 2-5 缺陷回归测试**

构造 4 个 requirement candidate，metadata 与质量标记复现 PDF 第 77 页，断言：

```python
suggestions = service.assess_candidates(candidates, confirm_llm=True)

assert client.calls == []
assert len(suggestions) == 4
assert {item.status for item in suggestions} == {AISuggestionStatus.SKIPPED}
assert {
    code
    for item in suggestions
    for code in item.guardrail_codes
} == {"no_substantive_evidence"}
```

- [x] **Step 4：运行测试确认 RED**

```powershell
cd backend
uv run --no-sync pytest `
  tests/services/test_ai_assessment_service.py `
  -q `
  --basetemp ../tmp/pytest-ai-routing-red
```

Expected: 新增 `image_body_not_extracted` 用例失败；失败原因应直接指向当前默认 substantive 行为。

- [x] **Step 5：实现最小纯函数分类器**

`backend/src/services/ai_evidence_eligibility.py` 对外只暴露：

```python
class AIEvidenceCategory(StrEnum):
    SUBSTANTIVE = "substantive"
    EXPLICIT_NON_SUBSTANTIVE = "explicit_non_substantive"
    UNRESOLVED_IMAGE_BODY = "unresolved_image_body"


@dataclass(frozen=True)
class AIEvidenceEligibility:
    category: AIEvidenceCategory
    is_substantive: bool


def classify_ai_evidence(evidence: EvidenceItem) -> AIEvidenceEligibility:
    ...
```

实现要求：

- 常量 `NON_SUBSTANTIVE_EVIDENCE_TYPES` 移入该模块，避免 service 和 guardrail 各写一份。
- 先判断显式非实质 `evidence_type`，再判断 `image_body_not_extracted`。
- 不根据中文关键词、公司名称、固定页码或 requirement ID 分类。
- 不写 evidence metadata。
- 不引入 OCR/VLM 调用。

- [x] **Step 6：运行 focused tests 确认 GREEN**

```powershell
cd backend
uv run --no-sync pytest `
  tests/services/test_ai_assessment_service.py `
  -q `
  --basetemp ../tmp/pytest-ai-routing-green
uv run --no-sync ruff check `
  src/services/ai_evidence_eligibility.py `
  tests/services/test_ai_assessment_service.py
```

Expected: PASS。

---

## Task 3：接入默认 AI 路由并规范零候选记录

**Files:**

- Modify: `backend/src/services/ai_assessment_service.py`
- Modify: `backend/src/workflows/single_report_workflow.py`
- Modify: `backend/tests/services/test_ai_assessment_service.py`
- Modify: `backend/tests/workflows/test_single_report_workflow.py`

- [x] **Step 1：让 service 复用唯一分类口径**

将以下位置统一改为调用 `classify_ai_evidence()`：

- `should_call()` 的实质证据判断；
- response 中 `disclosed_without_substantive_evidence` 护栏；
- `_skip_code()` 最终映射。

删除 `_evidence_type()` 的“缺失即 substantive”独立实现；`build_ai_assessment_messages()` 的字段结构和 Prompt 文本保持不变。

- [x] **Step 2：先写 workflow 零候选失败测试**

增加一个 `confirm_llm=true`、服务已配置、全部 candidates 均为 `image_body_not_extracted` 的用例，断言：

```python
assert client.calls == []
assert run.status is RunStatus.COMPLETED
assert all(not item.model_called for item in assessments)
assert len(repo.list_ai_suggestions_for_run(run.run_id)) == len(assessments)
assert all(item.status is AISuggestionStatus.SKIPPED for item in suggestions)
assert all(item.error_code == "no_substantive_evidence" for item in suggestions)
assert ai_stage.status == "skipped"
assert (ai_stage.completed_units, ai_stage.total_units) == (0, 0)
```

- [x] **Step 3：规范已授权零候选 workflow**

在 `SingleReportWorkflow._run_ai_assistance()` 中：

- 保留 `confirm_llm=false` 立即返回；
- 保留 service 未配置立即返回；
- service 已配置时总是调用 `assess_candidates()`，即使 `eligible_count == 0`；
- 持久化所有 skipped suggestion；
- `eligible_count == 0` 时 AI stage 记为 skipped `0/0`；
- 只有非 skipped suggestion 的 assessment 才标记 `model_called=true`。

不得把 skipped 数量写成 completed model calls。

- [x] **Step 4：固化部分候选场景**

对“部分可调用、部分 skipped”断言：

```text
stage total_units = eligible_count
stage completed_units = eligible_count
suggestion rows = all input candidates
model_called count = succeeded + failed
skipped count does not affect failed_count
```

- [x] **Step 5：运行 focused workflow tests**

```powershell
cd backend
uv run --no-sync pytest `
  tests/services/test_ai_assessment_service.py `
  tests/workflows/test_single_report_workflow.py `
  -q `
  --basetemp ../tmp/pytest-ai-routing-workflow
uv run --no-sync ruff check `
  src/services/ai_evidence_eligibility.py `
  src/services/ai_assessment_service.py `
  src/workflows/single_report_workflow.py `
  tests/services/test_ai_assessment_service.py `
  tests/workflows/test_single_report_workflow.py
```

Expected: PASS；Fake client 调用数与合格候选数完全一致。

- [x] **Step 6：提交后端核心修改**

```powershell
git add `
  backend/src/services/ai_evidence_eligibility.py `
  backend/src/services/ai_assessment_service.py `
  backend/src/workflows/single_report_workflow.py `
  backend/tests/services/test_ai_assessment_service.py `
  backend/tests/workflows/test_single_report_workflow.py
git commit -m "fix: tighten AI evidence candidate routing"
```

---

## Task 4：补齐前端跳过原因表达

**Files:**

- Modify: `frontend/lib/ai-presentation.ts`
- Modify: `frontend/lib/ai-presentation.test.ts`
- Modify only if required by failing test: `frontend/components/review/ai-suggestion-panel.tsx`
- Modify only if required by failing test: `frontend/components/review/review-editor.test.tsx`

- [x] **Step 1：先写中文映射失败测试**

至少断言：

```typescript
expect(aiGuardrailLabel("structure_not_independent")).toContain("上下文");
expect(aiGuardrailLabel("no_substantive_evidence")).toContain("证据不足");
expect(aiGuardrailLabel("low_review_priority")).toContain("优先级较低");
expect(aiGuardrailLabel("call_budget_exhausted")).toContain("数量上限");
```

增加 DOM 断言，确保页面不显示：

```text
structure_not_independent
no_substantive_evidence
call_budget_exhausted
```

- [x] **Step 2：运行测试确认 RED**

```powershell
cd frontend
pnpm test -- --run lib/ai-presentation.test.ts
```

Expected: 当前缺少前两个映射的测试失败。

- [x] **Step 3：增加固定中文文案**

使用以下产品语义：

```text
structure_not_independent -> 该项属于上下文结构，不单独调用 AI。
no_substantive_evidence -> 当前证据不足以支持 AI 判断，本项未调用 AI。
low_review_priority -> 该项复核优先级较低，本次未调用 AI。
call_budget_exhausted -> 本次 AI 调用已达到数量上限。
external_model_not_confirmed -> 本次分析未授权调用外部模型。
```

不得显示 `requirement`、`guardrail_codes`、`error_code` 等内部字段名。

- [x] **Step 4：运行 focused frontend tests**

```powershell
cd frontend
pnpm test -- --run `
  lib/ai-presentation.test.ts `
  components/review/review-editor.test.tsx
pnpm typecheck
```

Expected: PASS。

---

## Task 5：实现只读 AI 观测工具

**Files:**

- Create: `backend/src/tools/report_ai_assistance_metrics.py`
- Create: `backend/tests/tools/test_report_ai_assistance_metrics.py`

**边界：** 只读数据库，只向 `tmp/ai/` 写 JSON/CSV；不创建 `LLMClient`，不调用 `AIAssessmentService`，不写 suggestion、assessment、risk、review 或 export。

- [x] **Step 1：先写指标纯函数失败测试**

对 `summarize_ai_suggestions()` 至少覆盖：

- succeeded、failed、skipped 分离；
- `called_count = succeeded_count + failed_count`；
- skip reason 分布；
- guardrail 与技术失败分离；
- confidence 的 `null`、0–19%、20–39%、40–59%、60–79%、80–100% 分桶；
- accepted/modified/rejected 只统计能关联到同 assessment suggestion 的人工 snapshot；
- 人工处置分母为 0 时 rate 返回 `null`。

- [x] **Step 2：运行测试确认 RED**

```powershell
cd backend
uv run --no-sync pytest `
  tests/tools/test_report_ai_assistance_metrics.py `
  -q `
  --basetemp ../tmp/pytest-ai-observability-red
```

Expected: FAIL，模块尚不存在。

- [x] **Step 3：实现固定指标**

JSON summary 必须包含：

```text
run_id
confirm_llm
suggestion_count
called_count
succeeded_count
guardrail_blocked_count
technical_failed_count
skipped_count
skip_reason_counts
guardrail_code_counts
error_code_counts
confidence_bucket_counts
accepted_count
modified_count
rejected_count
resolved_ai_suggestion_count
acceptance_rate
modification_rate
rejection_rate
```

解释限制：

- `confidence_bucket_counts` 描述模型自报分数分布，不等同于校准准确率。
- acceptance/modified/rejected 描述产品使用行为，不等同于模型正确率。
- `confirm_llm=false` 且 suggestion_count 为 0 时，不能推导“模型全部成功”。

- [x] **Step 4：实现只读 CLI**

CLI 固定参数：

```text
--run-id
--output-prefix
```

数据库读取前执行：

```sql
SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY
```

输出：

```text
tmp/ai/{prefix}_summary.json
tmp/ai/{prefix}_suggestions.csv
```

CSV 允许字段：

```text
assessment_id
status
suggested_verdict
confidence
guardrail_codes
error_code
latency_ms
retry_count
```

禁止输出 `raw_response`、API key、数据库 URL、完整 Prompt、完整 evidence 文本和本机绝对路径。

- [x] **Step 5：测试只读与脱敏**

必须断言：

```python
assert "READ ONLY" in first_statement.upper()
assert "raw_response" not in serialized_output
assert "api_key" not in serialized_output.lower()
assert "database_url" not in serialized_output.lower()
```

- [x] **Step 6：运行 focused tests 和 Ruff**

```powershell
cd backend
uv run --no-sync pytest `
  tests/tools/test_report_ai_assistance_metrics.py `
  tests/services/test_ai_assessment_service.py `
  tests/workflows/test_single_report_workflow.py `
  -q `
  --basetemp ../tmp/pytest-ai-observability-green
uv run --no-sync ruff check `
  src/tools/report_ai_assistance_metrics.py `
  tests/tools/test_report_ai_assistance_metrics.py
```

Expected: PASS。

---

## Task 6：固化显式候选评估边界

**Files:**

- Modify: `backend/src/services/ai_assessment_service.py`
- Modify: `backend/tests/tools/test_evaluate_deepseek_against_manual_review.py`
- Modify: `docs/DEVELOPMENT.md`

- [x] **Step 1：补充方法 docstring**

`assess_explicit_candidates()` 必须明确：

```text
仅供离线评估和定向测试；故意绕过 should_call；不得由默认 workflow、API、analysis runner 或后台任务调用。
```

- [x] **Step 2：增加静态调用边界测试**

扫描 `backend/src`，允许调用文件仅为：

```text
src/tools/evaluate_deepseek_against_manual_review.py
```

方法定义文件本身不计为调用。未来新增调用方必须显式更新测试并重新批准范围。

- [x] **Step 3：验证产品默认路径没有绕过筛选**

```powershell
rg -n "assess_explicit_candidates\(" backend/src backend/tests
```

Expected:

- 产品 workflow/API/runner 中 0 个调用；
- 仅 service 定义、离线评估工具和测试存在引用。

- [x] **Step 4：提交展示与观测工作包**

```powershell
git add `
  backend/src/services/ai_assessment_service.py `
  backend/src/tools/report_ai_assistance_metrics.py `
  backend/tests/tools/test_report_ai_assistance_metrics.py `
  backend/tests/tools/test_evaluate_deepseek_against_manual_review.py `
  frontend/lib/ai-presentation.ts `
  frontend/lib/ai-presentation.test.ts `
  frontend/components/review/ai-suggestion-panel.tsx `
  frontend/components/review/review-editor.test.tsx
git commit -m "feat: explain and observe AI assistance routing"
```

`git add` 前先用 `git status --short` 确认仅暂存实际修改文件；未修改的可选文件不得强行加入。

---

## Task 7：执行完整自动门禁与差异审计

### 7.1 后端目标测试

- [x] **Step 1：运行 AI 纵向测试**

```powershell
cd backend
uv run --no-sync pytest `
  tests/services/test_ai_assessment_service.py `
  tests/workflows/test_single_report_workflow.py `
  tests/api/test_runs_api.py `
  tests/api/test_reports_api.py `
  tests/tools/test_report_ai_assistance_metrics.py `
  tests/tools/test_evaluate_deepseek_against_manual_review.py `
  -q `
  --basetemp ../tmp/pytest-ai-routing-focused-final
```

Expected: PASS；测试全部使用 fake client，不产生真实外部请求。

### 7.2 后端完整门禁

- [x] **Step 2：运行全量 pytest 和 Ruff**

```powershell
cd backend
uv run --no-sync pytest -q --basetemp ../tmp/pytest-ai-routing-full-final
uv run --no-sync ruff check src tests
```

Expected:

- pytest 全部通过；
- 测试数量不少于实施前 774；
- Ruff 0 error。

### 7.3 前端完整门禁

- [x] **Step 3：运行 lint、test、typecheck、build**

```powershell
cd frontend
pnpm lint
pnpm test -- --run
pnpm typecheck
pnpm build
```

Expected:

- lint 0 error；已知 warning 不新增；
- 测试文件和测试数量不少于实施前 39/146；
- typecheck 通过；
- production build 通过。

### 7.4 Envision v3 规则回归

- [x] **Step 4：重新生成 499 assessment review CSV**

```powershell
cd backend
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

- `577/499/78/0`；
- global fallback 0；
- 新增 false disclosed 0；
- 新增 wrong source page 0；
- audit 0 error、0 warning；
- 规则 verdict、review status、evidence page、risk、适用性和导出口径无非预期差异。

该命令必须保持 `confirm_llm=false`，不得触发 DeepSeek。

### 7.5 静态安全检查

- [x] **Step 5：确认未扩大范围**

```powershell
git diff --name-only
git diff --check
rg -n "confirm_llm=True|assess_explicit_candidates\(" backend/src
rg -n "needs_human_review|deepseek-gri-assist|deepseek-v4|OPENAI_COMPATIBLE_API_KEY" `
  backend/src frontend docs
```

Expected:

- 无 Alembic、schema、settings、Prompt、GRI manifest、risk rule 和 export 文件变更；
- 默认产品路径没有硬编码 `confirm_llm=True`；
- 密钥未进入 diff；
- `assess_explicit_candidates()` 未进入产品路径。

---

## Task 8：文档、验收报告与分批提交

**Files:**

- Modify: `README.md`
- Modify: `docs/DESIGN.md`
- Modify: `docs/DEVELOPMENT.md`
- Create: `docs/product/ai-candidate-routing-acceptance.md`
- Modify: `docs/plan/ai-candidate-routing-evidence-governance-plan.md`

- [x] **Step 1：更新设计唯一源**

`docs/DESIGN.md` 记录：

- AI-local evidence eligibility 的三类定义；
- `image_body_not_extracted` 不进入默认 AI 调用；
- index route metadata 不能单独视为非实质 evidence；
- 已授权零候选保存 skipped，未授权运行不保存逐项 suggestion；
- 规则/AI/人工三层优先级没有变化。

- [x] **Step 2：更新开发运行说明**

`docs/DEVELOPMENT.md` 记录只读工具命令：

```powershell
cd backend
uv run --no-sync python -m src.tools.report_ai_assistance_metrics `
  --run-id <run-id> `
  --output-prefix envision_ai_routing
```

明确输出不构成模型正确率、GRI 认证或 ESG 专家结论。

- [x] **Step 3：完成验收报告**

`docs/product/ai-candidate-routing-acceptance.md` 至少包含：

1. 实施前 499/436/59/4 基线；
2. 缺陷根因；
3. 代码 diff 分类；
4. targeted/full gates 实际结果；
5. Envision v3 差异；
6. 真实外部调用次数；
7. 未验证项和剩余风险；
8. 是否建议进入 Task 9。

- [x] **Step 4：更新 README 当前状态**

只更新最新门禁数字和 AI 路由行为，不改写历史测试数字。

- [x] **Step 5：计划自检**

```powershell
rg -n "T[B]D|TO[D]O|待[补]充[:：]|待[确]认[:：]" `
  docs/plan/ai-candidate-routing-evidence-governance-plan.md `
  docs/product/ai-candidate-routing-acceptance.md `
  README.md docs/DESIGN.md docs/DEVELOPMENT.md
rg -n "(^|[^A-Za-z])[A-Za-z]:[/\\]" `
  docs/plan/ai-candidate-routing-evidence-governance-plan.md `
  docs/product/ai-candidate-routing-acceptance.md `
  README.md docs/DESIGN.md docs/DEVELOPMENT.md
git diff --check
```

Expected:

- 无占位符；
- docs 不包含本机绝对路径；
- 无尾随空格或冲突标记。

- [x] **Step 6：提交文档和验收结果**

```powershell
git add `
  README.md `
  docs/DESIGN.md `
  docs/DEVELOPMENT.md `
  docs/product/ai-candidate-routing-acceptance.md `
  docs/plan/ai-candidate-routing-evidence-governance-plan.md
git commit -m "docs: record AI routing acceptance"
```

- [x] **Step 7：最终提交检查**

```powershell
git status -sb
git log -5 --oneline
git diff HEAD~3..HEAD --stat
```

Expected:

- 形成 3 个边界清晰的 commit；
- 工作区无本任务遗留修改，或明确列出用户原有修改；
- 不自动 push。

---

## Task 9：真实 DeepSeek 前后对比（独立授权，默认不执行）

**授权门槛：** 用户必须在 Task 1–8 全部门禁通过后，再次明确批准真实外部模型调用。此前对“执行计划”的批准不自动覆盖本 Task。

- [ ] **Step 1：确认运行条件**

- API key 仅存在本地环境变量；
- 不打印密钥；
- 使用默认产品 analyze 路径和 `confirm_llm=true`；
- 不调用 `assess_explicit_candidates()` 强制绕过；
- 不覆盖历史 report/run/suggestion。

- [ ] **Step 2：执行新 run 并生成只读观测结果**

预期对比：

| 指标 | 实施前 | 实施后目标 |
|---|---:|---:|
| GRI 2-5 弱证据实际调用 | 4 | 0 |
| GRI 2-5 skip reason | 无 | `no_substantive_evidence` |
| 新增 false disclosed | 0 | 0 |
| wrong source page | 0 | 0 |
| 规则/人工/风险变化 | 0 | 0 |

成功标准是调用资格正确，不要求出现更高 confidence。若报告没有其他合格 AI 候选，真实调用总数为 0 仍可判定本次路由修复通过。

- [ ] **Step 3：保存脱敏对比并单独 commit**

运行产物放 `tmp/ai/`，不提交原始响应；文档只记录聚合指标和脱敏案例。

---

## 5. 终止条件

出现任一情况立即停止，不继续顺手修复：

1. 需要修改 Prompt、模型、温度、token 上限或 provider。
2. 需要新增数据库迁移、API 字段、AI status 或 export 字段。
3. 规则 verdict、风险、适用性、人工 snapshot、577 checklist 或导出发生变化。
4. `confirm_llm=false` 产生外部请求或 499 条逐项 suggestion。
5. skipped assessment 被标记为 `model_called=true`。
6. `assess_explicit_candidates()` 出现在 workflow、API、runner 或后台任务。
7. 需要 OCR/VLM 才能获得 GRI 2-5 正文。
8. Envision v3 出现新增 false disclosed、wrong source page、global fallback、audit error 或 warning。
9. 全量后端、前端或 build gate 失败且原因不能归入本计划文件。
10. 在未获得独立授权时即将产生真实 DeepSeek 请求。

---

## 6. 完成定义

只有同时满足以下条件，Task 1–8 才可标记完成：

- GRI 2-5 第 77 页弱证据在默认产品路径中实际调用为 0；
- `confirm_llm=true` 的零候选运行保存可解释 skipped 记录；
- `confirm_llm=false` 行为完全保持：零调用、run 级 skipped、无逐项 suggestion；
- 前端显示中文原因，不暴露内部 code；
- 只读观测工具可复现调用、跳过、失败、置信度和人工处置分布；
- `assess_explicit_candidates()` 没有进入产品默认路径；
- 后端全量、Ruff、前端 lint/test/typecheck/build 全部通过；
- Envision v3 保持 `577/499/78/0`，安全和 audit gates 全部为 0；
- README、DESIGN、DEVELOPMENT 和验收报告与实际行为一致；
- 形成 3 个分批 commit，未 push；
- 真实 DeepSeek 对比若未独立批准，明确标记“未执行”，不能影响 Task 1–8 完成判断。

## 7. 宏观下一步

本计划完成后，项目进入“证据召回能力是否需要扩展”的决策点。应依据真实报告中 `image_body_not_extracted/scanned/complex_table` 的页级统计，判断是否启动 OCR/VLM 独立阶段；没有数据证明召回缺口前，不扩展 ParserBackend、大模型或后台队列架构。
