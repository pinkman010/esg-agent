# 报告工作区统一主图头部实施计划

> **执行代理要求：** 必须使用 `superpowers:executing-plans` 在当前窗口逐项执行，并使用 `superpowers:test-driven-development` 先写失败测试。步骤使用复选框跟踪。

**目标：** 为完整核查、人工复核、整改任务、输出版本和审计时间线增加统一的紧凑静态主图头部，同时让报告总览复用同一个组件并保留现有动效。

**架构：** 新增无业务状态的 `ReportPageHero` 展示组件，由页面或业务组件传入标题、说明、图片、状态和操作插槽。报告总览显式启用 Ken Burns；五个业务页面保持静态。现有查询、列表、复核、整改、输出和审计组件继续承担原职责。

**技术栈：** Next.js 16、React 19、TypeScript 5.9、Tailwind CSS 3.4、Next Image、Vitest、Testing Library。

---

## 文件结构

- 新增 `frontend/components/layout/report-page-hero.tsx`：统一报告工作区主图头部的布局、图片透明度、动画开关和可访问性。
- 新增 `frontend/components/layout/report-page-hero.test.tsx`：锁定共享组件的静态默认值、动效开关、插槽和无遮罩基线。
- 修改 `frontend/components/analysis/report-dashboard.tsx`：把现有报告总览头部迁移到共享组件。
- 修改 `frontend/components/analysis/report-dashboard.test.tsx`：确认报告总览迁移后视觉参数和业务入口不变。
- 修改 `frontend/components/analysis/assessment-table.tsx`：完整核查接入披露文档主图并保留动态总数。
- 修改 `frontend/components/analysis/assessment-table.test.tsx`：锁定完整核查主图和静态行为。
- 修改 `frontend/components/review/reviewer-gate.tsx`：填写复核人和三栏工作台共享人工复核主图。
- 修改 `frontend/components/review/reviewer-gate.test.tsx`：锁定人工复核图片、标题和复核人空值行为。
- 修改 `frontend/components/review/review-workspace.tsx`：移除加入头部后不再合适的整视口最小高度。
- 修改 `frontend/app/reports/[reportId]/actions/page.tsx`：整改任务接入监控主图。
- 修改 `frontend/app/reports/[reportId]/exports/page.tsx`：输出版本接入披露文档主图。
- 修改 `frontend/app/reports/[reportId]/audit/page.tsx`：审计时间线接入监控主图，保证加载和错误态也保留页面头部。
- 修改 `frontend/components/audit/report-audit-timeline.tsx`：删除已迁移到页面层的重复标题。
- 新增 `frontend/app/reports/[reportId]/report-workspace-pages.test.tsx`：锁定整改、输出和审计三个路由的标题与图片映射。
- 修改 `docs/DESIGN.md`、`docs/DEVELOPMENT.md`、`docs/plan/frontend-visual-migration-plan.md`、`docs/product/frontend-visual-migration-acceptance.md`：同步视觉边界和实际验收结果。

### Task 1：建立共享主图组件

**Files:**
- Create: `frontend/components/layout/report-page-hero.test.tsx`
- Create: `frontend/components/layout/report-page-hero.tsx`

- [x] **Step 1：先写共享组件失败测试**

测试应渲染静态头部和显式动效头部，锁定标题层级、图片、透明度、无遮罩和插槽：

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ReportPageHero } from "./report-page-hero";

describe("ReportPageHero", () => {
  it("renders a static decorative report hero by default", () => {
    const { container } = render(
      <ReportPageHero
        eyebrow="报告核查清单"
        title="完整 GRI 核查范围"
        description="核查说明"
        imageSrc="/visuals/module-policy-disclosure.webp"
        imagePosition="28% 50%"
        meta={<span>共 577 项</span>}
        action={<button type="button">进入页面</button>}
      />,
    );

    expect(screen.getByRole("heading", { level: 1, name: "完整 GRI 核查范围" })).toBeInTheDocument();
    expect(screen.getByText("共 577 项")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "进入页面" })).toBeInTheDocument();
    const artwork = container.querySelector('img[src*="module-policy-disclosure"]');
    expect(artwork).toHaveAttribute("alt", "");
    expect(artwork).toHaveClass("opacity-[0.23]");
    expect(artwork).not.toHaveClass("animate-ken-burns");
    expect(artwork).toHaveStyle({ objectPosition: "28% 50%" });
    expect(container.querySelector('[class*="linear-gradient"]')).toBeNull();
  });

  it("only enables the image motion when requested", () => {
    const { container } = render(
      <ReportPageHero
        eyebrow="当前报告"
        title="报告总览"
        imageSrc="/visuals/module-policy-disclosure.webp"
        animated
      />,
    );
    expect(container.querySelector("img")).toHaveClass("animate-ken-burns");
  });
});
```

- [x] **Step 2：运行测试并确认按预期失败**

Run:

```powershell
cd frontend
npm test -- components/layout/report-page-hero.test.tsx
```

Expected: FAIL，原因是 `report-page-hero.tsx` 尚不存在；不得出现依赖、网络或测试环境错误。

- [x] **Step 3：实现最小共享组件**

组件使用固定视觉参数，页面只能传内容、图片和裁切位置：

```tsx
import Image from "next/image";
import type { ReactNode } from "react";

type ReportPageHeroProps = {
  eyebrow: string;
  title: string;
  description?: string;
  imageSrc: string;
  imagePosition?: string;
  animated?: boolean;
  meta?: ReactNode;
  action?: ReactNode;
};

export function ReportPageHero({
  eyebrow,
  title,
  description,
  imageSrc,
  imagePosition = "50% 50%",
  animated = false,
  meta,
  action,
}: ReportPageHeroProps) {
  return (
    <section className="relative flex flex-col gap-5 overflow-hidden rounded-2xl border border-emerald-100/80 bg-emerald-50/60 p-6 lg:flex-row lg:items-end lg:justify-between">
      <Image
        src={imageSrc}
        alt=""
        aria-hidden="true"
        fill
        sizes="(min-width: 1280px) 1152px, 100vw"
        style={{ objectPosition: imagePosition }}
        className={`${animated ? "animate-ken-burns " : ""}pointer-events-none object-cover opacity-[0.23] brightness-95 saturate-125`}
      />
      <div className="relative min-w-0">
        <p className="text-sm font-semibold text-emerald-700">{eyebrow}</p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight">{title}</h1>
        {meta ? <div className="mt-3 flex flex-wrap items-center gap-2">{meta}</div> : null}
        {description ? <p className="mt-3 max-w-2xl text-sm leading-6 text-muted-foreground">{description}</p> : null}
      </div>
      {action ? <div className="relative shrink-0">{action}</div> : null}
    </section>
  );
}
```

- [x] **Step 4：运行共享组件测试并确认通过**

Run: `npm test -- components/layout/report-page-hero.test.tsx`

Expected: 1 个测试文件、2 项测试 PASS。

- [x] **Step 5：提交共享组件**

```powershell
git add -- frontend/components/layout/report-page-hero.tsx frontend/components/layout/report-page-hero.test.tsx
git commit -m "feat: add shared report page hero"
```

### Task 2：接入报告总览、完整核查和人工复核

**Files:**
- Modify: `frontend/components/analysis/report-dashboard.test.tsx`
- Modify: `frontend/components/analysis/report-dashboard.tsx`
- Modify: `frontend/components/analysis/assessment-table.test.tsx`
- Modify: `frontend/components/analysis/assessment-table.tsx`
- Modify: `frontend/components/review/reviewer-gate.test.tsx`
- Modify: `frontend/components/review/reviewer-gate.tsx`
- Modify: `frontend/components/review/review-workspace.tsx`

- [x] **Step 1：先补三类页面的失败断言**

在报告总览测试中补充动效断言：

```tsx
expect(heroArtwork).toHaveClass("animate-ken-burns");
```

在完整核查首个测试中使用现有 `container` 返回值并补充：

```tsx
const { container } = renderWithQuery(<AssessmentTable reportId="report-1" />);
const heroArtwork = container.querySelector('img[src*="module-policy-disclosure"]');
expect(heroArtwork).toHaveClass("opacity-[0.23]");
expect(heroArtwork).not.toHaveClass("animate-ken-burns");
```

在复核人入口首个测试中使用现有 `container` 返回值并补充：

```tsx
const { container } = renderWithQuery(<ReviewerGate reportId="report-1" />);
expect(screen.getByRole("heading", { level: 1, name: "人工复核" })).toBeInTheDocument();
const heroArtwork = container.querySelector('img[src*="module-materiality-benchmark"]');
expect(heroArtwork).toHaveClass("opacity-[0.23]");
expect(heroArtwork).not.toHaveClass("animate-ken-burns");
```

- [x] **Step 2：运行三类目标测试并确认预期失败**

Run:

```powershell
npm test -- components/analysis/report-dashboard.test.tsx components/analysis/assessment-table.test.tsx components/review/reviewer-gate.test.tsx
```

Expected: 新增断言 FAIL；原有业务断言继续通过。

- [x] **Step 3：迁移报告总览头部**

删除 `report-dashboard.tsx` 对 `next/image` 的直接导入，导入 `ReportPageHero`，用以下结构替换现有头部 `section`：

```tsx
<ReportPageHero
  eyebrow="当前报告"
  title="报告总览"
  imageSrc="/visuals/module-policy-disclosure.webp"
  imagePosition="28% 50%"
  animated
  meta={(
    <>
      <StatusBadge tone="success">核查范围 {data.standard_unit_count} 项</StatusBadge>
      <StatusBadge tone={data.high_priority_unresolved > 0 ? "danger" : "success"}>
        高优先级复核 {data.high_priority_reviewed}/{data.high_priority_total}
      </StatusBadge>
    </>
  )}
  description="高优先级复核完成不代表全部 577 项均已人工确认。"
  action={(
    <Link href={`/reports/${reportId}/review`} className={buttonVariants()}>
      <ListChecks aria-hidden="true" className="h-4 w-4" />
      进入复核工作台
    </Link>
  )}
/>
```

- [x] **Step 4：完整核查接入静态主图**

在 `AssessmentTable` 中导入 `ReportPageHero`，替换原文字头部：

```tsx
<ReportPageHero
  eyebrow="报告核查清单"
  title="完整 GRI 核查范围"
  description="独立判断项可进入人工复核；上下文条款已纳入相关判断，不重复生成结论。"
  imageSrc="/visuals/module-policy-disclosure.webp"
  imagePosition="28% 50%"
  meta={query.data ? (
    <span className="rounded-full bg-emerald-50 px-3 py-1.5 text-sm font-semibold text-emerald-800">
      共 {query.data.total} 项
    </span>
  ) : null}
/>
```

搜索筛选容器保留原功能，并把顶部间距保持为 `mt-4`。

- [x] **Step 5：人工复核接入静态主图**

让 `ReviewerGate` 始终渲染统一头部，再根据 `confirmed` 切换表单或工作台：

```tsx
return (
  <div>
    <div className="mx-auto w-full max-w-7xl px-5 py-6 lg:px-7">
      <ReportPageHero
        eyebrow="人工判断层"
        title="人工复核"
        description="逐项核对规则结果、证据和 AI 辅助建议，最终有效结论以人工复核快照为准。"
        imageSrc="/visuals/module-materiality-benchmark.webp"
        imagePosition="52% 50%"
      />
    </div>
    {confirmed ? (
      <ReviewWorkspace reportId={reportId} reviewerName={name} initialAssessmentId={initialAssessmentId} />
    ) : (
      <div className="mx-auto max-w-md px-6 pb-12">
        <h2 className="text-xl font-semibold">填写复核人</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          复核记录将保存本次填写的复核人名称、时间和原因。每次进入均需重新填写。
        </p>
        <label className="mt-6 block text-sm font-medium">
          复核人名称
          <input
            className="mt-2 h-10 w-full rounded-md border border-border px-3 font-normal"
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
        </label>
        <button
          type="button"
          className="mt-4 h-10 rounded-md bg-accent px-4 text-sm font-medium text-accent-foreground disabled:opacity-50"
          disabled={!name.trim()}
          onClick={() => {
            setName(name.trim());
            setConfirmed(true);
          }}
        >
          进入复核工作台
        </button>
      </div>
    )}
  </div>
);
```

同时把 `ReviewWorkspace` 根元素的 `min-h-[calc(100vh-3.5rem)]` 删除，依靠 PDF 查看器现有 `min-h-[520px]` 和自然页面滚动，避免主图加入后形成重复视口高度。

- [x] **Step 6：运行三类目标测试**

Run:

```powershell
npm test -- components/layout/report-page-hero.test.tsx components/analysis/report-dashboard.test.tsx components/analysis/assessment-table.test.tsx components/review/reviewer-gate.test.tsx
```

Expected: 4 个测试文件全部 PASS；报告总览有动效，完整核查和人工复核无动效。

- [x] **Step 7：提交前三页接入**

```powershell
git add -- frontend/components/analysis/report-dashboard.tsx frontend/components/analysis/report-dashboard.test.tsx frontend/components/analysis/assessment-table.tsx frontend/components/analysis/assessment-table.test.tsx frontend/components/review/reviewer-gate.tsx frontend/components/review/reviewer-gate.test.tsx frontend/components/review/review-workspace.tsx
git commit -m "feat: unify analysis and review page heroes"
```

### Task 3：接入整改、输出和审计页面

**Files:**
- Create: `frontend/app/reports/[reportId]/report-workspace-pages.test.tsx`
- Modify: `frontend/app/reports/[reportId]/actions/page.tsx`
- Modify: `frontend/app/reports/[reportId]/exports/page.tsx`
- Modify: `frontend/app/reports/[reportId]/audit/page.tsx`
- Modify: `frontend/components/audit/report-audit-timeline.tsx`

- [x] **Step 1：先写三个路由的失败测试**

测试中 mock 业务子组件，只验证页面结构与资产映射：

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import ActionsPage from "./actions/page";
import AuditPage from "./audit/page";
import ExportsPage from "./exports/page";

vi.mock("@/components/actions/action-list", () => ({ ActionList: () => <div>任务列表</div> }));
vi.mock("@/components/exports/export-versions", () => ({ ExportVersions: () => <div>输出列表</div> }));
vi.mock("@/components/audit/report-audit-timeline", () => ({ ReportAuditTimeline: () => <div>审计列表</div> }));

const params = Promise.resolve({ reportId: "report-1" });

describe("report workspace page heroes", () => {
  it("maps the monitoring artwork to actions", async () => {
    const { container } = render(await ActionsPage({ params }));
    expect(screen.getByRole("heading", { level: 1, name: "整改任务" })).toBeInTheDocument();
    expect(container.querySelector('img[src*="module-claw-monitor"]')).not.toHaveClass("animate-ken-burns");
  });

  it("maps the disclosure artwork to exports", async () => {
    const { container } = render(await ExportsPage({ params }));
    expect(screen.getByRole("heading", { level: 1, name: "输出与版本" })).toBeInTheDocument();
    expect(container.querySelector('img[src*="module-policy-disclosure"]')).not.toHaveClass("animate-ken-burns");
  });

  it("maps the monitoring artwork to audit", async () => {
    const { container } = render(await AuditPage({ params }));
    expect(screen.getByRole("heading", { level: 1, name: "审计时间线" })).toBeInTheDocument();
    expect(container.querySelector('img[src*="module-claw-monitor"]')).not.toHaveClass("animate-ken-burns");
  });
});
```

- [x] **Step 2：运行路由测试并确认预期失败**

Run: `npm test -- 'app/reports/[reportId]/report-workspace-pages.test.tsx'`

Expected: 3 项测试因目标页面尚无图片而 FAIL。

- [x] **Step 3：整改和输出页面接入共享头部**

在两个页面导入 `ReportPageHero`，保留原容器宽度和业务组件。`actions/page.tsx` 完整结构为：

```tsx
import { ActionList } from "@/components/actions/action-list";
import { ReportPageHero } from "@/components/layout/report-page-hero";

export default async function ActionsPage({ params }: { params: Promise<{ reportId: string }> }) {
  const { reportId } = await params;
  return (
    <div className="mx-auto w-full max-w-6xl px-5 py-6 lg:px-7">
      <ReportPageHero
        eyebrow="披露改进闭环"
        title="整改任务"
        description="将人工复核确认的披露缺口转化为责任人、截止日期和状态可追踪的任务。"
        imageSrc="/visuals/module-claw-monitor.webp"
        imagePosition="42% 50%"
      />
      <div className="pt-5"><ActionList reportId={reportId} /></div>
    </div>
  );
}
```

`exports/page.tsx` 完整结构为：

```tsx
import { ExportVersions } from "@/components/exports/export-versions";
import { ReportPageHero } from "@/components/layout/report-page-hero";

export default async function ExportsPage({ params }: { params: Promise<{ reportId: string }> }) {
  const { reportId } = await params;
  return (
    <div className="mx-auto w-full max-w-6xl px-5 py-6 lg:px-7">
      <ReportPageHero
        eyebrow="版本化交付"
        title="输出与版本"
        description="生成带复核范围说明的草稿或正式版本，并保留版本、创建人和生成时间。"
        imageSrc="/visuals/module-policy-disclosure.webp"
        imagePosition="28% 50%"
      />
      <div className="pt-5"><ExportVersions reportId={reportId} createdBy="当前复核人" /></div>
    </div>
  );
}
```

- [x] **Step 4：审计页面接入共享头部并删除重复标题**

在 `audit/page.tsx` 中把共享主图放在 `ReportAuditTimeline` 之前，完整结构为：

```tsx
import { ReportAuditTimeline } from "@/components/audit/report-audit-timeline";
import { ReportPageHero } from "@/components/layout/report-page-hero";

export default async function ReportAuditPage({ params }: { params: Promise<{ reportId: string }> }) {
  const { reportId } = await params;
  return (
    <div className="mx-auto w-full max-w-5xl px-5 py-6 lg:px-7">
      <ReportPageHero
        eyebrow="报告留痕"
        title="审计时间线"
        description="汇总报告上传、分析、重跑、人工复核、整改和输出事件。技术敏感信息已从公开视图移除。"
        imageSrc="/visuals/module-claw-monitor.webp"
        imagePosition="42% 50%"
      />
      <div className="pt-5"><ReportAuditTimeline reportId={reportId} /></div>
    </div>
  );
}
```

从 `report-audit-timeline.tsx` 删除原 `header`，保留加载、错误、空态、列表和分页逻辑。

- [x] **Step 5：运行路由与审计目标测试**

Run:

```powershell
npm test -- 'app/reports/[reportId]/report-workspace-pages.test.tsx' components/audit/report-audit-timeline.test.tsx components/actions/action-list.test.tsx components/exports/export-versions.test.tsx
```

Expected: 新增路由测试 3 项及现有业务测试全部 PASS。

- [x] **Step 6：提交后三页接入**

```powershell
git add -- 'frontend/app/reports/[reportId]/report-workspace-pages.test.tsx' 'frontend/app/reports/[reportId]/actions/page.tsx' 'frontend/app/reports/[reportId]/exports/page.tsx' 'frontend/app/reports/[reportId]/audit/page.tsx' frontend/components/audit/report-audit-timeline.tsx
git commit -m "feat: add heroes to action export and audit pages"
```

### Task 4：执行完整工程门禁和浏览器验收

**Files:**
- 预计无代码修改。

- [x] **Step 1：运行全部前端测试**

Run: `npm test`

Expected: 所有测试文件和测试项 PASS；基线约为 39 个测试文件、150 项测试，新增后数量应增加且不得减少既有测试。

- [x] **Step 2：运行类型、构建和静态检查**

Run:

```powershell
npm run typecheck
npm run build
npm run lint
```

Expected: typecheck 和 production build 成功；lint 为 0 error，允许保留当前已有的 2 个非阻塞 warning，不得新增 warning。

- [x] **Step 3：核对服务并做桌面浏览器验收**

确认 `http://localhost:3000` 和 `http://localhost:8000/health` 可访问；若服务未运行，按 `docs/DEVELOPMENT.md` 的 demo 启动方式启动。依次打开报告总览、完整核查、人工复核、整改任务、输出版本和审计时间线：

- 六页均有统一圆角主图头部；
- 完整核查与输出使用披露文档图；
- 人工复核使用多维比较图；
- 整改与审计使用监控图；
- 目标五页图片静态、无遮罩，文字可读；
- 报告总览保留 Ken Burns；
- 人工复核输入默认空，进入后三栏仍可操作；
- 审计加载、事件和分页正常。

- [x] **Step 4：做约 390px 窄屏验收**

使用浏览器移动视口检查同一组页面，确认头部纵向排列、无横向溢出、一级标题不重复，复核工作台“队列／判断／证据”切换栏未被遮挡。

### Task 5：同步文档并记录验收

**Files:**
- Modify: `docs/DESIGN.md`
- Modify: `docs/DEVELOPMENT.md`
- Modify: `docs/plan/frontend-visual-migration-plan.md`
- Modify: `docs/product/frontend-visual-migration-acceptance.md`

- [x] **Step 1：更新设计边界**

把 `docs/DESIGN.md` 中“业务页保持简洁头部”细化为：报告工作区允许使用紧凑静态主图头部；Ken Burns 仍只限首页和报告总览；图片继续遵守低透明度、无遮罩和 `prefers-reduced-motion` 边界。

- [x] **Step 2：记录实施与门禁结果**

在 `docs/DEVELOPMENT.md` 和 `docs/plan/frontend-visual-migration-plan.md` 记录：

- 新增共享组件及六页接入范围；
- 三张资产的页面映射；
- 五个业务页静态、报告总览保留动效；
- 自动测试、typecheck、build、lint 的实际结果；
- 桌面和窄屏浏览器验收结果；
- 本轮没有后端、API、数据库或业务语义变化。

- [x] **Step 3：更新视觉验收报告**

在 `docs/product/frontend-visual-migration-acceptance.md` 增加本轮验收小节，写明通过项、已知限制和 `v1.3.2` 仍为视觉补丁候选，版本号需等待用户主观确认后再决定。

- [x] **Step 4：检查文档并提交**

Run:

```powershell
rg -n "TBD|TODO|待定|C:\\|C:/" docs/DESIGN.md docs/DEVELOPMENT.md docs/plan/frontend-visual-migration-plan.md docs/product/frontend-visual-migration-acceptance.md
git diff --check
```

Expected: 无占位符、无本机绝对路径、无空白错误。

```powershell
git add -- docs/DESIGN.md docs/DEVELOPMENT.md docs/plan/frontend-visual-migration-plan.md docs/product/frontend-visual-migration-acceptance.md
git commit -m "docs: record report workspace hero acceptance"
```

## 完成条件

1. 报告总览和五个目标页面共用同一头部组件。
2. 三张现有模块图按已批准语义映射，无新增资产。
3. 五个业务页面无 Ken Burns、无遮罩；报告总览现有动效和透明度保持。
4. 人工复核、整改、输出和审计业务行为无回归。
5. 前端全量测试、typecheck、build、lint 及桌面/390px 浏览器验收完成。
6. 设计、开发、迁移计划和验收文档同步完成。
7. 不修改版本号、不创建标签、不 push；用户主观确认后再冻结 `v1.3.2`。
