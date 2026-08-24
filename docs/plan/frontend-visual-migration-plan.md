# 前端视觉升级与 esg-dashboard 资产迁移实施计划

## 1. 背景与目标

本项目前端（`frontend/`，Next.js 16 + React 19 + Tailwind 3.4 + React Query + recharts）已实现完整业务闭环（报告上传 → 确认 → 分析 → 核查 → 复核 → 整改 → 导出 → 审计），但视觉层较朴素：无骨架屏与动效体系、图表仅一个柱状图、状态标签映射多处重复、无统一按钮组件。

参考仓库 `../esg-dashboard`（Vite SPA + React 19 + Tailwind 3.4 + ECharts 6，纯静态数据）具备成熟的视觉体系：语义色板、卡片语言、动效、count-up 指标卡、骨架屏、空状态组件。两边技术栈高度兼容，可低成本迁移。

**目标**：将 esg-dashboard 的视觉资产与设计语言迁移进本项目，提升美观程度，保持现有业务逻辑不变。

**约束**：
- 原仓库全程只读，不得删除、覆盖或回退其中任何文件。
- 品牌资产（envision wordmark、视觉图）已获用户确认可以搬运。
- 最小改动原则：不改动业务逻辑、API 对接层、测试语义；视觉升级以增量方式落地。
- 本项目是工作台工具，重装饰（玻璃拟态 hero）只用于首页与报告 dashboard 头部，业务页保持清爽。

## 2. 迁移资产清单（来源 → 目标）

| 来源（esg-dashboard） | 目标（esg-agent） | 说明 |
|---|---|---|
| `src/lib/chartTheme.ts` | `frontend/lib/chart-theme.ts` | 语义色板 + ECharts 统一样式 |
| `src/index.css` 组件层与 keyframes | 并入 `frontend/app/globals.css` | `.panel`/`.subpanel`/动效/reduced-motion 降级 |
| `src/components/EChart.tsx` | `frontend/components/charts/echart.tsx` | 加 `'use client'`，按需引入 |
| `src/components/Panel.tsx` | `frontend/components/ui/panel.tsx` | 渐变竖条标题卡片容器 |
| `src/components/MetricCard.tsx` + `src/hooks/useCountUp.ts` | `frontend/components/ui/`、`frontend/lib/hooks/` | count-up + sparkline 指标卡 |
| `src/components/Badge.tsx` | 合并进 `frontend/components/ui/status-badge.tsx` | 语义徽章，与现有 tone 体系对齐 |
| `src/components/Skeleton.tsx`、`EmptyState.tsx`、`BackToTop.tsx` | `frontend/components/ui/` | 骨架屏、空状态、回顶 |
| `src/components/Select.tsx` | `frontend/components/ui/` | 统一下拉样式 |
| `public/brand/`、`public/visuals/` | `frontend/public/brand/`、`frontend/public/visuals/` | 品牌与视觉图资产 |
| `src/components/AppShell.tsx` | 参考改造 `frontend/components/layout/app-shell.tsx` | 改 next/link + usePathname，保留现有导航结构 |

不迁移：zustand、HashRouter、zod 静态数据契约、build-full-demo-dataset 脚本（本项目数据走真实后端 API）。

## 3. 分阶段实施

### 阶段 1：设计基建（收益最大，先做）

1. **依赖**：`frontend/package.json` 增加 `echarts`（v6），pnpm install。
2. **色板与主题**：复制 `chartTheme.ts` → `frontend/lib/chart-theme.ts`；将其语义色（emerald/rose/amber/sky + gapLevel）与本项目 `tailwind.config.ts` 的 HSL 变量对齐，补 `--gap-*` 等业务色到 `globals.css`。
3. **组件层样式**：把 `src/index.css` 的 `@layer components`（`.panel`、`.panel-interactive`、`.subpanel`、`.subpanel-accent`）与 keyframes（`.animate-fade-in`、`.animate-shimmer`、`.progress-sheen`）并入 `frontend/app/globals.css`，保留 `prefers-reduced-motion` 降级。
4. **基础组件迁移**：Panel、MetricCard、useCountUp、Skeleton、EmptyState、Select、BackToTop 迁入对应目录，加 `'use client'`，import 路径改为本项目别名（`@/`）；Badge 与现有 `status-badge.tsx` 合并，不新增并行体系。
5. **验证**：`pnpm lint` + `pnpm test` + `pnpm build` 全绿；写一个 `ui/panel.test.tsx` 级别的最小冒烟测试（与项目现有测试风格一致）。

### 阶段 2：图表层升级

1. `EChart.tsx` 迁入 `frontend/components/charts/echart.tsx`，echarts 按需注册（Bar/Line/Pie/Radar）。
2. 报告 dashboard 页（`app/reports/[reportId]/dashboard`）新增分布饼图/雷达图，数据来源沿用现有 API 响应，不新增端点。
3. 现有 recharts 柱状图 `charts/disclosure-summary-chart.tsx` 暂保留；待 ECharts 稳定后再评估是否统一切换（不在本计划范围内强制替换）。

### 阶段 3：页面美化与布局升级

1. **AppShell**：参考 esg-dashboard 侧边栏 + hero 思路改造 `app-shell.tsx`：桌面端侧边栏加品牌视觉图与渐变遮罩；首页/报告 dashboard 头部加 hero 视觉；业务页保持现有简洁头部。路由改用 `next/link` + `usePathname`。
2. **首页工作台 `home-workspace.tsx`**：指标卡换成新 MetricCard（count-up），加载态换骨架屏，空态换 EmptyState。
3. **报告 dashboard**：应用 Panel/MetricCard/新图表。
4. **静态资产**：复制 `public/brand/`、`public/visuals/*.webp` 到 `frontend/public/` 对应目录。
5. **顺手治理（仅视觉相关）**：
   - 统一 `reportStatusLabels` 等状态标签映射到 `lib/business-labels.ts`，删除组件内重复定义；
   - 统一字体定义（`tailwind.config.ts` 与 `globals.css` 取一份，中文系统字体栈为准）；
   - 抽 `ui/button.tsx` 统一按钮样式（variant: primary/secondary/ghost/danger）。

### 阶段 4：验收

1. 全量测试：`pnpm test`、`pnpm build`。
2. 人工走查核心路径：报告上传 → dashboard → 复核 → 导出，确认无视觉回归；主观视觉确认由用户完成，不替代自动工程门禁。
3. 检查 reduced-motion、移动端断点（侧边栏折叠）表现。
4. 更新 `docs/DESIGN.md` 前端章节；组件目录仍符合现有约定，无需修改 `AGENTS.md`。

## 4. 风险与对策

- **动效过度**：业务页只用 fade-in 与卡片悬浮，玻璃拟态/Ken Burns 仅限首页与 dashboard 头部；全部动效带 reduced-motion 降级。
- **图表双库并存**：recharts 与 ECharts 短期并存增加包体积，可接受；长期再统一。
- **样式冲突**：esg-dashboard 的 `.panel` 类名与本项目现有组件无冲突（本项目用 Tailwind 内联类），迁移时全局搜索确认。
- **品牌资产**：已获授权搬运；`docs/ASSETS.md` 需登记来源与用途。

## 5. 执行结果

本计划已获批准并一次性执行。代码实现提交为 `95f06f1`。

| 阶段 | 状态 | 结果 |
|---|---|---|
| 阶段 1：设计基建 | 完成 | ECharts 依赖、主题、组件层样式、基础 UI 组件、ESLint 9 配置和组件测试已落地。 |
| 阶段 2：图表升级 | 完成 | 报告总览新增披露结论饼图和复核工作量雷达图，数据只派生自现有 dashboard API。 |
| 阶段 3：页面与布局 | 完成 | 首页、报告总览、侧边栏、指标卡、骨架屏、状态标签、按钮和静态视觉资产完成迁移。 |
| 阶段 4：工程验收 | 完成 | lint、39 个测试文件/139 项测试、typecheck、production build 和本地 HTTP 冒烟通过。 |
| 阶段 4：主观视觉确认 | 待用户确认 | 2026-08-24 已补做桌面工作台、报告总览和 390px 窄屏自动浏览器复验；工程可读性通过，最终主观视觉效果仍待用户确认。 |

受控调整：首次无报告场景保留带上传入口的业务引导 hero，未替换为通用 `EmptyState`；`EmptyState` 组件继续服务列表或筛选空态。该调整保留了首屏任务引导，不改变业务状态语义。

完整工程验收见 `docs/product/frontend-visual-migration-acceptance.md`。主观视觉确认完成后即可冻结本轮视觉基线；后续视觉迭代应以实际使用问题为触发条件，避免继续扩大当前发布范围。

## 6. 轻度清晰化修正（2026-08-24）

用户在当前视觉基线上选择“轻度增强”。本次只提高桌面侧边栏、工作台两种状态主图和报告总览主图的 opacity，并同步降低白色渐变遮罩 alpha；图片源文件、定位、布局、Ken Burns 动效和业务行为保持不变。

实施使用视觉参数回归测试锁定四种状态。目标测试先因旧参数产生 4 个预期失败，最小修改后 3 个目标测试文件、9 项测试通过。完整门禁为 39 个测试文件、150 项测试通过，typecheck 和 production build 通过；lint 保持 0 error、2 个既有 warning。桌面浏览器核查确认图片辨识度提高且文字、导航、徽章、按钮可读，390px 窄屏仍使用移动导航并隐藏桌面侧边栏。

本次调整没有触及后端、API、业务语义或图片资产，不需要更新技术架构基线。详细参数和执行记录见 `docs/plan/frontend-visual-clarity-light-adjustment-plan.md`。

后续主观反馈认为轻度档仍偏浅，尤其是首页横向主图。经用户批准，侧边栏的白色渐变和绿色光晕、工作台两种状态及报告总览的线性渐变均已移除，共删除 5 个遮罩元素；图片 opacity 保持轻度档参数。目标测试、完整前端门禁及桌面/390px 浏览器核查通过，业务和技术边界保持不变。
