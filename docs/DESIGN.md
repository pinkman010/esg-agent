# esg-agent 从零构建设计规格

## 1. 结论

本项目采用前后端单仓 Monorepo，从端到端纵切开始建设：上传 PDF、解析并入库、生成 GRI 条款任务、运行披露分析、展示结果、人工复核、导出 JSON/CSV。

第一版目标是跑通真实闭环，不追求完整 GRI 覆盖、批量分析、登录权限、同行对标、舆情监测和多标准混合分析。

## 2. 已确认技术选型

| 类别 | 选型 | 结论 |
| --- | --- | --- |
| 仓库结构 | Monorepo | `backend`、`frontend`、`docs` 放在同一仓库 |
| 后端语言 | Python 3.11 | 兼顾 PDF、数据处理、LLM SDK 和兼容性 |
| 后端框架 | FastAPI | 自动 OpenAPI、文件上传、Pydantic 集成清晰 |
| 数据校验 | Pydantic v2 | API 响应、领域对象、模型输出统一校验 |
| 配置管理 | pydantic-settings | `.env` 和环境变量类型化 |
| 数据库 | PostgreSQL + 预留 pgvector | 第一版存结构化数据，后续接向量检索 |
| 数据访问 | SQLAlchemy 2.0 + Alembic | 兼顾迁移、事务、PostgreSQL 能力和扩展 |
| PDF 处理 | 混合多路由管线 | 兼顾扫描件、数字原生 PDF、复杂表格和低质量页 |
| 模型 SDK | OpenAI-compatible SDK | 通过薄适配层接 DeepSeek 和后续兼容模型 |
| 模型调用策略 | 默认不调用模型 | 只有用户显式确认后才调用外部模型 |
| 任务执行 | FastAPI 同步触发 + 后台任务表轮询 | 第一版用数据库记录运行状态，前端轮询 |
| 前端框架 | Next.js App Router | 工作台式页面、路由和布局规范明确 |
| 前端语言 | TypeScript | 降低前后端契约漂移 |
| 样式组件 | Tailwind CSS + shadcn/ui | 适合克制、清晰、可定制的工作台 |
| 表格 | TanStack Table | 支持条款、证据、复核列表的筛选和排序 |
| 图表 | Recharts | 内部图表组件封装，后续可切 ECharts |
| 数据获取 | TanStack Query | 支持任务轮询、缓存、mutation 和错误状态 |
| API 类型同步 | OpenAPI 自动生成 TypeScript types | 依赖 FastAPI OpenAPI 输出 |
| 测试 | pytest + Vitest/React Testing Library + build/typecheck | 覆盖后端核心逻辑和前端关键状态 |
| 包管理 | 后端 uv，前端 pnpm | 锁文件明确，安装速度快 |
| 本地服务 | Docker Compose 管 PostgreSQL；OCR/Tesseract 本机工具；前后端本机运行 | 数据库统一，开发迭代较快 |

## 3. 第一版产品闭环

用户流程：

```text
上传 PDF
  -> 保存原始文件、哈希和报告元数据
  -> 页面预检测和解析任务入库
  -> 用户显式确认是否调用模型
  -> 构建 GRI 披露任务
  -> DisclosureAgent 执行条款级分析
  -> 保存判断、证据、建议和运行日志
  -> 前端展示结果和证据
  -> 人工复核
  -> 导出 JSON/CSV
```

第一版必须满足：

- 上传 PDF 后生成 `report_id`。
- 分析运行生成 `run_id`。
- 外部模型调用必须由 `confirm_llm=true` 控制。
- 每条判断保留证据来源、页码、文件哈希、模型调用标记和复核状态。
- 没有证据或证据质量不足时进入人工复核。
- 前端所有核心指标来自后端 API。

## 4. 后端设计

后端使用 FastAPI，核心目录：

```text
backend/
  pyproject.toml
  alembic.ini
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
```

核心模块职责：

- `domain/`：Pydantic 领域模型和枚举，表达报告、运行、任务、证据、判断、建议、复核。
- `db/`：SQLAlchemy 表模型、session、repository 和 Alembic 迁移。
- `standards/`：`StandardAdapter` 和 `GRIAdapter`。
- `agents/`：`DisclosureAgent`，第一版只做披露分析。
- `workflows/`：`SingleReportWorkflow`，串联上传后分析流程。
- `services/`：PDF 处理、文档分块、复核存储、导出、审计日志。
- `tools/`：检索、证据规范化、判断、护栏、模型客户端。
- `api/`：`/api` 前缀下的 reports、runs、review、exports、health 接口。

## 5. 数据库设计方向

第一版使用 PostgreSQL。表结构围绕可追溯分析闭环设计：

- `reports`：原始文件、哈希、页数、解析状态。
- `analysis_runs`：运行状态、是否允许模型、开始/结束时间、错误信息。
- `document_pages`：页码、文本密度、图片占比、扫描页判断、质量标记。
- `document_chunks`：分块文本、页码、坐标、来源方法、OCR/VLM 状态、质量标记。
- `standard_requirements`：GRI 条款和要求。
- `disclosure_tasks`：一次运行中的条款任务。
- `assessments`：判断、理由、缺失项、模型调用标记、复核状态。
- `evidence_items`：证据文本、页码、坐标、来源文件哈希、来源方法。
- `recommendations`：建议和对应条款。
- `review_decisions`：人工复核记录。
- `audit_events`：上传、解析、模型调用、导出、复核等事件。

向量化预留：

- `document_chunks.embedding_status`
- `document_chunks.embedding_model`
- `document_chunks.embedding_vector` 第二阶段接 pgvector。
- 第一版不生成真实 embedding。

## 6. PDF 混合多路由管线

PDF 处理采用分级路由，不对所有页面默认全量 OCR。

```text
上传 PDF
  -> pypdf 读取页数、outline、元数据、基础文本可用性
  -> 页面预检测：文本密度、图片占比、表格复杂度、扫描页判断
  -> 数字原生页：pdfplumber 提取正文、坐标、表格
  -> 扫描关键页：OCRmyPDF + Tesseract 生成文本层，再交给 pypdf/pdfplumber
  -> 复杂失败页：Docling fallback
  -> 关键 KPI / 低质量页：授权后调用 deepseek-v4-flash 辅助识别
  -> 分块入库并标记质量
```

OCR 路由状态：

- `pypdf + pdfplumber` 仍是默认主链路。
- OCRmyPDF/Tesseract 已作为显式启用路由接入，默认不调用。
- 分析请求可传 `enable_ocr=true` 启用 OCR。
- 分析请求可传 `ocr_pages` 指定页码；未指定时只选择 `low_text_density` 或 `scanned` 页，且受 `OCR_MAX_PAGES` 限制。
- OCR 产物保存为派生 PDF，后续由 `pdfplumber` 读取目标页文本并生成 `source_method=ocr` 的 chunk。

关键原则：

- 原始 PDF 不覆盖。
- OCR 产物作为派生文件保存并记录来源。
- VLM 输出不作为未经复核的最终事实。
- OCR/VLM 来源的 KPI 默认标记 `needs_manual_review` 或低置信度。
- 页面和 chunk 需要保留 `source_method`、`ocr_status`、`vlm_used`、`bbox`、`quality_flags`。

第一版实现：

- pypdf/pdfplumber 主链路。
- 页面预检测。
- OCRmyPDF/Tesseract 工具路径配置和显式关键页 OCR 入口。
- Docling fallback 接口和状态字段。
- VLM 辅助识别接口和状态字段。

第一版不保证：

- 全量 OCR 后台队列。
- 全量 Docling 修复。
- OCR 置信度精细校准。

## 7. 模型调用设计

模型调用通过 OpenAI-compatible SDK 的薄适配层完成：

- `LLMClient`：文本判断、建议生成。
- `VisionLLMClient`：低质量页、关键 KPI、OCR 失败页的视觉辅助。
- `ProviderAdapter`：隔离 DeepSeek 与其他 OpenAI-compatible 服务差异。

调用规则：

- 默认不调用外部模型。
- 只有 `confirm_llm=true` 才能调用。
- 模型响应必须经过 Pydantic v2 校验。
- 校验失败进入人工复核。
- 测试中必须 mock 模型调用。
- 外部模型响应中的非公开数据不提交。

## 8. 前端设计

前端使用 Next.js App Router，核心页面：

```text
frontend/
  app/
    page.tsx
    reports/page.tsx
    runs/[runId]/page.tsx
    review/page.tsx
    audit/page.tsx
  components/
    layout/
    upload/
    analysis/
    evidence/
    review/
    charts/
  lib/
    api/
    generated/
    types.ts
    utils.ts
```

页面职责：

- 首页：最近运行记录、快速入口、系统状态。
- 报告上传页：上传 PDF、显示解析状态、确认模型调用、启动分析。
- 分析结果页：运行摘要、条款表格、证据详情、建议、导出入口。
- 人工复核页：待复核条款筛选、复核决策保存、历史复核记录。
- 审计日志页：运行事件、模型调用状态、文件哈希、错误信息。

前端约束：

- 工作台式界面，不做聊天入口。
- 空状态必须清楚显示暂无数据。
- 不展示无来源的准确率、完成率或最终结论。
- 图表只通过内部组件暴露业务入参，页面不直接依赖 Recharts API。
- API 类型由 OpenAPI 生成，业务组件使用封装后的 client。

## 9. API 边界

API 前缀为 `/api`。

第一版接口：

```text
GET  /api/health
POST /api/reports/upload
POST /api/reports/{report_id}/analyze
GET  /api/runs
GET  /api/runs/{run_id}
GET  /api/runs/{run_id}/assessments
GET  /api/runs/{run_id}/recommendations
GET  /api/review/runs
GET  /api/review/runs/{run_id}/assessments
POST /api/review/runs/{run_id}/decisions
GET  /api/exports/runs/{run_id}/assessments.csv
GET  /api/exports/runs/{run_id}/review.csv
GET  /api/exports/runs/{run_id}/assessments.json
GET  /api/exports/runs/{run_id}/review.json
GET  /api/audit/runs
```

上传和分析分离：

- 上传接口只保存文件和元数据。
- 分析接口显式触发工作流；请求体支持 `confirm_llm`、`enable_ocr`、`ocr_pages`。
- 前端通过 TanStack Query 轮询运行状态。

## 10. 测试与验证

后端测试：

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

前端测试：

- upload 页面状态。
- run 页面空状态和数据状态。
- review 决策提交。
- chart wrapper 业务入参渲染。
- `pnpm build` 和 typecheck。

验收：

- 后端 `pytest` 通过。
- 前端 `pnpm build`、typecheck、Vitest 通过。
- 上传、分析、复核、导出链路通过。
- 原 `envision` 和 `esg-dashboard` 不删除、不覆盖、不回退。

## 11. 风险与控制

扫描件处理耗时：

- 不默认全量同步 OCR。
- 先做页面预检测。
- 只有显式启用时才对指定页或低文本/扫描页 OCR。
- OCR 页数受 `OCR_MAX_PAGES` 限制。
- 后续可增量重跑。

多模态识别幻觉：

- VLM 结果标记 `vlm_assisted`。
- 默认进入人工复核或低置信度。
- 不把 VLM 输出直接写成最终披露事实。

PostgreSQL 本地依赖：

- Docker Compose 管数据库。
- `.env.example` 提供连接配置。
- Alembic 管迁移。

前后端契约漂移：

- FastAPI OpenAPI 生成 TypeScript types。
- 前端不手写重复接口类型。

图表库迁移：

- 图表库封装在 `components/charts/`。
- 页面只使用业务图表组件。
- 后续切 ECharts 只改组件内部。

## 12. 待进入实施计划的任务组

1. 初始化 Monorepo、Git、根配置和 Docker Compose。
2. 建立 FastAPI、Pydantic settings、PostgreSQL、SQLAlchemy、Alembic。
3. 实现领域模型、数据库表和 repository。
4. 实现 PDF 多路由解析框架和页面预检测。
5. 迁移允许的 GRI 和报告资产。
6. 实现 `GRIAdapter`。
7. 实现 `DisclosureAgent` 和模型适配层。
8. 实现 `SingleReportWorkflow`。
9. 实现 reports、runs、review、exports API。
10. 初始化 Next.js、Tailwind、shadcn/ui、TanStack Query、TanStack Table。
11. 实现上传、结果、复核、审计页面。
12. 配置 OpenAPI TS 生成、测试和构建脚本。
