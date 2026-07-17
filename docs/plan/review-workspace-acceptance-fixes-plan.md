# 分析终态与三栏复核验收修复实施计划

> **执行要求：** 使用 `superpowers:executing-plans` 在当前 `main` 工作区按TDD连续实施；不自动提交或push，不重置当前demo数据。

**目标：** 修复分析完成后阶段仍转圈、复核状态显示内部字段名、点击高风险队列触发PDF下载且三栏缺少明确加载反馈的问题。

**架构：** run进入终态时，前端刷新一次stages并如实展示刷新后的阶段状态，不用run终态覆盖阶段异常。复核状态统一通过业务标签模块输出中文。后端PDF接口改为inline响应，三栏中栏和右栏增加加载/失败状态，保持assessment详情与PDF页码联动。

**技术栈：** FastAPI、Starlette `FileResponse`、pytest、Next.js、TanStack Query、Vitest、React Testing Library。

---

## 任务1：分析终态阶段一致性

**文件：**

- 修改：`frontend/components/analysis/analysis-progress.tsx`
- 修改：`frontend/components/analysis/analysis-progress.test.tsx`

- [x] 先写失败测试：run返回`completed`，第一次stages响应仍含`running`，终态触发一次重新获取并显示全部“已完成”。
- [x] 运行：`pnpm test -- components/analysis/analysis-progress.test.tsx`，确认旧实现失败。
- [x] 实现终态一次性`refetch()`；刷新后仍存在的failed或缺失阶段继续如实展示，避免用run终态掩盖数据异常。
- [x] 重新运行组件测试，确认通过且终态不持续轮询。

## 任务2：复核状态中文业务标签

**文件：**

- 修改：`frontend/lib/business-labels.ts`
- 修改：`frontend/components/analysis/assessment-table.tsx`
- 修改：`frontend/components/analysis/assessment-table.test.tsx`
- 检查并按需修改：`frontend/components/review/review-workbench.tsx`

- [x] 先写失败测试，断言`pending_review`显示“待复核”，页面不显示内部枚举。
- [x] 增加统一映射：`pending_review`、`reviewed_approved`、`reviewed_modified`、`evidence_invalidated`、`reopened`、`not_required`、`needs_manual_review`及旧兼容状态。
- [x] 完整核查表和仍可访问的旧复核页面都使用同一映射。
- [x] 运行：`pnpm test -- components/analysis/assessment-table.test.tsx`。

## 任务3：PDF inline响应

**文件：**

- 修改：`backend/src/api/routes/reports.py`
- 修改：`backend/tests/api/test_reports_api.py`

- [x] 先写失败测试：`GET /api/reports/{report_id}/file`返回`200`、`application/pdf`，`Content-Disposition`为`inline`且不含`attachment`。
- [x] 运行针对性测试确认RED。
- [x] 使用安全的inline响应头；保留原始文件、不复制、不改变PDF内容。
- [x] 运行：`uv run --no-sync pytest tests/api/test_reports_api.py -q --basetemp=../tmp/pytest-pdf-inline`。

## 任务4：三栏加载与错误状态

**文件：**

- 修改：`frontend/components/review/review-workspace.tsx`
- 修改：`frontend/components/evidence/pdf-evidence-viewer.tsx`
- 修改：`frontend/components/review/review-workspace.test.tsx`
- 修改：`frontend/components/evidence/pdf-evidence-viewer.test.tsx`

- [x] 先写失败测试：点击队列后中栏显示“正在加载核查详情”，成功后显示requirement详情并将PDF定位到证据页。
- [x] 写失败测试：详情API失败显示“核查详情加载失败”；PDF iframe加载前显示“正在加载PDF证据”，`onLoad`后消失，`onError`显示“PDF证据加载失败”。
- [x] `ReviewWorkspace`区分未选择、加载中、失败和成功四种状态。
- [x] `PdfEvidenceViewer`继续使用同一inline文件接口和`#page=`，切换页码时重置加载状态。
- [x] 运行两组组件测试确认通过。

## 任务5：回归与服务重启

- [x] 后端全量：`uv run --no-sync pytest -q --basetemp=../tmp/pytest-review-workspace-full`。
- [x] 前端顺序运行：`pnpm typecheck`、`pnpm test`、`pnpm build`。
- [x] 运行Envision 577 gate，要求audit通过、verdict delta为0，且不调用外部模型、OCR或VLM。
- [x] 重启8000端口demo后端加载新代码，不重置`esg_agent_demo`。
- [x] 验证当前report的run与七阶段终态一致，PDF响应为inline，前后端均返回200。

## 完成标准

1. 分析完成页面没有任何running图标或持续轮询；
2. 普通页面不显示复核内部枚举；
3. 点击队列不再下载PDF；
4. 中栏明确显示加载、失败或详情；
5. 右栏PDF可嵌入并定位证据页；
6. 全量自动门禁与Envision 577 gate通过；
7. 当前demo报告和分析数据保留，供用户原地复验。
