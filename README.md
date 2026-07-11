# ESG-Agent

面向企业 ESG 团队的单报告 GRI 核查系统，支持报告上传、577 条 eligible GRI requirement 分析、证据追溯、高风险优先复核、整改任务和版本化输出。

## 项目状态

分析技术闭环已跑通：后端 API、PostgreSQL schema、PDF 解析、577 条 eligible GRI requirement、披露分析 workflow、证据路由、基础人工复核、导出和审计日志均已有实现。当前阶段转向企业产品闭环，重点建设报告生命周期、高风险队列、三栏复核工作台、追加式审计、整改任务和版本化输出。

## 仓库结构

```text
esg-agent/
  README.md
  backend/
  frontend/
  docs/
    DESIGN.md
    DEVELOPMENT.md
    ASSETS.md
    plan/
```

## 核心文档

- 技术设计：`docs/DESIGN.md`
- 开发、运行、测试：`docs/DEVELOPMENT.md`
- 资产与证据边界：`docs/ASSETS.md`
- 实施计划：`docs/plan/`
- 本地代理执行规则：`AGENTS.md`，该文件不提交到仓库。

## 第一版范围

第一版围绕企业 ESG 团队的单报告闭环：

```text
报告列表或上传空状态
  -> 上传 PDF 并识别企业、年度、语言和页数
  -> 用户确认报告信息
  -> 后台分析 577 条 eligible GRI requirement
  -> 展示业务阶段进度和部分失败
  -> 高风险队列优先人工复核
  -> 形成整改任务
  -> 导出完整核查表、管理层摘要和改进任务清单
```

前端以高风险队列为主要复核入口，并支持按 GRI 主题查看全部结果。高风险项全部完成后显示“高风险复核已完成”，该状态不表示全部 577 条均已人工确认。

第一版保留跨企业、跨报告格式的识别泛化能力，不做多租户、复杂权限、顾问项目空间、多公司批量处理、同行对标、舆情监测和多标准混合分析。

## 技术栈

完整技术选型以 `docs/DESIGN.md` 为准。当前已确认：

- 后端：Python 3.11、FastAPI、Pydantic v2、PostgreSQL、SQLAlchemy 2.0、Alembic。
- 前端：Next.js App Router、TypeScript、Tailwind CSS、shadcn/ui、TanStack Query、TanStack Table、Recharts。
- PDF：混合多路由管线，包含 pypdf、pdfplumber、OCRmyPDF/Tesseract、Docling fallback、VLM 辅助识别。
- 包管理：后端 uv，前端 pnpm。

OCR 本地前置条件：

- Tesseract 需可用，并安装 `chi_sim`、`eng` 语言包。
- OCRmyPDF 由后端依赖安装；真实 OCR 执行还需要 Ghostscript 命令可用。
- OCR 默认关闭，只在分析请求显式传入 `enable_ocr=true` 时运行。

## 开发提示

- 修改技术设计前先更新 `docs/DESIGN.md`。
- 涉及资产迁移或证据材料时先读 `docs/ASSETS.md`。
- 涉及本地运行、依赖、测试命令时先读 `docs/DEVELOPMENT.md`。

## 资产恢复

仓库不提交 PDF、Word、Excel 等二进制文档资产。

首次克隆后，按 `docs/ASSETS.md` 的“本地资产恢复”说明，将必需资产恢复到 `backend/data/reports/` 和 `backend/data/standards/`，并根据 `backend/data/manifests/assets_manifest.json` 完成 SHA256 校验。

## 本地运行

```powershell
docker compose up -d postgres

cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn src.main:app --reload --port 8000

cd ../frontend
pnpm install
pnpm dev
```

前端默认访问 `http://localhost:3000`，后端默认访问 `http://localhost:8000`。

## 验证命令

```powershell
cd backend
uv run pytest

cd ../frontend
pnpm typecheck
pnpm test
pnpm build
```
