# 侧边栏图片显示一致性修复实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**目标：** 让报告工作区六个桌面端页面的侧边栏图片保持相同裁切，并消除完整核查加载前后的图片跳变。

**架构：** 保留 `AppShell` 的 Grid 外层结构，由 `aside` 继续承担侧栏列占位和边框。新增视口高度的 sticky 内层容器，统一承载图片、遮罩和导航，使图片尺寸只取决于桌面视口，不再取决于右侧主内容高度。

**技术栈：** Next.js 16、React 19、Tailwind CSS、Vitest、Testing Library

---

## 文件结构

- 修改 `frontend/components/layout/app-shell.test.tsx`：增加侧栏视口容器的回归断言。
- 修改 `frontend/components/layout/app-shell.tsx`：增加固定视口高度的 sticky 内层容器。
- 不修改后端、API、业务组件、图片素材和全局样式。

### Task 1：用回归测试锁定侧栏视口容器

**Files:**
- Test: `frontend/components/layout/app-shell.test.tsx`

- [ ] **Step 1：写入当前实现无法通过的回归测试**

在 `describe("AppShell")` 中增加：

```tsx
it("keeps the desktop sidebar artwork sized to the viewport", () => {
  renderWithQuery(<AppShell><p>页面内容</p></AppShell>);

  const sidebarNavigation = screen.getByRole("navigation", { name: "页面导航" });
  const sidebar = sidebarNavigation.closest("aside");

  expect(sidebar).not.toBeNull();
  expect(sidebar?.firstElementChild).toHaveClass(
    "sticky",
    "top-16",
    "h-[calc(100vh-4rem)]",
    "overflow-hidden",
  );
});
```

- [ ] **Step 2：运行目标测试并确认预期失败**

在 `frontend` 目录运行：

```powershell
npm test -- components/layout/app-shell.test.tsx
```

预期：新增用例失败，失败原因是 `aside` 的第一个子元素尚未具备 `sticky`、`top-16`、`h-[calc(100vh-4rem)]` 和 `overflow-hidden` 类。

### Task 2：实现视口高度固定裁切

**Files:**
- Modify: `frontend/components/layout/app-shell.tsx:47-61`
- Test: `frontend/components/layout/app-shell.test.tsx`

- [ ] **Step 1：写入最小实现**

将现有侧栏改为以下结构；图片参数、遮罩参数和导航内容保持原值：

```tsx
<aside className="hidden min-h-[calc(100vh-4rem)] border-r border-border bg-white lg:block">
  <div className="sticky top-16 h-[calc(100vh-4rem)] overflow-hidden">
    <Image
      src="/visuals/sidebar-renewable-energy.webp"
      alt=""
      aria-hidden="true"
      fill
      sizes="236px"
      className="pointer-events-none object-cover object-[88%_58%] opacity-40 brightness-95 saturate-125 contrast-125"
    />
    <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(180deg,rgba(255,255,255,0.72)_0%,rgba(255,255,255,0.55)_32%,rgba(255,255,255,0.40)_62%,rgba(236,253,245,0.30)_100%)]" />
    <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_76%_10%,rgba(20,184,166,0.10),transparent_38%),radial-gradient(circle_at_25%_86%,rgba(16,185,129,0.10),transparent_34%)]" />
    <div className="relative px-3 py-5">
      <ReportContextNav />
    </div>
  </div>
</aside>
```

- [ ] **Step 2：运行目标测试并确认通过**

在 `frontend` 目录运行：

```powershell
npm test -- components/layout/app-shell.test.tsx
```

预期：`app-shell.test.tsx` 全部通过，无测试警告。

- [ ] **Step 3：检查修改范围并提交代码**

```powershell
git diff --check
git diff -- frontend/components/layout/app-shell.tsx frontend/components/layout/app-shell.test.tsx
git add -- frontend/components/layout/app-shell.tsx frontend/components/layout/app-shell.test.tsx
git commit -m "fix: keep sidebar artwork viewport-sized"
```

预期：提交仅包含共享布局组件及其测试，不包含 `frontend/next-env.d.ts`。

### Task 3：执行前端门禁和实际页面视觉验收

**Files:**
- Verify: `frontend/components/layout/app-shell.tsx`
- Verify: `frontend/components/layout/app-shell.test.tsx`

- [ ] **Step 1：运行前端全量测试**

在 `frontend` 目录运行：

```powershell
npm test
```

预期：全部测试文件和用例通过。

- [ ] **Step 2：运行类型检查**

```powershell
npm run typecheck
```

预期：退出码为 0，无 TypeScript 错误。

- [ ] **Step 3：运行生产构建**

```powershell
npm run build
```

预期：退出码为 0，Next.js 生产构建完成。

- [ ] **Step 4：执行桌面端六页面对比**

使用同一份已完成分析的报告，依次打开：

```text
/reports/{reportId}/dashboard
/reports/{reportId}/assessments
/reports/{reportId}/review
/reports/{reportId}/actions
/reports/{reportId}/exports
/reports/{reportId}/audit
```

逐页确认：

- 侧栏均显示同一张光伏图片的同一裁切位置和透明度。
- 完整核查从加载状态切换到 577 项表格后，侧栏图片不重新裁切。
- 页面滚动时侧栏导航保持在顶部栏下方，链接可见。
- 当前页面高亮与报告上下文信息保持正确。

- [ ] **Step 5：确认工作区边界**

```powershell
git status --short
git log -3 --oneline
```

预期：修复提交存在；`frontend/next-env.d.ts` 的既有未提交改动仍被保留，没有混入本次提交。
