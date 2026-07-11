# 企业 ESG 产品闭环实施计划

> **执行要求：** 本计划只有在 `docs/plan/product-closure-realignment-plan.md` 的设计审批清单获得人工批准后才能执行。执行时使用 `executing-plans`，保持纵向阶段、TDD 和小提交。

**目标：** 在现有 Next.js/FastAPI 单报告分析基础上，交付报告管理、577 条后台分析进度、固定风险队列、追加式人工复核、三栏工作台、整改任务和版本化输出。

**架构：** 系统 assessment/evidence 保持不可变；人工结果、风险、阶段、整改和输出使用独立表。每个阶段同时交付数据库、后端 API、前端页面和测试，OpenAPI 是前端类型唯一来源。

**技术栈：** FastAPI、Pydantic v2、PostgreSQL、SQLAlchemy 2.0、Alembic、Next.js App Router、TypeScript、TanStack Query、TanStack Table、pytest、Vitest。

**执行状态：** 阶段 1-8 的自动实现与门禁已于 2026-07-11 完成，当前进入人工产品验收。本文件中的任务清单保留原始实施分解，不再用未勾选项表示当前状态。批量复核、独立 reopen、report 级审计、单 export 下载和完整整改清单导出属于已确认的后续增强项。

| 阶段 | 当前状态 | 说明 |
| --- | --- | --- |
| 1-3 | 已完成 | 报告 metadata、577 分析进度、固定风险队列已通过自动门禁 |
| 4-6 | 已完成核心闭环 | 追加式复核、三栏工作台、完整核查表和整改任务已实现；批量复核与独立 reopen API 延后 |
| 7 | 已完成核心闭环 | 草稿、正式版本、门禁和 supersede 已实现；整改清单专用导出与文件下载 API 延后 |
| 8 | 自动门禁完成 | 等待人工产品验收 |

---

## 实施依赖

```text
阶段 1 报告列表与 metadata 确认
→ 阶段 2 577 分析进度与部分失败
→ 阶段 3 固定风险与队列
→ 阶段 4 人工快照与审计
→ 阶段 5 三栏工作台与完整核查表
→ 阶段 6 整改任务
→ 阶段 7 版本化输出
→ 阶段 8 端到端验收与泛化验证
```

一次只执行一个阶段。每个阶段通过测试和 OpenAPI 类型生成后进入下一阶段；人工界面检查集中在连续执行计划定义的最终验收点。

## 阶段 1：报告列表与 metadata 确认

**文件：**

- 修改：`backend/src/domain/enums.py`
- 修改：`backend/src/domain/models.py`
- 修改：`backend/src/db/models.py`
- 修改：`backend/src/db/repositories.py`
- 创建：`backend/alembic/versions/0003_report_metadata_and_status.py`
- 修改：`backend/src/api/schemas.py`
- 修改：`backend/src/api/routes/reports.py`
- 测试：`backend/tests/db/test_repositories.py`
- 测试：`backend/tests/api/test_reports_api.py`
- 测试：`backend/tests/api/test_openapi_contract.py`
- 修改：`frontend/app/reports/page.tsx`
- 创建：`frontend/app/reports/[reportId]/confirm/page.tsx`
- 创建：`frontend/components/reports/report-list.tsx`
- 创建：`frontend/components/reports/report-metadata-confirmation.tsx`
- 修改：`frontend/lib/api.ts`
- 测试：`frontend/components/reports/report-list.test.tsx`
- 测试：`frontend/components/reports/report-metadata-confirmation.test.tsx`

- [ ] 后端先写失败测试：上传后状态为 uploaded；报告列表分页；metadata 确认前不能分析；重复哈希返回 409。
- [ ] 运行 `uv run pytest tests/api/test_reports_api.py tests/db/test_repositories.py -q`，确认失败来自缺少状态和接口。
- [ ] 增加 ReportStatus、reports 字段和 0003 migration。
- [ ] 实现 `GET /api/reports`、详情和 `confirm-metadata`，保持现有 upload 兼容。
- [ ] 运行后端测试并生成 OpenAPI 类型。
- [ ] 前端先写报告空状态、列表状态和确认表单测试。
- [ ] 实现中文报告入口和确认页。
- [ ] 运行 `pnpm typecheck && pnpm test && pnpm build`。
- [ ] 提交：`feat: add report metadata confirmation flow`。

## 阶段 2：577 条分析进度与部分失败

**文件：**

- 修改：`backend/src/domain/enums.py`
- 修改：`backend/src/domain/models.py`
- 修改：`backend/src/db/models.py`
- 修改：`backend/src/db/repositories.py`
- 创建：`backend/alembic/versions/0004_analysis_stages_and_partial_runs.py`
- 修改：`backend/src/workflows/single_report_workflow.py`
- 修改：`backend/src/api/routes/reports.py`
- 修改：`backend/src/api/routes/runs.py`
- 测试：`backend/tests/workflows/test_single_report_workflow.py`
- 测试：`backend/tests/api/test_runs_api.py`
- 创建：`frontend/app/reports/[reportId]/progress/page.tsx`
- 创建：`frontend/components/analysis/analysis-progress.tsx`
- 测试：`frontend/components/analysis/analysis-progress.test.tsx`

- [ ] 写失败测试：正式 analyze 创建 577 个 task；阶段事件只追加；部分失败保留成功 assessment；retry-failed 只创建失败项任务。
- [ ] 移除生产 API 的 10 条限制，测试 fixture 仍可显式限制数量。
- [ ] 增加 RunStatus.PARTIALLY_COMPLETED、阶段事件表和 run 统计字段。
- [ ] workflow 在七个业务边界写阶段事件，并捕获 requirement 级异常。
- [ ] 实现 stages 和 retry-failed API。
- [ ] 前端实现七阶段进度、部分失败和后台继续提示。
- [ ] 运行后端/前端测试。
- [ ] 提交：`feat: add full GRI analysis progress and retry`。

## 阶段 3：固定风险模型与风险队列

**文件：**

- 创建：`backend/src/domain/risk.py`
- 创建：`backend/src/services/risk_service.py`
- 修改：`backend/src/db/models.py`
- 修改：`backend/src/db/repositories.py`
- 创建：`backend/alembic/versions/0005_assessment_risks.py`
- 修改：`backend/src/api/schemas.py`
- 修改：`backend/src/api/routes/runs.py`
- 创建：`backend/src/api/routes/assessments.py`
- 测试：`backend/tests/services/test_risk_service.py`
- 测试：`backend/tests/api/test_runs_api.py`
- 创建：`backend/tests/api/test_assessments_api.py`
- 创建：`frontend/components/review/risk-queue.tsx`
- 测试：`frontend/components/review/risk-queue.test.tsx`

- [ ] 写风险决策表失败测试：分析失败、unknown、无证据、质量风险、非实质证据、partial 和直接 disclosed。
- [ ] 实现纯函数风险分类，输出 level、reason codes 和 `risk-v1`。
- [ ] 创建只追加 assessment_risks 表和 repository 查询。
- [ ] 实现 dashboard、分页 assessment 和 review queue API。
- [ ] 前端实现中文风险原因和固定排序。
- [ ] 验证“高风险复核 X/Y”分母来自最新 run 风险集合。
- [ ] 提交：`feat: add fixed assessment risk queue`。

## 阶段 4：人工快照、字段变更与追加式审计

**文件：**

- 修改：`backend/src/domain/enums.py`
- 修改：`backend/src/domain/models.py`
- 修改：`backend/src/db/models.py`
- 修改：`backend/src/db/repositories.py`
- 创建：`backend/alembic/versions/0006_review_snapshots.py`
- 创建：`backend/src/services/review_service.py`
- 修改：`backend/src/api/routes/review.py`
- 测试：`backend/tests/services/test_review_service.py`
- 测试：`backend/tests/api/test_review_api.py`
- 修改：`frontend/lib/api.ts`
- 创建：`frontend/components/review/review-editor.tsx`
- 测试：`frontend/components/review/review-editor.test.tsx`

- [ ] 写失败测试：approve 可用预设原因；modify/invalidate/batch/reopen 备注必填；原 assessment 不改变；sequence 连续；并发 snapshot 冲突返回 409。
- [ ] 创建 review_snapshots 和 review_change_events；保留旧 review_decisions。
- [ ] 实现 effective result 组装和 review history。
- [ ] 每次人工操作后重新计算并追加 risk。
- [ ] 前端实现首次复核人、快速通过和字段编辑。
- [ ] 验证审计历史包含原值、新值、复核人、时间和原因。
- [ ] 提交：`feat: add append-only review snapshots`。

## 阶段 5：报告仪表盘、三栏工作台和完整核查表

**文件：**

- 创建：`frontend/app/reports/[reportId]/dashboard/page.tsx`
- 创建：`frontend/app/reports/[reportId]/review/page.tsx`
- 创建：`frontend/app/reports/[reportId]/assessments/page.tsx`
- 修改：`frontend/components/layout/app-shell.tsx`
- 创建：`frontend/components/review/review-workspace.tsx`
- 创建：`frontend/components/review/assessment-detail.tsx`
- 创建：`frontend/components/evidence/pdf-evidence-viewer.tsx`
- 创建：`frontend/components/analysis/assessment-table.tsx`
- 创建：`frontend/lib/business-labels.ts`
- 测试：`frontend/components/review/review-workspace.test.tsx`
- 测试：`frontend/components/evidence/pdf-evidence-viewer.test.tsx`
- 测试：`frontend/components/analysis/assessment-table.test.tsx`

- [ ] 写失败测试：桌面三栏、窄屏三视图、未保存修改拦截、风险队列定位、PDF 页码切换、577 条分页筛选。
- [ ] 建立中文业务词典，不在组件散落翻译。
- [ ] 实现 dashboard 指标和三栏工作台。
- [ ] 实现完整核查表并复用 assessment query。
- [ ] 确认普通界面不出现 profile、ontology、route、evidence kind。
- [ ] 使用 Playwright 或浏览器截图验证桌面和窄屏无重叠。
- [ ] 提交：`feat: build ESG review workspace`。

## 阶段 6：整改任务

**文件：**

- 修改：`backend/src/db/models.py`
- 修改：`backend/src/db/repositories.py`
- 创建：`backend/alembic/versions/0007_improvement_actions.py`
- 创建：`backend/src/services/action_service.py`
- 创建：`backend/src/api/routes/actions.py`
- 测试：`backend/tests/api/test_actions_api.py`
- 创建：`frontend/app/reports/[reportId]/actions/page.tsx`
- 创建：`frontend/components/actions/action-list.tsx`
- 测试：`frontend/components/actions/action-list.test.tsx`

- [ ] 写失败测试：从 assessment 创建任务、状态转换、完成/取消/重开备注、报告隔离。
- [ ] 创建 improvement_actions 和 API。
- [ ] 实现任务列表、筛选和编辑。
- [ ] 验证任务状态不自动改变 requirement 结论。
- [ ] 提交：`feat: add ESG improvement actions`。

## 阶段 7：草稿与版本化正式输出

**文件：**

- 修改：`backend/src/db/models.py`
- 修改：`backend/src/db/repositories.py`
- 创建：`backend/alembic/versions/0008_export_versions.py`
- 重构：`backend/src/services/export_service.py`
- 修改：`backend/src/api/routes/exports.py`
- 测试：`backend/tests/api/test_exports_api.py`
- 创建：`backend/tests/services/test_export_service.py`
- 创建：`frontend/app/reports/[reportId]/exports/page.tsx`
- 创建：`frontend/components/exports/export-versions.tsx`
- 测试：`frontend/components/exports/export-versions.test.tsx`

- [ ] 写失败测试：草稿随时生成并带标识；正式输出阻止未完成高风险；版本递增；旧正式版本 superseded；复核范围进入 manifest。
- [ ] 创建 export_versions。
- [ ] 实现 Excel、PDF、打印网页和任务清单生成服务。
- [ ] 输出明确区分人工确认与系统待确认结果。
- [ ] 前端实现门槛、版本和文件列表。
- [ ] 提交：`feat: add versioned ESG exports`。

## 阶段 8：端到端验收与泛化验证

**文件：**

- 修改：`backend/tests/api/test_openapi_contract.py`
- 创建：`backend/tests/e2e/test_report_product_flow.py`
- 创建：`frontend/tests/report-product-flow.test.tsx`
- 修改：`docs/DEVELOPMENT.md`
- 修改：`README.md`

- [ ] 验证上传、确认、577 分析、部分失败、风险队列、复核、整改、草稿和正式输出。
- [ ] 验证 Envision 577 baseline 不回退。
- [ ] 使用 Goldwind 或另一企业报告验证 profile/routing 泛化，不新增报告专用 per-ID contract。
- [ ] 运行 `uv run pytest`、`pnpm typecheck`、`pnpm test`、`pnpm build`。
- [ ] 更新运行和验收文档。
- [ ] 提交：`test: validate ESG product closure`。

## 人工检查点

各阶段按连续执行计划的自动门禁推进，阶段 8 完成后统一人工确认界面和 API 行为。以下情况立即停止：数据库迁移会丢失现有人工记录；正式输出无法追溯 snapshot；普通界面需要暴露内部 route/profile 才能工作；577 分析出现非预期回归；需要引入多租户或新技术栈。
