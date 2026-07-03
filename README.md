# esg-agent

单报告 ESG 披露分析系统，目标是支持上传报告、条款级披露分析、证据追溯、优化建议、人工复核和导出。

## 项目状态

第一版纵向闭环已跑通：后端 API、PostgreSQL schema、PDF 解析骨架、GRI checklist 首批真实 requirement、披露分析 workflow、前端工作台、人工复核、导出和审计日志均已实现。

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

第一版围绕单报告闭环：

```text
上传 PDF
  -> 保存报告和哈希
  -> 解析并入库
  -> 生成 GRI 披露任务
  -> 运行 DisclosureAgent
  -> 展示条款判断和证据
  -> 人工复核
  -> 导出 JSON/CSV
```

第一版不做登录权限、多公司批量处理、同行对标、舆情监测和多标准混合分析。

## 技术栈

完整技术选型以 `docs/DESIGN.md` 为准。当前已确认：

- 后端：Python 3.11、FastAPI、Pydantic v2、PostgreSQL、SQLAlchemy 2.0、Alembic。
- 前端：Next.js App Router、TypeScript、Tailwind CSS、shadcn/ui、TanStack Query、TanStack Table、Recharts。
- PDF：混合多路由管线，包含 pypdf、pdfplumber、OCRmyPDF/Tesseract、Docling fallback、VLM 辅助识别。
- 包管理：后端 uv，前端 pnpm。

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
