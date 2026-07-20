# 前端 AI 辅助复核与 MVP 最终验收实施计划

> **For agentic workers（执行要求）：** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` 按任务顺序实施；使用 checkbox 跟踪步骤。保持 `main` inline 执行，不创建分支或 worktree，不自动 push。

**Goal（目标）：** 在现有已冻结后端上完成 AI 显式授权、八阶段进度、规则/AI/人工三层复核、AI 建议采纳/修改/拒绝、完整核查表定位和最终浏览器产品验收。

**Architecture（架构）：** 前端继续以 OpenAPI 生成类型和现有 API 为唯一数据源。AI 建议保持只读，人工操作写入追加式 `review_snapshots`；不修改 `assessments`、`ai_assessment_suggestions`、risk-v2.1 规则和数据库结构。真实外部模型只在用户再次明确批准后，通过 metadata 页面勾选启用。

**Tech Stack（技术栈）：** Next.js App Router、React 19、TypeScript、TanStack Query、Vitest、Testing Library、FastAPI OpenAPI、PostgreSQL、普通 Chrome。

**执行状态：** Task 0-7 与 Task 8 Step 1-9 已完成；等待最终文档 checkpoint 提交和计划关闭记录。

---

## 一、已确认设计

### 1. 方案选择

采用“薄前端 + 现有人工快照 API”方案：

1. metadata 页面提供默认关闭的“启用 AI 辅助分析”选项；
2. `analyzeReport(reportId, confirmLlm)` 继续发送现有 `confirm_llm` 字段；
3. 进度页展示后端已经存在的 `ai_assistance` 第八阶段；
4. assessment 详情依次展示规则分析、AI 辅助建议、人工复核结果；
5. AI 建议的采纳、修改和拒绝均调用现有 `POST /api/assessments/{assessment_id}/review-decisions`；
6. `reason_code` 分别使用 `ai_suggestion_accepted`、`ai_suggestion_modified`、`ai_suggestion_rejected`；
7. `reviewer_note` 写入 AI `suggestion_id`，形成最低限度的可追溯关联；
8. 完整核查表通过 query string 定位到同一报告的三栏工作台。

暂不新增 AI disposition 表或专用采纳 API。该方案保持数据库 head 为 `0011_ai_suggestions`，不会重新打开后端规则设计。

### 2. 权威层级

```text
规则 assessment（只读确定性基线）
  ↓
AI suggestion（只读辅助意见，可失败或被 guardrail 拦截）
  ↓
人工 review snapshot（唯一可改变 effective result 的层）
```

界面必须遵守：

- AI 建议不能显示为“最终结论”“合规结论”或“人工已确认”；
- AI 建议缺失、失败或跳过时，规则结果仍可查看和复核；
- 点击“采纳 AI 建议”属于人工操作，必须保存复核人、时间、原因码、suggestion id 和完整结果字段；
- 点击“拒绝 AI 建议”必须保存规则结论及其依据，不能删除 AI suggestion；
- 高优先级复核完成不能表述为 577 个标准核查单元均已人工确认；
- 普通界面不显示 raw response、input hash、token usage 或内部异常堆栈。

### 3. 明确不进入本计划的事项

- 不修改 risk-v2.1、GRI 结构清单、证据规则或 Prompt；
- 不新增 Alembic migration；
- 不删除旧 `review_decisions`、旧 API 或旧前端兼容页面；
- 不启用 OCR 或 VLM；
- 不实现通用 verdict 批量复核、独立 reopen、report 级审计、单 export 下载或完整 `actions_xlsx`；
- 不引入聊天入口、AI 对话框或自动改写正式输出；
- 不使用 Codex 内置浏览器。

## 二、文件职责

| 文件 | 操作 | 单一职责 |
| --- | --- | --- |
| `frontend/lib/types.ts` | 修改 | 暴露 OpenAPI 生成的 AI 类型 |
| `frontend/lib/ai-presentation.ts` | 新增 | AI 状态、guardrail、置信度和可用性展示映射 |
| `frontend/lib/ai-presentation.test.ts` | 新增 | AI 展示模型单元测试 |
| `frontend/components/reports/report-metadata-confirmation.tsx` | 修改 | AI 显式授权并启动分析 |
| `frontend/components/reports/report-metadata-confirmation.test.tsx` | 修改 | 默认关闭和明确启用请求测试 |
| `frontend/components/analysis/progress-model.ts` | 修改 | 八阶段和非线性权重计算 |
| `frontend/components/analysis/progress-model.test.ts` | 修改 | AI completed/skipped/failed 进度测试 |
| `frontend/components/analysis/analysis-progress.tsx` | 修改 | 第八阶段和 AI 汇总展示 |
| `frontend/components/analysis/analysis-progress.test.tsx` | 修改 | 终态、失败降级和无转圈回归 |
| `frontend/components/review/ai-suggestion-panel.tsx` | 新增 | AI 建议只读展示和操作入口 |
| `frontend/components/review/ai-suggestion-panel.test.tsx` | 新增 | AI 成功/失败/跳过/guardrail/证据跳转测试 |
| `frontend/components/review/review-draft.ts` | 新增 | 人工修改草稿与 review payload 的纯函数 |
| `frontend/components/review/review-draft.test.ts` | 新增 | 采纳/修改/拒绝 payload 与页码校验 |
| `frontend/components/review/review-editor.tsx` | 修改 | 结构化人工复核表单和 AI 操作落库 |
| `frontend/components/review/review-editor.test.tsx` | 修改 | 三类 AI 操作、并发冲突和人工修改测试 |
| `frontend/components/review/assessment-detail.tsx` | 修改 | 规则、AI、人工三层布局 |
| `frontend/components/review/assessment-detail.test.tsx` | 修改 | 三层语义与切换重置测试 |
| `frontend/components/review/review-workspace.tsx` | 修改 | 初始 assessment 定位和 AI 证据页联动 |
| `frontend/components/review/review-workspace.test.tsx` | 修改 | 三栏加载、定位和 PDF 页跳转测试 |
| `frontend/components/review/reviewer-gate.tsx` | 修改 | 透传初始 assessment id |
| `frontend/components/analysis/assessment-table.tsx` | 修改 | 从完整核查表进入指定复核项 |
| `frontend/components/analysis/assessment-table.test.tsx` | 修改 | 493 条口径和定位链接测试 |
| `frontend/app/reports/[reportId]/review/page.tsx` | 修改 | 读取 `assessmentId` query string |
| `docs/DESIGN.md` | 修改 | 标记前端 AI 三层交互已完成 |
| `docs/DEVELOPMENT.md` | 修改 | 更新自动与人工验收路径 |
| `docs/product/page-architecture.md` | 修改 | 八阶段、493 独立结果和三层复核规格 |
| `docs/product/mvp-acceptance-report.md` | 新增 | 最终验收事实、截图索引、限制和交付结论 |

## 三、停止条件和外部调用边界

仅在以下情况暂停并报告：

1. 当前分支不是 `main`，或出现与本计划无关的未提交改动且无法隔离；
2. main/demo 数据库 head 不是 `0011_ai_suggestions`；
3. OpenAPI 不再包含 `AIAssessmentSuggestion`、`AISummaryResponse`、`latest_ai_suggestion` 或 `confirm_llm`；
4. 前端无法通过现有 review snapshot API表达采纳、修改或拒绝，需要新增数据库字段；
5. 发现 P0/P1 后端契约错误，需要修改已冻结后端；
6. 即将启动新的真实 DeepSeek 产品分析；执行者必须报告发送字段、`LLM_MAX_CALLS_PER_RUN`、预计影响和当前模型配置，获得用户明确批准；
7. 外部模型返回敏感信息、持续 schema 失败或连续三次网络失败；
8. 浏览器验收必须由人工完成验证码、登录或其他不可自动化交互。

自动测试、typecheck、build、Envision/Goldwind gate 和读取已有 AI suggestion 不触发外部调用，可连续执行。

## 四、Task 0：冻结执行基线

**Files:**
- Read: `README.md`
- Read: `docs/DESIGN.md`
- Read: `docs/DEVELOPMENT.md`
- Read: `docs/product/api-contract.md`
- Read: `frontend/lib/generated/api-types.ts`

- [x] **Step 1：确认 Git 边界**

```powershell
git branch --show-current
git status --short --branch
git log -3 --oneline
```

期望：分支为 `main`；工作区只允许本计划文件；禁止 reset、clean、checkout 和 push。

- [x] **Step 2：确认两个数据库 head**

```powershell
cd backend
uv run --no-sync alembic current
$env:DATABASE_URL="postgresql+psycopg://esg_agent:esg_agent@localhost:5432/esg_agent_demo"
uv run --no-sync alembic current
```

期望：两次均为 `0011_ai_suggestions (head)`。不得执行 downgrade、reset 或清库。

- [x] **Step 3：确认前端依赖的 OpenAPI 类型**

```powershell
cd ../frontend
rg -n "AIAssessmentSuggestion|AISummaryResponse|latest_ai_suggestion|confirm_llm" lib/generated/api-types.ts
```

期望：四类字段均存在。本计划不手写后端 DTO。

- [x] **Step 4：运行前端和后端相关基线**

```powershell
pnpm test -- --run
pnpm typecheck

cd ../backend
uv run --no-sync pytest tests/api/test_openapi_contract.py tests/api/test_reports_api.py tests/api/test_runs_api.py tests/api/test_assessments_api.py tests/api/test_review_api.py -q
```

期望：前端至少19个测试文件、51项测试；后端相关测试全部通过。该步骤不得调用 DeepSeek。

2026-07-20执行结果：保持 `main`，工作区仅有本计划文件；main/demo 均为 `0011_ai_suggestions`；OpenAPI AI字段完整；前端19个测试文件、51项测试和typecheck通过，后端相关API 42项测试通过，全程未调用外部模型。

## 五、Task 1：建立 AI 前端展示模型

**Files:**
- Modify: `frontend/lib/types.ts`
- Create: `frontend/lib/ai-presentation.ts`
- Create: `frontend/lib/ai-presentation.test.ts`

- [x] **Step 1：写失败测试**

```ts
import { describe, expect, it } from "vitest";
import { aiGuardrailLabel, aiStatusLabel, formatAIConfidence, isUsableAISuggestion } from "./ai-presentation";

describe("AI presentation", () => {
  it("uses advisory Chinese labels", () => {
    expect(aiStatusLabel("succeeded")).toBe("AI 建议已生成");
    expect(aiStatusLabel("failed")).toBe("AI 辅助未完成");
    expect(aiStatusLabel("skipped")).toBe("AI 辅助已跳过");
    expect(aiGuardrailLabel("verdict_upgrade_requires_human_review")).toContain("不能直接升级");
    expect(formatAIConfidence(0.723)).toBe("72%");
  });
});
```

- [x] **Step 2：运行测试并确认失败**

```powershell
cd frontend
pnpm test -- --run lib/ai-presentation.test.ts
```

期望：FAIL，原因是模块或函数尚不存在。

- [x] **Step 3：暴露类型并实现纯展示函数**

`frontend/lib/types.ts` 增加：

```ts
export type AIAssessmentSuggestion = components["schemas"]["AIAssessmentSuggestion"];
export type AISummaryResponse = components["schemas"]["AISummaryResponse"];
```

`frontend/lib/ai-presentation.ts` 只处理安全展示：

```ts
import type { AIAssessmentSuggestion } from "./types";

const guardrailLabels: Record<string, string> = {
  verdict_upgrade_requires_human_review: "AI 建议不能直接升级规则结论，需要人工判断。",
  evidence_reference_out_of_scope: "AI 引用了输入范围外的证据，建议已被拦截。",
  evidence_page_mismatch: "AI 证据页与输入证据不一致，需要人工判断。",
};

export function isUsableAISuggestion(value: AIAssessmentSuggestion | null | undefined) {
  return value?.status === "succeeded" && Boolean(value.suggested_verdict);
}
```

未知 guardrail 统一显示“AI 建议触发安全校验，需要人工判断”，不得回显内部代码作为主要文案。

- [x] **Step 4：运行测试**

```powershell
pnpm test -- --run lib/ai-presentation.test.ts
pnpm typecheck
```

期望：PASS。

- [x] **Step 5：提交**

```powershell
git add frontend/lib/types.ts frontend/lib/ai-presentation.ts frontend/lib/ai-presentation.test.ts
git commit -m "feat: add AI presentation model"
```

## 六、Task 2：metadata 页面显式启用 AI

**Files:**
- Modify: `frontend/components/reports/report-metadata-confirmation.tsx`
- Modify: `frontend/components/reports/report-metadata-confirmation.test.tsx`

- [x] **Step 1：增加默认关闭和明确启用测试**

测试必须断言：

```ts
expect(screen.getByRole("checkbox", { name: "启用 AI 辅助分析" })).not.toBeChecked();
fireEvent.click(screen.getByRole("button", { name: "启动分析" }));
expect(JSON.parse(String(fetchMock.mock.calls[2][1]?.body))).toMatchObject({ confirm_llm: false });
```

另一用例勾选后断言 `confirm_llm: true`。测试只 mock `fetch`，禁止真实请求。

- [x] **Step 2：运行测试并确认失败**

```powershell
pnpm test -- --run components/reports/report-metadata-confirmation.test.tsx
```

期望：FAIL，页面尚无 checkbox。

- [x] **Step 3：实现授权控件**

新增本地状态：

```ts
const [aiAssistanceEnabled, setAIAssistanceEnabled] = useState(false);
```

调用改为：

```ts
mutationFn: () => analyzeReport(reportId, aiAssistanceEnabled)
```

显示文案固定为：

```text
启用 AI 辅助分析
仅发送当前 requirement、有限证据片段、证据 ID、PDF 页码和必要报告信息。AI 建议不会覆盖规则结论或人工复核结果。
```

checkbox 默认关闭；报告已有结果或正在分析时不显示新的启动控件。

- [x] **Step 4：补充启动错误状态**

`analyzeMutation.isError` 时显示“分析启动失败，请检查服务配置后重试。”，不得显示 API Key、原始响应或堆栈。

- [x] **Step 5：运行测试和 typecheck**

```powershell
pnpm test -- --run components/reports/report-metadata-confirmation.test.tsx lib/api.test.ts
pnpm typecheck
```

期望：PASS；默认路径继续发送 `confirm_llm=false`。

- [x] **Step 6：提交**

```powershell
git add frontend/components/reports/report-metadata-confirmation.tsx frontend/components/reports/report-metadata-confirmation.test.tsx
git commit -m "feat: add explicit AI analysis consent"
```

## 七、Task 3：展示八阶段进度和 AI 汇总

**Files:**
- Modify: `frontend/components/analysis/progress-model.ts`
- Modify: `frontend/components/analysis/progress-model.test.ts`
- Modify: `frontend/components/analysis/analysis-progress.tsx`
- Modify: `frontend/components/analysis/analysis-progress.test.tsx`

- [x] **Step 1：写八阶段失败测试**

增加断言：

```ts
expect(analysisStages.map(([code]) => code)).toEqual([
  "file_validation", "pdf_parsing", "report_structure", "requirement_matching",
  "evidence_assessment", "risk_classification", "ai_assistance", "result_summary",
]);
expect(calculateAnalysisProgress("running", [
  completed("file_validation"), completed("pdf_parsing"), completed("report_structure"),
  completed("requirement_matching"), completed("evidence_assessment"), completed("risk_classification"),
  { ...completed("ai_assistance"), status: "skipped" },
]).percent).toBe(95);
```

- [x] **Step 2：运行测试并确认失败**

```powershell
pnpm test -- --run components/analysis/progress-model.test.ts components/analysis/analysis-progress.test.tsx
```

期望：FAIL，原因是缺少 `ai_assistance` 或 `skipped` 未计入。

- [x] **Step 3：调整阶段和权重**

使用总和100的权重：

```ts
export const analysisStageWeights = {
  file_validation: 5,
  pdf_parsing: 10,
  report_structure: 5,
  requirement_matching: 10,
  evidence_assessment: 55,
  risk_classification: 5,
  ai_assistance: 5,
  result_summary: 5,
} as const;
```

`completed`、`partially_failed` 和 `skipped` 均计入该阶段完整权重。`ai_assistance=skipped` 显示“未启用或无需调用”。

- [x] **Step 4：展示终态 AI 汇总**

当 `run.confirm_llm=true` 时显示：

```text
AI 辅助建议：成功 {succeeded} 条，失败 {failed} 条，跳过 {skipped} 条
```

当 `confirm_llm=false` 时显示“本次分析未启用 AI 辅助”。AI 失败不能覆盖“规则分析已完成”的终态。

- [x] **Step 5：验证完成后无转圈**

测试必须断言 terminal run 强制100%、所有 stage 图标不再使用 `animate-spin`，并保留“查看分析结果”和“进入高优先级复核”。

- [x] **Step 6：运行测试并提交**

```powershell
pnpm test -- --run components/analysis/progress-model.test.ts components/analysis/analysis-progress.test.tsx
pnpm typecheck
git add frontend/components/analysis
git commit -m "feat: show AI-assisted analysis stage"
```

## 八、Task 4：建立 AI 建议只读面板

**Files:**
- Create: `frontend/components/review/ai-suggestion-panel.tsx`
- Create: `frontend/components/review/ai-suggestion-panel.test.tsx`

- [x] **Step 1：写四类状态测试**

覆盖：

1. `latest_ai_suggestion=null`：显示“该核查项暂无 AI 建议”；
2. `succeeded`：显示建议结论、中文依据、缺失项、置信度、模型和证据页；
3. `failed`：显示“AI 辅助未完成，规则结果仍有效”；
4. guardrail 触发：显示本地化安全提示，不把被拦截结果显示为最终结论。

证据按钮测试：

```ts
fireEvent.click(screen.getByRole("button", { name: "查看 AI 证据 PDF 第 41 页" }));
expect(onEvidencePage).toHaveBeenCalledWith(41);
```

- [x] **Step 2：运行测试并确认失败**

```powershell
pnpm test -- --run components/review/ai-suggestion-panel.test.tsx
```

- [x] **Step 3：实现面板接口**

```ts
type Props = {
  suggestion: AIAssessmentSuggestion | null | undefined;
  onEvidencePage: (page: number) => void;
  onAccept: () => void;
  onEdit: () => void;
  onReject: () => void;
  busy: boolean;
};
```

仅 `status=succeeded` 且存在 guardrail 后 `suggested_verdict` 时显示三项操作：

- “采纳 AI 建议”；
- “载入 AI 建议并修改”；
- “拒绝 AI 建议并保留规则结论”。

面板底部固定显示：“AI 建议仅供人工复核参考，不构成最终 GRI 合规结论。”

- [x] **Step 4：隐藏内部字段**

普通面板不得渲染 `raw_response`、`input_hash`、`usage`、完整 `error_message`。只允许显示 provider/model、Prompt 版本、重试次数和本地化状态。

- [x] **Step 5：运行测试并提交**

```powershell
pnpm test -- --run components/review/ai-suggestion-panel.test.tsx
pnpm typecheck
git add frontend/components/review/ai-suggestion-panel.tsx frontend/components/review/ai-suggestion-panel.test.tsx
git commit -m "feat: add advisory AI suggestion panel"
```

## 九、Task 5：实现可审计的采纳、修改和拒绝

**Files:**
- Create: `frontend/components/review/review-draft.ts`
- Create: `frontend/components/review/review-draft.test.ts`
- Modify: `frontend/components/review/review-editor.tsx`
- Modify: `frontend/components/review/review-editor.test.tsx`

- [x] **Step 1：写 payload 纯函数失败测试**

采纳 AI 必须产生：

```ts
expect(buildAcceptAIPayload(detail, suggestion, "张三")).toMatchObject({
  operation_type: "modify",
  reviewer_name: "张三",
  reason_code: "ai_suggestion_accepted",
  reviewed_verdict: suggestion.suggested_verdict,
  rationale: suggestion.rationale_zh,
  missing_items: suggestion.missing_items_zh,
  evidence_pages: suggestion.evidence_pdf_pages,
  expected_previous_snapshot_id: detail.latest_snapshot_id,
});
```

拒绝 AI 必须恢复规则层字段：`system_verdict`、原始 `rationale`、`missing_items` 和规则 evidence pages；原因码为 `ai_suggestion_rejected`。

- [x] **Step 2：实现 review draft 纯函数**

导出：

```ts
export function draftFromDetail(detail: AssessmentDetailResponse): ReviewDraft;
export function draftFromAISuggestion(detail: AssessmentDetailResponse, suggestion: AIAssessmentSuggestion): ReviewDraft;
export function buildManualModifyPayload(detail: AssessmentDetailResponse, draft: ReviewDraft, reviewerName: string): ReviewSnapshotRequest;
export function buildAcceptAIPayload(detail: AssessmentDetailResponse, suggestion: AIAssessmentSuggestion, reviewerName: string): ReviewSnapshotRequest;
export function buildRejectAIPayload(detail: AssessmentDetailResponse, suggestion: AIAssessmentSuggestion, reviewerName: string): ReviewSnapshotRequest;
```

页码输入只接受逗号分隔的正整数，去重并升序；无效输入返回中文错误，不发送请求。

- [x] **Step 3：运行纯函数测试**

```powershell
pnpm test -- --run components/review/review-draft.test.ts
```

期望：PASS。

- [x] **Step 4：改造人工编辑器**

`ReviewEditor` 改为接收完整 `detail` 和 `onEvidencePage`，显示：

- 人工结论 select；
- 人工判断依据 textarea；
- 缺失项 textarea，每行一项；
- PDF 证据页 input；
- 复核备注 textarea；
- 快速通过规则结论；
- 保存人工修改；
- AI 采纳/载入修改/拒绝操作。

所有写请求必须发送 `expected_previous_snapshot_id=detail.latest_snapshot_id`。409 显示“该核查项已被其他复核操作更新，请刷新后重试。”；422 显示“复核内容不完整，请检查备注和修改字段。”。

- [x] **Step 5：定义 AI 操作行为**

- 采纳：立即提交 guardrail 后 AI 字段，备注包含 `suggestion_id`；
- 修改：把 AI 字段载入人工表单，不立即保存，按钮文案变为“保存人工修改”；
- 拒绝：提交规则层字段，备注包含 `suggestion_id`；
- 保存成功：刷新 detail、两个队列、完整核查表和 dashboard；
- 切换 requirement：依靠 assessment key 清空未保存草稿，不复用上一条内容。

- [x] **Step 6：运行组件测试**

```powershell
pnpm test -- --run components/review/review-draft.test.ts components/review/review-editor.test.tsx
pnpm typecheck
```

测试必须逐项检查三种 reason code、suggestion id、字段值、409 文案、无效页码不发请求。

- [x] **Step 7：提交**

```powershell
git add frontend/components/review/review-draft.ts frontend/components/review/review-draft.test.ts frontend/components/review/review-editor.tsx frontend/components/review/review-editor.test.tsx
git commit -m "feat: record human decisions on AI suggestions"
```

执行记录（2026-07-20）：新增 review draft 纯函数及 6 项测试，完成 AI 建议采纳、载入后人工修改、拒绝并保留规则结论三类可审计快照；人工修改支持结论、依据、缺失项和 PDF 页码，所有写入携带最新 snapshot id，并补充 409/422 中文提示。编辑器相关 15 项测试与 typecheck 通过。为保持调用链可编译，同步完成 `AssessmentDetail` 的新参数接线。

## 十、Task 6：整合三层详情和 PDF 联动

**Files:**
- Modify: `frontend/components/review/assessment-detail.tsx`
- Modify: `frontend/components/review/assessment-detail.test.tsx`
- Modify: `frontend/components/review/review-workspace.tsx`
- Modify: `frontend/components/review/review-workspace.test.tsx`

- [x] **Step 1：写三层语义失败测试**

一个带成功 AI suggestion 且已有人工 snapshot 的 fixture 必须显示三个明确标题：

```text
规则分析
AI 辅助建议
人工复核
```

同时断言：规则结论、AI建议结论、当前人工结论各自独立显示，页面不出现“AI最终结论”。

- [x] **Step 2：实现三层布局**

规则层显示 `system_verdict`、`rationale_display`、`missing_items_display` 和规则证据；AI 层交给 `AISuggestionPanel`；人工层交给 `ReviewEditor`。`effective_verdict` 只能标为“当前有效结论”，并附当前复核状态。

- [x] **Step 3：连接 AI 证据页**

AI 面板点击 PDF 页时调用现有 `setSelectedPdfPage`。右栏 iframe 的 `#page=` 必须更新，禁止触发文件下载或打开新窗口。

- [x] **Step 4：验证状态切换**

依次切换两个 assessment，断言：

- 前一条人工草稿不残留；
- PDF 页重置为新条目的首个规则证据页；
- AI 证据按钮仍可覆盖当前 PDF 页；
- detail loading/error 时右栏不显示上一条 PDF。

- [x] **Step 5：运行测试并提交**

```powershell
pnpm test -- --run components/review/assessment-detail.test.tsx components/review/review-workspace.test.tsx components/evidence/pdf-evidence-viewer.test.tsx
pnpm typecheck
git add frontend/components/review/assessment-detail.tsx frontend/components/review/assessment-detail.test.tsx frontend/components/review/review-workspace.tsx frontend/components/review/review-workspace.test.tsx
git commit -m "feat: integrate rule AI and human review layers"
```

执行记录（2026-07-20）：详情区明确拆分为“规则分析”“AI 辅助建议”“人工复核”三层，当前有效结论和复核状态仅归入人工层；规则与 AI 证据均通过现有 iframe 切页。新增双 assessment 切换、草稿清空、PDF 重置、AI 页覆盖及 loading/error 不残留旧 PDF 的测试。人工编辑草稿改用中文展示字段，AI 拒绝仍保留规则原始字段。相关 22 项测试和 typecheck 通过。

## 十一、Task 7：从完整核查表定位任意复核项

**Files:**
- Modify: `frontend/components/analysis/assessment-table.tsx`
- Modify: `frontend/components/analysis/assessment-table.test.tsx`
- Modify: `frontend/app/reports/[reportId]/review/page.tsx`
- Modify: `frontend/components/review/reviewer-gate.tsx`
- Modify: `frontend/components/review/review-workspace.tsx`
- Modify: `frontend/components/review/review-workspace.test.tsx`

- [x] **Step 1：修正列表验收口径**

测试 fixture 的 `total` 改为493，分页末页为451–493。页面标题附近增加说明：

```text
共 493 个独立判断项；另有 78 个父级上下文项和 6 个方法待确认项，不生成独立披露结论。
```

不得重新显示“577 条结果”。

- [x] **Step 2：增加定位链接测试**

```ts
expect(screen.getByRole("link", { name: "GRI 2-1-a" })).toHaveAttribute(
  "href",
  "/reports/report-1/review?assessmentId=a-1",
);
```

- [x] **Step 3：透传 query string**

`review/page.tsx` 读取 `searchParams.assessmentId`，经过 `ReviewerGate` 传入 `ReviewWorkspace`。进入工作台并确认复核人后，直接查询该 assessment detail；左栏仍保留高优先级和适用性队列。

- [x] **Step 4：运行测试并提交**

```powershell
pnpm test -- --run components/analysis/assessment-table.test.tsx components/review/review-workspace.test.tsx
pnpm typecheck
git add frontend/components/analysis/assessment-table.tsx frontend/components/analysis/assessment-table.test.tsx frontend/app/reports/[reportId]/review/page.tsx frontend/components/review/reviewer-gate.tsx frontend/components/review/review-workspace.tsx frontend/components/review/review-workspace.test.tsx
git commit -m "feat: link complete assessments to review workspace"
```

执行记录（2026-07-20）：完整核查表改为展示 API 返回的独立 assessment 总数，并明确 493/78/6 的结构范围；requirement id 变为带 `assessmentId` 的复核工作台链接。review page、复核人门禁和工作台已透传直接定位参数，确认复核人后自动加载目标详情并定位首个规则证据页。相关 6 项测试和 typecheck 通过；后端列表实现确认返回当前运行的独立 assessment，不混入上下文项和方法待确认项。

## 十二、Task 8：自动门禁、真实浏览器验收和最终交付

**Files:**
- Modify: `README.md`
- Modify: `docs/DESIGN.md`
- Modify: `docs/DEVELOPMENT.md`
- Modify: `docs/product/page-architecture.md`
- Create: `docs/product/mvp-acceptance-report.md`
- Output local-only: `backend/data/runtime/acceptance/frontend-ai/`
- Modify: `backend/data/manifests/assets_manifest.json` only when local acceptance artifacts are generated

- [x] **Step 1：运行前端全量门禁**

```powershell
cd frontend
pnpm test -- --run
pnpm typecheck
pnpm build
```

期望：测试数量高于51，typecheck 和 production build 成功。

- [x] **Step 2：运行后端冻结回归**

```powershell
cd ../backend
uv run --no-sync pytest -q --basetemp=../tmp/pytest-frontend-ai-final
```

期望：不少于626项通过。任何后端失败先判断是否为前端无关环境问题，不修改规则来迁就测试。

- [x] **Step 3：重跑 Envision 和 Goldwind gate**

按 `docs/DEVELOPMENT.md` 的当前命令重生成两个 gate。必须保持：

```text
Envision: 577/493/78/6, global_fallback=0, new_false_disclosed=0, new_wrong_source_page=0
Goldwind: false_disclosed=0, wrong_source_page=0, global_fallback=0
```

该步骤保持 `confirm_llm=false`，禁止 OCR/VLM 和真实外部模型。

- [x] **Step 4：启动隔离 demo 环境**

```powershell
docker compose up -d postgres

cd backend
$env:APP_ENV="demo"
$env:DATABASE_URL="postgresql+psycopg://esg_agent:esg_agent@localhost:5432/esg_agent_demo"
$env:UPLOAD_DIR="data/runtime/demo/uploads"
$env:DERIVED_DIR="data/runtime/demo/derived"
uv run --no-sync alembic upgrade head
uv run --no-sync uvicorn src.main:app --port 8000

cd ../frontend
pnpm dev
```

确认 `/api/runs/run-526bd97aef5d4b9baa14618b719081c9` 和固定报告 `report-14864b1a3ef64512b0e5d3676a120bc1` 可读。该历史 run 含真实评估 suggestion，但 `confirm_llm=false`；它只用于三层只读展示，不作为“页面授权已触发模型”的证据。

执行记录（2026-07-20）：前端 22 个测试文件、80 项测试、typecheck、production build 通过；后端 626 项测试通过。Envision gate 为 577/493/78/6、493 个唯一独立判断项、`global_fallback=0`、新增 false disclosed 0、新增 wrong source page 0；Goldwind 为 577 个唯一 requirement、recall 96.08%、false disclosed 0、wrong source page 0、unknown leakage 2、`global_fallback=0`。demo 后端显式连接 `esg_agent_demo`，固定报告和历史 run 可读；前端为 `http://localhost:3000`，后端为 `http://localhost:8000`。

- [x] **Step 5：执行真实新分析授权停止点**

在任何新的 `confirm_llm=true` 请求前报告：

```text
模型：当前 LLM_MODEL 配置
发送字段：requirement 文本、父级上下文、有限证据片段、证据ID、PDF页码、必要报告 metadata
禁止发送：整份PDF、API Key、数据库连接、人工姓名、审计备注
单 run 调用硬上限：LLM_MAX_CALLS_PER_RUN=200
并发上限：当前 LLM_MAX_CONCURRENCY 配置
OCR/VLM：关闭
```

获得用户明确批准后，才在普通 Chrome 勾选“启用 AI 辅助分析”并启动一次新的远景 v2 产品 run。未获批准时跳过真实新 run，继续使用已有 suggestion 完成只读 UI 验收，并在最终报告中标为“授权到真实产品 run 尚未执行”。

执行记录（2026-07-20）：用户明确批准真实调用。demo 环境使用 `deepseek-v4-flash`、Prompt `deepseek-gri-assist-v1.2`、并发 8、单 run 上限 200、OCR/VLM 关闭；metadata 页面勾选后启动 `run-021eeb43338f4381910218628b64554b`。本次产品 eligibility 为4条，成功4、失败0、跳过489；225条属于固定人工基线评估集，不作为每次新产品run的调用数量。

- [x] **Step 6：使用普通 Chrome 完成主流程**

禁止使用 Codex 内置浏览器。依次验收：

1. 上传同一份远景报告；
2. 重复提示中分别确认“查看已有报告”和“重新上传并分析”路径；
3. metadata 企业、年度、语言可人工修正；
4. AI checkbox 默认关闭，勾选后提示边界清晰；
5. 八阶段顺序正确，AI skipped/completed/partially_failed 文案正确；
6. 终态不转圈，显示“查看分析结果”；
7. 完整核查表显示493个独立判断项和577/493/78/6解释；
8. 从表格点击 requirement 进入指定三栏详情；
9. 规则、AI、人工三层不混淆；
10. AI 证据页在右栏 PDF 定位，不触发下载；
11. 选取第一条规则/AI一致的成功建议执行“采纳”；
12. 选取第一条规则/AI不一致的成功建议执行“载入并修改”；
13. 选取下一条规则/AI不一致的成功建议执行“拒绝”；
14. API 历史中分别出现三个 reason code，AI suggestion 行数和内容未被覆盖；
15. 草稿输出包含 AI 辅助免责声明；
16. 高优先级完成文案没有暗示577条均已人工确认。

操作的 requirement id、suggestion id、snapshot id 和截图路径写入验收报告。

执行记录（2026-07-20）：普通 Chrome 完成重复上传双路径、metadata/AI授权、八阶段终态、493项核查表、直接定位、三层详情、右栏PDF、采纳/修改/拒绝、草稿输出和高优先级范围文案验收。三类人工决策分别使用 `GRI 201-1-b`、`GRI 203-1-c`、`GRI 203-2-b`，完整ID见最终验收报告。

- [x] **Step 7：记录问题分级**

验收报告使用统一格式：

```markdown
| 编号 | 严重程度 | 页面/接口 | 前置条件 | 复现步骤 | 实际结果 | 期望结果 | 影响范围 | 建议修复 | 状态 |
```

- P0：数据破坏、密钥泄露、AI覆盖规则/人工结果；立即停止；
- P1：主流程阻塞、错误报告完成、证据页下载或无法显示；修复后重跑相关与全量门禁；
- P2：不阻塞的错误文案、布局或辅助状态；本计划内小修；
- P3：增强项；记录，不扩展本轮范围。

执行记录（2026-07-20）：发现1个P1——采纳AI后规则区误用人工snapshot字段。增加不可变 `system_rationale` / `system_missing_items` API字段并修复前端显示与拒绝payload，提交 `4abdac9`；后端627项、前端80项和Envision新鲜回归通过。Chrome本地文件选择自动化限制作为环境问题记录，不列为产品缺陷。

- [x] **Step 8：保存验收证据**

截图和运行摘要保存到：

```text
backend/data/runtime/acceptance/frontend-ai/
```

把路径、SHA256、大小、用途、日期登记到 `backend/data/manifests/assets_manifest.json`；不提交截图二进制，不写本机绝对路径，不保存 API Key 或完整模型 raw response。

执行记录（2026-07-20）：11张截图和 `acceptance-summary.json` 已保存到约定runtime目录并逐项登记manifest；未保存API Key、完整模型raw response或本机绝对路径，截图二进制保持git ignored。

- [x] **Step 9：更新最终文档**

`docs/product/mvp-acceptance-report.md` 必须包含：

- Git commit、数据库 head、运行环境；
- 自动测试、Envision、Goldwind 结果；
- 是否执行新的真实 AI 产品 run及调用数量；
- 规则/AI/人工三层验收样例；
- 真实问题及处理状态；
- 已验证能力、人工操作边界、已知限制；
- “AI 输出仅供辅助，不构成最终 GRI 合规结论”；
- 未实现规划接口和 `actions_xlsx` 限制；
- 最终 MVP 是否通过验收及理由。

同步 `README.md`、`docs/DESIGN.md`、`docs/DEVELOPMENT.md` 和 `docs/product/page-architecture.md` 的当前事实。

执行记录（2026-07-20）：新增 `docs/product/mvp-acceptance-report.md` 并同步 README、DESIGN、DEVELOPMENT、API契约和页面规格。用户将Goldwind优先级降低，最终验收以Envision为主；Goldwind历史100条结果继续保留但不作为本轮阻塞门禁。

- [ ] **Step 10：提交最终 checkpoint**

```powershell
git status --short
git diff --check
git add -- README.md frontend docs backend/data/manifests/assets_manifest.json
git diff --cached --check
git commit -m "feat: complete AI-assisted MVP product acceptance"
git status --short --branch
```

期望：保持 `main`；工作区干净或仅剩明确 ignored 的 runtime/tmp；不 push。

## 十三、完成判定

本计划只有同时满足以下条件才能标记完成：

- AI 开关默认关闭，开启行为有明确授权文案；
- `confirm_llm=false` 自动测试路径不创建外部客户端或请求；
- 八阶段进度包含 AI 辅助，skipped 和失败降级表达准确；
- 分析终态为100%，不再显示运行转圈；
- 规则、AI、人工三层独立展示；
- AI 成功、失败、跳过和 guardrail 状态均有中文业务文案；
- AI 证据页只在右栏 PDF 定位，不触发下载；
- 采纳、修改和拒绝均生成追加式人工 snapshot；
- 三类 snapshot 可追溯 reviewer、reason code、suggestion id、时间和字段变化；
- AI suggestion 不被更新或删除；
- 完整核查表显示493个独立判断项，并解释577/493/78/6；
- 高优先级完成文案不暗示577条全部人工确认；
- 前端全量测试、typecheck、build通过；
- 后端不少于626项测试通过；
- Envision gate 继续通过；Goldwind 仅保留已有历史 gate 证据，不阻塞本轮验收；
- 普通 Chrome 完成人工产品验收；
- 最终验收报告和本地证据清单完整；
- OCR/VLM未启用，旧API未删除，数据库未清空，未push。

## 十四、执行后的产品状态

完成后可以对外演示：

```text
上传远景2024中文ESG报告
→ 确认metadata并明确选择是否启用DeepSeek
→ 577个标准单元编译为493个独立判断项
→ 规则引擎生成确定性基线
→ AI仅对符合条件的条目生成辅助建议
→ 规则/AI/人工三层复核并定位PDF证据
→ 人工采纳、修改或拒绝AI建议
→ 生成整改任务和版本化输出
```

产品表述固定为：“AI 辅助 ESG 披露核查与人工复核工作流”。不得表述为自动认证、自动合规裁决或全部577条均已人工确认。
