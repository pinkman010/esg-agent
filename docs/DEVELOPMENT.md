# 开发运行文档

## 0. 当前发布基线

截至 2026-08-23，当前正式发布基线为 `v1.3.1`，后端包、前端包和 OpenAPI `info.version` 统一为 `1.3.1`。运行时 OpenAPI 的 40 条 `/api/*` 路径已全部同步到 `frontend/lib/generated/api-types.ts`，其中包括 `GET /api/capabilities/ocr`。

v1.3.1 发布门禁按顺序执行，避免 PostgreSQL、pytest、前端构建和 Envision regeneration 并发争用本机内存。最终记录为：后端 823 项测试与 Ruff 通过；前端 39 个测试文件、150 项测试、lint（0 error、2 条既有 warning）、typecheck 和 production build 通过；Envision v3 regeneration 与 audit 通过，`577/499/78/0`、0 global fallback、0 新增 false disclosed、0 新增 wrong source page。发布门禁使用 `confirm_llm=false`、`OCR_ENABLED=false`，不会发起 DeepSeek、embedding、OCR 或 VLM 调用。

完整发布范围、限制和终止条件见 `docs/product/v1.3.1-final-release-acceptance.md`；`docs/product/v1.3-final-release-acceptance.md` 保留为历史发布记录。

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

第一版正式主链路需要：

- PostgreSQL。
- pgvector 只服务离线影子 embedding；正式分析链路不读取向量结果。
- Node.js。
- Python 3.11。

受控 OCR 路由额外需要：

- OCRmyPDF。
- Tesseract，以及请求语言对应的语言包。
- Ghostscript，供 OCRmyPDF 真实执行 OCR 时调用。

缺少上述 OCR 依赖不会影响 `enable_ocr=false` 的正式默认链路。OCR 已通过 Envision 第 77 页单页受控试点；通用扫描报告仍需满足 `docs/plan/ocr-production-readiness-deferred-plan.md` 的样本和质量门槛。

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
- OCR 开关、语言和页数上限。
- OpenAI-compatible API base URL。
- 模型名称。
- CORS 来源。

OCR 相关环境变量：

- `OCR_ENABLED=false`：全局强制门禁；只有该值为 `true` 且请求显式传入 `enable_ocr=true` 时才允许 OCR。
- `OCR_LANG=chi_sim+eng`：OCRmyPDF/Tesseract 语言。
- `OCR_MAX_PAGES=5`：未显式指定页码时最多处理的低文本/扫描页数。
- `TESSERACT_CMD`：Tesseract 命令或路径。
- `OCRMYPDF_CMD=ocrmypdf`：OCRmyPDF 命令。
- `GHOSTSCRIPT_CMD`：Ghostscript 命令；Windows 通常使用 `gswin64c`。
- `OCR_TIMEOUT_SECONDS=300`：单次 OCR 子进程超时，允许范围为 1–1800 秒。

`GET /api/capabilities/ocr` 返回全局开关、依赖可用性、语言、页数上限和稳定 dependency code，不返回本机路径或原始 stderr。该接口与分析 workflow 共用 preflight；`/api/health` 继续只表达服务存活。

2026-08-17 本机受控试点验证版本为 OCRmyPDF 17.8.0、Ghostscript CLI 10.07.1（Chocolatey 包 `Ghostscript 10.7.1`）和 Tesseract 5.5.0.20241111，语言包为 `chi_sim`、`eng`、`osd`。版本核验命令：

```powershell
cd backend
uv run --no-sync ocrmypdf --version
gswin64c --version
tesseract --version
tesseract --list-langs
```

运行回滚优先设置 `OCR_ENABLED=false` 并保持请求 `enable_ocr=false`。需要移除系统依赖时，先停止 OCR 任务，再由管理员执行 `choco uninstall ghostscript -y`；该操作不删除原始报告，派生文件仍按 runtime 数据策略处理。

DeepSeek 相关环境变量：

- `OPENAI_COMPATIBLE_API_BASE=https://api.deepseek.com`；
- `OPENAI_COMPATIBLE_API_KEY`：只保存在本机 `backend/.env`，禁止提交；
- `LLM_MODEL=deepseek-v4-flash`；
- `LLM_THINKING_TYPE=enabled`、`LLM_REASONING_EFFORT=high`；
- `LLM_RESPONSE_FORMAT=json_object`；
- `LLM_PROMPT_VERSION=deepseek-gri-assist-v1.2`；
- `LLM_MAX_CONCURRENCY=8`、`LLM_MAX_CALLS_PER_RUN=200`。

外部模型默认关闭。只有分析请求显式传入 `confirm_llm=true` 才允许调用；失败 suggestion 追加保留并降级，不能覆盖规则 assessment、人工 snapshot、适用性或正式输出门禁。

AI 默认候选筛选还要求 structure 独立、复核优先级为高/中且至少有一条合格实质 evidence。`image_body_not_extracted` 和显式非实质 evidence 不进入默认调用；索引限定路由和短文本标记本身不构成跳过依据。`confirm_llm=true` 且零合格候选时保存逐项 skipped 原因但不调用模型；`confirm_llm=false` 仍不保存逐项 suggestion。

只读观测命令：

```powershell
cd backend
uv run --no-sync python -m src.tools.report_ai_assistance_metrics `
  --run-id <run-id> `
  --output-prefix envision_ai_routing
```

工具在 `REPEATABLE READ READ ONLY` 事务中读取指定 run，输出到 `tmp/ai/`，不创建模型 client、不写数据库，也不输出 raw response、完整 Prompt、证据正文、密钥或数据库 URL。confidence 和人工采纳/修改/拒绝分布只用于产品工程观测，不构成模型正确率、GRI 认证或 ESG 专家结论。

SiliconFlow BGE-M3 离线影子 RAG 环境变量：

- `EMBEDDING_ENABLED=false`：默认关闭；
- `EMBEDDING_PROVIDER=siliconflow`；
- `EMBEDDING_API_BASE=https://api.siliconflow.cn/v1`；
- `EMBEDDING_API_KEY`：只保存在本机 `backend/.env` 或当前 shell，禁止提交；
- `EMBEDDING_MODEL=BAAI/bge-m3`；
- `EMBEDDING_DIM=1024`；
- `EMBEDDING_BATCH_SIZE=16`；
- `EMBEDDING_MAX_INPUT_TOKENS=8192`；
- `EMBEDDING_MAX_INPUT_CHARS=6000`；
- `EMBEDDING_TIMEOUT_SECONDS=60`；
- `EMBEDDING_MAX_RETRIES=2`。

`EMBEDDING_ENABLED=true` 只表示允许 embedding client 发起调用，仍需执行当次人工批准。DeepSeek 影子生成另需 `--confirm-llm` 和单独批准；两个授权不能互相替代。

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
pnpm lint
pnpm typecheck
pnpm test
pnpm build
pnpm dev
```

### 本地演示环境

本机使用一套代码和 PostgreSQL 实例，数据库按用途隔离：

- `esg_agent`：开发、回归和长期验收数据；
- `esg_agent_demo`：可重建的空演示库；
- `esg_agent_test`：pytest 测试库。

演示环境配置参考 `backend/.env.demo.example`。演示上传和派生文件写入 `backend/data/runtime/demo/`，原始报告、标准文件和 manifest 继续从共享只读资产目录读取。

在启动 demo 后端、执行 Alembic 或运行重置工具前，先在同一个 PowerShell 终端加载演示配置：

```powershell
docker compose up -d postgres

$demoDbExists = docker compose exec -T postgres `
  psql -U esg_agent -d postgres -tAc `
  "SELECT 1 FROM pg_database WHERE datname='esg_agent_demo'"
if ($demoDbExists.Trim() -ne "1") {
  docker compose exec -T postgres createdb -U esg_agent esg_agent_demo
}

$env:APP_ENV="demo"
$env:DATABASE_URL="postgresql+psycopg://esg_agent:esg_agent@localhost:5432/esg_agent_demo"
$env:UPLOAD_DIR="backend/data/runtime/demo/uploads"
$env:DERIVED_DIR="backend/data/runtime/demo/derived"
$env:OCR_ENABLED="false"
```

这些变量只影响当前终端进程，不写入或提交 `.env`。后续 `reset_demo_environment`、Alembic 和 uvicorn 必须在同一终端运行，确保三者使用同一 demo 配置。

普通演示路径：在首页重复上传同一 PDF 后选择“查看已有结果”或“重新上传并分析”。前一个选项打开相同哈希下按创建时间排序的最新报告；后一个选项使用 `duplicate_policy=create_new` 创建新的 `report_id` 并进入 metadata 确认页。已有报告和历史结果保持不变，不需要清空数据库或切换环境。

在线清理属于维护操作，只允许 demo 后端，普通前端不调用。请求体为 `{"confirmation":"RESET_DEMO"}`；存在 `pending/running` run 时返回 `409 demo_reset_blocked_active_run`；非 demo 或实际连接库不是 `esg_agent_demo` 时返回 `404 demo_reset_unavailable`。数据库清理成功但运行时文件清理失败时返回 `500 demo_runtime_cleanup_failed`，此时数据库已经为空，必须按故障恢复路径处理。

在线重置不会触碰共享只读资产或 `esg_agent`。它只用于维护人员主动清理隔离演示环境，不作为产品验收步骤。

停止服务后的离线故障恢复：

```powershell
# 先关闭仍连接 demo 库的后端和分析任务
cd backend
uv run --no-sync python -m src.tools.reset_demo_environment --dry-run
uv run --no-sync python -m src.tools.reset_demo_environment --confirm-database esg_agent_demo
uv run --no-sync alembic current
uv run --no-sync uvicorn src.main:app --reload --port 8000
```

重置工具只允许 `APP_ENV=demo`、数据库名为 `esg_agent_demo`，且上传和派生目录位于 `backend/data/runtime/demo/`。任一校验失败时停止。重置不处理 `backend/data/reports/`、`backend/data/standards/`、`backend/data/manifests/` 或现有 `esg_agent` 数据。

后端重启会在 lifespan 启动阶段把数据库中遗留的 `pending/running` run 标记为 `failed`，原因固定为“分析服务重启，任务已中断”。该恢复只收敛状态，不自动重跑、不清库；用户随后可从报告页重新启动分析。

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

## 7. 企业产品闭环验收

当前代码 Alembic head：`0012_chunk_embeddings`。`0003` 至 `0008` 覆盖报告 metadata、分析阶段、风险快照、人工复核快照、整改任务和版本化输出；`0009` 增加 active run 唯一索引；`0010` 增加 risk-v2.1 维度；`0011` 增加标准结构计数、task 上下文和追加式 AI suggestion；`0012` 启用 pgvector 并增加只读影子向量派生表。main/demo 数据库均已在独立授权后升级到 `0012`；后续新增 migration 仍须单独确认目标数据库，并在启动使用新代码 head 的后端前执行 `uv run --no-sync alembic upgrade head`。

核心产品 API：

- `POST /api/reports/upload`（支持 `duplicate_policy=reject|create_new`）、`POST /api/reports/{report_id}/confirm-metadata`
- `POST /api/reports/{report_id}/analyze`、`GET /api/runs/{run_id}/stages`
- `GET /api/reports/{report_id}/dashboard`、`GET /api/reports/{report_id}/scope-items`
- `GET /api/reports/{report_id}/review-queue`、`GET /api/reports/{report_id}/applicability-queue`
- `GET /api/reports/{report_id}/pages/{page_number}/image`
- `POST /api/assessments/{assessment_id}/review-decisions`
- `POST /api/reports/{report_id}/applicability-decisions`
- `POST /api/reports/{report_id}/actions`、`PATCH /api/actions/{action_id}`
- `POST /api/reports/{report_id}/exports/draft`、`POST /api/reports/{report_id}/exports/formal`
- `POST /api/demo/reset`（仅 demo 环境）

正式输出门禁：分析必须完整，且全部高复核优先级 assessment 必须已有有效 review snapshot。草稿不受该门禁限制，但 review scope 会记录草稿标识、分析不完整数、高/中优先级复核范围、适用性待判定数、run、engine version 和 risk rule version。正式版本使用递增版本号，旧正式版本标记为 superseded，文件 manifest 保存路径、大小和 SHA256。

risk-v2.1 将披露结论、证据状态、适用性状态和复核优先级分开。`unknown + 无证据` 为低优先级，`unknown + 仅索引/从略说明` 为中优先级，只有明确冲突、证据失效或严重质量异常进入高优先级。优先级数量由当前 499 个独立判断结果动态产生，不能硬编码比例；上下文项不进入优先级分布。

产品闭环自动验收命令：

```powershell
docker compose up -d postgres

cd backend
uv run --no-sync alembic upgrade head
uv run --no-sync pytest -q

cd ../frontend
pnpm typecheck
pnpm test
pnpm build
```

API 端到端测试覆盖上传、metadata 确认、标准范围计数、规则阶段与后端 AI 辅助阶段、复核队列、人工复核、整改、草稿门禁和正式输出。人工产品验收重点检查：报告列表、分析进度、dashboard、三栏复核、完整核查表、整改任务、版本化输出，以及“高优先级项目已复核”表述未暗示 577 个标准核查单元均已人工确认。

首次上传演示还必须检查：企业名称、年度和语言由文件名及 PDF 前两页本地文本自动预填；普通页面不显示内部 `report_id`；前端按八个业务阶段权重和真实 units 计算进度，不显示固定条数；AI 阶段展示 succeeded/failed/skipped 汇总，终态不转圈；超过 120 秒无 stage event 时显示中断提示。重复上传需同时验证“查看已有结果”和“重新上传并分析→新 report metadata 确认”两条路径。

### 前端演示体验人工验收

本轮以普通 Edge 或 Chrome 验收，不使用 Codex 内置浏览器。启动后先确认后端实际读取 Demo 配置：

```powershell
$env:APP_ENV="demo"
$env:DATABASE_URL="postgresql+psycopg://esg_agent:esg_agent@localhost:5432/esg_agent_demo"
$env:UPLOAD_DIR="backend/data/runtime/demo/uploads"
$env:DERIVED_DIR="backend/data/runtime/demo/derived"

cd backend
uv run --no-sync python -c "from sqlalchemy.engine import make_url; from src.config.settings import get_settings; print(make_url(get_settings().database_url).database)"
```

命令必须输出 `esg_agent_demo`。再检查后端运行环境身份和报告审计路由：

```powershell
$health = Invoke-RestMethod -Uri "http://localhost:8000/api/health"
$openapi = Invoke-RestMethod -Uri "http://localhost:8000/openapi.json"

$health.app_env
$openapi.paths.PSObject.Properties.Name -contains "/api/reports/{report_id}/audit"
```

普通产品预期依次输出 `demo` 和 `True`。任一结果不符时停止产品验收，不继续上传、复核或生成输出；先重启当前代码对应的后端并检查启动终端中的环境变量。

前端演示主路径：

1. 打开工作台首页，确认无报告、分析中和已完成报告分别提供真实下一步。
2. 上传 Envision 2024 中文报告，确认首次上传页不预先显示 577。
3. 核对自动识别的企业、年度和语言；人工确认后启动分析。AI 默认关闭，只有明确授权时才开启。
4. 查看八阶段进度、当前阶段、完成阶段数、终态按钮和 120 秒中断提示。
5. 在报告总览核对 577 项范围、披露结论、复核优先级、适用性和规则/AI/人工分层。
6. 验证完整核查范围首页、末页、上下文项和复核详情跳转。
7. 在三栏工作台验证队列、规则/AI/人工三层、PDF 页图、缩放、翻页、重试和追加式人工快照。
8. 创建并更新整改任务，确认关联核查项、负责人、截止日期和变更说明。
9. 生成草稿并检查输出门禁、复核范围和版本信息；页面不得声称单文件下载或完整 `actions_xlsx` 已实现。
10. 再次上传相同 PDF，分别验证“查看已有结果”和“重新上传并分析”两条路径。

三个验收视口：

- 1440px：完整报告侧栏和三栏复核同时可见。
- 1024px：报告侧栏收窄；复核区可通过“队列 / 判断 / 证据”切换。
- 768px：使用顶部导航；表格仅在自身区域横向滚动，页面主体不产生横向溢出。

发现问题按以下格式记录：

```text
标题：
严重程度：阻断 / 严重 / 一般 / 轻微
环境：浏览器、视口、APP_ENV、数据库名、report/run
前置条件：
复现步骤：
预期结果：
实际结果：
影响范围：
证据：截图、接口响应或日志
建议修复：
```

旧 `review_decisions` 已完成两个连续阶段的数据映射兼容测试，但旧 API、旧前端工作台和旧导出仍有调用者，因此暂不删除。完成调用迁移后，应以独立 migration 验证 upgrade/downgrade，再申请清理。

### 当前验收风险与后续项

本轮已闭环：重复上传提供“查看已有结果”和“重新上传并分析”，后者保留历史并创建新报告；同一报告 active run 同时受 API 预检查和 `0009` 数据库部分唯一索引保护；metadata 进入分析后禁止改写；服务重启会收敛遗留 active run。

- 适用性单条与当前页批量确认、assessment reopen、report 级审计和单 export 文件下载均已实现；通用 verdict 批量复核、独立 report reopen 和单 export metadata 接口不在当前范围。
- `actions_xlsx` 已按整改任务字段生成任务清单，并进入草稿和正式输出的四文件 manifest；无任务时仍生成带固定表头和免责声明的有效工作簿。
- 旧 `/api/review/*`、旧 `/api/exports/runs/*`、`/api/audit/runs` 和对应旧前端页面仍承担兼容用途，不能删除 `review_decisions`。
- Goldwind 100 条历史人工 gate 保留；Phase 1.7 另以 Goldwind 52 页真实报告完成独立产品 E2E。两者均为工程证据，不构成 ESG 专家 gold。
- `esg_agent` 开发/长期验收库包含多次 Envision regeneration 记录，禁止为演示清理；重复上传可直接创建新报告，因此普通演示和验收都不依赖空库。需要隔离展示数据时可连接 `esg_agent_demo`，reset 只作为显式维护操作。
- Codex 内置浏览器控制在本机发生两次桌面应用闪退。自动页面截图改用独立无头 Edge；人工验收使用普通浏览器，不再启用 Codex 内置浏览器。
- 外部模型和 OCR/VLM 默认关闭。DeepSeek 只在 `confirm_llm=true` 且用户明确批准后启用；OCR/VLM 本轮未启用。

当前自动门禁（2026-07-29）：后端 774 项测试和 Ruff 通过；前端 30 个测试文件、121 项测试、typecheck 和 production build 通过；Envision v3 内部结构为 `577/499/78/0`，global fallback、新增 false disclosed 和新增 wrong source page 均为 0，audit 为 0 error、0 warning。16 条历史结果差异全部进入最终裁决资产，0 条 pending。Goldwind 52 页真实报告产品 E2E 通过。代码和空测试数据库 head 均为 `0012_chunk_embeddings`。

DeepSeek 225 条真实评估固定使用 Envision 报告 `report-14864b1a3ef64512b0e5d3676a120bc1` 和 run `run-526bd97aef5d4b9baa14618b719081c9`。最终指标：一致 162/224（72.32%），适用性例外 1，累计定向补跑 18 次；guardrail 后 false disclosed、证据 ID 越界、可比错页、schema 失败和模型失败均为 0。该结果保留为 AI 辅助工程基线，不构成 GRI 专家认证或最终合规结论。本轮 v1.1 冻结没有修改 DeepSeek 模型、Prompt、调用范围或 guardrail。

普通 Chrome 已在 `APP_ENV=demo`、`esg_agent_demo` 和 demo runtime 下完成 Envision v1.1 主流程验收。产品通过“重新上传并分析”创建新的 `report_id`，不要求 reset 空库；同一哈希存在多份历史时，重复响应按创建时间返回最新报告。本轮 report 为 `report-15401bb4334e40d4a0885730f2635b22`，run 为 `run-92bf75b11eb042dab6cb689311634fe1`；`confirm_llm=false`，八阶段完成，499 个独立判断项规则失败 0，AI 阶段 skipped，OCR/VLM 均未启用。Dashboard 显示核查范围 577 项；完整范围首尾分页、上下文状态和三栏页图证据均通过。验收保存 1 条追加式人工 snapshot，高优先级进度更新为 1/9；创建 1 条关联 `GRI 2-5-a` 的整改任务，并生成草稿 `export-cbe69421eda24bb4b67ca7fa2b9df3b9`。Chrome 自动化无法向原生文件选择器赋值，用户已在普通 Chrome 完成真实重复上传，双路径继续由真实 API 和前端自动测试覆盖。验收事实见 `docs/product/mvp-acceptance-report.md`。

review CSV 生成后必须执行硬门禁自查：

```powershell
cd backend
@'
from src.tools.review_csv_audit import audit_review_csv
result = audit_review_csv("../tmp/review/current_350_review_after_rules.csv", report_total_pages=78)
print("ok=", result.ok)
print("errors=", result.errors)
print("warnings=", result.warnings)
'@ | uv run --no-sync python -
```

自查覆盖 `global_fallback`、页码越界、`page_label` 乱码、`omission_note` 升格、KPI 表缺少 `complex_table`、鉴证页缺少 OCR/VLM 风险标记、GRI 305 误挂 PDF 第 3 页等硬规则。

### Requirement/Evidence Ontology

系统将 requirement 拆为语义标签，将 evidence 拆为证据类型，再通过 verdict matrix 判断 `disclosed` / `partially_disclosed` / `unknown`。

规则优先级：

1. `omission_note` / `not_applicable` 先短路为 `unknown + needs_manual_review`。
2. contract / report profile 提供候选页。
3. evidence kind 识别证据类型。
4. ontology matrix 给默认 verdict。
5. per-ID contract 作为最终 override / guardrail。

关键边界：

- KPI 数量或比例可以支撑数值类 leaf。
- 总体值不能自动传播到性别、员工类别、地区拆分 leaf。
- 政策和管理机制不能自动支撑具体风险运营点、供应商类型或安保人员人权培训比例。
- `compilation_requirement` 只转成充分性规则、`missing_items` 和 guardrail，不作为独立 assessment requirement。
- 固定 PDF 页码只用于当前报告回归样本；跨报告逻辑必须依赖 KPI 行标签、年份列、单位和 evidence type。

### Envision 固定页码清单

固定页码清单输出到 `tmp/review/envision_fixed_page_inventory.csv`，用于把 Envision 2024 的回归页码从通用 contract 迁入 report profile。

当前批次统计：

- `batch_1_kpi_pages`：66 行，PDF 第 63-68 页 KPI 表。
- `batch_2_section_pages`：154 行，章节正文页。
- `batch_3_index_omission_pages`：23 行，索引、从略和不适用说明页。
- `batch_4_empty_routes`：68 行，无有效证据的 no-evidence guardrail。

迁移顺序为 KPI 页、章节页、索引/从略页、empty routes。每批迁移必须跑 577 regression gate，硬字段不得回退；允许 `candidate_page_source` 从 contract 切换为 report profile。

first-pass 质量评估命令：

```powershell
cd backend
uv run --no-sync python -m src.tools.first_pass_quality ../tmp/review/current_550_review.csv ../tmp/review/current_550_review_after_rules.csv
```

该工具按 `requirement_id` 聚合首行，并支持人工复核字段：`manual_label`、`correct_pdf_pages`、`suggested_verdict`、`issue_type`。输出指标包括 first-pass recall、false disclosed、wrong source page、unknown leakage 和 after-rules delta。

## 8. Envision v3 Review CSV Regeneration Gate

用途：从 Envision 2024 源报告、report profile 和 v3 标准结构重新生成 499 个独立 assessment 的证据展开 CSV，并验证 `577/499/78/0` 内部范围、最终裁决和已批准人工基线。

命令：

```powershell
cd backend
uv run --no-sync python -m src.tools.regenerate_review_csv `
  --report-id envision_2024_v3 `
  --pdf "data/reports/Envision Energy 2024-zh.pdf" `
  --profile data/reports/profiles/envision_2024.json `
  --requirements data/manifests/gri_requirement_checklist_v3.json `
  --manual-review-workbook data/review_inputs/envision_2024/manual/envision_2024_577_manual_review_second_review_Pro_20260719.xlsx `
  --final-adjudications data/review_inputs/envision_2024/adjudication/envision_2024_result_adjudication_v1.csv `
  --output data/runtime/evaluations/envision_2024/current_499_review_regenerated.csv `
  --baseline data/review_inputs/envision_2024/baselines/current_577_review_regenerated.csv `
  --audit-output data/runtime/evaluations/envision_2024/current_499_review_regenerated_audit.json `
  --diff-summary-output data/runtime/evaluations/envision_2024/current_499_review_regeneration_diff_summary.json `
  --scope-summary-output data/runtime/evaluations/envision_2024/current_499_review_scope_summary.json `
  --report-total-pages 78
```

通过标准：

- 标准单元 577、独立 assessment 499、上下文项 78、方法待确认项 0。
- 唯一 assessment requirement 为 499；多证据可展开为多行。
- 6 条复合结构裁决全部可追溯，16 条结果裁决为 0 pending。
- `structure_status`、`source_requirement_text`、`effective_requirement_text` 不得为空。
- `review_csv_audit` 通过。
- `global_fallback=0`。
- `omission_note` 不升格。
- `disclosed` 全部为 `not_required`。
- `partially_disclosed` 和 `unknown` 全部为 `needs_manual_review`。
- 224 个可比较人工 verdict 加 1 个适用性例外不得新增 false disclosed 或 wrong source page。

产物写入 `backend/data/runtime/evaluations/envision_2024/`，本地保留并登记 SHA256，不提交运行时文件。

## 9. Review CSV 与诊断字段分层

新增 review、routing 或 holdout 字段前，必须先说明字段所属层级和消费者。默认不把诊断字段升为正式证据 schema。

字段分层：

- 正式证据字段：可进入产品 schema、数据库或前端 review UI。包括 `source_pdf_page`、`source_report_page`、`page_label`、`evidence_type`、`evidence_preview`、`quality_flags`、`requires_ocr`、`requires_vlm`、`needs_ocr_or_vlm`。
- 复核导出字段：服务人工复核 CSV，可出现在 review export，但不一定进入核心数据库列。包括 `rationale`、`missing_items`、`candidate_pdf_pages`、`candidate_report_pages`、`retrieval_strategy`。
- 路由诊断字段：只允许进入 `*_diagnosis.csv`、`*_review_pack.csv`、`*_quality_summary.json` 等临时诊断产物，不进入正式 review CSV 或产品 schema。包括 `route_status`、`route_failure_reason`、`profile_candidate_pdf_pages`、`before_*`、`manual_label`、`suggested_verdict`、`issue_type`、`correct_pdf_pages`。
- ontology/internal metadata：默认内部使用，不升为顶层字段，除非前端筛选、审计统计或多人复核明确需要。包括 `semantic_group`、`facets`、`evidence_kinds`、`candidate_page_source`、`kpi_metric_terms`、`decision_source`。

约束：

- 不继续向主 review CSV 无边界加列。
- 新增诊断信息优先放入单独诊断文件。
- 下一轮 `preview anchor` 和 `section route guardrail` 改造不得新增顶层字段，优先复用 `evidence_preview`、`retrieval_strategy`、`evidence_type` 和现有诊断产物。

## 10. OpenAPI 类型生成

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

## 11. SiliconFlow BGE-M3 离线影子 RAG

当前阶段只处理显式指定报告的 `document_chunks`。结果只进入 `tmp/embedding/`，不接入 `retrieve_evidence()`、`SingleReportWorkflow`、正式 API 或前端，不改变 assessment、risk、AI suggestion、人工 snapshot 和 export。

先在测试库验证 migration：

```powershell
cd backend
$env:APP_ENV="test"
$env:DATABASE_URL="postgresql+psycopg://esg_agent:esg_agent@localhost:5432/esg_agent_test"
uv run --no-sync python -c "from sqlalchemy.engine import make_url; from src.config.settings import get_settings; print(make_url(get_settings().database_url).database)"
uv run --no-sync alembic upgrade head
uv run --no-sync alembic current
```

输出数据库名必须为 `esg_agent_test`，head 必须为 `0012_chunk_embeddings`。main/demo migration 需要分别批准，不能用测试库通过替代环境确认。

真实 SiliconFlow 调用前，由用户在本机环境配置 `EMBEDDING_API_KEY` 并明确批准。命令不得打印密钥：

```powershell
cd backend
$env:EMBEDDING_ENABLED="true"
uv run --no-sync python -m src.tools.embed_document_chunks `
  --report-id report-xxx `
  --limit 128
uv run --no-sync python -m src.tools.shadow_vector_retrieval `
  --report-id report-xxx `
  --query "温室气体排放范围一和范围二披露" `
  --top-k 10 `
  --output tmp/embedding/ghg_scope_search.csv
```

批量召回评估使用人工复核工作簿的 `correct_pdf_pages` 作为 gold pages，以 regeneration CSV 的 candidate/source pages 作为规则召回对照：

```powershell
cd backend
uv run --no-sync python -m src.tools.evaluate_shadow_retrieval `
  --report-id report-xxx `
  --requirements data/manifests/gri_requirement_checklist_v3.json `
  --baseline data/review_inputs/envision_2024/baselines/current_577_review_regenerated.csv `
  --manual-review-workbook data/review_inputs/envision_2024/manual/envision_2024_577_manual_review_second_review_Pro_20260719.xlsx `
  --top-k 10 `
  --output-prefix tmp/embedding/envision_shadow_retrieval
```

输出包括：

- `envision_shadow_retrieval_cases.csv`：499 个独立 assessment 的逐项召回明细；
- `envision_shadow_retrieval_summary.json`：`hit@k`、`recall@k`、MRR 和规则/向量命中对照；
- 没有人工 `correct_pdf_pages` 的 requirement 保留在明细中，但不进入召回指标分母。

构造 context pack 不调用 DeepSeek：

```powershell
cd backend
uv run --no-sync python -m src.tools.build_shadow_rag_contexts `
  --report-id report-xxx `
  --retrieval-cases tmp/embedding/envision_shadow_retrieval_cases.csv `
  --output tmp/embedding/envision_shadow_rag_contexts.jsonl
```

默认命令保持纯向量上下文。已完成人工页码基线对照时，可以生成离线混合上下文：

```powershell
cd backend
uv run --no-sync python -m src.tools.build_shadow_rag_contexts `
  --report-id report-xxx `
  --retrieval-cases tmp/embedding/envision_shadow_retrieval_cases.csv `
  --retrieval-mode hybrid_rrf `
  --vector-pool-k 10 `
  --context-k 5 `
  --rrf-rule-weight 2 `
  --rrf-vector-weight 1 `
  --rrf-constant 60 `
  --output tmp/embedding/envision_hybrid_shadow_rag_contexts.jsonl
```

混合模式从当前数据库只读加载指定报告的 `document_chunks`，用 RRF 融合 `rule_pages` 和向量候选。Top 10 是内部向量候选池，实际写入每个 context 的候选最多为 Top 5。该命令不调用 SiliconFlow 或 DeepSeek，不写数据库；无法在数据库中解析的规则页写入 `unresolved_rule_pages`，不会伪造正文。

Phase 1.5 封版命令不调用外部服务，并强制 `EMBEDDING_ENABLED=false`。执行前必须确认实际数据库为 `esg_agent_demo`：

```powershell
cd backend
$env:APP_ENV="demo"
$env:DATABASE_URL="postgresql+psycopg://esg_agent:esg_agent@localhost:5432/esg_agent_demo"
$env:UPLOAD_DIR="backend/data/runtime/demo/uploads"
$env:DERIVED_DIR="backend/data/runtime/demo/derived"
$env:EMBEDDING_ENABLED="false"
$phase15GitHead = git rev-parse HEAD
uv run --no-sync python -m src.tools.finalize_shadow_rag_phase1 `
  --report-id report-15401bb4334e40d4a0885730f2635b22 `
  --retrieval-cases ../tmp/embedding/envision_demo_bge_m3_shadow_retrieval_cases.csv `
  --context-output tmp/embedding/envision_phase1_5_contexts.jsonl `
  --output-prefix tmp/embedding/envision_phase1_5_acceptance `
  --report-total-pages 78 `
  --git-head $phase15GitHead
```

命令先校验 `APP_ENV=demo`、配置数据库名为 `esg_agent_demo`、运行时 Git HEAD 与 `--git-head` 完全一致，再在 `REPEATABLE READ READ ONLY` 事务内确认实际连接库为 `esg_agent_demo`，读取报告 chunk 和非影子表计数并连续构建两次 context。输入 manifest 同时记录工作区脏状态、Git 状态摘要和四个关键实现文件的 SHA256。输出固定为：

- `tmp/embedding/envision_phase1_5_contexts.jsonl`
- `tmp/embedding/envision_phase1_5_acceptance_cases.csv`
- `tmp/embedding/envision_phase1_5_acceptance_summary.json`
- `tmp/embedding/envision_phase1_5_input_manifest.json`
- `tmp/embedding/envision_phase1_5_formal_state.json`
- `tmp/embedding/envision_phase1_5_acceptance_report.md`

目标数据库、embedding 开关、Git HEAD、输入文件、report chunk、499 条 requirement 集合、119 条 gold 覆盖、落盘 JSONL 结构审计、两次 hash、正式表计数或相对质量门禁任一不合格时，命令以非零状态停止。历史 `correct_pdf_pages` 只作为工程 gold；无 gold requirement 不进入召回指标分母。

Phase 1.5 focused 验证：

```powershell
cd backend
uv run --no-sync pytest `
  tests/tools/test_shadow_context_acceptance.py `
  tests/tools/test_finalize_shadow_rag_phase1.py `
  tests/tools/test_shadow_retrieval.py `
  tests/tools/test_shadow_rag.py `
  tests/db/test_repositories.py `
  -q
uv run --no-sync ruff check `
  src/tools/shadow_context_acceptance.py `
  src/tools/finalize_shadow_rag_phase1.py `
  tests/tools/test_shadow_context_acceptance.py `
  tests/tools/test_finalize_shadow_rag_phase1.py
```

可选生成评估属于独立停止点。取得 DeepSeek 真实调用批准且本机已经配置 `OPENAI_COMPATIBLE_API_KEY` 后，才允许显式传入：

```powershell
cd backend
uv run --no-sync python -m src.tools.evaluate_shadow_rag `
  --contexts tmp/embedding/envision_shadow_rag_contexts.jsonl `
  --confirm-llm `
  --output-prefix tmp/embedding/envision_shadow_rag
```

影子输出使用 `shadow_*` 字段和 `shadow-chunk:<chunk_id>`，不构成最终合规结论。真实 SiliconFlow 和真实 DeepSeek 调用需要分别批准。

## 12. 开发日志

### 2026-08-17

- 完成 OCR 单页受控试点：增加共享 dependency preflight、非阻断 `GET /api/capabilities/ocr`、全局/请求双重门禁、显式/profile/低质量页选择、页码与页数校验、有限超时、安全错误码、派生文件清理和 OCR 审计。数据库、GRI 范围、规则、风险、AI、人工快照、前端和导出 schema 均未修改。
- 管理员安装 Chocolatey `Ghostscript 10.7.1` 后，OCRmyPDF 17.8.0、Ghostscript CLI 10.07.1、Tesseract 5.5.0.20241111 和 `chi_sim+eng` preflight 通过。Envision 第 77 页真实 OCR 生成 1 个 2,324 字符 chunk，命中“德勤”“鉴证结论”两个锚点，带 `needs_manual_review`，原始 PDF SHA-256 不变。
- 新 OCR run 固定 `confirm_llm=false`，499/499 成功。与基线逐项比较时，仅 GRI 2-5 四项从 1 条 `pdfplumber` evidence 增加为同页 `pdfplumber + ocr` 两条 evidence；其余 495 项保护字段差异为 0，global fallback、新增 false disclosed、新增 wrong source page 均为 0。DeepSeek、embedding、VLM 调用均为 0。
- 重新冻结门禁为后端 822 项测试和 Ruff 通过；前端 lint 0 error、2 条既有 warning，39 个测试文件 149 项测试、typecheck 和 production build 通过；Envision regeneration 保持 `577/499/78/0`、audit 0 error/0 warning 和 16 条最终裁决 0 pending。完整事实见 `docs/product/ocr-controlled-pilot-acceptance.md`。
- 完成 AI 候选路由与证据类型治理受控解冻：新增只供 AI 使用的 evidence eligibility 分类器，`image_body_not_extracted` 和显式非实质 evidence 不再进入默认外部模型候选；`index_page_bounded`、候选来源和 `short_text` 不被单独视为非实质 evidence。分类器不回写规则证据。
- `confirm_llm=true` 且零合格候选时追加保存逐项 skipped 原因，AI stage 保持 skipped `0/0`，skipped assessment 不标记 `model_called`；`confirm_llm=false` 仍为零调用、run 级 skipped、无逐项 suggestion。
- 前端补齐上下文项和实质证据不足的中文跳过原因；新增只读 AI 观测 CLI，真实读取历史 Envision run 后复现 499 条 suggestion、4 次 succeeded、495 次 skipped、0 次 failed，输出只包含脱敏聚合和白名单字段。该读取没有产生新的外部模型调用或数据库写入。
- `assess_explicit_candidates()` 增加离线边界说明和 AST 调用方测试，当前仅 `evaluate_deepseek_against_manual_review.py` 调用，默认 workflow、API、runner 和后台任务均未调用。
- 最终门禁为后端 focused 87 项、全量 792 项和 Ruff 通过；前端 lint 0 error、2 条既有 warning，39 个测试文件 149 项测试、typecheck 和 production build 通过；Envision regeneration 保持 `577/499/78/0`，global fallback、新增 false disclosed、新增 wrong source page、audit error 和 audit warning 均为 0。本轮没有修改模型、Prompt、数据库、规则、风险、人工快照、OCR/VLM、RAG 或导出。
- 独立授权的 Task 9 通过默认上传、元数据确认和 analyze API 新建 Envision report/run，并设置 `confirm_llm=true`。结果为 499 条 suggestion、0 个合格候选、0 次真实 DeepSeek 请求、436 条 `low_review_priority` 和 63 条 `no_substantive_evidence`；旧 run 的 4 次 GRI 2-5 弱证据调用全部转为 skipped。前后 499 项 system verdict、risk、evidence status、applicability、risk reason、evidence count 和 PDF 页码差异均为 0，范围保持 `577/499/78/0`。脱敏 JSON/CSV 仅保存在 `tmp/ai/`，不提交模型原始响应。
- 收口中文人工复核与审计时间线的产品展示边界。实测 Envision 报告 499/499 个独立判断项的 `effective_requirement_text` 来自官方英文标准资产；中文界面保留 GRI 编号、中文判断依据、中文缺失项和证据，不再默认渲染英文要求正文。未来提供经过确认的中文要求正文时可直接显示。
- 审计 API 和数据库继续保留完整关联 ID，产品时间线隐藏 run/report/action/assessment/snapshot/export/file/profile 等内部 ID，并只展示已登记的业务 payload 字段；负责人、截止日期、状态、适用性等业务变更保持可见，未知字段不回退为开发字段名，可见错误或原因文本中的内部 ID 统一脱敏。
- 审计下载与版本生成事件将 `assessment_xlsx` 等四种内部格式转换为产品名称，字节数转换为 B/KB/MB；PDF 页数和页面质量统计增加“页”单位，解析文本块数不进入产品时间线，三种文档解析状态均使用中文说明。
- 新增七项回归测试并完成红绿验证。最终前端 lint 为 0 error、2 条已知 warning；39 个测试文件、146 项测试、typecheck 和 production build 通过。应用内浏览器只读复验 `GRI 2-27-a-i` 和 7 条实际审计事件，目标英文正文、完整技术 ID、原始字段名、原始输出格式和解析文本块数均为 0，console error/warning 为 0。

### 2026-08-16

- 完成前端视觉迁移工程收口：引入 ECharts 按需图表封装、统一语义色板、Panel/MetricCard/Skeleton/EmptyState/Select/BackToTop/Button 基础组件，并升级首页、报告总览和桌面侧边栏视觉；业务 API、后端规则、数据库、AI/RAG/OCR 和导出语义均未改变。
- 补齐 ESLint 9 flat config 与 `pnpm lint`，修复同步 effect 状态、回顶按钮隐藏焦点、Panel tooltip 唯一 ID、Select 标签语义、reduced-motion count-up 和按钮尺寸类冲突。最终 lint 为 0 error、2 条已知 warning；39 个测试文件、139 项测试、typecheck 和 production build 通过。
- 7 个授权迁移的品牌/视觉资产与 `../esg-dashboard` 来源逐文件 SHA-256 一致；首页、报告列表、报告总览和 3 个核心视觉资源在 demo 产品服务上均返回 200。完整结论见 `docs/product/frontend-visual-migration-acceptance.md`。

### 2026-07-29

- v1.2.1 发布后缺陷修复候选完成：health 增加非敏感 `app_env`；普通产品服务固定连接 `esg_agent_demo` 和 demo runtime；报告审计路由版本错配改为明确提示；复核人不再从 localStorage 跨报告回填；主产品链路中的开发字段名统一转换为中文业务术语。
- v1.2.1 门禁为后端 774 项、Ruff、前端 30 个测试文件 121 项、typecheck 和 production build 全部通过。Envision regeneration 保持 `577/499/78/0`，新增 false disclosed、wrong source page、global fallback、audit error 和 audit warning 均为 0；DeepSeek、SiliconFlow、OCR 和 VLM 调用均为 0。
- Chrome 在当前 demo 服务上只读复验 Goldwind 首页和 metadata、8/8 阶段、复核人空值、完整范围中文术语及 12 条审计事件；console 与服务日志无 error、warning 或 404。demo 库没有待确认报告，因此 AI 授权说明由生产组件渲染测试和静态扫描验收，没有为截图新增或删除业务记录。完整结论见 `docs/product/v1.2.1-post-release-remediation-acceptance.md`。
- Phase 1.7 经完整发布门禁复验后以 fast-forward 集成到 `main`，形成提交 `876859f`；annotated tag `v1.2` 与 `main` 原子推送到远端，未使用 force push。发布后本地只保留 `main`，已合并功能分支和临时 worktree 已清理。
- 经批准执行 `docs/plan/phase1.7-final-closure-and-release-readiness-plan.md`，一次解冻完成运行谱系有效视图、577 项失败/未生成投影、报告审计、扫描 PDF 能力边界、通用 profile 解析、Goldwind 独立闭环和正式输出后纠正；没有新增 migration、表或外部服务依赖。
- 有效视图从最新 run 沿 `parent_run_id` 合并同一报告结果，带循环、深度和跨报告防护。失败或未生成行不生成伪 verdict、evidence、risk、applicability 或人工状态；dashboard、scope、review、report status 和 formal export gate 使用同一有效语义。
- 完全扫描且未启用实验 OCR 的 PDF 在 requirement 规则执行前返回 `unsupported_scanned_pdf`；数字文本与少量扫描页混合报告标记为 `supported_with_review`。本轮未运行 OCR/VLM，也未改变 OCR 实验路由。
- Goldwind 52 页真实 PDF 已通过上传、metadata、499 assessment、577 项范围、页码边界、人工快照、整改任务、四类草稿文件下载和报告审计 E2E。Goldwind 使用 profile 配置进入通用 workflow，没有专用规则分支，也不构成 ESG 专家 gold。
- 正式输出后的纠正复用 assessment `reopen`：报告进入 `reopened`，新解决型人工快照恢复 gate，N+1 正式版本替代 N，旧快照和文件保持可读。没有新增独立 report reopen API 或 `voided` 操作。
- 最终门禁：`uv run pytest -q` 为 774 passed，`uv run ruff check .` 通过；前端 30 个测试文件 119 项测试、typecheck 和 production build 通过。空测试数据库从零迁移到 `0012_chunk_embeddings (head)`，health、OpenAPI 和服务重启恢复冒烟通过。
- Envision v3 重新生成保持 `577/499/78/0`，499 个唯一独立 assessment，global fallback、新增 false disclosed、新增 wrong source page、audit error 和 audit warning 均为 0，16 条最终裁决无 pending。
- 独立代码复核发现并关闭运行选择、未生成项统计、旧审计接口脱敏、复核事务、导出事务和画像身份校验 6 个 P1，以及打印版空结论、通用 POSIX 路径脱敏、dashboard 计数字段语义和渲染失败目录清理 4 个 P2。复核和导出均增加故障注入回滚测试；报告画像绑定真实源 PDF SHA-256，同名同页但内容不同的文件不得使用内置画像。
- Chrome 使用隔离 demo 端口完成 Goldwind metadata、八阶段进度、577 项、PDF 第 6 页、人工快照、整改创建/更新、草稿、正式 v1、下载和 12 条审计事件。窄屏无横向溢出，键盘 Tab 顺序可用，console error/warning 为 0。原生文件选择器因 Chrome 扩展文件 URL 权限无法自动赋值，上传改由同一 demo 后端正式 API 完成；产品上传接口和 multipart 路径已有真实 E2E 覆盖。
- Chrome 验收发现新审计事件缺少中文名称，提交 `8f79a58` 补齐画像、分析启动、人工快照、草稿和正式输出标签及关键 payload 字段，并增加前端回归测试。
- OpenAPI 生成时默认 8000 端口已有用户服务，因此对独立后端端口执行等价的 `pnpm exec openapi-typescript` 命令；生成类型、后端 schema、组件类型检查和 production build 一致。完整结论见 `docs/product/phase1.7-final-closure-acceptance.md`。
- 经批准执行 `docs/plan/phase1.6-product-closure-implementation-plan.md`，在解冻起点 `5e4848b` 上完成安全 export 文件交付、`actions_xlsx`、577 项全局搜索和组合筛选、整改任务截止日期更新；没有新增 migration、表或外部服务依赖。
- export 对外 manifest 只返回 `file_id`、`filename`、`format`、`size`、`sha256`；`GET /api/exports/{export_id}/files/{file_id}` 校验归属、目录边界、存在性、大小和 SHA256，并兼容历史 manifest。OpenAPI、生成的前端类型和页面均不暴露内部 `relative_path` 或本机路径。
- `/scope-items` 支持 `query`、`unit_status`、`effective_verdict`、`review_priority`、`review_status`、`applicability_status`，先过滤后分页；上下文项继续保持 verdict、priority、review 和 applicability 为空。
- 整改任务 PATCH 支持 due date 新增、修改和显式清空，并区分未提供字段；前端仅提交实际变更。`actions_xlsx` 使用固定免责声明和列顺序，无任务时仍生成有效工作簿。
- 最终验证：后端 727 项测试通过，Ruff 通过；前端 28 个测试文件 114 项测试、typecheck、production build 通过；核心后端纵向测试 37 项通过。Envision v3 regeneration 保持 `577/499/78/0`，global fallback、新增 false disclosed、新增 wrong source page、audit error、audit warning 均为 0。
- Chrome 验收覆盖 577 项总量、78 个上下文项、搜索、组合筛选、空态、清空、分页、正式输出门禁、四文件草稿和四个下载事件；console error/warning 为 0。当前数据库没有可复用整改任务样本，因此没有为浏览器验收制造任务；due date 写路径由组件、API 和端到端测试覆盖。
- 本轮在审查前和审查修复后各执行一次 Envision regeneration gate，共创建两个新的本地报告/run；Chrome 只为第一次 gate 的报告生成一个四文件草稿。没有保存人工 snapshot、创建或修改整改任务，也没有调用 DeepSeek、SiliconFlow、OCR 或 VLM。
- 最终独立审查修复 `d729abb`：scope 筛选类型直接派生自 OpenAPI，移除无效 verdict 并提供两种合法不适用状态；旧客户端 `status=null` 按未提供处理；XLSX 中以 `= + - @` 开头的用户文本增加公式注入转义。红灯验证后，后端目标 14 项、前端全量 114 项和 typecheck 通过。
- Phase 1.6 完整验收见 `docs/product/phase1.6-product-closure-acceptance.md`。完成文档同步和最终自检后，v1.1 后端基线重新冻结。

### 2026-07-28

- 完成 OCR 架构只读复核并决定保持 v1.1 后端冻结：pypdf/pdfplumber 继续作为正式默认链路；OCRmyPDF/Tesseract 路由保留为实验能力，Docling/PaddleOCR/VLM 和后台队列均不启动。当前可确认 OCRmyPDF 17.8.0 与 Tesseract `chi_sim/eng/osd` 可用，Ghostscript 不可用，真实扫描样本端到端验收仍未完成。
- OCR 条件解冻触发点限定为真实扫描页造成关键证据缺失、产品验收明确要求扫描 PDF，或形成可复核扫描样本集。触发后一次性完成 preflight、结构化安全错误、失败审计、非阻断 capability 状态、真实样本评测和完整回归；当前延期边界见 `docs/plan/ocr-production-readiness-deferred-plan.md`。
- 本轮只读审计收集到 709 项后端测试；OCR 目标测试 `tests/services/test_ocr.py`、`tests/api/test_reports_api.py`、`tests/workflows/test_single_report_workflow.py` 实测 49 项通过。收集数量只表示测试发现范围，不替代全量执行结果；v1.1 已冻结的 709 项全量通过记录继续以 2026-07-27 封版结果为准。
- LLM 辅助层继续保持 `confirm_llm` 显式授权、规则/AI/人工三层隔离和追加式 suggestion；当前不修改 DeepSeek 模型、Prompt、候选筛选、数据库、API、导出或 RAG 接入。
- `confirm_llm=false` 只记录 run 级授权状态和 AI stage skipped，不写 499 条逐项 skipped suggestion。
- `assess_explicit_candidates()` 只允许离线评估工具和测试使用，不进入默认产品工作流。
- 完成不解冻后端的 LLM 展示收口：前端从既有 `status` 与 `guardrail_codes` 派生“需人工独立判断”和“技术调用未完成”，不新增 API 状态，被 guardrail 拦截的 suggestion 继续不可采纳；前端 28 个测试文件、105 项测试、typecheck 和 production build 通过。
- 修正 `low_review_priority` 的跳过原因展示，避免把低复核优先级误写为安全校验；真实演示数据浏览器复验无 AI 操作按钮，控制台无错误。
- 在提交 `570a996` 上重新执行 Phase 1.5 封版、后端全量测试、Ruff、前端完整门禁和 Envision v3 回归；499 个影子 context、119 条工程 gold 覆盖、18 张正式表计数不变，`577/499/78/0`、新增 false disclosed、wrong source page、global fallback、audit error 和 audit warning 均为 0。真实外部模型调用为 0，后端继续冻结。
- Phase 1.5 收尾事实集中记录在 `docs/product/phase1.5-closeout-report.md`；Task 4–6 继续延期，不因收尾自动解冻。
- 在提交 `5e251de` 上完成只读实际产品巡检：首页、报告列表、总览、完整核查、三栏复核、整改任务和输出版本均可加载，浏览器控制台 0 错误，关键业务表计数前后不变；run 使用 `confirm_llm=false`，AI stage skipped，真实外部调用为 0。
- 冻结内关闭产品巡检 OBS-003：报告列表使用现有 ReportResponse 字段显示创建时间、语言、页数和短 report ID；5 份同企业同年度报告可区分，原状态和跳转不变，前端 28 个测试文件/106 项测试、typecheck、production build 及浏览器只读核验通过。
- 冻结内关闭产品巡检 OBS-005：输出页复用 dashboard 执行正式输出预检，加载中、读取失败、分析不完整或高优先级未完成时禁用正式按钮并展示原因；草稿不受影响，后端继续执行最终门禁。前端 28 个测试文件/109 项测试、typecheck、production build 及浏览器只读核验通过。
- 冻结内关闭产品巡检 OBS-006：复核工作台复用 dashboard 的 run_id 和现有 run.confirm_llm，把无 suggestion 细分为 AI 未启用、已启用但单项无建议、读取中和状态不可用；suggestion 状态和三层优先级不变。前端 28 个测试文件/111 项测试、typecheck、production build 及浏览器只读核验通过。
- 巡检剩余优先缺口为单 export 文件下载及 manifest 绝对路径；完整核查全局搜索和整改截止日期更新列为后端解冻后事项。问题证据、优先级和进入条件见 `docs/product/phase1.5-product-observation-backlog.md`。
- 冻结边界复核确认：现有 API 没有 export 单文件下载端点，assessment 全局查询参数不含 requirement/关键词/结论/复核状态，UpdateActionRequest 不含 due_date；上述剩余项不在前端绕过，等待单独批准后端解冻。
- 在提交 `c3528b1` 上完成交付前普通 Chrome 最终只读验收：首页、键盘导航、报告实例识别、总览、577 项首末分页、三栏复核、AI 未启用空态、PDF 第 77/78 页查看、整改任务和正式输出前置门禁均通过，console error/warning 为 0。`esg_agent_demo` 的 18 张正式表前后计数完全一致，没有业务写入或外部模型调用；结果见 `docs/product/phase1.5-product-observation-backlog.md`。

### 2026-07-27

- 完成混合影子 RAG Phase 1.5 自动工程验收：499 个 context、499 个唯一 hash、0 个重复页、0 个未解析规则页和 0 个确定性差异；119 条有 gold 样本中，混合 Hit@5、Recall@5 和 MRR 均高于规则基线，gain 11、loss 0。
- 封版工具使用 PostgreSQL `REPEATABLE READ READ ONLY`，18 张非影子表前后计数一致；Phase 1.5 focused 57 项、后端全量 709 项测试和 Envision `577/499/78/0` 门禁通过。
- Phase 2 保持可选且未启动，Phase 3 关闭；本阶段没有新增 ESG 专家判断，不调用外部服务，不接入正式分析链路。

### 2026-07-26

- 完成离线混合影子上下文：规则召回与 BGE-M3 向量 Top 10 按 RRF 2：1 融合，最终输出 Top 5；规则页通过只读 `document_chunks` 查询补齐正文，不接入正式 evidence、assessment、risk、AI suggestion、review snapshot、export、API 或前端。
- 完成报告中心前端演示体验优化：首页、报告总览、八阶段进度、完整 577 项核查、三栏复核、整改任务和版本化输出形成连续主路径。
- 普通产品页面继续统一使用 577 项口径；499 个独立判断项和 78 个上下文项只在技术审计中使用。完整核查支持真实总数、首尾分页和独立项复核跳转，全局搜索与组合筛选保留为非阻断后续项。
- Demo 验收保存 1 条追加式人工 snapshot，高优先级进度由 0/9 更新为 1/9；创建 1 条关联 `GRI 2-5-a` 的整改任务，并生成记录实际复核范围的新草稿。
- 最终门禁：后端 651 项、前端 28 个测试文件 103 项、typecheck、production build 和 Envision v3 gate 全部通过；`577/499/78/0`、global fallback 0、新增 false disclosed 0、新增 wrong source page 0、audit 0 error/0 warning。
- 当前服务和真实写入均确认连接 `esg_agent_demo`；正式库未清空、未重建。外部模型、OCR 和 VLM 均未调用。

### 2026-07-25

- 冻结 `Envision 2024 中文报告 MVP 后端基线 v1.1`：普通产品口径统一为 577 项；v3 内部结构为 `577/499/78/0`。
- 6 条历史复合结构问题按 `envision-method-v1.1` 裁决；16 条历史结果差异按 `envision-result-v1.1` 固化，13 条规则一致、3 条最终人工覆盖、0 条 pending。原始 Sol/Pro 工作簿保持只读且 SHA256 不变。
- 新增 577 项只读范围接口和完整范围输出；499 个独立项生成 assessment，78 个上下文项显示 `context_incorporated` 且不生成伪 verdict。
- 普通 Chrome 在 `APP_ENV=demo`、`esg_agent_demo` 完成无 AI 主流程。修复证据 iframe 空白问题，右栏改为只读页图接口；点击复核项不下载 PDF。
- 最终门禁：后端 651 项、前端 80 项、typecheck、production build 和 Envision v3 gate 通过；global fallback、新增 false disclosed、新增 wrong source page、audit error/warning 均为 0。
- 正式库最新 v3 regeneration run 与 demo 最新产品 run 完成只读逐项一致性审计：两边均为 `577/499/78/0`、499 成功、0 失败，499 个 requirement 的 task 结构、规则结果、证据和 risk-v2.1 维度差异为 0，规范化 SHA256 均为 `66a7edc337d44cebc662a5e5c3cf60a7ce6a3426da8efb5dfc5ea7ad8561b29a`。以后修改结构、规则、证据路由或 risk 规则时必须重新执行该对比。
- DeepSeek 模型、Prompt、调用范围和 guardrail 未改变；本轮 `confirm_llm=false`，OCR/VLM 未启用。Goldwind 不阻塞本轮冻结。

### 2026-07-20

- 完成 `0011_ai_suggestions`、v2 标准结构编译和 DeepSeek 辅助后端冻结；577 个标准单元编译为 493 个独立判断项、78 个上下文项和 6 个方法待确认项。
- 225 条真实 DeepSeek 基线评估完成并保留追加式重试审计；一致率 72.32%，安全硬门禁全部为 0，16 条方法差异和 4 条人工—AI证据页差异继续保留。
- Envision v2 与 Goldwind 100 条人工 gold gate 通过；修复 OHS 相邻 KPI 行绕过 leaf 口径门禁的问题。
- main/demo 均升级到 `0011_ai_suggestions` 并生成只读最终备份；后端 626 项、前端 51 项、typecheck 和 production build 通过。
- 完成前端 AI 显式授权、八阶段进度、规则/AI/人工三层展示和采纳/修改/拒绝；浏览器验收发现规则层误用人工字段，修复提交为 `4abdac9`。
- 最终门禁更新为后端 627 项、前端 80 项、typecheck、production build 和 Envision v2 回归通过；Goldwind 优先级降低，不作为本轮阻塞门禁。
- 普通 Chrome 完成重复上传、metadata、真实 AI 产品 run、493 项核查表、PDF 三栏、三类人工快照和草稿输出验收；OCR/VLM 未启用。

### 2026-07-11

- 企业 ESG 产品闭环阶段 0-8 自动门禁完成，进入人工产品验收停止点。
- 新增 `0003` 至 `0008` migrations，覆盖 report metadata、分析阶段、风险、复核快照、整改任务和版本化输出。
- API 端到端测试覆盖当时的上传、确认、577 计数、分析阶段进度、高优先级与适用性复核、整改、草稿和正式输出；后端全量 555 项测试通过。
- 前端普通入口收敛为首页和 ESG 报告，核心业务文案中文化；17 项测试、typecheck 和 production build 通过。
- Envision 577 零回归；Goldwind 100 条人工 gold recall 为 96.08%，无 false disclosed 和 wrong source page，保留 2 条 unknown leakage。
- 旧 `review_decisions` 两个兼容周期数据映射通过，但仍有调用者，清理延期。

### 2026-07-05

- 接入显式 OCRmyPDF/Tesseract 路由：`enable_ocr=false` 时保持现有 `pypdf + pdfplumber` 主链路；`enable_ocr=true` 时支持 `ocr_pages` 指定页码，未指定时仅选择 `low_text_density` 或 `scanned` 页并受 `OCR_MAX_PAGES` 限制。
- OCR 派生 PDF 写入运行时派生目录；OCR chunk 使用 `source_method=ocr`，默认携带 `needs_manual_review`，不覆盖原始 PDF。
- 新增 OCR 配置项：`OCR_ENABLED`、`OCR_LANG`、`OCR_MAX_PAGES`、`TESSERACT_CMD`、`OCRMYPDF_CMD`；后端依赖加入 `ocrmypdf` 并更新锁文件。
- 当时验证：`uv run pytest -q --basetemp=../tmp/pytest-ocr-main-final` 通过，结果为 179 passed；该数字仅表示 2026-07-05 当时测试发现范围，不作为当前全量基线。`uv run ocrmypdf --version` 返回 17.8.0；Tesseract 可见 `chi_sim`、`eng`、`osd` 语言包。
- 限制：Ghostscript 当前仍是本机外部前置条件；若 `gs`/`gswin64c` 不可用，真实 OCRmyPDF 执行会失败，单元测试只覆盖 mock 路径和默认关闭行为。
- 生成 `tmp/review/current_600_review.csv` 时确认：当前 `GRIAdapter` 的独立核查过滤口径为 `assessment_mode=current_gap`、`requirement_type=requirement`、`is_mandatory=True`、`scoring_role=hard_score`，因此实际进入首轮证据核查的是 577 条 requirement，不是 checklist 总数 661 条。
- checklist 剩余 84 条均为 `requirement_type=compilation_requirement`。这些条目不应作为独立 `disclosed` / `partially_disclosed` / `unknown` 任务处理，应映射到对应 leaf requirement 的充分性规则、`missing_items`、guardrail 或口径校验中。
- `tmp/review/current_600_review.csv` 当前包含 773 行、577 个唯一 requirement；按唯一 requirement 聚合后为 37 条 `disclosed`、189 条 `partially_disclosed`、351 条 `unknown`，37 条 `not_required`、540 条 `needs_manual_review`。本轮未调用外部模型。
- 新增第 551-577 条 requirement 均为 `unknown + needs_manual_review`，主题集中在 `GRI 416-2`、`GRI 417`、`GRI 418-1`。后续人工复核应重点判断是否存在产品责任、营销沟通、客户隐私相关的明确零事件声明、KPI 或从略说明。
- `review_csv_audit` 对 `tmp/review/current_600_review.csv` 通过，未发现 `global_fallback`、页码越界、`page_label` 乱码、`omission_note` 升格、KPI 表缺少 `complex_table` 或鉴证页 OCR/VLM 标记回退。
- 历史分析引擎阶段已完成：577 条独立 requirement 首轮核查、84 条 `compilation_requirement` 映射复核、requirement/evidence ontology refactor 和 577 回归。该顺序不再是当前产品开发入口；当前入口以本节末尾的产品方向调整记录为准。
- 84 条 `compilation_requirement` 映射表建议先作为阶段性审查产物输出到 `tmp/review/`，字段至少包括 `compilation_requirement_id`、`canonical_disclosure_id`、`target_requirement_ids`、`facet`、`missing_item_template`、`guardrail_effect`、`source_requirement_text`。确认稳定后再决定是否产品化为 manifest 或规则文件。
- requirement/evidence ontology migration 已完成到 evidence-backed verdict 边界：`zero_event_compliance`、`compilation guardrail`、`GHG/energy/water/waste KPI`、`OHS management`、`OHS KPI parent`、`employee KPI / benefits`、`human_rights_policy` 以及 residual evidence-backed groups 均已迁入 ontology matrix 或 metadata。每批均执行 577 regression gate，结果均为 577 requirement 不变、`global_fallback=0`、无新增 `disclosed`、无 verdict/review/evidence/page/quality/OCR 字段变化，仅 `missing_items` 出现预期变化。
- no-evidence guardrail migration 已完成：原剩余 68 条 `unknown + needs_manual_review` per-ID explicit verdict 已迁移到 `no_evidence_guardrails.py`，用于结构化阻断零事件分类、风险地点、方法范围、拆分维度和安保人员培训等无效 evidence 传播；`remaining_explicit_verdicts.csv` 重新导出后为 0 条。
- ontology 后 577 回归产物：`tmp/review/current_577_review_after_ontology.csv`、`tmp/review/current_577_review_after_ontology_audit.json`、`tmp/review/current_577_review_ontology_diff.csv`、`tmp/review/current_577_review_ontology_diff_summary.json`。最新 gate 结论为 audit 通过，`compilation_overlap=0`，无新增或删除 requirement，无 verdict / review_status / source page / evidence_type / quality_flags / OCR-VLM 字段变化，`first_pass_quality` 的 disclosed/partial/unknown delta 均为 0；当前 diff 仅剩 ontology matrix 补充的 `missing_items` 差异。
- Report profile 与 evidence routing 第一阶段已完成：新增 `backend/data/reports/profiles/envision_2024.json` 作为 Envision 2024 报告实例画像；PDF 和 manifests 仍沿用后端现有数据目录，profile 只保存报告级候选页、KPI 页、页码偏移和行级 KPI term。
- Evidence routing 优先级为 GRI 索引、report profile、contract metadata、ontology metadata、KPI row matcher、ontology matrix、contract guardrail。固定 PDF 页码只作为当前报告 profile candidate，不作为跨报告通用规则。
- 首批 KPI 行级匹配只覆盖 PDF 第 63-68 页，支持 `kpi_row_label`、`kpi_row_value`、`kpi_row_unit`、`kpi_year_column` metadata，并优先用 KPI 行片段生成 `evidence_preview`。
- 577 profile routing 回归产物：`tmp/review/current_577_review_after_profile_routing.csv`、`tmp/review/current_577_review_after_profile_routing_audit.json`、`tmp/review/current_577_review_profile_routing_diff.csv`、`tmp/review/current_577_review_profile_routing_diff_summary.json`。本次 gate 结论为 audit 通过，577 requirement 不变，无新增 `disclosed`，无 verdict / review_status / source page / evidence_type / quality_flags / OCR-VLM 字段变化；仅 6 条 `candidate_page_source` 从 contract 切换为 profile。
- Holdout 当前只实现接口和指标字段，不执行跨报告 holdout。正式 holdout 需要先确定新报告资产、人工复核样本和禁止新增 per-ID contract 的验收边界。
- Goldwind 2024 holdout 已执行首轮 remediation：生成 `backend/data/reports/profiles/goldwind_2024.json`、`tmp/review/holdout_goldwind_2024_first_pass.csv`、`tmp/review/holdout_goldwind_2024_reviewed.csv`、`tmp/review/holdout_goldwind_2024_quality_summary.json` 和 `tmp/review/holdout_goldwind_2024_audit.json`。本次不启用 OCR；profile 已识别双页拼版 GRI 索引并生成 337 条 requirement route，`profile_route_hit_count=40`、`global_fallback_count=0`、`false_disclosed_count=0`，first-pass 与 reviewed CSV 均通过 `review_csv_audit`。本轮同时将 `global_no_index` 后备证据降为 `unknown + needs_manual_review`，避免无候选页全局命中直接支撑 `disclosed`；Envision 577 回归 audit 通过，577 requirement 数量和 verdict/review 分布不变。
- Goldwind holdout recall 改造完成：新增 recall 诊断表 `tmp/review/holdout_goldwind_2024_recall_diagnosis.csv`；profile builder 从 Goldwind GRI 索引抽取 requirement route，并增加双页拼版页码换算、章节 route 和 KPI 行级 preview。当前 `profile_route_hit_count` 从 40 提升到 53，`global_no_index_count` 从 53 降到 23，`false_disclosed_count=0`，`wrong_source_page_count=0`，`global_fallback_count=0`；`tmp/review/holdout_goldwind_2024_first_pass.csv`、`tmp/review/holdout_goldwind_2024_reviewed.csv`、`tmp/review/holdout_goldwind_2024_audit.json` 均通过 gate。Envision 577 regression 产物 `tmp/review/current_577_review_after_profile_routing_regression.csv` audit 通过，577 requirement 数量不变，verdict/review/source/evidence/page/quality/OCR-VLM 字段无回退。
- Goldwind route review pack 已生成：新增 `tmp/review/holdout_goldwind_2024_route_improvement.csv`、`tmp/review/holdout_goldwind_2024_review_pack.csv`、`tmp/review/holdout_goldwind_2024_route_improvement_summary.json`。本轮接入 `report_profile_section` 到 workflow，并给 Goldwind profile 增加“产品服务与研发创新”章节；`global_no_index_count` 从 23 降到 4，`global_fallback_count=0`，Goldwind 最大 source/candidate PDF 页码均为 52，first-pass/reviewed audit 均通过。route improvement 共 5 行，其中 4 行为 `candidate_without_evidence`，1 行为 `missing_candidate`；当前停止点为人工复核 `tmp/review/holdout_goldwind_2024_review_pack.csv`。focused tests 通过；现有 Envision 577 profile routing regression diff 为 0。本轮未找到可复用的 Envision 577 重新生成脚本，因此只验证历史 regression 产物，后续应沉淀正式 regression 生成入口。
- Goldwind recall 诊断扩充完成：新增 `backend/data/holdout/goldwind_2024_recall_gold.json`，当前保存 5 条已人工复核的 gold case，并生成 `tmp/review/holdout_goldwind_2024_recall_diagnosis.csv`。新增 `preview_sample_audit` 工具并生成 `tmp/review/holdout_goldwind_2024_preview_sample.csv`，本轮 4 条抽样均为 `missing_anchor`，对应当前仍缺有效 source 或 source 错页的诊断样本，不改变 verdict。最终 `profile_route_hit_count=53`、`global_no_index_count=23`、`false_disclosed_count=0`、`wrong_source_page_count=0`、`global_fallback_count=0`；Goldwind first-pass/reviewed audit 通过，Envision 577 regression 无 requirement 数量变化，无 verdict/review/source/evidence/page/quality/OCR-VLM 回退。
- Goldwind evidence hit 改造完成：针对 `GRI 205-1-a`、`GRI 205-1-b`、`GRI 414-1-a`、`GRI 403-9-a-i`、`GRI 418-1-a` 生成新一轮 `tmp/review/holdout_goldwind_2024_review_pack.csv`，并生成 `tmp/review/holdout_goldwind_2024_evidence_hit_summary.json`。本轮目标是验证 profile route handoff、bounded retrieval、KPI/段落行级匹配和 partial matrix 边界；`GRI 418-1-a` 保持 unknown guardrail。Goldwind first-pass/reviewed audit 通过，`global_fallback_count=0`、`global_no_index_count=4`、`profile_route_hit_count=535`、`false_disclosed_count=0`，Goldwind 最大 source/candidate PDF 页码均为 52。5 个目标项均为 `candidate_with_evidence`，其中 `GRI 205-1-a`、`GRI 205-1-b`、`GRI 403-9-a-i`、`GRI 414-1-a` 为 `partially_disclosed`，`GRI 418-1-a` 保持 `unknown`；当前停止点为人工复核 review pack。Envision 577 regeneration gate 通过，577 requirement 数量不变，verdict/review/source/evidence/page/quality/OCR-VLM 字段无回退。
- Goldwind preview anchor 与 section guardrail 改造完成：`GRI 205-1-a`、`GRI 205-1-b` 的 preview 锚到反舞弊培训、业务单位、风险程度、审计策略和商业道德问题；`GRI 414-1-a` 锚到供应商社会责任审核、85 家审核和审核率；`GRI 403-9-a-i` 锚到员工因工死亡人数 KPI；`GRI 418-1-a` 不再通过 `report_profile_section` 映射到产品服务章节，产品服务页和一般数据/隐私泄露表述均不能形成 source evidence，保持 `unknown + needs_manual_review`。未新增主 review CSV 顶层字段，诊断信息仍写入 `tmp/review/holdout_goldwind_2024_review_pack.csv` 和 `tmp/review/holdout_goldwind_2024_evidence_hit_summary.json`。验证：focused tests 通过 132 项；Goldwind first-pass/reviewed audit 通过，`global_fallback_count=0`、`global_no_index_count=5`、`false_disclosed_count=0`、最大 source/candidate PDF 页码 52；Envision 577 regeneration gate audit 通过，按 requirement 聚合后 verdict/review/source/candidate/quality flags 无差异。当前停止点为人工复核更新后的 Goldwind review pack。
- Goldwind 分层 100 条 remediation 与定向 50 条扩展已完成：人工 gold 保存在 `tmp/review/holdout_goldwind_2024_stratified_100_reviewed.csv`，修复后 `first_pass_recall=0.9608`、`false_disclosed_count=0`、`wrong_source_page_count=0`、`unknown_leakage_count=2`、`profile_route_valid_evidence_rate=1.0`、`cross_leaf_missing_items_count=0`、`guardrail_as_evidence_count=0`。本轮增加 leaf evidence promotion、PDF 表格串行文本匹配、profile route 覆盖旧 no-evidence guardrail、leaf-specific missing item 与 compilation guardrail 分离，并在 review CSV 导出中保留 `candidate_page_source`。Envision 577 重新生成 audit 通过，verdict 分布相对批准 baseline 零差异。新增定向样本采用可用量配额：OHS 12、供应商环境/社会评估 4、能源与温室气体 12、员工流动与育儿假 11、零事件合规 11；产物为 `tmp/review/holdout_goldwind_2024_targeted_50_selection.csv`、`tmp/review/holdout_goldwind_2024_stratified_150_selection.csv`、`tmp/review/holdout_goldwind_2024_targeted_50_summary.json` 和 `tmp/review/holdout_goldwind_2024_targeted_50_review_pack.csv`。review pack 共 50 行、50 个唯一 requirement，与原 100 条无重复，人工字段保持空白，最大 source/candidate PDF 页码为 47，`global_fallback=0`。验证：focused tests 180 项、后端全量测试 423 项通过。当前停止点为人工复核新增 50 条 review pack。
- 产品方向已重新聚焦为企业 ESG 团队的单报告 GRI 核查闭环。holdout/review-pack 工具链暂停扩展，`tmp/review/holdout_goldwind_2024_targeted_50_review_pack.csv` 暂不继续人工复核；Goldwind 100 条 gate、Envision 577 零回归、定向 50 条 selection/review pack 和现有分析引擎改动全部保留。下一阶段开发入口调整为报告列表与 metadata 确认、577 条后台阶段进度、固定高风险队列、只追加人工快照与审计、整改任务和版本化输出。review CSV、profile、ontology 和 holdout 工具继续作为分析引擎维护与泛化验证工具，不进入普通产品界面。`docs/plan/product-closure-realignment-plan.md` 完成设计冻结并获得人工批准前，不创建 Alembic migration，不修改正式 API，不实现新页面。
- Goldwind KPI row anchor 精细化完成：`GRI 403-9-a-i` 的 preview 现在从 `员工因工死亡人数 人 1 0 1` 开始，不再带入 AA1000 或审验声明前置文本；`GRI 414-1-a` 的 preview 现在从供应商社会责任审核上下文开始，直接显示 85 家审核、83 家 A 级、97.6% 占比等关键行级信息。`GRI 418-1-a` 仍保持无 source evidence。验证：focused tests 通过 133 项；Goldwind first-pass/reviewed audit 通过；Envision 577 regeneration gate audit 通过，按 requirement 聚合后 verdict/review/source/candidate/quality flags 无差异。
- Goldwind leaf-level evidence promotion guardrail 完成：`GRI 414-1-a` 仍保留 profile candidate `[31, 32]`，但只允许包含社会责任、劳工人权、健康安全或商业道德锚点的页面晋升为 substantive evidence，Goldwind PDF 第 32 页绿色供应链内容仅作 candidate，source evidence 仅保留 PDF 第 31 页。对 `unknown + no source evidence + no expected route` 的 holdout 诊断行清理历史 `evidence_kind` 和 `false_disclosed` 状态，`GRI 418-1-a` 现为 `acceptable` 且 `evidence_kind` 为空。验证：相关单测 122 项通过；Goldwind first-pass/reviewed audit 均为 0 错误；Envision 577 regeneration gate `ok=true`，verdict delta 为 0，`false_disclosed` / `wrong_source_page` / `unknown_leakage` 均为 0。
- Goldwind holdout review pack 聚合字段补齐：每个 requirement 保持一行，新增 `requirement_text`、`verdict`、`review_status`、`source_pdf_pages`、`rationale`、`missing_items`。多个 source PDF 页码按数值排序并输出 JSON 数组；first-pass 中 `requirement_text` 为空时，从 GRI checklist 映射回填。本轮重生成输出 5 行、5 个唯一 requirement，`requirement_text` 空值为 0。
- Goldwind holdout leaf 复核文案精细化：`GRI 205-1-a`、`GRI 205-1-b`、`GRI 414-1-a`、`GRI 403-9-a-i` 由 contract 提供 leaf-specific `rationale` 和原子化 `missing_items`，避免 ontology 通用文案跨 leaf 串用；`GRI 418-1-a` 的 no-evidence 分支明确拆分投诉总数、外部方投诉和监管机构投诉。Review pack 新增 `guardrail_items`，compilation requirement 不再混入 leaf `missing_items`，assessment 内的充分性约束仍保留。Goldwind first-pass 生成器已从 GRI checklist 回填 `requirement_text`，本轮 5 条样本空值为 0。

### 2026-07-04

- 增加 `review_csv_audit` 工具，将人工复核硬规则固化为可重复运行的 review CSV gate；新增首批 leaf-level evidence contract，先覆盖 GRI 305 的候选页、禁用页、verdict 和 review status；PDF 第 63、65、68 页 KPI evidence 统一使用行级 preview helper，并修复 `GRI 205-3-b` PDF 第 68 页缺少 `complex_table` 的质量标记问题。
- 扩展 `omission_note` 识别：支持“因商业保密限制从略披露”“因不适用而从略披露”“不适用从略披露”“confidentiality constraints”“not applicable”。从略说明只作为缺口解释保留，固定进入 `unknown + needs_manual_review`。
- 当前 `review_csv_audit.py`、`evidence_contracts.py`、`DisclosureAgent` 中的部分页码规则、`SingleReportWorkflow._candidate_page_overrides()` 和 `GRIAdapter` 的部分关键词服务于远景能源样本的 661 条核查。核查完成后，应将通用 GRI 充分性规则、报告实例页码 profile、报告实例关键词扩展拆分，避免样本页码和公司特定表达长期留在产品运行链路。
- 根据 `current_150_review.csv` 人工复核结论，增加 `GRI 2-20-a-iii`、`GRI 2-20-b`、`GRI 2-21`、`GRI 2-30` 的 `omission_note` 继承规则；GRI 索引中的“因商业保密限制从略披露”只作为缺口解释保留，不提升 `disclosed`。
- 增加 `GRI 2-22`、`GRI 2-23`、`GRI 2-24`、`GRI 2-25`、`GRI 2-26`、`GRI 2-27`、`GRI 2-28`、`GRI 2-29`、`GRI 3-1` 的中文关键词、候选页收窄和子项级充分性规则；章节封面页不能单独作为 evidence，候选页超过报告页数时过滤。
- 生成 `tmp/review/current_150_review_after_rules.csv`：150 个 requirement、227 行、169 条 evidence；按 requirement 聚合后为 11 条 `disclosed`、58 条 `partially_disclosed`、81 条 `unknown`，11 条 `not_required`、139 条 `needs_manual_review`；169 条 evidence 均为 `index_page_bounded`，0 条 `global_fallback`；其中 23 条为 `omission_note`、7 条为 `index_statement`，未调用外部模型。
- 根据 `current_200_review.csv` 人工复核结论，增加 `GRI 201`、`GRI 202`、`GRI 203` topic-specific 规则：`201-1`、`201-4`、`202-2` 继承 `omission_note`；`201-3` 严格要求退休计划/养老金/缴费比例等强证据，普通员工福利和薪酬福利不能支撑；`201-2` 使用 PDF 第 17-19 页气候风险与机遇内容，子项按 disclosed/partial/unknown 区分；`203` 从章节封面扩展到 PDF 第 42-44 页社区项目正文，并保留 partial + 人工复核。
- 生成 `tmp/review/current_200_review_after_rules.csv`：200 个 requirement、299 行、221 条 evidence；按 requirement 聚合后为 14 条 `disclosed`、65 条 `partially_disclosed`、121 条 `unknown`，14 条 `not_required`、186 条 `needs_manual_review`；221 条 evidence 均为 `index_page_bounded`，0 条 `global_fallback`；其中 43 条为 `omission_note`、7 条为 `index_statement`，未调用外部模型。
- 根据 `current_250_review.csv` 人工复核结论，增加 `GRI 204`、`GRI 205`、`GRI 206` topic-specific 规则：`204-1` 继承 `omission_note`；`205` 从治理章节封面扩展到 PDF 第 57-59 页和 KPI 第 68 页，并按反腐败风险评估、培训传达、供应商阳光协议、腐败事件 KPI 做子项级判断；`205-3-b` 可由 KPI 直接支撑 `disclosed`，`205-2-a`、`205-2-d`、`205-3-c`、`205-3-d` 保持 `unknown`；`206-1-a` 使用反竞争行为 KPI 作为 partial evidence，`206-1-b` 保持 `unknown`。
- 根据 `current_250_review_after_rules.csv` 人工复核结论，补充 `GRI 207` 与 `GRI 302-1` 规则：`207-4` 全组继承 `omission_note`；`207-1-a`、`207-1-a-iii`、`207-2-a` 及其部分子项、`207-3-a` 使用 PDF 第 57 页税务治理内容作为 partial evidence；`207-3` 子项税务机关沟通、公共政策倡导、外部意见收集保持 `unknown`；`302-1-a` 和 `302-1-c` 使用 PDF 第 63 页能源 KPI 作为 partial evidence，并标记 `complex_table`；`302-1-b` 和 `302-1-d` 保持 `unknown`。
- 重新生成 `tmp/review/current_250_review_after_rules.csv`：250 个 requirement、354 行、260 条 evidence；按 requirement 聚合后为 15 条 `disclosed`、82 条 `partially_disclosed`、153 条 `unknown`，15 条 `not_required`、235 条 `needs_manual_review`；260 条 evidence 均为 `index_page_bounded`，0 条 `global_fallback`；其中 59 条为 `omission_note`、7 条为 `index_statement`，未调用外部模型。
- 根据 `current_300_review.csv` 人工复核结论，补充 `GRI 302` 与 `GRI 303` 规则：`302-1-e` 使用 PDF 第 63 页能源使用总量 KPI 判定为 `disclosed`；`302-4-a` 和 `302-4-b` 使用 PDF 第 23 页节能改造与 PDF 第 63 页节电量 KPI 作为 partial evidence；`302-1-f/g`、`302-2`、`302-3`、`302-4-c/d`、`302-5` 保持 `unknown`；`303-1`、`303-2-a/a-ii`、`303-3` 部分取水拆分、`303-4` 部分排水拆分使用 PDF 第 16、22、25、63 页作为 partial evidence，水源、排放目的地、高水风险区域拆分和数据编制方法不足的子项保持 `unknown`。
- 生成 `tmp/review/current_300_review_after_rules.csv`：300 个 requirement、413 行、290 条 evidence；按 requirement 聚合后为 16 条 `disclosed`、102 条 `partially_disclosed`、182 条 `unknown`，16 条 `not_required`、284 条 `needs_manual_review`；290 条 evidence 均为 `index_page_bounded`，0 条 `global_fallback`；其中 59 条为 `omission_note`、7 条为 `index_statement`，未调用外部模型。新增第 251-300 条中为 1 条 `disclosed`、20 条 `partially_disclosed`、29 条 `unknown`；PDF 第 63 页 KPI evidence 标记 `complex_table`。

### 2026-07-03

- 完成 evidence retrieval 质量改造：从 GRI 指标索引页提取 disclosure 候选页，检索优先限定在候选页，fallback 和低质量页进入人工复核。
- 增加 `backend/src/standards/gri_report_index.py`，按 `report_index_pdf_page - report_index_report_page` 将报告页码换算为 PDF 页码。
- 修复 GRI 索引页双列表格解析污染问题：同一行中右侧 disclosure 的页码不再并入左侧 disclosure 候选页。
- 真实 PDF `confirm_llm=false` 验收通过：10 个 assessment、5 条 evidence、7 条 recommendation、1 条 `index_page_bounded` evidence、4 条 `global_fallback` evidence、9 条待复核 assessment，四个导出接口均返回 `200`。
- 本次未调用外部模型；fallback evidence 和低质量页 evidence 只能作为人工复核入口，不能作为最终合规结论。
- 根据 `tmp/fallback_review.csv` 人工复核结论，调整披露判定门禁：`global_fallback` evidence 只能作为可疑线索，不再支撑 `disclosed`。
- 为 `GRI 2-2-a` 增加中文检索词：报告边界、实际运营场所、统计口径、合并范围、纳入报告；命中候选页但只披露报告边界时，判为 `partially_disclosed` 并记录缺失项。
- 为 `GRI 2-2-c-ii` 增加合并口径、并购、收购、实体处置等中文检索词；无候选页正确证据时保持 `unknown + needs_manual_review`。
- 重新跑真实 PDF `confirm_llm=false` 验收：10 个 assessment、3 条 evidence、9 条 recommendation、2 条 `index_page_bounded` evidence、1 条 `global_fallback` evidence、9 条待复核 assessment，四个导出接口均返回 `200`，未调用外部模型。
- 根据 bounded evidence 人工复核结论，增加 `GRI 2-2-c-iii` 充分性规则：候选页只说明报告期、资料来源、编制流程或报告边界时，不能支撑 `disclosed`，改为 `unknown + needs_manual_review` 并记录缺失的合并方法与差异说明。
- 再次跑真实 PDF `confirm_llm=false` 验收：10 个 assessment、3 条 evidence、10 条 recommendation、2 条 `index_page_bounded` evidence、1 条 `global_fallback` evidence、10 条待复核 assessment，四个导出接口均返回 `200`，未调用外部模型。
- 根据前 10 条 requirement 人工复核结论，增加 `GRI 2-1` 与 `GRI 2-2-c` 的中文关键词、候选页补充和充分性规则：`2-1-a` 可使用封面/报告说明页公司全称，`2-1-c` 可补充总部页，`2-1-d` 与 `2-2-c` 只支持部分披露，`2-2-c-ii` 无效 fallback evidence 被过滤。
- 重新跑真实 PDF `confirm_llm=false` 验收：10 个 assessment、7 条 evidence、9 条 recommendation、7 条 `index_page_bounded` evidence、0 条 `global_fallback` evidence；结果为 1 条 `disclosed`、4 条 `partially_disclosed`、5 条 `unknown`，四个导出接口均返回 `200`，未调用外部模型。
- 根据 `current_10_review_after_rules.csv` 人工复核结论，保留前 10 条 verdict/review_status 分布，并将 `GRI 2-2-c-iii` 的第 3 页 insufficient evidence 过滤出有效 evidence；再次跑真实 PDF `confirm_llm=false` 验收：10 个 assessment、6 条 evidence、9 条 recommendation、6 条 `index_page_bounded` evidence、0 条 `global_fallback` evidence，四个导出接口均返回 `200`，未调用外部模型。
- 后续 GRI 结构化字段引用以实际存在字段为准：`report_index_pdf_page`、`report_index_report_page`、`evidence_expectation`、`official_pdf_page_candidates`；不得引用不存在的 `report_index_target_pages` 或 `expected_evidence_type`。
- 根据 `current_20_review.csv` 人工复核结论，增加 `GRI 2-3`、`GRI 2-4`、`GRI 2-5` 的中文关键词、索引备注和充分性规则：`2-3-a` 报告期只能支撑部分披露，`2-3-d` 联系邮箱可支撑披露，`2-4` 使用 GRI 索引页“无信息重述”，`2-5` 使用鉴证报告页，`source_page=23/60/64` 的 `global_fallback` 误命中被过滤。
- 生成 `tmp/review/current_20_review_after_rules.csv`：20 个 requirement、21 行、14 条 evidence，结果为 7 条 `disclosed`、6 条 `partially_disclosed`、7 条 `unknown`；7 条 `not_required`、13 条 `needs_manual_review`；14 条 evidence 均为 `index_page_bounded`，0 条 `global_fallback`，未调用外部模型。
- 增加 evidence 页码双轨字段：`source_pdf_page` 用于程序定位，`source_report_page` 用于人工阅读和 GRI 索引展示；保留 `source_page` 兼容旧 API，并在 CSV/JSON 导出中增加 `page_label`。
- 对低文本鉴证页增加 `needs_ocr_or_vlm` 和 `ocr_or_vlm_reason` 标记；本阶段只做路由预留，不调用 OCR/VLM。
- 生成 `tmp/review/current_20_review_after_page_fields.csv`：20 个 requirement、21 行、14 条 evidence，结果分布保持 7 条 `disclosed`、6 条 `partially_disclosed`、7 条 `unknown`；`GRI 2-5` evidence 展示为 `PDF 第 77 页 / 报告页 76`，并标记 `assurance_page_text_too_short`，未调用外部模型。
- 补齐字段契约：新增 `candidate_pdf_pages`、`candidate_report_pages`、`requires_ocr`、`requires_vlm`、`evidence_preview`；低文本鉴证页追加 `short_text` 和 `image_body_not_extracted` 质量标记，同时保留旧字段兼容。
- 生成 `tmp/review/current_20_review_after_contract_fields.csv`：20 个 requirement、21 行、14 条 evidence，结果分布保持不变；`GRI 2-5` 三条 evidence 均为 `requires_ocr=true`、`requires_vlm=false`，未调用外部模型。
- 修复 `evidence_preview` 页首截断问题：preview 改为基于 requirement 关键词的命中窗口，并优先选择包含邮箱、日期和更多关键词的候选片段；`GRI 2-4` preview 稳定显示 `2-4 信息重述 无信息重述 /`。
- 生成 `tmp/review/current_20_review_final_contract.csv`：20 个 requirement、21 行、14 条 evidence，结果分布保持不变；无 evidence 的 unknown 行导出布尔字段统一为 `false`，未调用外部模型。
- 根据 `current_50_review.csv` 人工复核结论，增加 `GRI 2-6`、`GRI 2-7`、`GRI 2-8`、`GRI 2-9-b` 的中文关键词、候选页补充和子项级充分性规则：`2-6` 使用业务概况、ESG 合作网络和责任采购页作为部分披露证据，`2-7-c` 使用人员结构和 KPI 页，`2-7-c-ii` 的“截至报告期末”可支撑披露，`2-8` 严格保持非雇员工作者口径，普通员工、供应商和承包商安全内容不能替代，`2-9-b` 使用 ESG 治理架构页作为部分披露证据。
- 生成 `tmp/review/current_50_review_after_rules.csv`：50 个 requirement、63 行、35 条 evidence；按 requirement 聚合后为 10 条 `disclosed`、12 条 `partially_disclosed`、28 条 `unknown`，10 条 `not_required`、40 条 `needs_manual_review`；35 条 evidence 均为 `index_page_bounded`，0 条 `global_fallback`；修复 `page_label` 中文乱码，`GRI 2-6` 子项 evidence 页码收窄，`GRI 2-7-e` 清空无效 evidence，`GRI 2-5-b-ii` 使用 PDF 第 77 页并标记 `requires_ocr=true`，未调用外部模型。
- 根据 `current_100_review.csv` 人工复核结论，增加治理类 disclosure 规则：`global_fallback` 在 agent 层全部清空；GRI 索引中的“从略披露”行作为 `omission_note` evidence 保留但不提升 `disclosed`；`GRI 2-9-a/b`、`GRI 2-12`、`GRI 2-13` 白名单子项可使用 PDF 第 13 页 ESG 治理架构作为 partial evidence；`GRI 2-9-c`、`GRI 2-11`、`GRI 2-10`、`GRI 2-19`、`GRI 2-20` 不使用 PDF 第 13 页支撑。
- 生成 `tmp/review/current_100_review_after_rules.csv`：100 个 requirement、113 行、61 条 evidence；按 requirement 聚合后为 10 条 `disclosed`、22 条 `partially_disclosed`、68 条 `unknown`，10 条 `not_required`、90 条 `needs_manual_review`；61 条 evidence 均为 `index_page_bounded`，0 条 `global_fallback`；其中 16 条为 `omission_note`，覆盖 `GRI 2-10`、`GRI 2-19`、`GRI 2-20`，未调用外部模型。

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
