# Phase 1.7 最终闭环与发布就绪实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: 使用 `executing-plans` 按任务顺序执行；实现功能或修复缺陷时使用 `test-driven-development`；宣布完成前使用 `verification-before-completion`。
>
> 用户已于 2026-07-29 批准按本计划开始实施。实施授权覆盖计划内代码、测试、文档和分批提交；不授权主数据库破坏性写入、外部模型调用、OCR/VLM 调用、打标签或推送。

**目标：** 在一次受控解冻中完成 Phase 1.7，使项目达到“本地部署、单报告、数字文本 PDF、GRI 577 项辅助复核产品闭环”的发布就绪状态，并以明确终止条件结束第一阶段主线开发。

**架构：** 保留规则判定、AI 辅助建议、人工复核快照三层优先级；通过运行谱系解析补齐部分失败与重试后的 577 项有效视图；补充报告级审计、扫描 PDF 能力边界、独立报告验证、正式输出后的纠正闭环和干净环境发布验证。不得为了 Phase 1.7 接入生产 OCR、RAG Phase 2、外部模型或企业级平台能力。

**技术栈：** FastAPI、SQLAlchemy、PostgreSQL、Alembic、pytest、React/Next.js、TypeScript、Vitest、Playwright/Chrome、OpenAPI。

**计划状态：** 已完成；等待用户批准集成、`v1.2` 标签和 push。

**建议发布基线：** `v1.2`。标签、提交和推送必须在全部 gates 通过后另行批准。

---

## 一、最终产品声明与严格边界

Phase 1.7 全部通过后，只允许声明：

> esg-agent 已形成可本地运行的单报告 ESG 披露分析闭环，支持数字文本型 PDF 的 GRI 577 项结构化核查、证据定位、规则结果、AI 辅助建议、人工复核快照、整改跟踪、草稿/正式输出、审计追踪和失败恢复。系统输出属于工程辅助分析，不构成 GRI 认证、法律意见、外部鉴证或最终合规结论。

### 1.1 结构口径

- 标准单元：577。
- 独立判断项：499。
- 上下文项：78。
- method pending：0。
- 规则结果仍是底层工程判断。
- AI 只允许生成追加式辅助建议。
- 人工快照形成最终有效复核结论。
- 上下文项不得伪造独立 assessment。

### 1.2 输入边界

- 正式支持：数字文本型 PDF。
- 有条件支持：数字文本与少量扫描页混合的 PDF；扫描页必须保留质量警告和人工复核标记。
- 明确拒绝：完全扫描且未显式启用 OCR 的 PDF；返回安全、稳定、可操作的错误。
- Phase 1.7 不把 OCRmyPDF、Tesseract、Docling、PaddleOCR、VLM 纳入正式产品依赖。
- `enable_ocr=true` 保持实验能力，不进入最终发布声明和强制验收 gate。

### 1.3 模型边界

- 所有自动验收统一使用 `confirm_llm=false`。
- 禁止外部 LLM、OCR、VLM 网络或进程调用。
- 不修改 Prompt、模型默认参数、候选筛选规则和 `ai_assessment_suggestions` 表结构。

### 1.4 明确排除项

以下事项不阻塞 Phase 1.7 结束，统一进入条件化路线图：

- 生产 OCR 与 Ghostscript 环境治理。
- RAG Phase 2、跨报告知识检索和向量召回优化。
- AI 运行观测平台、采纳率看板和模型一致性运营。
- 批量 verdict 复核。
- 报告列表高级搜索、排序和批量管理。
- 独立导出元数据查询接口。
- 企业级身份认证、多租户、权限矩阵。
- 生产队列、横向扩容、备份恢复和灾备。
- GRI 认证、ESG 专家 gold、法律或鉴证结论。

---

## 二、固定架构决策

实施期间不得临时改成其他大架构。触发变更时必须停下并重新评审计划。

### 2.1 部分失败采用“运行谱系有效视图”

选择运行谱系解析，不复制父 run 的 assessment、evidence、risk、AI suggestion 或 human snapshot。

核心规则：

1. 最新 run 代表当前产品运行。
2. 从最新 run 沿 `parent_run_id` 向上遍历。
3. 同一 requirement 优先使用谱系中最新的 assessment。
4. 找不到 assessment 且出现在失败摘要中的独立项标记为 `failed`。
5. 找不到 assessment 且没有明确失败记录的独立项标记为 `not_generated`。
6. 上下文项的 `analysis_status` 为 `null`。
7. 每个有效 assessment 返回 `source_run_id`，保证来源可审计。
8. 遍历必须包含循环检测和最大深度限制。
9. 有效视图只读，不改变历史 run 的不可变事实。

建议数据结构：

```python
@dataclass(frozen=True)
class EffectiveAssessment:
    assessment: DisclosureAssessment
    source_run_id: UUID


@dataclass(frozen=True)
class EffectiveRunView:
    latest_run: AnalysisRun
    assessments_by_requirement: Mapping[str, EffectiveAssessment]
    failed_requirement_ids: frozenset[str]
    not_generated_requirement_ids: frozenset[str]
```

### 2.2 失败状态与结构状态正交

577 项范围行保留结构状态：

- `assessed`
- `context_incorporated`

新增或统一有效分析状态：

- `succeeded`
- `failed`
- `not_generated`
- 上下文项为 `null`

失败行不得伪造 assessment、证据、页码、verdict 或人工结论。

建议响应字段：

```text
analysis_status
source_run_id
failure_code
failure_message
```

其中 `failure_message` 必须截断并脱敏，不得包含本机绝对路径、密钥、完整 stderr 或外部原始响应。

### 2.3 纠正闭环复用现有人工复核能力

- assessment 纠正继续使用现有 `operation_type=reopen`。
- 不新增重复的“报告 reopen”接口。
- 人工 reopen 后，报告进入 `reopened`。
- 新正式输出生成前，必须重新满足正式输出 gate。
- 新正式输出成功后，旧正式输出标记为 `superseded`，文件仍可审计和下载。
- `voided` 输出状态、独立报告 reopen 接口和独立导出元数据接口不纳入本阶段。

### 2.4 第二报告采用配置解析，不新增规则分支

移除 Envision 文件名硬编码，新增报告 profile 解析器：

1. 从 `backend/data/reports/profiles/*.json` 读取 profile。
2. 使用规范化后的 `pdf_file` 匹配上传文件名。
3. 校验报告身份、页数边界和匹配唯一性。
4. 未匹配时返回 `None`，继续通用解析。
5. 多个 profile 同时匹配时明确失败。
6. 不为 Goldwind 增加专用规则代码。

### 2.5 双报告 gate

- Envision：权威主线回归样本，继续验证 577/499/78/0、证据页码、global fallback 和既有回归指标。
- Goldwind：独立报告产品泛化与闭环样本，验证上传、分析、复核、整改、草稿和下载。
- Goldwind 不替代 Envision。
- Goldwind 工程结果不升级为 ESG 专业结论。
- 任一报告需要修改标准、规则或证据口径才能通过时，停止 Phase 1.7 实施并重新评审。

---

## 三、影响范围

### 3.1 预计新增文件

```text
backend/src/services/effective_run_view_service.py
backend/src/services/document_capability_service.py
backend/src/reports/profile_resolver.py
backend/tests/services/test_effective_run_view_service.py
backend/tests/services/test_document_capability_service.py
backend/tests/services/test_analysis_runner.py
backend/tests/reports/test_profile_resolver.py
backend/tests/api/test_report_audit_api.py
backend/tests/api/test_phase17_product_closure_e2e.py
frontend/app/reports/[reportId]/audit/page.tsx
frontend/components/audit/report-audit-timeline.tsx
frontend/components/audit/report-audit-timeline.test.tsx
frontend/components/layout/report-context-nav.test.tsx
docs/product/phase1.7-final-closure-acceptance.md
```

### 3.2 预计修改文件

```text
backend/src/api/routes/assessments.py
backend/src/api/routes/audit.py
backend/src/api/routes/exports.py
backend/src/api/routes/reports.py
backend/src/api/routes/review.py
backend/src/api/routes/runs.py
backend/src/api/schemas.py
backend/src/db/repositories.py
backend/src/services/analysis_job.py
backend/src/services/analysis_runner.py
backend/src/services/export_service.py
backend/src/services/requirement_scope_service.py
backend/src/services/review_service.py
backend/src/workflows/single_report_workflow.py
backend/tests/api/test_assessments_api.py
backend/tests/api/test_audit_api.py
backend/tests/api/test_exports_api.py
backend/tests/api/test_openapi_contract.py
backend/tests/api/test_product_closure_e2e.py
backend/tests/api/test_reports_api.py
backend/tests/api/test_review_api.py
backend/tests/api/test_runs_api.py
backend/tests/services/test_requirement_scope_service.py
backend/tests/workflows/test_single_report_workflow.py
frontend/components/analysis/analysis-progress.tsx
frontend/components/analysis/assessment-table.tsx
frontend/components/analysis/report-dashboard.tsx
frontend/components/layout/report-context-nav.tsx
frontend/lib/api.ts
frontend/lib/types.ts
frontend/lib/generated/api-types.ts
README.md
docs/ASSETS.md
docs/DESIGN.md
docs/DEVELOPMENT.md
docs/product/api-contract.md
docs/product/mvp-acceptance-report.md
docs/product/state-model.md
```

### 3.3 数据库影响

计划目标是零 migration：

- 不新增表。
- 不修改列。
- 不回填历史数据。
- 不复制 assessment。
- 不修改不可变历史事件。

发现必须 migration 才能满足闭环时，立即停止，单独汇报代价和替代方案。

---

## 四、执行任务

每个任务遵循：先写失败测试，再写最小实现，再跑目标测试，再提交。提交仅在用户授权执行和提交后进行。

### 任务 1：执行前基线、脏工作区和范围冻结

**修改文件：**

- 修改：`docs/product/phase1.7-final-closure-acceptance.md`，仅在实施获批后创建执行记录。

**步骤：**

- [ ] 检查当前分支、HEAD、工作区和未跟踪文件。

```powershell
git status --short --branch
git log -1 --oneline
git diff --check
```

- [ ] 记录既有用户改动，禁止覆盖或回退。
- [ ] 确认数据库 URL 仅指向测试库或 demo 库。
- [ ] 确认 `confirm_llm=false`、OCR/VLM 禁用。
- [ ] 跑最小基线：

```powershell
Set-Location backend
uv run pytest tests/services/test_requirement_scope_service.py tests/api/test_runs_api.py tests/api/test_product_closure_e2e.py -q
uv run ruff check src tests

Set-Location ../frontend
npm test -- --run
npm run typecheck
```

- [ ] 基线失败时停止，不把既有失败归因于 Phase 1.7。

**验收：**

- 工作区来源清楚。
- 测试数据库身份清楚。
- 不存在外部调用风险。
- 基线结果写入验收记录。

---

### 任务 2：为运行谱系有效视图编写失败测试

**新增文件：**

- `backend/tests/services/test_effective_run_view_service.py`

**测试场景：**

- [ ] 单个完整 run 返回 499 个有效 assessment。
- [ ] 父 run 部分失败、子 run 重试成功时，子 assessment 覆盖对应 requirement。
- [ ] 子 run 仍失败时，保留父 run 成功 assessment，并将缺失项标记为 `failed`。
- [ ] 从未生成且没有失败摘要的独立项标记为 `not_generated`。
- [ ] `source_run_id` 指向真实 assessment 所属 run。
- [ ] 三层谱系按最近优先合并。
- [ ] 重复 requirement 不产生重复行。
- [ ] `parent_run_id` 循环明确失败。
- [ ] 超过最大深度明确失败。
- [ ] 不属于 499 独立项的 assessment 不进入有效判断集合。
- [ ] 不修改任何父 run 或 assessment。

核心断言示例：

```python
view = service.build(report_id=report.id, independent_requirement_ids=expected_ids)

assert len(view.assessments_by_requirement) == 498
assert view.assessments_by_requirement["GRI-X"].source_run_id == retry_run.id
assert view.failed_requirement_ids == frozenset({"GRI-Y"})
assert view.not_generated_requirement_ids == frozenset()
```

**运行：**

```powershell
Set-Location backend
uv run pytest tests/services/test_effective_run_view_service.py -q
```

**预期：** 因服务尚不存在而失败。

---

### 任务 3：实现运行谱系有效视图

**新增文件：**

- `backend/src/services/effective_run_view_service.py`

**修改文件：**

- `backend/src/db/repositories.py`

**实现要求：**

- [ ] 新增按 ID 读取 run 的只读 repository 方法。
- [ ] 新增读取 run assessment 的稳定方法。
- [ ] 最新 run 从既有 `latest_run_for_report` 获取。
- [ ] 使用 `setdefault` 或等价逻辑保证最近 assessment 优先。
- [ ] 从结构化 `failure_summary.failed_requirement_ids` 和 `retry_requirement_ids` 识别失败范围。
- [ ] 最大谱系深度固定为 32。
- [ ] 循环和损坏父引用返回稳定领域错误。
- [ ] 所有集合只接受标准清单中的独立 requirement ID。
- [ ] 服务不执行 INSERT、UPDATE 或 DELETE。

伪代码：

```python
current = latest_run
seen_run_ids: set[UUID] = set()

while current is not None:
    ensure_not_seen_or_too_deep(current.id)
    for assessment in repository.list_assessments_by_run(current.id):
        if assessment.requirement_id in expected_ids:
            effective.setdefault(
                assessment.requirement_id,
                EffectiveAssessment(assessment, current.id),
            )
    failed_ids.update(read_safe_failed_ids(current.failure_summary))
    current = repository.get_run(current.parent_run_id)
```

- [ ] 已存在 assessment 的 requirement 从失败集合移除。
- [ ] 其余缺失项按有无失败事实区分 `failed` 与 `not_generated`。

**验证：**

```powershell
Set-Location backend
uv run pytest tests/services/test_effective_run_view_service.py -q
uv run ruff check src/services/effective_run_view_service.py tests/services/test_effective_run_view_service.py
```

**建议提交：**

```text
feat: resolve effective assessments across retry lineage
```

---

### 任务 4：先用失败测试固定 577 项部分失败 API 语义

**修改测试：**

- `backend/tests/services/test_requirement_scope_service.py`
- `backend/tests/api/test_assessments_api.py`
- `backend/tests/api/test_reports_api.py`
- `backend/tests/api/test_review_api.py`
- `backend/tests/api/test_exports_api.py`

**新增测试：**

- [ ] 最新 run 只有部分重试 assessment 时，范围接口仍返回 577 行。
- [ ] 499 个独立项中成功、失败、未生成数量相加等于 499。
- [ ] 78 个上下文项仍是 `context_incorporated` 且 `analysis_status=null`。
- [ ] 失败行的 assessment、verdict、evidence、review snapshot 均为空。
- [ ] 成功行包含正确 `source_run_id`。
- [ ] dashboard 使用有效视图计数，不把子 run 的局部数量当作总量。
- [ ] review queue 只包含存在有效 assessment 的项目。
- [ ] draft export 可表示失败行，且不得伪造判定。
- [ ] formal export 在有效视图仍存在失败或未生成项时被阻止。
- [ ] 现有完整 run API 响应保持兼容。
- [ ] 原先“assessment 不完整统一返回 409”的断言被替换为结构化完整范围断言。

建议响应断言：

```python
assert response.status_code == 200
assert response.json()["total"] == 577
failed_row = find_row(response.json(), "GRI-Y")
assert failed_row["analysis_status"] == "failed"
assert failed_row["assessment_id"] is None
assert failed_row["failure_code"] == "assessment_failed"
```

**运行：**

```powershell
Set-Location backend
uv run pytest `
  tests/services/test_requirement_scope_service.py `
  tests/api/test_assessments_api.py `
  tests/api/test_reports_api.py `
  tests/api/test_review_api.py `
  tests/api/test_exports_api.py -q
```

**预期：** 新断言失败，证明现有 409 缺口被测试捕获。

---

### 任务 5：把有效视图接入范围、看板、复核和导出

**修改文件：**

- `backend/src/services/requirement_scope_service.py`
- `backend/src/services/export_service.py`
- `backend/src/services/review_service.py`
- `backend/src/api/routes/assessments.py`
- `backend/src/api/routes/exports.py`
- `backend/src/api/routes/reports.py`
- `backend/src/api/routes/review.py`
- `backend/src/api/schemas.py`

**实现要求：**

- [ ] `RequirementScopeService` 使用 `EffectiveRunViewService`。
- [ ] 删除“最新 run assessment 必须恰好 499，否则 409”的硬拒绝。
- [ ] 577 行顺序继续来自标准清单，不来自数据库偶然顺序。
- [ ] 新字段保持 nullable，避免破坏旧客户端。
- [ ] dashboard、review queue、export 使用同一有效视图来源。
- [ ] draft export 显式展示失败/未生成，禁止用空 verdict 冒充成功。
- [ ] formal export gate 要求 499 个独立项均有有效 assessment，并继续满足人工复核规则。
- [ ] 风险、证据、AI 建议和人工快照只绑定实际有效 assessment。
- [ ] 不改变规则、证据、风险和人工优先级。

**验证：**

```powershell
Set-Location backend
uv run pytest `
  tests/services/test_effective_run_view_service.py `
  tests/services/test_requirement_scope_service.py `
  tests/api/test_assessments_api.py `
  tests/api/test_reports_api.py `
  tests/api/test_review_api.py `
  tests/api/test_exports_api.py -q
uv run ruff check src tests
```

**建议提交：**

```text
feat: expose complete scope for partial and retried runs
```

---

### 任务 6：闭合重试后的报告状态和错误契约

**修改测试：**

- `backend/tests/api/test_runs_api.py`
- `backend/tests/api/test_reports_api.py`
- `backend/tests/api/test_product_closure_e2e.py`

**修改文件：**

- `backend/src/services/analysis_job.py`
- `backend/src/services/analysis_runner.py`
- `backend/src/api/routes/runs.py`
- `backend/src/api/schemas.py`
- `backend/src/db/repositories.py`

**测试先行：**

- [ ] 只有 failed requirement 可进入 retry。
- [ ] retry child 的 `eligible_requirement_count` 表示本次工作量，不伪装为 499。
- [ ] retry 成功后，根据有效视图决定 report 是否 `analysis_completed`。
- [ ] retry 仍失败时，report 保持 `analysis_partial` 或等价现有状态。
- [ ] 原始失败 run 和 child run 的谱系可审计。
- [ ] 空失败集合不能创建 retry run。
- [ ] 非法 requirement ID 被拒绝。
- [ ] 错误消息不得包含绝对路径、数据库 URL、token 或超长 stderr。
- [ ] 服务重启造成的 active run 中断具有稳定错误码。

**实现要求：**

- [ ] run 自身状态描述本次执行结果。
- [ ] report 状态描述谱系合并后的产品结果。
- [ ] `failure_summary` 保存结构化错误码、失败 requirement ID 和安全摘要。
- [ ] 通用异常只保留安全错误类别。
- [ ] 不改变历史 run 状态和 assessment。

**验证：**

```powershell
Set-Location backend
uv run pytest tests/api/test_runs_api.py tests/api/test_reports_api.py tests/api/test_product_closure_e2e.py -q
```

**建议提交：**

```text
fix: finalize report state from effective retry results
```

---

### 任务 7：前端展示部分失败、未生成和重试谱系

**修改文件：**

- `frontend/components/analysis/analysis-progress.tsx`
- `frontend/components/analysis/assessment-table.tsx`
- `frontend/components/analysis/report-dashboard.tsx`
- `frontend/lib/api.ts`
- `frontend/lib/types.ts`
- `frontend/lib/generated/api-types.ts`

**修改或新增测试：**

- 相应组件现有测试文件。

**测试先行：**

- [ ] 失败项显示“分析失败”，不显示 verdict。
- [ ] 未生成项显示“未生成”，不显示证据。
- [ ] 成功继承父 run 时正常展示结果。
- [ ] 失败原因只显示安全摘要。
- [ ] retry 后的总范围仍显示 577/499/78。
- [ ] formal 输出按钮在有效视图不完整时保持禁用并说明原因。
- [ ] 键盘和屏幕阅读器可读取状态。

**实现要求：**

- [ ] `analysis_status` 使用独立徽标，不覆盖结构状态。
- [ ] 不暴露 `source_run_id` 原始 UUID 给普通用户；可在审计页查看。
- [ ] 不把失败项归为“不披露”。
- [ ] 空态文案区分无结果、执行失败和未生成。

**验证：**

```powershell
Set-Location frontend
npm test -- --run
npm run typecheck
npm run build
```

**建议提交：**

```text
feat: present partial analysis and retry outcomes
```

---

### 任务 8：报告级审计 API

**新增测试：**

- `backend/tests/api/test_report_audit_api.py`

**修改文件：**

- `backend/src/api/routes/audit.py`
- `backend/src/api/schemas.py`
- `backend/src/db/repositories.py`

**API：**

```http
GET /api/reports/{report_id}/audit?event_type=&offset=0&limit=50
```

**测试先行：**

- [ ] 返回指定报告所有 run 的审计事件。
- [ ] 返回 payload 中直接记录 `report_id` 的报告级事件。
- [ ] 不返回其他报告事件。
- [ ] 支持分页和 `event_type` 过滤。
- [ ] 按 `created_at` 和稳定次序倒序。
- [ ] report 不存在返回 404。
- [ ] payload 递归移除路径、密钥、token、原始模型响应和过长错误。
- [ ] `run_id` 允许为空。
- [ ] 不改变现有 `/api/audit/runs` 行为。

建议 schema：

```python
class ReportAuditEventResponse(BaseModel):
    audit_event_id: UUID
    run_id: UUID | None
    event_type: str
    payload: dict[str, Any]
    created_at: datetime


class ReportAuditListResponse(BaseModel):
    items: list[ReportAuditEventResponse]
    total: int
    offset: int
    limit: int
```

**安全白名单：**

- 可保留：状态、计数、requirement ID、run ID、export ID、操作类型、安全错误码。
- 必须移除：绝对路径、数据库连接、API key、Authorization、原始 Prompt、原始模型响应、完整 stderr。
- 字符串设置最大长度。

**验证：**

```powershell
Set-Location backend
uv run pytest tests/api/test_report_audit_api.py tests/api/test_audit_api.py -q
uv run ruff check src tests
```

**建议提交：**

```text
feat: add safe report-level audit timeline API
```

---

### 任务 9：报告级审计前端

**新增文件：**

- `frontend/app/reports/[reportId]/audit/page.tsx`
- `frontend/components/audit/report-audit-timeline.tsx`
- `frontend/components/audit/report-audit-timeline.test.tsx`

**修改文件：**

- `frontend/components/layout/report-context-nav.tsx`
- `frontend/components/layout/report-context-nav.test.tsx`
- `frontend/lib/api.ts`
- `frontend/lib/types.ts`
- `frontend/lib/generated/api-types.ts`

**测试先行：**

- [ ] 报告导航可进入审计页。
- [ ] 时间线显示事件名称、时间、run 来源和安全摘要。
- [ ] 空审计、加载失败和分页状态清楚。
- [ ] 不渲染任意原始 JSON。
- [ ] 失败重试、人工复核、整改、草稿和正式输出事件可区分。
- [ ] 页面标题和返回路径正确。
- [ ] 键盘导航与焦点状态有效。

**实现要求：**

- [ ] 普通用户看到中文事件摘要。
- [ ] 未识别事件使用安全通用文案。
- [ ] 技术标识只在详情中按需展示。
- [ ] 不增加报告全局高级搜索等范围外功能。

**验证：**

```powershell
Set-Location frontend
npm test -- --run
npm run typecheck
npm run build
```

**建议提交：**

```text
feat: add report audit timeline
```

---

### 任务 10：数字文本 PDF 能力边界

**新增文件：**

- `backend/src/services/document_capability_service.py`
- `backend/tests/services/test_document_capability_service.py`

**修改测试：**

- `backend/tests/workflows/test_single_report_workflow.py`
- `backend/tests/api/test_reports_api.py`

**纯函数契约：**

```python
class DocumentCapabilityStatus(StrEnum):
    SUPPORTED = "supported"
    SUPPORTED_WITH_REVIEW = "supported_with_review"
    UNSUPPORTED_SCANNED_PDF = "unsupported_scanned_pdf"
```

**测试先行：**

- [ ] 全部数字文本页返回 `supported`。
- [ ] 数字文本与扫描页混合返回 `supported_with_review`。
- [ ] 完全扫描且 `enable_ocr=false` 返回 `unsupported_scanned_pdf`。
- [ ] 低文本但没有扫描证据的页面不误判为完全扫描。
- [ ] 空 PDF 或损坏 PDF 沿用现有解析错误。
- [ ] `enable_ocr=true` 不被误写成正式支持。
- [ ] 错误信息不包含源文件绝对路径。

**工作流接入：**

- [ ] 在 PDF 解析后、577 项规则计算前执行能力检查。
- [ ] 完全扫描文档提前失败，避免生成虚假 assessment。
- [ ] run 保存 `failure_code=unsupported_scanned_pdf`。
- [ ] audit 保存页数统计和安全提示。
- [ ] 混合文档的扫描页 chunk 保持 `needs_manual_review`。
- [ ] `enable_ocr=false` 的数字文本主路径结果不变。

**验证：**

```powershell
Set-Location backend
uv run pytest `
  tests/services/test_document_capability_service.py `
  tests/services/test_document_parser.py `
  tests/workflows/test_single_report_workflow.py `
  tests/api/test_reports_api.py -q
```

**建议提交：**

```text
feat: enforce digital-text PDF capability boundary
```

---

### 任务 11：扫描 PDF 失败的前端可见性

**修改文件：**

- `frontend/components/analysis/analysis-progress.tsx`
- `frontend/lib/types.ts`

**修改测试：**

- `analysis-progress` 对应测试文件。

**测试先行：**

- [ ] `unsupported_scanned_pdf` 显示明确说明。
- [ ] 告知当前版本支持数字文本 PDF。
- [ ] 不承诺 OCR 自动成功。
- [ ] 不展示本机依赖、路径或 stderr。
- [ ] 其他失败继续使用现有通用错误。

建议用户文案：

> 当前报告主要由扫描图像组成，正式分析仅支持含可提取文字的 PDF。请上传数字文本版本，或在实验环境单独验证 OCR 后重试。

**验证：**

```powershell
Set-Location frontend
npm test -- --run
npm run typecheck
```

**建议提交：**

```text
feat: explain unsupported scanned PDF runs
```

---

### 任务 12：通用报告 profile 解析器

**新增文件：**

- `backend/src/reports/profile_resolver.py`
- `backend/tests/reports/test_profile_resolver.py`
- `backend/tests/services/test_analysis_runner.py`

**修改文件：**

- `backend/src/services/analysis_runner.py`

**测试先行：**

- [ ] Envision 文件名解析到 Envision profile。
- [ ] Goldwind 文件名解析到 Goldwind profile。
- [ ] 大小写、Unicode 和首尾空格按既定规范化处理。
- [ ] 未知文件返回 `None`。
- [ ] 重复匹配明确失败。
- [ ] profile 缺失 `pdf_file` 明确失败。
- [ ] 页数明显不符时明确失败或拒绝 profile，不静默套用。
- [ ] 不改变 profile 内规则和证据数据。

建议接口：

```python
class ReportProfileResolver:
    def resolve(
        self,
        *,
        original_filename: str,
        page_count: int,
        source_file_hash: str,
    ) -> Path | None:
        ...
```

**实现要求：**

- [ ] 删除 `analysis_runner.py` 中 Envision 精确文件名特判。
- [ ] profile 目录使用项目相对路径或配置，不写本机路径。
- [ ] 解析只负责选 profile，不修改规则。
- [ ] 解析结果写入安全 audit event。

**验证：**

```powershell
Set-Location backend
uv run pytest tests/reports/test_profile_resolver.py tests/services/test_analysis_runner.py -q
uv run ruff check src tests
```

**建议提交：**

```text
refactor: resolve report profiles from declared metadata
```

---

### 任务 13：独立 Goldwind 产品闭环自动验收

**新增文件：**

- `backend/tests/api/test_phase17_product_closure_e2e.py`

**资产：**

- 使用现有 `backend/data/reports/Goldwind 2024-zh.pdf`。
- 使用现有 `backend/data/reports/profiles/goldwind_2024.json`。
- 禁止覆盖、替换或改写原始 PDF。

**数据库：**

- 自动 E2E 只使用测试数据库。
- 不写主数据库。
- demo 数据库只在后续 Chrome 验收获批后使用。
- 不自动 reset demo 数据库。

**端到端步骤：**

- [ ] 上传 Goldwind PDF。
- [ ] 校验 metadata、页数和文件 hash。
- [ ] 确认报告元数据。
- [ ] 使用 `confirm_llm=false` 启动分析。
- [ ] profile 自动解析为 Goldwind。
- [ ] 分析完成后返回 577/499/78/0。
- [ ] 所有证据页码位于报告页数范围。
- [ ] 不出现 global fallback。
- [ ] 不产生外部 AI suggestion。
- [ ] 创建一条工程验收用人工复核快照。
- [ ] 创建整改事项。
- [ ] 更新整改负责人或截止日期。
- [ ] 生成四文件草稿包。
- [ ] 下载全部草稿文件并校验非空、MIME、文件名和 hash。
- [ ] 报告级审计包含上传、分析、复核、整改和导出事件。
- [ ] 不把工程 fixture 结论描述为 ESG 专家结论。

**Goldwind 历史工程质量对照：**

- 100 项历史 gold recall：96.08%。
- false disclosed：0。
- wrong source page：0。
- unknown leakage：2。

这些指标只作差异监控。Phase 1.7 不通过修改 gold、规则或 profile 来追求表面提升。

**运行：**

```powershell
Set-Location backend
$env:APP_ENV = "test"
$env:DATABASE_URL = $env:ESG_AGENT_TEST_DATABASE_URL
uv run pytest tests/api/test_phase17_product_closure_e2e.py -q
```

**停止条件：**

- 需要新增 Goldwind 专用规则分支。
- 需要修改 577 标准口径。
- 需要外部 LLM/OCR/VLM。
- 需要覆盖原始报告。

**建议提交：**

```text
test: cover Goldwind product closure flow
```

---

### 任务 14：正式输出后的纠正、重开与 supersede 闭环

**修改文件：**

- `backend/tests/api/test_product_closure_e2e.py`
- `backend/tests/api/test_review_api.py`
- `backend/tests/api/test_exports_api.py`
- 必要时修改：
  - `backend/src/services/review_service.py`
  - `backend/src/services/export_service.py`

**测试先行：**

- [ ] 满足 gate 后生成正式输出版本 N。
- [ ] 对一个 assessment 执行现有 `operation_type=reopen`。
- [ ] report 进入 `reopened`。
- [ ] reopen 未解决时，新正式输出被阻止。
- [ ] 新人工快照完成纠正后，报告重新满足 gate。
- [ ] 生成正式输出版本 N+1。
- [ ] 版本 N 标记为 `superseded`。
- [ ] 版本 N+1 标记为当前正式输出。
- [ ] 两个版本文件均可下载和审计。
- [ ] 纠正不得改写旧快照、旧 assessment 或旧导出事实。

**实现约束：**

- 优先复用现有服务。
- 不新增重复 reopen API。
- 不实现 `voided` 状态。
- 不引入数据库 migration。

**验证：**

```powershell
Set-Location backend
uv run pytest `
  tests/api/test_product_closure_e2e.py `
  tests/api/test_review_api.py `
  tests/api/test_exports_api.py -q
```

**建议提交：**

```text
test: close post-export correction and supersede flow
```

若测试暴露真实缺陷，修复代码后使用：

```text
fix: preserve correction history across formal exports
```

---

### 任务 15：OpenAPI、前端类型和兼容性冻结

**修改文件：**

- `backend/tests/api/test_openapi_contract.py`
- `frontend/lib/generated/api-types.ts`
- `docs/product/api-contract.md`

**步骤：**

- [ ] 为新增字段和报告审计接口补 OpenAPI contract 测试。
- [ ] 生成前端 API 类型，不手工伪造。
- [ ] 对比生成前后 schema diff。
- [ ] 确认现有字段未被删除或改变非空语义。
- [ ] 确认失败响应使用稳定错误码。
- [ ] 文档记录 draft/formal gate、谱系来源和扫描 PDF 错误。

**验证：**

```powershell
Set-Location backend
uv run pytest tests/api/test_openapi_contract.py -q

Set-Location ../frontend
npm run generate:api
git diff -- lib/generated/api-types.ts
npm run typecheck
```

生成命令若与项目现有脚本名不同，只能使用 `package.json` 已声明脚本，并在执行记录中写明。

**建议提交：**

```text
docs: freeze Phase 1.7 API contract
```

---

### 任务 16：干净测试数据库与启动验证

**前提：**

- `ESG_AGENT_TEST_DATABASE_URL` 必须指向专用测试数据库。
- 禁止把主数据库或 demo 数据库 URL 赋给该变量。

**步骤：**

- [ ] 在专用测试数据库从空 schema 执行 migration 到 head。
- [ ] 验证 Alembic head 仍为既有最新版本；零 migration 是计划目标。
- [ ] 启动后端并检查 health。
- [ ] 检查 OpenAPI 可读取。
- [ ] 启动前端生产构建。
- [ ] 执行一个不调用外部服务的上传/分析 smoke。
- [ ] 记录进程退出和重启后的 run 恢复行为。

**命令：**

```powershell
Set-Location backend
$env:APP_ENV = "test"
$env:DATABASE_URL = $env:ESG_AGENT_TEST_DATABASE_URL
uv run alembic upgrade head
uv run pytest tests/test_health.py tests/api/test_phase17_product_closure_e2e.py -q
```

后端启动命令必须使用 `docs/DEVELOPMENT.md` 当前正式命令。

**验收：**

- 无手工 SQL。
- 无隐藏 seed 前提。
- 无主数据库和 demo 数据库破坏性操作。
- health、OpenAPI 和核心 E2E 全部通过。

---

### 任务 17：全量自动 gates

#### 17.1 后端

```powershell
Set-Location backend
uv run pytest -q --basetemp=../tmp/pytest-phase17-final
uv run ruff check src tests
```

最低要求：

- 测试数不得低于 Phase 1.6 的 727。
- 0 failed。
- Ruff 0 error。

#### 17.2 前端

```powershell
Set-Location frontend
npm test -- --run
npm run typecheck
npm run build
```

最低要求：

- 测试文件数不得低于 28。
- 测试数不得低于 114。
- typecheck 通过。
- production build 通过。

#### 17.3 Envision 权威回归

使用 `docs/DEVELOPMENT.md` 和既有验收脚本中的正式命令重新生成结果，不复用旧输出冒充新结果。

必须满足：

```text
standard_units = 577
independent_items = 499
context_items = 78
method_pending = 0
new_false_disclosed = 0
wrong_source_page = 0
global_fallback = 0
audit_errors = 0
audit_warnings = 0
```

#### 17.4 Goldwind 独立报告 gate

- 上传、元数据确认、分析、复核、整改、草稿、下载全链路通过。
- 577/499/78/0。
- 页码越界 0。
- global fallback 0。
- 外部模型调用 0。
- 对历史 100 项工程基线做差异说明。

#### 17.5 安全和路径扫描

```powershell
rg -n --hidden --glob '!tmp/**' --glob '!.git/**' `
  '(C:\\Users\\|C:\\Alvin\\|api[_-]?key|Authorization: Bearer|sk-[A-Za-z0-9])' `
  README.md docs backend frontend
```

要求：

- docs 不出现本机绝对路径。
- 无密钥。
- 无外部响应中的非公开数据。
- 已知测试 fixture 命中必须逐项说明。

---

### 任务 18：Chrome 最终自动验收

**环境：**

- 使用 demo 数据库。
- 不 reset demo 数据库。
- `confirm_llm=false`。
- OCR/VLM 禁用。
- 上传测试使用 Goldwind 原始资产的只读副本语义；不得修改源文件。

**桌面端流程：**

- [x] 报告列表和上传入口可用。
- [x] 上传 Goldwind，确认 metadata。
- [x] 启动分析并观察进度。
- [x] 进入 577 项范围和 dashboard。
- [x] 验证失败/未生成空态不会伪造 verdict。
- [x] 打开 PDF 证据页。
- [x] 创建人工复核快照。
- [x] 创建和更新整改事项。
- [x] 生成草稿并下载文件。
- [x] 打开报告审计时间线。
- [x] 验证正式输出 gate 文案。
- [x] 浏览器 console 0 error。
- [x] 关键请求无 4xx/5xx。

**窄屏和键盘：**

- [x] 关键页面无横向遮挡。
- [x] Tab 顺序合理。
- [x] 按钮有可辨识名称。
- [x] 对话框焦点可进入和退出（验收流程未出现模态对话框，页面焦点未被困住）。
- [x] 状态不只依赖颜色。

**自动验收限制：**

- 浏览器验收判断工程交互和产品流程。
- 不判断 ESG 专业正确性。
- 文件选择器或系统下载窗口只有 Chrome 无法覆盖时才使用 Computer Use。

---

### 任务 19：文档校准与发布冻结

**新增文件：**

- `docs/product/phase1.7-final-closure-acceptance.md`

**修改文件：**

- `README.md`
- `docs/DESIGN.md`
- `docs/DEVELOPMENT.md`
- `docs/ASSETS.md`
- `docs/product/api-contract.md`
- `docs/product/mvp-acceptance-report.md`
- `docs/product/state-model.md`

**校准要求：**

- [x] README 写明最终支持声明和限制。
- [x] DESIGN 写明运行谱系有效视图、报告审计和 PDF 能力边界。
- [x] DEVELOPMENT 写明测试、双报告 gate、测试数据库和启动命令。
- [x] ASSETS 只记录现有 Envision/Goldwind 资产用途与保护规则。
- [x] API contract 与 OpenAPI 一致。
- [x] state model 明确 assessment reopen 驱动 report reopened。
- [x] 删除或标记未实现的独立 report reopen、voided 输出等承诺。
- [x] `mvp-acceptance-report.md` 标注为历史快照；历史事实不静默改写。
- [x] 清理仍称 `actions_xlsx` 或下载未实现的过期描述。
- [x] 新验收报告记录命令、日期、commit、测试数、差异和限制。
- [x] 文档不写本机绝对路径。

**最终文档必须回答：**

1. 产品支持什么。
2. 产品不支持什么。
3. 规则、AI、人工三层如何决定最终有效结论。
4. 部分失败和 retry 如何形成 577 项有效视图。
5. 正式输出后如何纠正。
6. 为什么 Envision 与 Goldwind 都要验收。
7. 哪些结果属于工程证据，哪些不能当作专业认证。
8. 什么条件下才启动 OCR、RAG Phase 2 或企业化建设。

**验证：**

```powershell
git diff --check
rg -n 'TODO|TBD|待补充|稍后补充' README.md docs
rg -n 'actions_xlsx.*未实现|下载.*未实现' README.md docs
```

**建议提交：**

```text
docs: freeze Phase 1.7 final product closure
```

---

### 任务 20：独立代码复核和最终终止判定

**复核范围：**

- [x] 运行谱系是否可能串报告。
- [x] 最新优先合并是否确定性。
- [x] 失败行是否伪造 verdict 或 evidence。
- [x] formal export 是否绕过有效完整性 gate。
- [x] reopen/supersede 是否保留不可变历史。
- [x] audit 是否泄露路径、密钥或原始响应。
- [x] profile resolver 是否可能误匹配。
- [x] 完全扫描 PDF 是否在规则执行前被拒绝。
- [x] Goldwind 是否引入专用规则分支。
- [x] 所有外部调用默认关闭。

**完成标准：**

- Critical/P0：0。
- Important/P1：0。
- P2：必须明确列入限制或路线图，不得隐瞒。
- 代码复核发现缺陷时，回到对应任务补测试、修复、重跑相关 gate。

**最终 Git 检查：**

```powershell
git status --short --branch
git diff --check
git log --oneline --decorate -20
```

**发布动作：**

- 不自动 push。
- 不自动打 `v1.2` 标签。
- 汇报 commit 列表、验证结果、未完成项和风险。
- 用户批准后再执行 tag/push。

---

## 五、验收矩阵

| 产品能力 | 自动测试 | Envision | Goldwind | Chrome | 通过标准 |
|---|---:|---:|---:|---:|---|
| 上传与 metadata | 是 | 是 | 是 | 是 | 文件、页数、hash 一致 |
| 577 项结构 | 是 | 是 | 是 | 是 | 577/499/78/0 |
| 部分失败展示 | 是 | 定向 | 定向 | 是 | 200 返回完整范围，无伪造结论 |
| retry 谱系 | 是 | 定向 | 定向 | 是 | 最近成功覆盖，历史可追溯 |
| 证据页码 | 是 | 是 | 是 | 是 | 页码范围正确，PDF 可打开 |
| AI 默认关闭 | 是 | 是 | 是 | 是 | 外部调用 0 |
| 人工复核 | 是 | 是 | 是 | 是 | 生成追加式 snapshot |
| 整改跟踪 | 是 | 是 | 是 | 是 | 创建、更新、审计完整 |
| 草稿输出 | 是 | 是 | 是 | 是 | 四文件可下载、hash 可验证 |
| 正式输出纠正 | 是 | 是 | 定向 | 是 | reopen 阻断、N+1 supersede N |
| 报告审计 | 是 | 是 | 是 | 是 | 事件完整、payload 安全 |
| 扫描 PDF 边界 | 是 | 不适用 | 不适用 | 定向 | 安全错误，无虚假 assessment |
| 干净环境 | 是 | 是 | 是 | 冒烟 | migration、启动、health 通过 |
| 文档一致性 | 是 | 适用 | 适用 | 适用 | 无过期承诺、无绝对路径 |

---

## 六、停止条件、回退和风险

### 6.1 立即停止条件

出现以下任一情况时，不继续扩大修改：

1. 必须新增数据库 migration。
2. 有效谱系改变父 run 中未重试成功项的 verdict、证据或风险。
3. Envision 任一核心回归指标出现非零负向差异。
4. Goldwind 需要专用规则、修改 profile gold 或改变 577 口径。
5. 产品闭环必须依赖真实 OCR、LLM 或 VLM。
6. 需要 reset 主数据库或覆盖 demo 数据。
7. 任务扩展到认证、多租户、生产队列或企业运维。
8. 原始报告或标准资产有被修改的风险。

### 6.2 回退原则

- 每个工作包独立提交，便于定位和回退。
- 不使用破坏性 Git 命令。
- 不回退用户既有改动。
- 不删除历史 run、assessment、snapshot、export 或 audit event。
- 测试数据库可由测试 fixture 管理；主数据库和 demo 数据库不得自动清空。
- 某工作包失败时，优先回退该工作包，不牵连已验证的独立提交。

### 6.3 主要风险

| 风险 | 影响 | 控制措施 |
|---|---|---|
| 最新 run 局部数据被误当全量 | 范围、导出和看板错误 | 单一有效视图服务，所有消费者统一使用 |
| 重试谱系循环或损坏 | 请求挂起或错误合并 | 深度限制、循环检测、领域错误 |
| 失败行被当作不披露 | 形成错误正式结论 | 独立 `analysis_status`，verdict 保持空 |
| formal export 绕过缺失项 | 输出不完整 | 有效 499 完整性 gate |
| audit 泄露敏感信息 | 安全与隐私风险 | 白名单、递归脱敏、长度限制 |
| profile 误匹配 | 使用错误证据规则 | 唯一匹配、页数与源 PDF SHA-256 校验、歧义或身份不一致时失败 |
| Goldwind 被误当专业 gold | 夸大产品结论 | 文档固定工程验证边界 |
| 扫描 PDF 生成虚假结果 | 证据不可复核 | 规则执行前能力检查 |
| 计划范围继续膨胀 | 无法形成终止基线 | 排除项和停止条件硬约束 |

---

## 七、Phase 1.7 最终终止条件

只有以下条件全部满足，才能宣布 Phase 1.7 完成：

- [x] 部分失败 run 可通过 577 项完整范围接口查看，不再因 assessment 不足统一返回 409。
- [x] retry 后形成确定、可审计的有效谱系结果。
- [x] 失败和未生成项不产生虚假 verdict、证据或正式结论。
- [x] 正式输出后的 assessment reopen、重新复核和 supersede 形成闭环。
- [x] 报告级审计覆盖上传、分析、重试、复核、整改和输出。
- [x] 完全扫描 PDF 获得明确、安全的能力边界错误。
- [x] Envision 权威回归全部通过。
- [x] Goldwind 独立产品闭环全部通过。
- [x] 干净测试数据库 migration、启动、health 和核心 E2E 通过。
- [x] 后端全量、Ruff、前端测试、typecheck 和 build 通过。
- [x] Chrome 桌面端、窄屏、键盘和 PDF 交互验收通过。
- [x] 外部 LLM/OCR/VLM 调用为 0。
- [x] 文档、OpenAPI、前端类型和实际行为一致。
- [x] Critical/P0 和 Important/P1 未解决问题为 0。
- [x] 剩余 P2 全部关闭或写入限制与条件化路线图。
- [x] 工作区无意外文件，无密钥和本机绝对路径泄露。

达到上述条件后：

1. 第一阶段产品主线结束。
2. 推荐形成 `v1.2` 最终产品闭环基线。
3. 不自动创建 Phase 1.8。
4. 后续只接受以下三类触发：
   - 真实用户使用暴露可复现闭环缺陷。
   - 独立 ESG 专家 gold 证明规则或证据存在明确偏差。
   - OCR、RAG 或企业化需求具有样本、指标、预算和验收标准。

---

## 八、建议执行批次

在用户批准执行后，建议一次解冻、连续完成，按可审计提交分批：

1. **批次 A：失败恢复**
   - 任务 1—7。
   - 输出：有效谱系、577 完整范围、retry 状态、前端失败展示。

2. **批次 B：审计与输入边界**
   - 任务 8—11。
   - 输出：报告审计、扫描 PDF 安全边界。

3. **批次 C：独立报告与纠正闭环**
   - 任务 12—14。
   - 输出：通用 profile、Goldwind 闭环、正式输出纠正。

4. **批次 D：发布冻结**
   - 任务 15—20。
   - 输出：OpenAPI、干净环境、全量 gates、Chrome、文档和独立复核。

每批结束都运行目标测试并提交，但不 push。全部通过后统一向用户汇报，再决定 `v1.2` 标签和 push。
