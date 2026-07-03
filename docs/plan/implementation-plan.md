# esg-agent 实施计划

> **给后续执行代理的要求：** 实施本计划时，必须使用 `superpowers:subagent-driven-development` 处理可并行的独立任务，或使用 `superpowers:executing-plans` 顺序执行。进度用本文件中的 checkbox 更新。

## 目标

从空项目构建一个可运行的单报告 ESG 披露分析系统：

```text
上传 PDF
  -> 保存原始文件
  -> PDF 多路由解析
  -> 构建 GRI 披露任务
  -> 生成披露判断
  -> 生成证据和建议
  -> 人工复核
  -> JSON/CSV 导出
```

第一版优先跑通真实端到端闭环，暂不追求完整 GRI 覆盖、批量处理、登录权限、同行对标、舆情监测和多标准混合分析。

## 依据文档

- 产品和架构决策：`docs/DESIGN.md`
- 开发、运行和测试说明：`docs/DEVELOPMENT.md`
- 资产迁移规则：`docs/ASSETS.md`
- 历史计划归档：`docs/plan/esg-agent从零重建实施计划.md`

## 已确认技术栈

- 后端：Python 3.11、FastAPI、Pydantic v2、pydantic-settings、SQLAlchemy 2.0、Alembic、PostgreSQL、预留 pgvector、pytest。
- PDF：`pypdf`、`pdfplumber`、OCRmyPDF/Tesseract 接口、Docling fallback 接口、VLM 接口。
- LLM：通过薄适配层调用 OpenAI-compatible SDK，默认目标模型为 `deepseek-v4-flash`。
- 前端：Next.js App Router、TypeScript、Tailwind CSS、shadcn/ui、lucide-react、TanStack Table、Recharts、TanStack Query。
- API 契约：FastAPI OpenAPI 输出，前端自动生成 TypeScript types/client。
- 包管理：后端 `uv`，前端 `pnpm`。
- 本地服务：Docker Compose 管 PostgreSQL，后端和前端本机运行。

## 执行规则

- 除非 API 请求显式传入 `confirm_llm=true`，不得调用外部模型。
- 不提交 `.env`、上传报告、OCR 派生文件、runtime 数据库、外部模型私有响应、本地绝对路径。
- 原始 PDF 必须保留；OCR、解析、导出等派生产物单独保存。
- OCR/VLM 来源的 KPI 证据默认低置信度或 `needs_manual_review`。
- 禁止复制旧 agent 代码、旧 Streamlit 页面、旧 SQLite 数据库、历史运行目录、归档脚本、旧分阶段测试、静态假数据、无真实后端来源的指标卡片。
- 实施保持纵向小步闭环；只有当前功能确实需要时才增加抽象。
- 后端行为变化优先补最小 pytest 覆盖，再写实现。
- 前端核心页面必须覆盖空状态、加载状态、错误状态和数据状态。
- `docs/plan/` 下的计划文件必须使用中文；命令、路径、依赖名、代码标识和 API 路径可保留英文原文。

## 目标目录结构

```text
.
  README.md
  .gitignore
  .env.example
  docker-compose.yml

  backend/
    pyproject.toml
    alembic.ini
    .env.example
    alembic/
      env.py
      versions/
    src/
      main.py
      config/
      domain/
      db/
      standards/
      agents/
      workflows/
      services/
      tools/
      api/
    tests/
    data/
      reports/
      standards/
        gri/
        gri_requirements.sample.json
      manifests/
      runtime/

  frontend/
    package.json
    next.config.ts
    tsconfig.json
    postcss.config.mjs
    tailwind.config.ts
    app/
    components/
    lib/

  docs/
    DESIGN.md
    DEVELOPMENT.md
    ASSETS.md
    plan/
```

---

## 阶段 1：仓库基础

### 1.1 创建基础忽略规则和环境示例

- [x] 更新 `.gitignore`。

必须包含：

```gitignore
AGENTS.md
.env
.env.*
!.env.example
__pycache__/
.pytest_cache/
.ruff_cache/
.coverage
htmlcov/
.venv/
node_modules/
.next/
coverage/
dist/
backend/data/runtime/*
!backend/data/runtime/.gitkeep
.superpowers/
tmp/
```

- [x] 创建根目录 `.env.example`。

必须包含：

```env
DATABASE_URL=postgresql+psycopg://esg_agent:esg_agent@localhost:5432/esg_agent
BACKEND_CORS_ORIGINS=http://localhost:3000
UPLOAD_DIR=backend/data/runtime/uploads
DERIVED_DIR=backend/data/runtime/derived
TESSERACT_CMD=
OCRMYPDF_CMD=ocrmypdf
OPENAI_COMPATIBLE_API_BASE=
OPENAI_COMPATIBLE_API_KEY=
LLM_MODEL=deepseek-v4-flash
```

- [x] 创建 runtime 目录：
  - `backend/data/runtime/uploads/.gitkeep`
  - `backend/data/runtime/derived/.gitkeep`
  - `backend/data/runtime/exports/.gitkeep`

验证：

```powershell
rg -n -P "(?<![A-Za-z+])\\b[A-Za-z]:[\\\\/]" docs README.md .env.example
```

预期：除 `AGENTS.md` 外无匹配。

### 1.2 增加 PostgreSQL Docker Compose

- [x] 创建 `docker-compose.yml`。

服务要求：

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: esg_agent
      POSTGRES_USER: esg_agent
      POSTGRES_PASSWORD: esg_agent
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

验证：

```powershell
docker compose config
```

当前环境未检测到 `docker` 命令，Compose 配置需在安装 Docker 后补验。

---

## 阶段 2：后端骨架

### 2.1 创建后端包

- [x] 创建 `backend/pyproject.toml`。

最小依赖：

```toml
[project]
name = "esg-agent-backend"
version = "0.1.0"
requires-python = ">=3.11,<3.12"
dependencies = [
  "fastapi",
  "uvicorn[standard]",
  "pydantic>=2",
  "pydantic-settings",
  "python-multipart",
  "sqlalchemy>=2",
  "alembic",
  "psycopg[binary]",
  "pypdf",
  "pdfplumber",
  "openai",
]

[dependency-groups]
dev = [
  "httpx",
  "pytest",
  "pytest-cov",
  "ruff",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

- [x] 创建 `backend/.env.example`，字段与根目录环境示例保持一致。
- [x] 创建 `backend/src/__init__.py`。
- [x] 创建 `backend/src/main.py`。

行为要求：

- FastAPI app title 为 `esg-agent`。
- 注册 `/api/health`。
- 从 settings 读取 CORS 配置。

### 2.2 增加配置模块

- [x] 创建 `backend/src/config/settings.py`。

必须支持字段：

- `database_url`
- `backend_cors_origins`
- `upload_dir`
- `derived_dir`
- `tesseract_cmd`
- `ocrmypdf_cmd`
- `openai_compatible_api_base`
- `openai_compatible_api_key`
- `llm_model`

验证：

```powershell
cd backend
uv sync
uv run pytest
```

### 2.3 增加 health 测试

- [x] 创建 `backend/tests/test_health.py`。

断言：

- `GET /api/health` 返回 `200`。
- 响应包含 `{"status": "ok"}`。

---

## 阶段 3：领域模型层

### 3.1 创建枚举

- [x] 创建 `backend/src/domain/enums.py`。

必须包含：

- `RunStatus`：`pending`、`running`、`completed`、`failed`
- `ReviewStatus`：`not_required`、`needs_manual_review`、`approved`、`rejected`、`corrected`
- `AssessmentVerdict`：`disclosed`、`partially_disclosed`、`not_disclosed`、`unknown`
- `EvidenceSourceMethod`：`pypdf`、`pdfplumber`、`ocr`、`docling`、`vlm`、`manual`
- `PageQualityFlag`：`digital_text`、`scanned`、`low_text_density`、`complex_table`、`ocr_failed`、`needs_manual_review`

### 3.2 创建 Pydantic 领域模型

- [x] 创建 `backend/src/domain/models.py`。

必须包含：

- `Report`
- `AnalysisRun`
- `PageExtraction`
- `DocumentChunk`
- `DisclosureRequirement`
- `DisclosureTask`
- `EvidenceItem`
- `DisclosureAssessment`
- `Recommendation`
- `ReviewDecision`

判断和证据链路必须保留字段：

- `run_id`
- `report_id`
- `standard_id`
- `standard_version`
- `disclosure_id`
- `requirement_id`
- `evidence_id`
- `source_text`
- `source_page`
- `source_file_hash`
- `model_called`
- `review_status`

### 3.3 测试领域校验

- [x] 创建 `backend/tests/domain/test_models.py`。

覆盖：

- 有证据的有效 assessment 可以通过校验。
- 无证据时不得产生确定性披露结论，必须进入人工复核或返回 `unknown`。
- OCR/VLM 来源且涉及 KPI 的证据默认进入人工复核。

验证：

```powershell
cd backend
uv run pytest tests/domain
```

---

## 阶段 4：数据库和 Repository 层

### 4.1 创建 SQLAlchemy 基础设施

- [x] 创建 `backend/src/db/base.py`。
- [x] 创建 `backend/src/db/session.py`。
- [x] 创建 `backend/src/db/models.py`。

必须包含表：

- `reports`
- `analysis_runs`
- `document_pages`
- `document_chunks`
- `standard_requirements`
- `disclosure_tasks`
- `assessments`
- `evidence_items`
- `recommendations`
- `review_decisions`
- `audit_events`

向量化预留字段放在 `document_chunks`：

- `embedding_status`
- `embedding_model`
- `embedding_dim`
- `embedding_updated_at`

第一版不生成真实 embedding。

### 4.2 增加 Alembic

- [x] 创建 `backend/alembic.ini`。
- [x] 创建 `backend/alembic/env.py`。
- [x] 创建初始 migration 到 `backend/alembic/versions/`。

迁移要求：

- 使用 PostgreSQL 兼容字段类型。
- UUID 字段统一使用字符串或 PostgreSQL UUID，不混用。
- 需要查询的结构化字段用 `JSONB`，其余优先简单文本字段。
- 至少增加索引：
  - `reports.file_hash`
  - `analysis_runs.report_id`
  - `assessments.run_id`
  - `assessments.review_status`
  - `evidence_items.assessment_id`

### 4.3 创建 Repository

- [x] 创建 `backend/src/db/repositories.py`。

必须支持：

- 创建 report。
- 查询 report。
- 创建 run。
- 更新 run 状态。
- 保存页面和 chunks。
- 保存任务、assessment、evidence、recommendation。
- 列出 runs。
- 按 run 查询 assessments。
- 保存 review decision。
- 创建 audit event。

### 4.4 数据库测试

- [x] 创建 `backend/tests/db/test_repositories.py`。

要求：

- 使用测试数据库 session。
- 不依赖生产 `.env`。
- 覆盖核心 repository 写入和查询。

验证：

```powershell
cd backend
uv run pytest tests/db
```

---

## 阶段 5：PDF 多路由解析

### 5.1 文档存储

- [x] 创建 `backend/src/services/document_store.py`。

要求：

- 上传 PDF 保存到 `backend/data/runtime/uploads/`。
- 计算 SHA-256 hash。
- 不覆盖已存在原始文件。
- 派生产物保存到 `backend/data/runtime/derived/`。

### 5.2 页面检测和解析器

- [x] 创建 `backend/src/services/document_parser.py`。

必须包含：

- `PageQuality`
- `ParsedDocument`
- `classify_page_quality(page_text, image_count, table_count)`
- `DocumentParser.parse_pdf(path)`

解析要求：

- 用 `pypdf` 读取元数据、页数、outline。
- 用 `pdfplumber` 提取页面文本、表格提示和可用坐标。
- 识别扫描页和低文本密度页。
- 默认只标记需要 OCR 的页面，不全量 OCR。
- 返回 chunks 时保留 `source_method`、`source_page`、`bbox`、`quality_flags`。

### 5.3 OCR 和 fallback 接口

- [x] 创建 `backend/src/services/ocr.py`。
- [x] 创建 `backend/src/services/docling_fallback.py`。

第一版要求：

- OCR 函数接收选定页码。
- OCR 错误必须写入质量标记。
- Docling fallback 可先返回 `not_configured`，等待后续显式接入依赖。

### 5.4 解析器测试

- [x] 创建 `backend/tests/services/test_document_parser.py`。
- [x] 创建 `backend/tests/services/test_document_store.py`。

覆盖：

- 数字原生文本页标记为 `digital_text`。
- 空文本或低文本密度页标记为 `scanned` 或 `low_text_density`。
- OCR hook 可被 mock，且来源方法记录为 `ocr`。
- 原始文件路径保持不变。

---

## 阶段 6：标准适配器和 GRI

### 6.1 标准适配器契约

- [x] 创建 `backend/src/standards/base.py`。

协议要求：

- `standard_id`
- `standard_version`
- `load_requirements()`
- `build_tasks(run_id, report_id)`

### 6.2 GRIAdapter

- [x] 创建 `backend/src/standards/gri.py`。
- [x] 创建 `backend/data/standards/gri_requirements.sample.json`。

第一版范围：

- 保留一个足够端到端测试的 GRI-like seed subset。
- 运行入口使用 `backend/data/manifests/gri_requirement_checklist.json` 转换出的首批 10 条真实 `current_gap` requirement。
- 不把首批 10 条 requirement 表述为完整 GRI 覆盖。

### 6.3 适配器测试

- [x] 创建 `backend/tests/standards/test_gri_adapter.py`。

覆盖：

- 可以加载 requirements。
- 可以构建包含 `run_id`、`report_id`、`standard_id`、`standard_version`、`disclosure_id`、`requirement_id` 的任务。
- requirement JSON 格式错误时给出清晰失败。

---

## 阶段 7：工具层和 LLM 边界

### 7.1 检索和证据工具

- [x] 创建 `backend/src/tools/retrieval.py`。
- [x] 创建 `backend/src/tools/evidence.py`。

第一版检索：

- 对 `document_chunks` 做确定性 keyword search。
- 返回 top evidence candidates，包含页码和来源方法。
- 暂不做 embedding search。

### 7.2 判断和护栏

- [x] 创建 `backend/src/tools/judgment.py`。
- [x] 创建 `backend/src/tools/guardrails.py`。

行为要求：

- 没有证据时，verdict 为 `unknown`，review status 为 `needs_manual_review`。
- OCR/VLM 来源且用于 KPI 内容时，review status 为 `needs_manual_review`。
- 所有模型输出必须经过 Pydantic 校验。
- 校验失败生成需要人工复核的 assessment。

### 7.3 LLM client

- [x] 创建 `backend/src/tools/llm_client.py`。

行为要求：

- `confirm_llm=false` 时返回或抛出 `ModelCallBlocked`。
- `confirm_llm=true` 时通过配置的 base URL 和 model 调用 OpenAI-compatible SDK。
- 不记录密钥。
- 测试中必须 mock 外部调用。

### 7.4 工具测试

- [x] 创建：
  - [x] `backend/tests/tools/test_retrieval.py`
  - [x] `backend/tests/tools/test_guardrails.py`
  - [x] `backend/tests/tools/test_llm_client.py`

---

## 阶段 8：DisclosureAgent 和 Workflow

### 8.1 DisclosureAgent

- [x] 创建 `backend/src/agents/disclosure_agent.py`。

行为要求：

- 接收一个 `DisclosureTask`。
- 检索证据。
- 生成 `DisclosureAssessment`。
- 对缺失或部分披露生成 recommendations。
- 遵守 `confirm_llm`。
- 保存 `model_called` 状态。

### 8.2 SingleReportWorkflow

- [x] 创建 `backend/src/workflows/single_report_workflow.py`。

流程要求：

```text
读取 report
  -> 创建 run
  -> 解析 PDF
  -> 保存 pages/chunks
  -> 加载 GRI requirements
  -> 构建 disclosure tasks
  -> 对每个 task 执行 DisclosureAgent
  -> 保存 assessments/evidence/recommendations
  -> 标记 run completed 或 failed
  -> 写入 audit events
```

### 8.3 Workflow 测试

- [x] 创建 `backend/tests/agents/test_disclosure_agent.py`。
- [x] 创建 `backend/tests/workflows/test_single_report_workflow.py`。

覆盖：

- 不调用模型的成功路径。
- `confirm_llm=false` 阻止 LLM 调用。
- parser 失败时 run 标记为 failed 并保存错误。
- 无证据任务进入人工复核。

---

## 阶段 9：后端 API

### 9.1 Reports API

- [x] 创建 `backend/src/api/routes/reports.py`。

接口：

- `POST /api/reports/upload`
- `POST /api/reports/{report_id}/analyze`

行为要求：

- 上传接口只接受 PDF。
- 上传后返回 `report_id`、file hash、original filename 和 status。
- analyze 接收 `confirm_llm`。
- analyze 创建或启动 run，并返回 `run_id`。

### 9.2 Runs API

- [x] 创建 `backend/src/api/routes/runs.py`。

接口：

- `GET /api/runs`
- `GET /api/runs/{run_id}`
- `GET /api/runs/{run_id}/assessments`
- `GET /api/runs/{run_id}/recommendations`

### 9.3 Review API

- [x] 创建 `backend/src/api/routes/review.py`。

接口：

- `GET /api/review/runs`
- `GET /api/review/runs/{run_id}/assessments`
- `POST /api/review/runs/{run_id}/decisions`

行为要求：

- review decision 记录 reviewer action、note、timestamp 和目标 assessment。
- review 更新必须创建 audit event。

### 9.4 Export API

- [x] 创建 `backend/src/api/routes/exports.py`。
- [x] 创建 `backend/src/services/export_service.py`。

接口：

- `GET /api/exports/runs/{run_id}/assessments.csv`
- `GET /api/exports/runs/{run_id}/review.csv`
- `GET /api/exports/runs/{run_id}/assessments.json`
- `GET /api/exports/runs/{run_id}/review.json`

### 9.5 API 测试

- [x] 创建：
  - `backend/tests/api/test_reports_api.py`
  - `backend/tests/api/test_runs_api.py`
  - `backend/tests/api/test_review_api.py`
  - `backend/tests/api/test_exports_api.py`

验证：

```powershell
cd backend
uv run pytest
```

---

## 阶段 10：前端骨架

### 10.1 创建 Next.js 文件

- [x] 创建 `frontend/package.json`。

必须依赖：

- `next`
- `react`
- `react-dom`
- `typescript`
- `@tanstack/react-query`
- `@tanstack/react-table`
- `recharts`
- `lucide-react`
- `clsx`
- `tailwind-merge`
- `class-variance-authority`

必须 dev dependencies：

- `vitest`
- `@testing-library/react`
- `@testing-library/jest-dom`
- `jsdom`
- `openapi-typescript`
- `tailwindcss`
- `postcss`
- `autoprefixer`
- `eslint`

- [x] 创建：
  - `frontend/next.config.ts`
  - `frontend/tsconfig.json`
  - `frontend/postcss.config.mjs`
  - `frontend/tailwind.config.ts`
  - `frontend/app/globals.css`
  - `frontend/app/layout.tsx`
  - `frontend/app/page.tsx`

### 10.2 API client 和 QueryProvider

- [x] 创建 `frontend/lib/api.ts`。
- [x] 创建 `frontend/lib/query-client.tsx`。
- [x] 创建 `frontend/lib/types.ts`。

API client 要求：

- 使用 `NEXT_PUBLIC_API_BASE_URL`，默认 `http://localhost:8000`。
- 非 2xx 响应抛出 typed error。
- 暴露与后端 endpoints 对应的函数。

### 10.3 布局

- [x] 创建 `frontend/components/layout/app-shell.tsx`。

导航：

- Home
- Reports
- Runs
- Review
- Audit

UI 约束：

- 工作台式布局。
- 不做聊天式入口。
- 不展示假指标。

验证：

```powershell
cd frontend
pnpm install
pnpm typecheck
pnpm test
pnpm build
```

---

## 阶段 11：前端核心页面

### 11.1 Reports 页面

- [x] 创建 `frontend/app/reports/page.tsx`。
- [x] 在 `frontend/components/upload/` 创建上传组件。

行为要求：

- 选择 PDF。
- 上传 PDF。
- 展示返回的 `report_id` 和 hash。
- 展示外部模型调用确认控件。
- 启动分析。
- 跳转到 run result 页面。

### 11.2 Run result 页面

- [x] 创建 `frontend/app/runs/[runId]/page.tsx`。
- [x] 在 `frontend/components/analysis/` 创建结果组件。

行为要求：

- 轮询 run status。
- 展示空状态、加载状态、错误状态和数据状态。
- 用 TanStack Table 展示 assessment table。
- 展示证据页码和来源方法。
- 展示 recommendations。
- 提供 JSON/CSV 导出链接。

### 11.3 Review 页面

- [x] 创建 `frontend/app/review/page.tsx`。
- [x] 在 `frontend/components/review/` 创建复核组件。

行为要求：

- 列出有人工复核项的 runs。
- 按 review status 筛选。
- 保存 approve/reject/correct 决策。
- 展示已保存决策状态。

### 11.4 Audit 页面

- [x] 创建 `frontend/app/audit/page.tsx`。

行为要求：

- 展示 run events、model call status、file hash 和 errors。
- 没有事件时展示空状态。

### 11.5 图表封装

- [x] 创建 `frontend/components/charts/disclosure-summary-chart.tsx`。

要求：

- Recharts 使用只保留在该组件内。
- 页面组件传业务数据，不直接传 Recharts-specific props。
- 后续迁移 ECharts 时，主要修改 chart components。

---

## 阶段 12：OpenAPI 类型生成

### 12.1 增加 OpenAPI 生成脚本

- [x] 在 `frontend/package.json` 增加脚本：

```json
{
  "scripts": {
    "generate:api": "openapi-typescript http://localhost:8000/openapi.json -o lib/generated/api-types.ts"
  }
}
```

- [x] 创建 `frontend/lib/generated/.gitkeep`。

### 12.2 后端契约验证

- [x] 确认后端 OpenAPI 可通过 `/openapi.json` 访问。
- [x] 后端 API 稳定后生成前端 types。
- [x] 可行时用生成类型替换重复手写 response types。

验证：

```powershell
cd frontend
pnpm generate:api
pnpm typecheck
```

---

## 阶段 13：资产迁移 Manifest

### 13.1 创建显式 manifest

- [x] 创建 `backend/data/manifests/assets_manifest.json`。

初始结构：

```json
{
  "assets": [],
  "notes": [
    "Only approved source materials may be copied into this project.",
    "Original source repositories must not be deleted, overwritten, or rolled back."
  ]
}
```

### 13.2 后续只迁移获批来源资产

允许资产类别：

- 远景能源 2024 中文 ESG 报告。
- GRI 标准资料。
- 必要 prompt 文本。
- 必要 manifest 记录。
- 可复用 UI 信息架构笔记。

验证：

```powershell
rg -n "static fake|mock metric|old sqlite|streamlit" backend frontend docs
```

预期：实现不依赖禁止迁移的旧资产。

---

## 阶段 14：端到端验收

### 14.1 后端验证

- [x] 启动 PostgreSQL：

```powershell
docker compose up -d postgres
```

- [x] 运行 migration：

```powershell
cd backend
uv run alembic upgrade head
```

- [x] 运行测试：

```powershell
cd backend
uv run pytest
```

### 14.2 前端验证

- [x] 运行前端检查：

```powershell
cd frontend
pnpm typecheck
pnpm test
pnpm build
```

### 14.3 手动工作流验证

- [x] 启动后端：

```powershell
cd backend
uv run uvicorn src.main:app --reload --port 8000
```

- [x] 启动前端：

```powershell
cd frontend
pnpm dev
```

- [x] 验证：
  - 上传 PDF 返回 `report_id`。
  - `confirm_llm=false` 分析返回 `run_id`。
  - run 可在不调用外部模型的情况下完成。
  - assessments 展示 evidence、page、source method 和 review status。
  - 缺少证据的条款进入人工复核。
  - review decision 可保存。
  - JSON 和 CSV 可导出。
  - audit view 展示 upload、parse、analyze、review、export events。

### 14.4 文档更新

- [x] 用实际 setup 和 run 命令更新 `README.md`。
- [x] 用最终测试命令更新 `docs/DEVELOPMENT.md`。
- [x] 只有确认设计决策变化时才更新 `docs/DESIGN.md`。
- [x] docs 路径保持相对路径，不写本地绝对路径。

---

## 完成标准

- [x] 后端 pytest 通过。
- [x] 前端 typecheck 通过。
- [x] 前端测试通过。
- [x] 前端 build 通过。
- [x] 上传工作流通过。
- [x] `confirm_llm=false` 分析工作流通过。
- [x] 人工复核工作流通过。
- [x] 导出工作流通过。
- [x] docs 中没有本地绝对路径。
- [x] 未跟踪 `.env`、上传 PDF、OCR 派生文件和外部模型私有响应。

## 第一版已知限制

- GRI 覆盖从真实 checklist 的首批 10 条 `current_gap` requirement 开始，尚未覆盖完整 GRI。
- schema 预留向量检索字段，但第一版不启用向量检索。
- Docling 先保留 fallback 接口，依赖和运行环境后续显式接入。
- OCR 按页面分类定向执行，不默认全报告 OCR。
- VLM 辅助能力受 `confirm_llm=true` 控制，高风险证据必须人工复核。
