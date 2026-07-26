# 前端演示体验优化实施计划

> 状态：待审核、待执行
> 日期：2026-07-26
> 设计依据：`docs/plan/frontend-demo-experience-design.md`
> 当前分支：`main`
> 执行边界：不新建分支、不回退已有改动、不自动 push

## 1. 目标

在保持 Envision 2024 中文报告后端基线冻结的前提下，将现有前端从功能验收页面升级为可在 5–8 分钟内完成求职展示、产品验收和 ESG 实际操作的报告中心工作台。

完成后需要满足：

1. 首页、报告总览和三栏复核形成统一的报告中心体验。
2. 上传、metadata、八阶段分析、完整核查、复核、整改和输出可以连续完成。
3. 所有数字和状态来自现有 API 与 Demo 数据库。
4. 普通页面只公开 577 项产品口径，不暴露 499、78、6、16 等内部结构数字。
5. 规则、AI、人工三层保持独立。
6. 点击复核队列不会触发 PDF 下载。
7. 自动测试、生产构建、Envision 577 gate 和人工 Demo 验收全部通过。

## 2. 当前实现基线

### 2.1 已有能力

- Next.js App Router、TypeScript、Tailwind、TanStack Query 和 Recharts 已接入。
- 报告上传、重复上传双路径、metadata 确认和八阶段分析已实现。
- 报告 Dashboard、577 项范围分页、双复核队列、追加式人工快照、整改任务和版本化输出已实现。
- AI suggestion 作为独立追加层存在；最终产品 run 当前使用 `confirm_llm=false`。
- Demo 数据库与正式/长期验收数据库已经隔离。
- 前端当前基线为 22 个测试文件、80 项测试、typecheck 和 production build 通过。
- 后端当前基线为 651 项测试通过。

### 2.2 当前体验缺口

- `AppShell` 只有“首页”和“ESG 报告”，缺少当前报告导航和激活状态。
- 首页只提供功能说明，不能直接展示当前报告、关键结果和建议下一步。
- Dashboard 只有四个指标卡，缺少披露结论、三层状态、产品闭环和输出门禁。
- 三栏复核可用，但队列进度、选中状态、分层层级、PDF 工具栏和响应式切换不足。
- 上传、metadata、进度、完整核查、整改和输出的视觉结构尚未统一。
- 加载、空数据、错误和部分失败状态表现不一致。
- `docs/DESIGN.md` 的进度权重说明仍是 AI 阶段加入前的旧表述，需要与当前八阶段实现校准。

## 3. 冻结边界

执行期间禁止修改：

- 577 项产品核查口径。
- `envision-method-v1.1`。
- `envision-result-v1.1`。
- `risk-v2.1`。
- 数据库表结构和 Alembic migration。
- assessment、evidence、applicability 和 review priority 的计算规则。
- 追加式 review snapshot 语义。
- 正式输出门禁。
- 原始报告、标准文件、manifest 和人工复核资产。
- 旧 `review_decisions`、旧 API 和旧前端兼容页面。

外部模型、OCR 和 VLM 默认关闭。自动测试和 Envision gate 禁止携带外部模型、OCR 或 VLM 参数。

## 4. 实施方式

- 使用测试驱动方式：先补失败测试，再做最小实现，再运行相关测试。
- 每个任务只修改本任务列出的文件。
- 每批完成后先执行 `git diff --check`，再提交。
- 产品代码修改期间保持 `main` 分支。
- 所有提交只保存在本地，不 push。
- 遇到停止条件立即暂停，不通过前端伪造数据绕过问题。

## 5. Task 0：冻结基线复核与文档契约校准

**目标：** 在修改页面前证明当前基线可重复，并校准八阶段进度文档。

**修改文件：**

- `docs/DESIGN.md`
- `docs/DEVELOPMENT.md`
- `docs/plan/frontend-demo-experience-design.md`
- `docs/plan/frontend-demo-experience-implementation-plan.md`

### Step 0.1：检查工作区和基线

```powershell
git status --short
git branch --show-current
git log -1 --oneline

cd frontend
pnpm test -- --run
pnpm typecheck
pnpm build
```

期望：

- 分支为 `main`。
- 除已批准的两份前端设计/计划文档外，没有未知改动。
- 前端基线测试、typecheck 和 build 通过。

### Step 0.2：校准八阶段权重说明

以以下现有实现和契约为证据：

- `frontend/components/analysis/progress-model.ts`
- `frontend/components/analysis/progress-model.test.ts`
- `docs/product/api-contract.md`

将 `docs/DESIGN.md` 进度说明校准为：

```text
文件检查 5%
PDF 解析 10%
报告结构识别 5%
requirement 匹配 10%
证据与结论生成 55%
复核优先级计算 5%
AI 辅助分析 5%
结果汇总 5%
```

只修改文档，前端计算和后端阶段行为保持不变。

### Step 0.3：检查文档

```powershell
rg -n "七阶段|七个阶段" docs/DESIGN.md docs/DEVELOPMENT.md docs/plan/frontend-demo-experience-design.md
git diff --check
```

期望：当前产品路径不再使用七阶段旧口径。

### Step 0.4：提交文档批次

```powershell
git add docs/DESIGN.md docs/DEVELOPMENT.md docs/plan/frontend-demo-experience-design.md docs/plan/frontend-demo-experience-implementation-plan.md
git diff --cached --check
git commit -m "docs: plan frontend demo experience optimization"
```

## 6. Task 1：报告中心应用外壳和基础组件

**目标：** 建立统一的侧边导航、当前报告上下文、状态语义和页面容器。

**新增文件：**

- `frontend/components/layout/report-context-nav.tsx`
- `frontend/components/layout/app-shell.test.tsx`
- `frontend/components/ui/metric-card.tsx`
- `frontend/components/ui/status-badge.tsx`
- `frontend/lib/report-route.ts`
- `frontend/lib/report-route.test.ts`

**修改文件：**

- `frontend/components/layout/app-shell.tsx`
- `frontend/app/layout.tsx`
- `frontend/app/globals.css`

### Step 1.1：先写路由解析失败测试

在 `frontend/lib/report-route.test.ts` 覆盖：

```ts
expect(reportIdFromPath("/reports/report-1/dashboard")).toBe("report-1");
expect(reportIdFromPath("/reports/report-1/review")).toBe("report-1");
expect(reportIdFromPath("/reports")).toBeNull();
expect(reportIdFromPath("/runs/run-1")).toBeNull();
```

运行：

```powershell
cd frontend
pnpm test -- lib/report-route.test.ts
```

期望：新测试先失败。

### Step 1.2：实现纯路由解析

在 `frontend/lib/report-route.ts` 只负责从 App Router pathname 中解析当前 `reportId`，不访问浏览器存储，不推断报告状态。

运行同一测试，期望通过。

### Step 1.3：先写应用外壳失败测试

在 `frontend/components/layout/app-shell.test.tsx` 覆盖：

- 全局导航包含“工作台首页”和“ESG 报告”。
- 当前 URL 含 `reportId` 时，通过 `getReport` 显示企业、年份和报告状态。
- 当前报告导航包含报告总览、完整核查、人工复核、整改任务和输出版本。
- 当前路由具有 `aria-current="page"`。
- 根布局使用 `lang="zh-CN"`。
- 全局页面不显示虚构的当前报告。
- 页面不显示数据库名称和内部 499/78 数字。

### Step 1.4：实现报告中心外壳

`ReportContextNav` 作为客户端组件：

- 使用 `usePathname()` 获取当前路径。
- 使用 `reportIdFromPath()` 解析报告 ID。
- 只有解析到报告 ID 时调用 `getReport(reportId)`。
- 加载失败时保留全局导航，并显示简洁的报告上下文错误。
- 当前报告导航使用真实 `reportId` 构造 URL。

`AppShell` 负责：

- 固定侧边栏。
- 桌面和窄屏导航。
- 品牌区。
- 主内容容器。
- 激活状态。

`globals.css` 负责：

- 统一中文字体栈。
- 品牌、边框、背景、优先级和适用性颜色变量。
- 全局 focus ring。
- 减少动态效果偏好。

### Step 1.5：实现基础展示组件

`MetricCard` 和 `StatusBadge` 只接收已格式化的 label、value、tone 和说明，不重新计算业务状态。

### Step 1.6：验证与提交

```powershell
pnpm test -- lib/report-route.test.ts components/layout/app-shell.test.tsx
pnpm typecheck
git diff --check
git add frontend/app/layout.tsx frontend/app/globals.css frontend/components/layout frontend/components/ui frontend/lib/report-route.ts frontend/lib/report-route.test.ts
git commit -m "feat: add report-centered application shell"
```

## 7. Task 2：动态工作台首页

**目标：** 首页直接展示最新报告、产品闭环、真实指标和建议下一步。

**新增文件：**

- `frontend/components/home/home-workspace.tsx`
- `frontend/components/home/home-workspace.test.tsx`
- `frontend/lib/report-next-action.ts`
- `frontend/lib/report-next-action.test.ts`

**修改文件：**

- `frontend/app/page.tsx`

### Step 2.1：先写下一步规则测试

`report-next-action.test.ts` 覆盖：

| 报告状态 | 下一步 |
|---|---|
| 无报告 | 上传第一份报告 |
| metadata 待确认 | 确认报告信息 |
| ready_for_analysis | 启动分析 |
| analyzing | 查看分析进度 |
| analysis_completed | 查看报告总览或进入高优先级复核 |
| high_risk_review_completed | 查看整改任务或输出 |
| formally_exported | 查看输出版本 |

下一步 helper 只转换已有状态，不自行改变报告状态。

### Step 2.2：先写首页失败测试

覆盖：

- 请求 `listReports(1, 1)` 后使用返回顺序中的最新报告。
- 无报告时显示上传入口。
- 有已完成报告时请求 Dashboard。
- 展示 577 项核查范围、披露结论、复核优先级、适用性和高优先级进度。
- 所有链接带真实 `reportId`。
- 不出现 499、78、6、16。
- API 失败时显示可重试错误。
- Dashboard 尚不可用时显示报告状态，不伪造指标。

### Step 2.3：实现动态首页

`HomeWorkspace` 使用 TanStack Query：

1. 请求最新报告。
2. 仅在报告已产生结果时请求 Dashboard。
3. 报告状态为 `analyzing` 时请求现有 `listRuns()`，按 `report_id` 和 active status 定位进度 URL。
4. 根据真实状态生成下一步。
5. 显示六步产品闭环。
6. 显示 AI 边界，不声称当前 run 已启用 AI。

`frontend/app/page.tsx` 只负责渲染 `HomeWorkspace`。

### Step 2.4：验证与提交

```powershell
pnpm test -- lib/report-next-action.test.ts components/home/home-workspace.test.tsx
pnpm typecheck
git diff --check
git add frontend/app/page.tsx frontend/components/home frontend/lib/report-next-action.ts frontend/lib/report-next-action.test.ts
git commit -m "feat: build dynamic ESG report workspace home"
```

## 8. Task 3：报告总览 Dashboard

**目标：** 在一个页面解释 577 核查范围、披露结论、复核优先级、适用性、三层状态和输出门禁。

**新增文件：**

- `frontend/components/analysis/dashboard-distribution.tsx`
- `frontend/components/analysis/dashboard-distribution.test.tsx`

**修改文件：**

- `frontend/components/analysis/report-dashboard.tsx`
- `frontend/components/analysis/report-dashboard.test.tsx`

### Step 3.1：扩展 Dashboard 失败测试

使用真实响应形状覆盖：

- `standard_unit_count=577`。
- `verdict_counts` 转换为已披露、部分披露和待确认。
- `review_priority_counts` 转换为高、中、低优先级。
- `applicability_undetermined_total` 独立显示。
- 高优先级进度显示为 `reviewed/total`。
- `failed_requirement_count>0` 时显示正式输出阻塞。
- 高优先级完成时仍保留“未代表 577 项全部人工确认”的说明。
- 不显示“高风险”。
- Dashboard 返回 `run_id` 时使用 `getRun(run_id)` 展示真实 AI 启用状态和 suggestion 汇总。

### Step 3.2：实现结果分布组件

`DashboardDistribution` 接收后端计数字典，负责：

- 中文标签。
- 数值和比例。
- 空值归零。
- 图形和文字双重表达。

不得将 577 当作独立 assessment 分母来计算优先级比例；优先级比例以计数字典实际总和为分母。

### Step 3.3：重构 Dashboard 页面

页面顺序：

1. 报告标题和 577 核查范围。
2. 高优先级未解决、复核进度、适用性待确认和分析失败指标。
3. 披露结论分布。
4. 复核优先级分布。
5. 规则、AI、人工三层说明。
6. 正式输出门禁。
7. 完整核查、人工复核、整改和输出入口。

### Step 3.4：验证与提交

```powershell
pnpm test -- components/analysis/report-dashboard.test.tsx components/analysis/dashboard-distribution.test.tsx
pnpm typecheck
git diff --check
git add frontend/components/analysis/report-dashboard.tsx frontend/components/analysis/report-dashboard.test.tsx frontend/components/analysis/dashboard-distribution.tsx frontend/components/analysis/dashboard-distribution.test.tsx
git commit -m "feat: present the Envision review dashboard"
```

## 9. Task 4：上传、Metadata 和八阶段进度

**目标：** 统一首次上传、重复上传、信息确认、并发门禁和分析终态体验。

**修改文件：**

- `frontend/components/upload/report-upload-panel.tsx`
- `frontend/components/upload/report-upload-panel.test.tsx`
- `frontend/components/reports/report-list.tsx`
- `frontend/components/reports/report-list.test.tsx`
- `frontend/components/reports/report-metadata-confirmation.tsx`
- `frontend/components/reports/report-metadata-confirmation.test.tsx`
- `frontend/components/analysis/analysis-progress.tsx`
- `frontend/components/analysis/analysis-progress.test.tsx`
- `frontend/components/analysis/progress-model.ts`
- `frontend/components/analysis/progress-model.test.ts`
- `frontend/app/reports/page.tsx`

### Step 4.1：补重复上传和报告列表测试

覆盖：

- `409 duplicate_report` 显示“报告已存在”。
- “查看已有结果”打开响应中的最新 `report_id`。
- “重新上传并分析”使用 `duplicate_policy=create_new`。
- 重新上传失败时保留已有报告。
- 报告列表根据状态进入确认、进度或 Dashboard；存在 `analyzing` 报告时使用现有 `listRuns()` 定位其 active run。
- 普通页面不显示原始 `report_id`。

### Step 4.2：补 active run 门禁测试

在 metadata 组件测试：

- `409 analysis_already_running` 解析 `run_id`。
- 显示“该报告正在分析”。
- 提供“查看分析进度”。
- 不显示通用“分析启动失败”覆盖结构化错误。

只消费现有错误契约，不修改后端门禁。

### Step 4.3：补进度终态和异常测试

覆盖：

- 八阶段顺序固定。
- 权重总和为 100。
- `completed` 和 `partially_completed` 强制 100%。
- 终态停止轮询和旋转图标。
- `partially_completed` 显示失败数与重跑入口。
- `failed` 显示失败阶段。
- 120 秒无有效 stage event 显示中断提示。
- 当前阶段和完成阶段数可见。
- 首次上传及 metadata 页面不显示 577。

### Step 4.4：统一页面视觉

- 报告列表和上传组成清晰的主次区域。
- Metadata 对自动识别值和人工确认做明确区分。
- AI 开关默认关闭，并保持现有数据最小化说明。
- 进度页显示总体百分比、当前阶段、完成阶段数和八阶段列表。
- 完成后显示“查看分析结果”和“进入高优先级复核”。

### Step 4.5：验证与提交

```powershell
pnpm test -- components/upload/report-upload-panel.test.tsx components/reports/report-list.test.tsx components/reports/report-metadata-confirmation.test.tsx components/analysis/analysis-progress.test.tsx components/analysis/progress-model.test.ts
pnpm typecheck
git diff --check
git add frontend/app/reports/page.tsx frontend/components/upload frontend/components/reports frontend/components/analysis/analysis-progress.tsx frontend/components/analysis/analysis-progress.test.tsx frontend/components/analysis/progress-model.ts frontend/components/analysis/progress-model.test.ts
git commit -m "feat: clarify report upload and analysis progress"
```

## 10. Task 5：三栏人工复核工作台

**目标：** 一屏完成队列定位、规则/AI/人工分层、PDF 核证和追加式复核。

**修改文件：**

- `frontend/components/review/reviewer-gate.tsx`
- `frontend/components/review/review-workspace.tsx`
- `frontend/components/review/review-workspace.test.tsx`
- `frontend/components/review/risk-queue.tsx`
- `frontend/components/review/risk-queue.test.tsx`
- `frontend/components/review/assessment-detail.tsx`
- `frontend/components/review/assessment-detail.test.tsx`
- `frontend/components/review/review-editor.tsx`
- `frontend/components/review/review-editor.test.tsx`
- `frontend/components/review/ai-suggestion-panel.tsx`
- `frontend/components/review/ai-suggestion-panel.test.tsx`
- `frontend/components/evidence/pdf-evidence-viewer.tsx`
- `frontend/components/evidence/pdf-evidence-viewer.test.tsx`
- `frontend/components/actions/action-creator.tsx`
- `frontend/components/actions/action-creator.test.tsx`

### Step 5.1：先补工作台结构测试

覆盖：

- 左栏显示队列类型、总数、已复核进度和选中状态。
- 中栏固定顺序为规则判断、AI 辅助建议、人工复核。
- 右栏只在选中 assessment 后显示。
- 直接链接 `assessmentId` 可以打开详情。
- 切换 assessment 后未保存表单和 PDF 页重置。
- 队列、详情、PDF 任一请求失败时其他区域保持可用。
- 窄屏使用“队列 / 判断 / 证据”切换，不丢失当前 selection。

### Step 5.2：补 PDF 失败和工具测试

覆盖：

- 点击证据只更新 `<img src>`。
- 没有 `download` 属性和文件跳转。
- 上一页、下一页、放大、缩小和恢复宽度只改变前端状态。
- 页码下限为 1。
- 通过现有 `getReport(reportId)` 获取 `page_count`，到达末页时禁用“下一页”。
- 图片失败显示重试按钮。
- 点击重试重新创建图片请求。
- 切换 requirement 后缩放恢复到默认值。

### Step 5.3：重构队列

`RiskQueue`：

- 显示真实 `total`。
- 通过现有 `getReportDashboard(reportId)` 显示高优先级 `reviewed/total`，不把待处理队列数量伪装成完整复核进度。
- 高优先级和适用性队列分别显示解释。
- 选中项具有可见状态和 `aria-current`。
- 原因代码统一映射为中文。
- 适用性批量操作保持当前已实现能力。
- 不增加通用 verdict 批量复核。

### Step 5.4：重构详情分层

`AssessmentDetail` 和 `ReviewEditor`：

- 第一层展示不可变 `system_*` 字段。
- 第二层展示 `latest_ai_suggestion`；无建议时显示“本次分析未启用或该项无 AI 建议”。
- 第三层展示当前有效人工结论和表单。
- 所有状态通过 `business-labels.ts` 中文化。
- “快速通过规则结论”和“保存人工修改”保持追加式 snapshot。
- 整改任务创建器收纳为次级区域，避免占据主判断首屏。

### Step 5.5：复核成功后的局部刷新

保持并验证以下查询失效：

```text
review-queue
applicability-queue
assessment-detail
report-assessments
report-dashboard
actions
```

不得通过刷新整个页面掩盖状态同步问题。

### Step 5.6：验证与提交

```powershell
pnpm test -- components/review components/evidence/pdf-evidence-viewer.test.tsx components/actions/action-creator.test.tsx
pnpm typecheck
git diff --check
git add frontend/components/review frontend/components/evidence/pdf-evidence-viewer.tsx frontend/components/evidence/pdf-evidence-viewer.test.tsx frontend/components/actions/action-creator.tsx frontend/components/actions/action-creator.test.tsx
git commit -m "feat: refine the three-column review workbench"
```

## 11. Task 6：完整 577 项核查表

**目标：** 明确 577 总数、上下文项和独立判断项差异，保留真实分页、首尾访问和复核跳转。

### 11.1 本轮范围裁剪

当前 `GET /api/reports/{report_id}/scope-items` 仅支持 `page` 和 `page_size`。前端无法在不下载全部 577 项的情况下提供跨页筛选。

为保持后端冻结并加快 MVP 验收，本任务不修改后端路由、OpenAPI、生成类型或分析服务。跨全部 577 项的全局搜索和组合筛选登记为非阻断后续项。

禁止增加只能筛选当前 50 项的前端伪筛选，避免用户误认为筛选覆盖完整 577 项。

**修改文件：**

- `frontend/components/analysis/assessment-table.tsx`
- `frontend/components/analysis/assessment-table.test.tsx`

### Step 6.1：补完整范围失败测试

覆盖：

- 页面显示“共 577 项”。
- 第一页显示第 1–50 项。
- 末页显示第 551–577 项。
- “首页、上一页、下一页、末页”按真实分页请求工作。
- 切换页面后保持 requirement 排序。
- 独立判断项显示中文 verdict、复核优先级、复核状态和证据页。
- 独立判断项可以进入对应复核详情。
- 上下文项显示“已纳入相关判断”，没有伪 verdict、priority、review status 或复核链接。
- 加载失败显示明确错误，不显示空白表格。
- API 返回空范围时显示明确空状态。
- 页面不显示 499、78、6 或 16 等内部数字。

运行：

```powershell
cd frontend
pnpm test -- components/analysis/assessment-table.test.tsx
```

期望：新测试先失败。

### Step 6.2：优化完整核查表

- 页面标题固定为“完整 GRI 核查范围”。
- 总数和当前范围同时可见。
- 保留真实服务端分页，不一次请求全部 577 项。
- 表头、状态标签、行间距和上下文项层级与报告中心视觉一致。
- 复核链接保留 `assessmentId`，并正确编码。
- 表格横向滚动只作用于较窄视口。

### Step 6.3：验证与提交

```powershell
cd frontend
pnpm test -- components/analysis/assessment-table.test.tsx
pnpm typecheck
git diff --check
git add frontend/components/analysis/assessment-table.tsx frontend/components/analysis/assessment-table.test.tsx
git commit -m "feat: refine the complete GRI scope table"
```

## 12. Task 7：整改任务和输出版本

**目标：** 让闭环最后两步具有清晰状态、关联来源和输出门禁。

**修改文件：**

- `frontend/app/reports/[reportId]/actions/page.tsx`
- `frontend/components/actions/action-list.tsx`
- `frontend/components/actions/action-list.test.tsx`
- `frontend/app/reports/[reportId]/exports/page.tsx`
- `frontend/components/exports/export-versions.tsx`
- `frontend/components/exports/export-versions.test.tsx`

### Step 7.1：补整改任务测试

覆盖：

- 空状态引导用户返回复核工作台。
- 每个任务显示标题、关联 requirement、优先级、负责人、截止日期和状态；关联 requirement 通过现有 `getAssessmentDetail(reportId, assessment_id)` 获取，不显示内部 assessment ID。
- 更新状态时要求变更说明。
- 成功后只刷新当前报告的 actions。
- 更新失败时保留用户输入。
- 不声称 `actions_xlsx` 已可用。

### Step 7.2：补输出版本测试

覆盖：

- 草稿和正式版本明确区分。
- `analysis_incomplete` 显示失败数量。
- `high_risk_review_incomplete` 文案改为“高优先级复核未完成”。
- review scope 说明高优先级完成不代表 577 项全部人工确认。
- 历史版本显示版本号、状态、创建人和时间。
- 页面不提供尚未实现的单文件下载按钮。

### Step 7.3：实现统一页面结构

- 整改任务使用状态摘要和任务卡片。
- 输出页面先展示门禁说明，再展示生成操作和历史版本。
- 生成中禁用重复提交。
- 错误保持在操作附近。

### Step 7.4：验证与提交

```powershell
cd frontend
pnpm test -- components/actions/action-list.test.tsx components/exports/export-versions.test.tsx
pnpm typecheck
git diff --check
git add -- 'frontend/app/reports/[reportId]/actions/page.tsx' 'frontend/app/reports/[reportId]/exports/page.tsx' frontend/components/actions/action-list.tsx frontend/components/actions/action-list.test.tsx frontend/components/exports/export-versions.tsx frontend/components/exports/export-versions.test.tsx
git commit -m "feat: complete remediation and export presentation"
```

## 13. Task 8：响应式、错误状态和前端全量回归

**目标：** 统一所有页面的加载、空数据、错误、键盘操作和三档视口。

**修改文件：**

- `frontend/app/globals.css`
- Task 1–7 中实际涉及的组件和测试
- `docs/DEVELOPMENT.md`

### Step 8.1：补缺失的错误状态测试

逐页检查并补测试：

- 首页 API 失败。
- 报告列表为空。
- Dashboard 无 run 或加载失败。
- 完整核查 409/空结果。
- 复核队列为空。
- PDF 加载失败和重试。
- 整改任务为空。
- 输出列表为空和门禁失败。

### Step 8.2：响应式检查

设计行为：

- 1440px：完整侧栏和三栏复核。
- 1024px：收窄侧栏，复核工作台通过页签切换 PDF。
- 768px：侧栏折叠，表格横向滚动。

不新增只为演示存在的虚拟数据或假动画。

### Step 8.3：可访问性检查

- 当前导航具有 `aria-current`。
- 所有图标按钮具有可读名称。
- 状态不只依赖颜色。
- 表单标签与控件关联。
- 错误信息使用 `role="alert"`。
- 键盘焦点可见。
- `prefers-reduced-motion` 生效。

### Step 8.4：前端串行全量

```powershell
cd frontend
pnpm test -- --run
pnpm typecheck
pnpm build
```

必须串行执行，避免 `.next/types` 与 build 竞争。

### Step 8.5：更新开发文档并提交

在 `docs/DEVELOPMENT.md` 增加：

- 前端演示主路径。
- 三个验收视口。
- Demo 数据库确认方式。
- 普通 Edge/Chrome 人工验收要求。
- 发现问题记录模板。

```powershell
git diff --check
git add frontend docs/DEVELOPMENT.md
git commit -m "test: harden frontend demo acceptance states"
```

## 14. Task 9：Demo 人工产品验收

**目标：** 在隔离 Demo 环境完成真实 Envision 2024 中文报告闭环。

### Step 9.1：启动 Demo 数据库和后端

在同一个 PowerShell 终端设置 Demo 环境：

```powershell
docker compose up -d postgres

$env:APP_ENV="demo"
$env:DATABASE_URL="postgresql+psycopg://esg_agent:esg_agent@localhost:5432/esg_agent_demo"
$env:UPLOAD_DIR="backend/data/runtime/demo/uploads"
$env:DERIVED_DIR="backend/data/runtime/demo/derived"

cd backend
uv run --no-sync alembic upgrade head
uv run --no-sync uvicorn src.main:app --port 8000
```

启动前通过后端健康接口和只读数据库查询确认实际连接为 `esg_agent_demo`。发现连接到 `esg_agent` 时立即停止。

### Step 9.2：启动前端

另开终端：

```powershell
cd frontend
pnpm dev
```

验收地址：

- `http://localhost:3000`
- `http://localhost:8000/docs`

### Step 9.3：普通浏览器主流程

使用独立 Edge 或 Chrome，不使用 Codex 内置浏览器。

按顺序验证：

1. 首页显示最新 Demo 报告或空状态。
2. 上传 Envision 2024 中文报告。
3. 核对企业、年度和语言；必要时人工修正。
4. AI 保持关闭，启动分析。
5. 八阶段真实运行，完成后 100% 且停止转圈。
6. 点击“查看分析结果”。
7. Dashboard 显示 577 和当前真实分布。
8. 完整核查总数、首尾分页和复核跳转正确。
9. 进入高优先级复核，点击队列不会下载 PDF。
10. 核对规则、AI 空状态和人工三层。
11. 提交一条人工快照并验证队列和 Dashboard 更新。
12. 创建或查看整改任务。
13. 生成草稿并验证 review scope。
14. 重复上传相同 PDF，分别验证查看已有报告和重新上传并分析。
15. 刷新、返回和直接访问 URL 后状态恢复。

### Step 9.4：三档视口

- 1440×900：完整演示。
- 1920×1080：投屏检查。
- 1024×768：窄屏兼容。

### Step 9.5：记录问题

统一格式：

```text
编号：
严重程度：P0 / P1 / P2 / P3
前置条件：
复现步骤：
实际结果：
期望结果：
影响范围：
建议修复：
状态：
```

处理规则：

- P0/P1：修复后重跑相关测试、前端全量和对应人工路径。
- P2：影响主演示路径时修复；不影响时登记为已知限制。
- P3：记录为后续优化，不阻塞本轮 MVP。

## 15. Task 10：最终自动门禁和 Envision 577 gate

**目标：** 证明前端工作没有破坏冻结后端。

### Step 10.1：后端全量

```powershell
cd backend
uv run --no-sync pytest -q --basetemp=../tmp/pytest-frontend-demo-final
```

期望：不少于当前 651 项，0 failed、0 error。

### Step 10.2：前端全量

```powershell
cd frontend
pnpm test -- --run
pnpm typecheck
pnpm build
```

期望：全部通过，测试数不得低于计划执行前基线。

### Step 10.3：无外部模型 Envision v3 gate

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

硬门禁：

```text
standard_unit_count=577
independent_assessment_count=499
context_only_count=78
method_pending_count=0
unique_assessment_requirement_id_count=499
global_fallback_count=0
new_false_disclosed_count=0
new_wrong_source_page_count=0
audit.ok=true
audit.errors=[]
audit.warnings=[]
```

该命令不得带 LLM、OCR 或 VLM 参数。

### Step 10.4：最终 Git 检查

```powershell
git status --short
git diff --check
git log --oneline --decorate -12
```

确认：

- 所有计划内改动已按批次 commit。
- 没有 `.env`、密钥、外部模型响应或 Demo runtime 文件进入提交。
- 没有修改原始报告和标准资产。
- 没有自动 push。

## 16. 验收通过标准

全部满足后，前端演示体验验收才可以完成：

- 首页、Dashboard 和三栏复核符合已确认设计。
- 上传到版本输出主路径连续可用。
- 重复上传双路径和 active run 门禁可理解。
- 分析终态不转圈。
- 577 完整核查可分页、可访问首尾项、可进入复核。
- PDF 在页面内显示，不触发下载。
- 规则、AI、人工三层独立。
- 高优先级完成文案不暗示全部 577 项人工确认。
- Demo 数据库连接正确。
- 前端测试、typecheck、build 全部通过。
- 后端全量测试通过。
- Envision 577 gate 通过。
- P0/P1 为 0。

## 17. 停止条件

出现以下任一情况立即停止执行并汇报：

- 实际连接数据库不是 `esg_agent_demo`，且即将进行人工写入。
- 页面数据与冻结 Envision 基线不一致。
- 前端体验改动需要新增后端接口、数据库迁移或修改分析规则。
- 需要修改 577、499/78 结构或 risk-v2.1。
- 人工复核可能覆盖历史 snapshot。
- 外部模型、OCR 或 VLM 被意外调用。
- 原始报告、标准文件或人工复核资产可能被覆盖。
- 发现用户未授权的工作区改动与计划文件重叠。
- P0/P1 无法在当前前端范围内修复。

## 18. 明确不实施的规划项

本计划不实现：

- 通用 verdict 批量复核。
- 独立 report 或 assessment reopen。
- report 级审计页面。
- 单 export 文件下载 API。
- `actions_xlsx` 完整整改清单。
- 多企业对标、ESRS、舆情或行业模块。
- 账号和权限系统。
- 自动 Demo reset 按钮。
- 完整核查表跨 577 项的全局搜索和组合筛选。
- Goldwind 新一轮优化。
