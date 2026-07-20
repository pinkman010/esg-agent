# ESG-Agent

面向企业 ESG 团队的单报告 GRI 核查系统，支持报告上传、577 个 GRI 标准核查单元编译、493 个独立 requirement 分析、证据追溯、AI 辅助建议、人工复核、整改任务和版本化输出。

## 项目状态

确定性产品闭环和 AI 辅助后端已完成本地冻结验收：577 个标准核查单元被确定性编译为 493 个独立判断项、78 个父级上下文项和 6 个方法待确认项；规则 assessment、DeepSeek 独立建议和人工结果分层保存。225 条真实 AI 基线评估的一致率为 72.32%，证据越界、可比错页、schema 失败、模型失败和 guardrail 后的 false disclosed 均为 0；16 条 Sol/Pro 差异继续等待方法裁决。最终自动门禁为后端 626 项测试、前端 19 个测试文件 51 项测试、typecheck、production build、Envision v2 回归和 Goldwind 100 条人工 gold gate 全部通过。

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
  -> 编译 577 个标准核查单元并分析 493 个独立 requirement
  -> 展示业务阶段进度和部分失败
  -> 高优先级队列优先人工复核，并独立处理适用性待判定项
  -> 形成整改任务
  -> 生成版本化核查表、管理层摘要和打印版输出
```

前端以高复核优先级队列为主要入口，并支持访问适用性待判定队列和全部独立判断结果。高优先级项全部完成后只表示该队列已处理，不表示全部 577 个标准核查单元均已人工确认。`unknown` 是披露结论，不能单独解释为高优先级。

`actions_xlsx` 完整改任务清单导出、通用 verdict 批量复核、独立 reopen、report 级审计和单 export 下载仍为增强项；当前正式输出在全部高优先级项目完成有效人工复核前会被阻止。

第一版保留跨企业、跨报告格式的识别泛化能力，不做多租户、复杂权限、顾问项目空间、多公司批量处理、同行对标、舆情监测和多标准混合分析。

## 技术栈

完整技术选型以 `docs/DESIGN.md` 为准。当前已确认：

- 后端：Python 3.11、FastAPI、Pydantic v2、PostgreSQL、SQLAlchemy 2.0、Alembic。
- 前端：Next.js App Router、TypeScript、Tailwind CSS、shadcn/ui、TanStack Query、TanStack Table、Recharts。
- PDF：混合多路由管线，包含 pypdf、pdfplumber、OCRmyPDF/Tesseract、Docling fallback、VLM 辅助识别。
- AI：DeepSeek OpenAI-compatible API；默认关闭，仅在用户显式确认后生成追加式辅助建议，不覆盖规则或人工结果。
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

当前数据库 head 为 `0011_ai_suggestions`。正式输出要求独立判断结果完整且全部高优先级项完成复核；草稿可随时生成，并明确披露未复核的中优先级和适用性待判定范围。完整产品验收说明见 `docs/DEVELOPMENT.md` 的“企业产品闭环验收”章节。

当前处于 AI 辅助后端冻结检查点。前端尚未展示规则结论、AI 建议、人工结论三层交互，该部分进入下一份实施计划；已知风险和尚未实现的规划接口统一记录在 `docs/DEVELOPMENT.md`。
