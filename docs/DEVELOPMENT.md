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
- Ghostscript，供 OCRmyPDF 真实执行 OCR 时调用。
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
- OCR 开关、语言和页数上限。
- OpenAI-compatible API base URL。
- 模型名称。
- CORS 来源。

OCR 相关环境变量：

- `OCR_ENABLED=false`：默认关闭 OCR 自动路由。
- `OCR_LANG=chi_sim+eng`：OCRmyPDF/Tesseract 语言。
- `OCR_MAX_PAGES=5`：未显式指定页码时最多处理的低文本/扫描页数。
- `TESSERACT_CMD`：Tesseract 命令或路径。
- `OCRMYPDF_CMD=ocrmypdf`：OCRmyPDF 命令。

DeepSeek 相关环境变量：

- `OPENAI_COMPATIBLE_API_BASE=https://api.deepseek.com`；
- `OPENAI_COMPATIBLE_API_KEY`：只保存在本机 `backend/.env`，禁止提交；
- `LLM_MODEL=deepseek-v4-flash`；
- `LLM_THINKING_TYPE=enabled`、`LLM_REASONING_EFFORT=high`；
- `LLM_RESPONSE_FORMAT=json_object`；
- `LLM_PROMPT_VERSION=deepseek-gri-assist-v1.2`；
- `LLM_MAX_CONCURRENCY=8`、`LLM_MAX_CALLS_PER_RUN=200`。

外部模型默认关闭。只有分析请求显式传入 `confirm_llm=true` 才允许调用；失败 suggestion 追加保留并降级，不能覆盖规则 assessment、人工 snapshot、适用性或正式输出门禁。

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

### 本地演示环境

本机使用一套代码和 PostgreSQL 实例，数据库按用途隔离：

- `esg_agent`：开发、回归和长期验收数据；
- `esg_agent_demo`：可重建的空演示库；
- `esg_agent_test`：pytest 测试库。

演示环境配置参考 `backend/.env.demo.example`。演示上传和派生文件写入 `backend/data/runtime/demo/`，原始报告、标准文件和 manifest 继续从共享只读资产目录读取。

在启动 demo 后端、执行 Alembic 或运行重置工具前，先在同一个 PowerShell 终端加载演示配置：

```powershell
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

当前代码 Alembic head：`0011_ai_suggestions`。`0003` 至 `0008` 覆盖报告 metadata、分析阶段、风险快照、人工复核快照、整改任务和版本化输出；`0009` 增加 active run 唯一索引；`0010` 增加 risk-v2.1 维度；`0011` 增加标准结构计数、task 上下文和追加式 AI suggestion。启动后端前必须执行 `uv run --no-sync alembic upgrade head`。

核心产品 API：

- `POST /api/reports/upload`（支持 `duplicate_policy=reject|create_new`）、`POST /api/reports/{report_id}/confirm-metadata`
- `POST /api/reports/{report_id}/analyze`、`GET /api/runs/{run_id}/stages`
- `GET /api/reports/{report_id}/dashboard`、`GET /api/reports/{report_id}/review-queue`、`GET /api/reports/{report_id}/applicability-queue`
- `POST /api/assessments/{assessment_id}/review-decisions`
- `POST /api/reports/{report_id}/applicability-decisions`
- `POST /api/reports/{report_id}/actions`、`PATCH /api/actions/{action_id}`
- `POST /api/reports/{report_id}/exports/draft`、`POST /api/reports/{report_id}/exports/formal`
- `POST /api/demo/reset`（仅 demo 环境）

正式输出门禁：分析必须完整，且全部高复核优先级 assessment 必须已有有效 review snapshot。草稿不受该门禁限制，但 review scope 会记录草稿标识、分析不完整数、高/中优先级复核范围、适用性待判定数、run、engine version 和 risk rule version。正式版本使用递增版本号，旧正式版本标记为 superseded，文件 manifest 保存路径、大小和 SHA256。

risk-v2.1 将披露结论、证据状态、适用性状态和复核优先级分开。`unknown + 无证据` 为低优先级，`unknown + 仅索引/从略说明` 为中优先级，只有明确冲突、证据失效或严重质量异常进入高优先级。当前固定 Envision 输入的只读回归基线为高 12、中 60、低 505，另有适用性待判定 343；数量只作为本次数据回归断言，不能写入规则或配置。

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

旧 `review_decisions` 已完成两个连续阶段的数据映射兼容测试，但旧 API、旧前端工作台和旧导出仍有调用者，因此暂不删除。完成调用迁移后，应以独立 migration 验证 upgrade/downgrade，再申请清理。

### 当前验收风险与后续项

本轮已闭环：重复上传提供“查看已有结果”和“重新上传并分析”，后者保留历史并创建新报告；同一报告 active run 同时受 API 预检查和 `0009` 数据库部分唯一索引保护；metadata 进入分析后禁止改写；服务重启会收敛遗留 active run。

- 适用性单条与当前页批量确认已实现；通用 verdict 批量复核、独立 report/assessment reopen、report 级审计、单 export metadata 和文件下载 API 尚未实现；这些接口在 `docs/product/api-contract.md` 标记为规划中。
- `actions_xlsx` 尚未按整改任务字段生成完整任务清单，后端当前明确返回 422，前端不请求该格式；当前验收只覆盖核查表 XLSX、管理层摘要 PDF 和打印 HTML。
- 旧 `/api/review/*`、旧 `/api/exports/runs/*`、`/api/audit/runs` 和对应旧前端页面仍承担兼容用途，不能删除 `review_decisions`。
- Goldwind 100 条人工 gold gate 的 `unknown_leakage_count=2`，但 `false_disclosed_count=0`、`wrong_source_page_count=0`；该风险不阻塞 MVP 人工验收。
- `esg_agent` 开发/长期验收库包含多次 Envision regeneration 记录，禁止为演示清理；重复上传可直接创建新报告，因此普通演示和验收都不依赖空库。需要隔离展示数据时可连接 `esg_agent_demo`，reset 只作为显式维护操作。
- Codex 内置浏览器控制在本机发生两次桌面应用闪退。自动页面截图改用独立无头 Edge；人工验收使用普通浏览器，不再启用 Codex 内置浏览器。
- 外部模型和 OCR/VLM 默认关闭。DeepSeek 只在 `confirm_llm=true` 且用户明确批准后启用；OCR/VLM 本轮未启用。

当前自动门禁（2026-07-20）：后端 627 项测试通过；前端 22 个测试文件、80 项测试、typecheck 和 production build 通过；Envision v2 为 577/493/78/6、493 个唯一独立判断项、global fallback 0、224 个可比人工 verdict 加 1 个适用性例外无新增 false disclosed 或 wrong source page。Goldwind 100 条历史人工 gold 为 recall 96.08%、false disclosed 0、wrong source page 0、unknown leakage 2，当前作为低优先级泛化证据，不再阻塞 Envision 主线验收。main 与 demo 数据库 head 均为 `0011_ai_suggestions`。

DeepSeek 225 条真实评估固定使用 Envision 报告 `report-14864b1a3ef64512b0e5d3676a120bc1` 和 run `run-526bd97aef5d4b9baa14618b719081c9`。最终指标：一致 162/224（72.32%），适用性例外 1，累计定向补跑 18 次；guardrail 后 false disclosed、证据 ID 越界、可比错页、schema 失败和模型失败均为 0。Sol/Pro 尚未裁决的 16 条继续单列，人工—AI证据页差异 4 条继续保留。该结果标记为 AI 辅助工程基线，不构成 GRI 专家认证或最终合规结论。

普通 Chrome 已在 `APP_ENV=demo`、`esg_agent_demo` 和 demo runtime 下完成 Envision 主流程验收。当前产品流程保留历史，通过“重新上传并分析”创建新的 `report_id`，不要求 reset 空库。同一哈希存在多份历史时，重复响应按创建时间返回最新报告。新产品 run `run-021eeb43338f4381910218628b64554b` 完成 493 个独立判断项，规则失败 0；显式启用 AI 后，4 条满足产品调用条件并全部成功，489 条按规则跳过。固定 225 条工程基线用于三层交互样例，已通过普通 Chrome 生成采纳、人工修改、拒绝各一条追加式 snapshot，并生成带 AI 免责声明的草稿输出。验收事实和截图索引见 `docs/product/mvp-acceptance-report.md`。

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

## 8. Envision v2 Review CSV Regeneration Gate

用途：从 Envision 2024 源报告、report profile 和 v2 标准结构重新生成 493 个独立 assessment 的证据展开 CSV，并验证 577/493/78/6 范围及已批准人工基线。

命令：

```powershell
cd backend
uv run --no-sync python -m src.tools.regenerate_review_csv `
  --report-id envision_2024_v2 `
  --pdf "data/reports/Envision Energy 2024-zh.pdf" `
  --profile data/reports/profiles/envision_2024.json `
  --requirements data/manifests/gri_requirement_checklist_v2.json `
  --manual-review-workbook data/review_inputs/envision_2024/manual/envision_2024_577_manual_review_second_review_Pro_20260719.xlsx `
  --output data/runtime/evaluations/envision_2024/current_493_review_regenerated.csv `
  --baseline data/review_inputs/envision_2024/baselines/current_577_review_regenerated.csv `
  --audit-output data/runtime/evaluations/envision_2024/current_493_review_regenerated_audit.json `
  --diff-summary-output data/runtime/evaluations/envision_2024/current_493_review_regeneration_diff_summary.json `
  --scope-summary-output data/runtime/evaluations/envision_2024/current_493_review_scope_summary.json `
  --report-total-pages 78
```

通过标准：

- 标准单元 577、独立 assessment 493、上下文项 78、方法待确认项 6。
- 唯一 assessment requirement 为 493；多证据可展开为多行。
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

## 11. 开发日志

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
- API 端到端测试覆盖上传、确认、577 计数、七阶段进度、高优先级与适用性复核、整改、草稿和正式输出；后端全量 555 项测试通过。
- 前端普通入口收敛为首页和 ESG 报告，核心业务文案中文化；17 项测试、typecheck 和 production build 通过。
- Envision 577 零回归；Goldwind 100 条人工 gold recall 为 96.08%，无 false disclosed 和 wrong source page，保留 2 条 unknown leakage。
- 旧 `review_decisions` 两个兼容周期数据映射通过，但仍有调用者，清理延期。

### 2026-07-05

- 接入显式 OCRmyPDF/Tesseract 路由：`enable_ocr=false` 时保持现有 `pypdf + pdfplumber` 主链路；`enable_ocr=true` 时支持 `ocr_pages` 指定页码，未指定时仅选择 `low_text_density` 或 `scanned` 页并受 `OCR_MAX_PAGES` 限制。
- OCR 派生 PDF 写入运行时派生目录；OCR chunk 使用 `source_method=ocr`，默认携带 `needs_manual_review`，不覆盖原始 PDF。
- 新增 OCR 配置项：`OCR_ENABLED`、`OCR_LANG`、`OCR_MAX_PAGES`、`TESSERACT_CMD`、`OCRMYPDF_CMD`；后端依赖加入 `ocrmypdf` 并更新锁文件。
- 验证：`uv run pytest -q --basetemp=../tmp/pytest-ocr-main-final` 通过，结果为 179 passed；`uv run ocrmypdf --version` 返回 17.8.0；Tesseract 可见 `chi_sim`、`eng`、`osd` 语言包。
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
