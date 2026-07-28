# ESG-Agent

面向企业 ESG 团队的单报告 GRI 核查系统，支持报告上传、577 项 GRI 核查、证据追溯、AI 辅助建议、人工复核、整改任务和版本化输出。

## 项目状态

Envision 2024 中文报告 MVP 后端基线 v1.1 已冻结。产品统一对外表达为“完成 577 项 GRI 核查”；内部结构为 577 个标准单元、499 个独立判断项、78 个上下文项、0 个方法待确认项。规则 assessment、DeepSeek suggestion 和人工 snapshot 分层保存，16 条历史判断差异已写入最终裁决资产，当前待裁决数为 0。

当前门禁：后端 709 项测试通过；前端 28 个测试文件、105 项测试、typecheck 和 production build 通过；Envision v3 回归的新增 false disclosed、wrong source page 和 global fallback 均为 0。Goldwind 100 条历史 gate 保留为次级泛化证据，不阻塞 Envision 主线。

混合影子 RAG Phase 1.5 已完成自动工程验收。499 个独立判断项均生成确定性的规则、向量和混合 Top 5 对比；在其中 119 条具有历史工程 gold 的样本中，混合 Hit@5、Recall@5 和 MRR 均高于规则基线，正式业务表和 Envision 冻结门禁保持不变。该能力继续只用于离线诊断，不进入正式 evidence、assessment、risk、AI suggestion、API 或前端，也不构成 ESG 专家判断。Phase 2 为可选增强且未启动，Phase 3 保持关闭。

该基线属于本地产品与工程验收，不构成 GRI 专家认证、外部鉴证或企业部署承诺。企业条件适用性仍可能需要企业确认。

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
  -> 生成版本化核查表、管理层摘要和打印版输出
```

前端以高复核优先级队列为主要入口，并支持适用性待判定队列和完整 577 项核查范围。高优先级队列完成只表示该队列已处理，不表示 577 项均已人工确认。`unknown` 属于披露结论，不能单独触发高优先级。

`actions_xlsx` 完整改任务清单导出、通用 verdict 批量复核、独立 reopen、report 级审计和单 export 下载仍为增强项。正式输出要求分析完整且全部高优先级项已有有效人工复核；草稿可随时生成，并披露实际复核范围。

## 技术栈

- 后端：Python 3.11、FastAPI、Pydantic v2、PostgreSQL、SQLAlchemy 2.0、Alembic。
- 前端：Next.js App Router、TypeScript、Tailwind CSS、TanStack Query、TanStack Table、Recharts。
- PDF：pypdf、pdfplumber；OCR、Docling 和 VLM 仅作为显式授权后的降级能力。
- AI：DeepSeek OpenAI-compatible API；默认关闭，只生成追加式辅助建议。
- 包管理：后端 uv，前端 pnpm。

原始 PDF 不覆盖。OCR 默认关闭，仅在分析请求显式传入 `enable_ocr=true` 后运行；外部模型只有用户显式确认后才允许调用。

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

前端默认访问 `http://localhost:3000`，后端 OpenAPI 默认访问 `http://localhost:8000/docs`。数据库 head 为 `0012_chunk_embeddings`。

## 验证命令

```powershell
cd backend
uv run pytest

cd ../frontend
pnpm test -- --run
pnpm typecheck
pnpm build
```

普通页面只使用 577 项产品口径。内部技术审计可以使用 `577/499/78/0`，含义依次为标准单元、独立判断项、上下文项和方法待确认项。任何 GRI 清单、结构裁决、证据规则、risk-v2.1、模型/Prompt、数据库 schema 或 API 语义变更都需要解除冻结并重跑完整门禁。
