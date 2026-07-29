# ESG-Agent

面向企业 ESG 团队的单报告 GRI 核查系统，支持报告上传、577 项 GRI 核查、证据追溯、AI 辅助建议、人工复核、整改任务和版本化输出。

## 项目状态

Phase 1.7 已完成最终闭环与发布就绪验收，正式发布基线为 `v1.2`，对应提交 `876859f`，`main` 已与远端同步。产品统一对外表达为“完成 577 项 GRI 核查”；内部结构为 577 个标准单元、499 个独立判断项、78 个上下文项、0 个方法待确认项。规则 assessment、AI suggestion 和人工 snapshot 分层保存；部分失败和 retry 通过运行谱系形成完整、可审计的 577 项有效视图。

v1.2.1 发布后缺陷修复已形成本地补丁候选：普通产品运行统一使用 demo 环境，health 可核对运行身份，复核人每次进入均为空，主流程开发字段名已产品化，审计接口版本错配会给出明确提示。`v1.2` 标签保持不动；补丁尚未合并、打标或推送。完整验收见 `docs/product/v1.2.1-post-release-remediation-acceptance.md`。

当前门禁：后端 774 项测试和 Ruff 通过；前端 30 个测试文件、121 项测试、typecheck 和 production build 通过；Envision v3 回归的新增 false disclosed、wrong source page 和 global fallback 均为 0，audit 为 0 error、0 warning。Goldwind 52 页真实数字文本报告已完成独立上传、分析、复核、整改、草稿、下载和审计闭环，用作产品泛化工程证据。内置报告画像同时校验文件名、页数和源 PDF SHA-256，防止同名同页文件误用报告专属证据路由。

混合影子 RAG Phase 1.5 已完成自动工程验收。499 个独立判断项均生成确定性的规则、向量和混合 Top 5 对比；在其中 119 条具有历史工程 gold 的样本中，混合 Hit@5、Recall@5 和 MRR 均高于规则基线，正式业务表和 Envision 冻结门禁保持不变。该能力继续只用于离线诊断，不进入正式 evidence、assessment、risk、AI suggestion、API 或前端，也不构成 ESG 专家判断。Phase 2 为可选增强且未启动，Phase 3 保持关闭。

该发布基线属于本地产品与工程验收，不构成 GRI 专家认证、外部鉴证、法律意见或企业部署承诺。企业条件适用性仍可能需要企业确认。

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
- API 契约：`docs/product/api-contract.md`
- MVP 验收：`docs/product/mvp-acceptance-report.md`
- LLM 辅助建议层验收：`docs/product/llm-assistance-acceptance.md`
- RAG Phase 1.5 验收：`docs/product/rag-phase1.5-acceptance-report.md`
- Phase 1.5 收尾报告：`docs/product/phase1.5-closeout-report.md`
- Phase 1.5 实际产品巡检与问题清单：`docs/product/phase1.5-product-observation-backlog.md`
- Phase 1.6 产品闭环验收：`docs/product/phase1.6-product-closure-acceptance.md`
- Phase 1.7 最终闭环与发布就绪验收：`docs/product/phase1.7-final-closure-acceptance.md`
- 实施计划：`docs/plan/`

## 第一版范围

```text
报告列表或上传空状态
  -> 上传 PDF 并识别企业、年度、语言和页数
  -> 用户确认报告信息
  -> 完成 577 项 GRI 核查
  -> 展示八阶段进度和部分失败
  -> 高优先级队列优先人工复核，并独立处理适用性待判定项
  -> 形成整改任务
  -> 生成版本化核查表、整改任务清单、管理层摘要和打印版输出
```

前端以高复核优先级队列为主要入口，并支持适用性待判定队列和完整 577 项核查范围。完整核查支持 requirement/条款搜索，以及单元类型、结论、复核优先级、复核状态和适用性的组合筛选；过滤在分页前执行。高优先级队列完成只表示该队列已处理，不表示 577 项均已人工确认。`unknown` 属于披露结论，不能单独触发高优先级。

完整范围接口从最新 run 沿 `parent_run_id` 合并同一报告的有效结果。部分失败和 retry 仍返回 577 项；失败或未生成的独立项只显示 `analysis_status`、来源 run 和安全错误摘要，不伪造 verdict、证据、风险或人工结论。

版本化输出提供安全的单文件下载，公开 manifest 只包含文件 ID、文件名、格式、大小和 SHA256，不返回服务器存储路径。整改任务支持更新或清空截止日期，`actions_xlsx` 已进入草稿和正式输出格式。报告级审计覆盖上传、分析、重跑、人工复核、整改、输出和下载。正式输出后的纠正复用 assessment reopen；新正式版本替代旧版本，旧文件和历史快照保持可审计。通用 verdict 批量复核和独立 report reopen API 不在当前范围。

## 技术栈

- 后端：Python 3.11、FastAPI、Pydantic v2、PostgreSQL、SQLAlchemy 2.0、Alembic。
- 前端：Next.js App Router、TypeScript、Tailwind CSS、TanStack Query、TanStack Table、Recharts。
- PDF：pypdf、pdfplumber 为正式默认链路；OCRmyPDF/Tesseract 为实验性显式路由，Docling 和 VLM 仍为设计预留。
- AI：DeepSeek OpenAI-compatible API；默认关闭，只生成追加式辅助建议。
- 包管理：后端 uv，前端 pnpm。

原始 PDF 不覆盖。正式支持数字文本型 PDF；少量扫描页混合报告带人工复核警告；完全扫描且未启用实验 OCR 的文档会在规则执行前返回 `unsupported_scanned_pdf`。OCR 默认关闭，仅在分析请求显式传入 `enable_ocr=true` 且确有目标页时进入实验性路由。Ghostscript preflight 和真实扫描样本发布门禁尚未完成，因此 OCR 不属于正式生产能力；延期与条件解冻边界见 `docs/plan/ocr-production-readiness-deferred-plan.md`。外部模型只有用户显式确认后才允许调用。

## 本地运行

```powershell
docker compose up -d postgres

$demoDbExists = docker compose exec -T postgres `
  psql -U esg_agent -d postgres -tAc `
  "SELECT 1 FROM pg_database WHERE datname='esg_agent_demo'"
if ($demoDbExists.Trim() -ne "1") {
  docker compose exec -T postgres createdb -U esg_agent esg_agent_demo
}

cd backend
uv sync
$env:APP_ENV="demo"
$env:DATABASE_URL="postgresql+psycopg://esg_agent:esg_agent@localhost:5432/esg_agent_demo"
$env:UPLOAD_DIR="backend/data/runtime/demo/uploads"
$env:DERIVED_DIR="backend/data/runtime/demo/derived"
uv run alembic upgrade head
uv run uvicorn src.main:app --reload --port 8000

cd ../frontend
pnpm install
pnpm dev
```

前端默认访问 `http://localhost:3000`，后端 OpenAPI 默认访问 `http://localhost:8000/docs`。数据库 head 为 `0012_chunk_embeddings`。普通产品运行和演示统一使用 `APP_ENV=demo`、`esg_agent_demo` 与 demo runtime；`esg_agent` 保留给开发和长期回归，其中允许存在 regeneration 技术记录。不得通过删除 `esg_agent` 中的历史记录改善首页展示。

## 验证命令

```powershell
cd backend
uv run pytest

cd ../frontend
pnpm test -- --run
pnpm typecheck
pnpm build
```

普通页面只使用 577 项产品口径。内部技术审计可以使用 `577/499/78/0`，含义依次为标准单元、独立判断项、上下文项和方法待确认项。`v1.2` 已作为 Phase 1.7 最终产品闭环基线冻结；任何 GRI 清单、结构裁决、证据规则、risk-v2.1、模型/Prompt、数据库 schema 或 API 语义变更都需要解除冻结并重跑完整门禁。
