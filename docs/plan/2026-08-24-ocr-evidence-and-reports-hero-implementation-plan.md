# OCR 证据降级展示与 ESG 报告入口主图实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**目标：** 在不修改后端的前提下，降级展示需人工复核的 OCR 证据，并为 `/reports` 补齐已批准的静态主图头部。

**架构：** 两个补丁共享前端验证周期，但保持独立代码边界和独立提交。人工复核组件仅依据现有 `source_method` 与 `quality_flags` 调整展示；报告入口页仅复用现有 `ReportPageHero`，不修改共享组件、列表、上传和数据请求。

**技术栈：** Next.js 16、React 19、TypeScript、Tailwind CSS、Vitest、Testing Library、现有 `ReportPageHero`。

---

## 文件结构

- 修改 `frontend/components/review/assessment-detail.tsx`：呈现证据来源、低质量 OCR 警告、折叠原始识别文本和 PDF 原页核对按钮。
- 修改 `frontend/components/review/assessment-detail.test.tsx`：覆盖低质量 OCR 降级、审计原文、普通 PDF 证据与页码回调。
- 修改 `frontend/app/reports/page.tsx`：使用共享 `ReportPageHero` 替换纯文字头部。
- 新建 `frontend/app/reports/page.test.tsx`：覆盖主图、静态边界、唯一一级标题和业务子组件保留。
- 修改 `docs/plan/frontend-visual-migration-plan.md`：记录本轮视觉范围补漏。
- 修改 `docs/product/frontend-visual-migration-acceptance.md`：记录自动与浏览器验收结果。
- 修改 `docs/DEVELOPMENT.md`：记录验证命令、结果与后端未解冻边界。

## Task 1：低质量 OCR 证据降级展示

**文件：**

- 修改：`frontend/components/review/assessment-detail.test.tsx`
- 修改：`frontend/components/review/assessment-detail.tsx`

- [ ] **Step 1：先写低质量 OCR 与普通 PDF 证据测试**

将 Vitest 导入补充为 `vi`：

```tsx
import { describe, expect, it, vi } from "vitest";
```

在 `describe("AssessmentDetail", ...)` 中增加以下两个测试：

```tsx
it("downgrades low-quality OCR evidence while keeping the raw preview auditable", () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const onEvidencePage = vi.fn();
  const rawOcrPreview = "...e OE ee se le 我们的责任是在执行你证工作的莫础上...";
  const assessment = {
    ...detail("assessment-ocr", "GRI 2-5-b-ii"),
    evidence_items: [
      {
        evidence_id: "evidence-ocr",
        source_pdf_page: 77,
        source_report_page: 76,
        page_label: "PDF 第 77 页 / 报告页 76",
        evidence_preview: rawOcrPreview,
        source_method: "ocr",
        quality_flags: ["needs_manual_review"],
        bbox: null,
      },
    ],
  } satisfies AssessmentDetailResponse;

  render(
    <QueryClientProvider client={queryClient}>
      <AssessmentDetail
        reportId="report-1"
        detail={assessment}
        aiAvailability="disabled"
        reviewerName="张三"
        onEvidencePage={onEvidencePage}
      />
    </QueryClientProvider>,
  );

  expect(screen.getByText("OCR 识别文本")).toBeInTheDocument();
  expect(
    screen.getByText("OCR 识别质量不足，请核对右侧 PDF 原页。"),
  ).toBeInTheDocument();
  const disclosure = screen
    .getByText("查看原始 OCR 识别文本")
    .closest("details");
  if (!disclosure) throw new Error("OCR disclosure not found");
  expect(disclosure).not.toHaveAttribute("open");
  expect(within(disclosure).getByText(rawOcrPreview)).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "核对 PDF 原页" }));
  expect(onEvidencePage).toHaveBeenCalledWith(77);
  fireEvent.click(screen.getByText("查看原始 OCR 识别文本"));
  expect(onEvidencePage).toHaveBeenCalledTimes(1);
});

it("keeps pdfplumber evidence directly readable and linked to its PDF page", () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const onEvidencePage = vi.fn();
  const assessment = {
    ...detail("assessment-pdf", "GRI 2-5-b-ii"),
    evidence_items: [
      {
        evidence_id: "evidence-pdf",
        source_pdf_page: 77,
        source_report_page: 76,
        page_label: "PDF 第 77 页 / 报告页 76",
        evidence_preview: "独立有限鉴证报告",
        source_method: "pdfplumber",
        quality_flags: ["digital_text"],
        bbox: null,
      },
    ],
  } satisfies AssessmentDetailResponse;

  render(
    <QueryClientProvider client={queryClient}>
      <AssessmentDetail
        reportId="report-1"
        detail={assessment}
        aiAvailability="disabled"
        reviewerName="张三"
        onEvidencePage={onEvidencePage}
      />
    </QueryClientProvider>,
  );

  expect(screen.getByText("PDF 原文")).toBeInTheDocument();
  expect(screen.getByText("独立有限鉴证报告")).toBeInTheDocument();
  expect(screen.queryByText("查看原始 OCR 识别文本")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "核对 PDF 原页" }));
  expect(onEvidencePage).toHaveBeenCalledWith(77);
});
```

- [ ] **Step 2：运行测试并确认按预期失败**

运行：

```powershell
cd frontend
pnpm test -- components/review/assessment-detail.test.tsx
```

预期：新增测试失败，失败原因是页面尚未显示“OCR 识别文本”“PDF 原文”或质量警告；既有测试继续通过。

- [ ] **Step 3：实现最小降级展示**

在 `assessment-detail.tsx` 顶部增加来源显示函数：

```tsx
function evidenceSourceLabel(sourceMethod: string) {
  if (sourceMethod === "pdfplumber") return "PDF 原文";
  if (sourceMethod === "ocr") return "OCR 识别文本";
  return sourceMethod;
}
```

用以下结构替换当前 `detail.evidence_items.map(...)` 中的整块 `button`：

```tsx
{detail.evidence_items.map((item) => {
  const isLowQualityOcr =
    item.source_method === "ocr" &&
    item.quality_flags.includes("needs_manual_review");

  return (
    <div
      key={item.evidence_id}
      className="w-full border-l-2 border-accent py-2 pl-3 text-left text-sm"
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-medium text-accent">{item.page_label}</span>
        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-muted-foreground">
          {evidenceSourceLabel(item.source_method)}
        </span>
      </div>
      {isLowQualityOcr ? (
        <div className="mt-2 space-y-2">
          <p className="text-sm font-medium text-amber-800">
            OCR 识别质量不足，请核对右侧 PDF 原页。
          </p>
          <details className="text-muted-foreground">
            <summary className="cursor-pointer text-xs font-medium text-foreground">
              查看原始 OCR 识别文本
            </summary>
            <p className="mt-2 break-words leading-5">{item.evidence_preview}</p>
          </details>
        </div>
      ) : (
        <p className="mt-1 break-words leading-5 text-muted-foreground">
          {item.evidence_preview}
        </p>
      )}
      <button
        type="button"
        className="mt-2 text-xs font-medium text-accent underline-offset-4 hover:underline"
        onClick={() => onEvidencePage(item.source_pdf_page)}
      >
        核对 PDF 原页
      </button>
    </div>
  );
})}
```

- [ ] **Step 4：运行目标测试并确认通过**

运行：

```powershell
cd frontend
pnpm test -- components/review/assessment-detail.test.tsx
```

预期：`assessment-detail.test.tsx` 全部通过，新增低质量 OCR 与普通 PDF 证据测试均为绿色。

- [ ] **Step 5：运行相邻复核回归并提交**

运行：

```powershell
cd frontend
pnpm test -- components/review/assessment-detail.test.tsx components/review/review-workspace.test.tsx components/evidence/pdf-evidence-viewer.test.tsx
pnpm typecheck
```

预期：所有目标测试和 TypeScript 检查通过。

提交：

```powershell
git add -- frontend/components/review/assessment-detail.tsx frontend/components/review/assessment-detail.test.tsx
git commit -m "fix: downgrade low-quality OCR evidence previews"
```

## Task 2：ESG 报告入口页主图

**文件：**

- 新建：`frontend/app/reports/page.test.tsx`
- 修改：`frontend/app/reports/page.tsx`

- [ ] **Step 1：先写入口页主图测试**

新建 `frontend/app/reports/page.test.tsx`：

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import ReportsPage from "./page";

vi.mock("@/components/reports/report-list", () => ({
  ReportList: () => <div>报告列表内容</div>,
}));
vi.mock("@/components/upload/report-upload-panel", () => ({
  ReportUploadPanel: () => <div>报告上传内容</div>,
}));

describe("ReportsPage", () => {
  it("uses the static disclosure hero while preserving report operations", () => {
    const { container } = render(<ReportsPage />);

    expect(
      screen.getByRole("heading", { level: 1, name: "ESG 报告" }),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(
      screen.getByText("上传报告、确认信息，并从当前业务状态继续 GRI 核查。"),
    ).toBeInTheDocument();
    expect(screen.getByText("报告列表内容")).toBeInTheDocument();
    expect(screen.getByText("报告上传内容")).toBeInTheDocument();

    const artwork = container.querySelector(
      'img[src*="module-policy-disclosure"]',
    );
    expect(artwork).toHaveAttribute("alt", "");
    expect(artwork).toHaveAttribute("loading", "eager");
    expect(artwork).toHaveClass("opacity-[0.23]");
    expect(artwork).not.toHaveClass("animate-ken-burns");
    expect(container.querySelector('[class*="linear-gradient"]')).toBeNull();
  });
});
```

- [ ] **Step 2：运行测试并确认按预期失败**

运行：

```powershell
cd frontend
pnpm test -- app/reports/page.test.tsx
```

预期：测试因 `/reports` 尚无 `module-policy-disclosure.webp` 图片而失败，报告列表与上传替身断言通过。

- [ ] **Step 3：复用共享主图组件**

在 `frontend/app/reports/page.tsx` 增加导入：

```tsx
import { ReportPageHero } from "@/components/layout/report-page-hero";
```

用共享组件替换纯文字头部，并给下方栅格增加顶部间距：

```tsx
<ReportPageHero
  eyebrow="报告工作区"
  title="ESG 报告"
  description="上传报告、确认信息，并从当前业务状态继续 GRI 核查。"
  imageSrc="/visuals/module-policy-disclosure.webp"
/>
<div className="mt-7 grid min-w-0 gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">
  <section className="min-w-0">
    <h2 className="mb-3 text-base font-semibold">报告列表</h2>
    <ReportList />
  </section>
  <ReportUploadPanel />
</div>
```

- [ ] **Step 4：运行入口页与共享组件测试**

运行：

```powershell
cd frontend
pnpm test -- app/reports/page.test.tsx components/layout/report-page-hero.test.tsx components/reports/report-list.test.tsx components/upload/report-upload-panel.test.tsx
```

预期：四个测试文件全部通过；入口页只有一个 `h1`，主图静态、无遮罩且 eager 加载。

- [ ] **Step 5：运行 TypeScript 检查并提交**

运行：

```powershell
cd frontend
pnpm typecheck
```

预期：退出码为 0。

提交：

```powershell
git add -- frontend/app/reports/page.tsx frontend/app/reports/page.test.tsx
git commit -m "feat: add hero to ESG reports entry"
```

## Task 3：完整自动门禁与浏览器验收

**文件：**

- 修改：`docs/plan/frontend-visual-migration-plan.md`
- 修改：`docs/product/frontend-visual-migration-acceptance.md`
- 修改：`docs/DEVELOPMENT.md`

- [ ] **Step 1：运行完整前端门禁**

运行：

```powershell
cd frontend
pnpm test
pnpm typecheck
pnpm build
pnpm lint
```

预期：测试、类型检查和生产构建退出码为 0；lint 保持 0 error，只允许记录已有且与本轮无关的 warning。

- [ ] **Step 2：桌面端浏览器验收 ESG 报告入口**

打开 `http://localhost:3000/reports`，使用约 `1280x720` 视口验证：

- `h1` 数量为 1；
- 资产为 `/visuals/module-policy-disclosure.webp`；
- 图片没有 `animate-ken-burns`，没有遮罩，使用 eager 加载；
- 报告列表和上传面板均可见；
- 页面没有水平滚动；
- 控制台没有本轮新增错误。

- [ ] **Step 3：桌面端浏览器验收 OCR 降级展示**

打开显式 OCR 试点报告：

```text
http://localhost:3000/reports/report-c500a26acd844eb19041446ef79a3daa/review?assessmentId=assessment%3Arun-5220d8feef2f4159b705da9403e541ae%3AGRI%202-5-b-ii
```

填写临时复核人名称后验证：

- OCR 证据默认显示质量警告，不直接展开异常文本；
- `pdfplumber` 证据显示“PDF 原文”并直接显示预览；
- 点击“核对 PDF 原页”定位 PDF 第 77 页；
- 展开“查看原始 OCR 识别文本”后可以审计原始预览；
- 展开操作不改变 PDF 页码；
- 控制台没有本轮新增错误。

- [ ] **Step 4：移动端浏览器验收**

将视口调整为约 `390x844`，分别验证 `/reports` 与上述人工复核地址：

- 主图文字和图片不裁切，页面没有水平滚动；
- 报告列表与上传面板按单列排列；
- 人工复核“队列／判断／证据”切换可用；
- OCR 警告、折叠原文和 PDF 核对操作无相互遮挡。

- [ ] **Step 5：更新文档并提交**

在三个文档中记录以下已验证事实，并使用本轮实际命令输出替换旧统计：

- `/reports` 已纳入共享静态主图基线；
- 需人工复核的 OCR 证据默认降级展示，原始文本仍可审计；
- 本轮只修改前端，没有解冻后端、改变规则或修改历史 run；
- 记录全量测试文件数、测试数、typecheck、build、lint 和桌面／移动端浏览器结果；
- `v1.3.2` 仍为候选状态，暂不改版本号或发布标签。

提交：

```powershell
git add -- docs/plan/frontend-visual-migration-plan.md docs/product/frontend-visual-migration-acceptance.md docs/DEVELOPMENT.md
git commit -m "docs: record OCR evidence and reports hero acceptance"
```

## Task 4：最终差异与停止点检查

- [ ] **Step 1：检查提交与工作区边界**

运行：

```powershell
git status --short
git log -8 --oneline
git diff HEAD~3..HEAD --stat
```

预期：本轮代码与文档已经分批提交；`首页.png` 仍保持未跟踪且未修改；不存在未提交的本轮源代码差异。

- [ ] **Step 2：复核两个规格的终止条件**

逐项核对：

- OCR 证据默认降级、原文可展开、PDF 可核对、普通证据无回归；
- ESG 报告入口使用指定静态主图，业务组件和响应式布局无回归；
- 后端、数据库、API、GRI 口径、规则、AI、人工快照和导出均未修改；
- 自动门禁和真实浏览器验收均有当轮证据；
- 本轮不继续扩展新的视觉或 OCR 引擎需求。

- [ ] **Step 3：汇报候选版本状态**

汇报每个 commit、自动门禁、浏览器结果、已知既有 warning、未 push 状态和 `v1.3.2` 最终冻结建议。
