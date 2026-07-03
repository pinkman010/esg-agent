# 开发运行文档

## 1. 本地开发方式

本项目采用前后端单仓：

- 后端：`backend/`
- 前端：`frontend/`
- 文档：`docs/`

本地服务策略：

- PostgreSQL 由 Docker Compose 管理。
- OCR/Tesseract 使用本机工具。
- 后端和前端本机运行。

## 2. 包管理

已确认包管理方式：

- 后端使用 `uv`。
- 前端使用 `pnpm`。

后端依赖声明以 `backend/pyproject.toml` 为准。前端依赖声明以 `frontend/package.json` 为准。

## 3. 依赖服务

第一版需要：

- PostgreSQL。
- pgvector 预留，第一版不生成真实 embedding。
- Tesseract。
- OCRmyPDF。
- Node.js。
- Python 3.11。

工具路径约定：

- 工具类地址优先查找：`$CODEX_TOOLS_DIR`。
- soffice：`$SOFFICE_PATH`。
- pdftoppm：`$PDFTOPPM_PATH`。

## 4. 环境变量

项目不得提交 `.env`。

应提供：

- 根目录 `.env.example`。
- `backend/.env.example`。
- `frontend/.env.example`，如前端需要。

后端配置通过 `pydantic-settings` 读取，至少应覆盖：

- PostgreSQL 连接字符串。
- 上传文件目录。
- 派生文件目录。
- OCR/Tesseract 工具路径。
- OpenAI-compatible API base URL。
- 模型名称。
- CORS 来源。

测试默认使用独立 PostgreSQL 数据库，避免清空开发库：

- `TEST_DATABASE_URL` 未设置时默认指向测试库名 `esg_agent_test`。
- 测试 helper 会在需要时创建测试库。
- 不要把 `TEST_DATABASE_URL` 指向开发库名 `esg_agent`。

## 5. 常用命令

前后端脚手架已初始化。常用命令如下。

计划命令形态：

```powershell
# 后端
docker compose up -d postgres
cd backend
uv sync
uv run alembic upgrade head
uv run pytest
uv run uvicorn src.main:app --reload

# 前端
cd frontend
pnpm install
pnpm generate:api
pnpm typecheck
pnpm test
pnpm build
pnpm dev
```

## 6. 测试策略

后端测试使用 `pytest`，重点覆盖：

- domain models。
- PDF 页面预检测和分块。
- `GRIAdapter`。
- `DisclosureAgent`。
- `SingleReportWorkflow`。
- PostgreSQL repository。
- reports API。
- review API。
- exports API。
- audit API。
- OpenAPI 契约。
- 测试数据库隔离。

前端测试使用 Vitest 和 React Testing Library，重点覆盖：

- 上传页状态。
- 运行结果页空状态和数据状态。
- 人工复核提交。
- 图表封装组件。
- API client 基础请求状态。

验收命令以实际脚手架为准，至少包括：

- 后端 `pytest`。
- 前端 typecheck。
- 前端 Vitest。
- 前端 build。

## 7. OpenAPI 类型生成

前端 API 类型通过 FastAPI OpenAPI 自动生成。

约束：

- 后端接口变更后同步生成前端 types/client。
- 前端业务组件不手写重复接口类型。
- 生成文件放在 `frontend/lib/generated/` 或实施计划确认的等价目录。

生成命令：

```powershell
cd frontend
pnpm generate:api
```

生成前需要后端在 `http://localhost:8000` 提供 `/openapi.json`。

## 8. 开发日志

### 2026-07-03

- 完成 evidence retrieval 质量改造：从 GRI 指标索引页提取 disclosure 候选页，检索优先限定在候选页，fallback 和低质量页进入人工复核。
- 增加 `backend/src/standards/gri_report_index.py`，按 `report_index_pdf_page - report_index_report_page` 将报告页码换算为 PDF 页码。
- 修复 GRI 索引页双列表格解析污染问题：同一行中右侧 disclosure 的页码不再并入左侧 disclosure 候选页。
- 真实 PDF `confirm_llm=false` 验收通过：10 个 assessment、5 条 evidence、7 条 recommendation、1 条 `index_page_bounded` evidence、4 条 `global_fallback` evidence、9 条待复核 assessment，四个导出接口均返回 `200`。
- 本次未调用外部模型；fallback evidence 和低质量页 evidence 只能作为人工复核入口，不能作为最终合规结论。

### 2026-07-02

- 确认从端到端纵切开始构建项目。
- 确认 PostgreSQL + pgvector 预留，替代早期 SQLite 设想。
- 确认 PDF 混合多路由管线。
- 确认前端使用 Next.js App Router。
- 初始化前端 Next.js App Router、Tailwind、TanStack Query、Vitest 骨架。
- 实现前端上传、结果、复核、审计页面和 Recharts 图表封装。
- 增加 FastAPI `response_model` 契约，前端类型由 OpenAPI 生成到 `frontend/lib/generated/`。
- 将后端 pytest 隔离到测试库 `esg_agent_test`，避免测试清空开发库。
- 完成本地端到端 HTTP 验收：上传、`confirm_llm=false` 分析、人工复核、JSON/CSV 导出和 audit 事件。
- 从 `../envision` 受控复制首批真实验收资产：远景能源 2024 中文 ESG 报告、GRI 官方合并标准 PDF、4 个 GRI/source manifest；记录到 `backend/data/manifests/assets_manifest.json`。
- 简化本项目数据目录：报告放在 `backend/data/reports/`，标准放在 `backend/data/standards/`，manifest 放在 `backend/data/manifests/`，运行时文件仍放在 `backend/data/runtime/`。
- 用 `backend/data/reports/Envision Energy 2024-zh.pdf` 跑通 `confirm_llm=false` 真实 PDF 验收：上传、解析、分块、assessment、review、JSON/CSV 导出、audit 均通过；未调用外部模型。
- 本次真实 PDF 解析质量：78 页，77 页可抽取文本，77 个 chunk，总抽取文本 73,824 字符；第 78 页标记为 `low_text_density` 和 `scanned`；23 页检测到表格，6 页标记为 `complex_table`。
- 修复真实 PDF 验收暴露的长 evidence/recommendation ID 入库问题：超过数据库主键长度时使用 deterministic hash，原始 `task_id` 和 `chunk_id` 保留在 evidence metadata。
- 将运行入口从 `backend/data/standards/gri_requirements.sample.json` 切换为 `backend/data/manifests/gri_requirement_checklist.json` 的前 10 条 `current_gap`、mandatory、`hard_score` requirement。
- 当前真实 checklist 来源项仍标记为 `pending_review`，第一版关键词检索得到的 evidence 只能用于流程验收和人工复核入口，不能作为最终合规结论。
- 本次未复制旧 agent 代码、旧 Streamlit 页面、旧运行结果、旧 prompt、旧 SQLite 数据或 `../esg-dashboard` 内容。
- 将技术设计保存到 `docs/DESIGN.md`。
- 精简文档体系为 `AGENTS.md`、`README.md`、`docs/DESIGN.md`、`docs/DEVELOPMENT.md`、`docs/ASSETS.md`。

