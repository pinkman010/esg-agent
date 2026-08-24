# 前端背景图轻度清晰化实施计划

> **供代理执行：** 必须使用 `superpowers:executing-plans` 按任务逐项执行；实施遵循测试先行，步骤使用复选框跟踪。

**目标：** 在不改变布局、图片资产和业务行为的前提下，轻度提高桌面侧边栏、工作台主图与报告总览主图的可见度，同时维持文字可读性。

**架构：** 保留现有 `next/image`、图片定位、亮度、饱和度和 Ken Burns 动效，只调整组件内 Tailwind opacity 与渐变遮罩 alpha。使用现有组件测试锁定视觉参数，先观察旧参数导致断言失败，再做最小实现。

**技术栈：** Next.js 16、React 19、Tailwind CSS 3.4、Vitest、Testing Library。

---

## 1. 文件范围

- 修改 `frontend/components/layout/app-shell.tsx`：桌面侧边栏背景图透明度与白色渐变遮罩。
- 修改 `frontend/components/layout/app-shell.test.tsx`：锁定侧边栏轻度清晰化参数。
- 修改 `frontend/components/home/home-workspace.tsx`：首次使用和已有报告两种工作台主图透明度与遮罩。
- 修改 `frontend/components/home/home-workspace.test.tsx`：分别锁定两种工作台状态的视觉参数。
- 修改 `frontend/components/analysis/report-dashboard.tsx`：报告总览头图透明度与遮罩。
- 修改 `frontend/components/analysis/report-dashboard.test.tsx`：锁定报告总览头图视觉参数。
- 更新 `docs/plan/frontend-visual-migration-plan.md`：记录本次轻度修正的执行结果和边界。

本次不修改 `frontend/public/visuals/` 图片资产，不修改布局、字体、动效、API、后端、数据库和业务状态语义。

## 2. 轻度档参数

| 区域 | 图片 opacity | 渐变遮罩 alpha |
|---|---:|---|
| 桌面侧边栏 | `0.40 → 0.50` | `0.72/0.55/0.40/0.30 → 0.64/0.48/0.34/0.26` |
| 工作台首次使用主图 | `0.22 → 0.28` | `0.88/0.60/0.32 → 0.82/0.54/0.28` |
| 工作台已有报告主图 | `0.18 → 0.25` | `0.90/0.62/0.34 → 0.84/0.56/0.30` |
| 报告总览主图 | `0.16 → 0.23` | `0.88/0.58/0.30 → 0.82/0.52/0.27` |

## 3. 实施任务

### Task 1：测试先行锁定轻度档

**文件：**
- 修改：`frontend/components/layout/app-shell.test.tsx`
- 修改：`frontend/components/home/home-workspace.test.tsx`
- 修改：`frontend/components/analysis/report-dashboard.test.tsx`

- [x] **Step 1：为侧边栏增加失败断言**

在现有桌面侧边栏测试中取得渲染容器，定位 `sidebar-renewable-energy` 图片和其后的遮罩元素，断言：

```tsx
expect(sidebarArtwork).toHaveClass("opacity-50");
expect(sidebarArtwork?.nextElementSibling).toHaveClass(
  "bg-[linear-gradient(180deg,rgba(255,255,255,0.64)_0%,rgba(255,255,255,0.48)_32%,rgba(255,255,255,0.34)_62%,rgba(236,253,245,0.26)_100%)]",
);
```

- [x] **Step 2：为工作台两种状态增加失败断言**

首次使用状态断言 `opacity-[0.28]` 与 `0.82/0.54/0.28` 遮罩；已有报告状态断言 `opacity-[0.25]` 与 `0.84/0.56/0.30` 遮罩。

- [x] **Step 3：为报告总览增加失败断言**

定位 `module-policy-disclosure` 图片，断言 `opacity-[0.23]` 与 `0.82/0.52/0.27` 遮罩。

- [x] **Step 4：运行目标测试并确认按预期失败**

```powershell
cd frontend
pnpm test components/layout/app-shell.test.tsx components/home/home-workspace.test.tsx components/analysis/report-dashboard.test.tsx
```

预期：测试因仍存在旧 opacity 或旧渐变遮罩而失败；不得出现语法错误、网络错误或测试环境错误。

### Task 2：最小修改实现轻度档

**文件：**
- 修改：`frontend/components/layout/app-shell.tsx`
- 修改：`frontend/components/home/home-workspace.tsx`
- 修改：`frontend/components/analysis/report-dashboard.tsx`

- [x] **Step 1：调整侧边栏**

把图片类 `opacity-40` 改为 `opacity-50`，把遮罩 alpha 改为 `0.64/0.48/0.34/0.26`；保留定位、亮度、饱和度、对比度和径向绿色装饰。

- [x] **Step 2：调整工作台主图**

首次使用状态改为 `opacity-[0.28]` 和 `0.82/0.54/0.28` 遮罩；已有报告状态改为 `opacity-[0.25]` 和 `0.84/0.56/0.30` 遮罩。保留内容层 `relative` 和现有 Ken Burns 动效。

- [x] **Step 3：调整报告总览主图**

改为 `opacity-[0.23]` 和 `0.82/0.52/0.27` 遮罩；保留按钮、状态徽章和文字层级。

- [x] **Step 4：运行目标测试并确认通过**

```powershell
cd frontend
pnpm test components/layout/app-shell.test.tsx components/home/home-workspace.test.tsx components/analysis/report-dashboard.test.tsx
```

预期：3 个测试文件全部通过。

### Task 3：视觉和工程门禁

**文件：**
- 更新：`docs/plan/frontend-visual-migration-plan.md`

- [x] **Step 1：浏览器核查**

在桌面宽度核查工作台首页、报告总览和带报告上下文的侧边栏，确认图片可辨识度提高，标题、按钮、导航和指标仍清晰；窄屏确认桌面侧边栏隐藏逻辑未改变。

- [x] **Step 2：运行完整前端门禁**

```powershell
cd frontend
pnpm test
pnpm lint
pnpm typecheck
pnpm build
```

预期：全量测试、类型检查和生产构建通过；lint 不新增 error 或 warning。

- [x] **Step 3：记录结果**

在 `docs/plan/frontend-visual-migration-plan.md` 中追加“轻度清晰化修正”结果，记录改动边界、测试结果和主观视觉限制。

- [x] **Step 4：分批提交**

```powershell
git add docs/plan/frontend-visual-clarity-light-adjustment-plan.md
git commit -m "docs: plan light visual clarity adjustment"

git add frontend/components/layout/app-shell.tsx frontend/components/layout/app-shell.test.tsx frontend/components/home/home-workspace.tsx frontend/components/home/home-workspace.test.tsx frontend/components/analysis/report-dashboard.tsx frontend/components/analysis/report-dashboard.test.tsx docs/plan/frontend-visual-migration-plan.md
git commit -m "style: improve background image clarity"
```

`首页.png` 属于用户未跟踪文件，不纳入任何提交。

## 4. 终止条件

- 只实施轻度档，不继续提升到中度档。
- 不替换或锐化图片源文件。
- 不因本次视觉修正改动业务逻辑、API 或后端。
- 自动门禁通过后交付用户做主观确认；主观确认只判断清晰度和可读性，不替代工程测试。

## 5. 执行结果

- 目标测试先观察到 3 个文件中的 4 个视觉参数断言按预期失败；完成最小修改后，3 个文件、9 项测试全部通过。
- 桌面浏览器核查覆盖工作台和报告总览：侧边栏、主图、标题、按钮、状态徽章和正文保持可读；轻度档没有改变布局层级。
- 390px 窄屏核查确认桌面侧边栏继续隐藏，移动端主导航继续显示。
- 完整前端门禁通过：39 个测试文件、150 项测试，typecheck 和 production build 通过；lint 为 0 error、2 个既有 warning，本次未新增 warning。
- 本次没有修改图片资产、后端、API、业务状态或数据库；`首页.png` 保持用户未跟踪文件状态。
