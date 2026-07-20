# ESG-Agent 产品与技术设计规格

## 1. 产品结论

ESG-Agent 第一版面向企业 ESG 团队，提供单报告 GRI 核查闭环。系统保留 577 个 GRI 标准核查单元，经版本化结构编译形成 493 个独立判断项、78 个父级上下文项和 6 个方法待确认项；只有独立判断项生成 verdict，避免把父级容器和方法说明伪装成并列披露结论。

第一版用户流程：

```text
报告列表或上传空状态
→ 上传 PDF
→ 自动识别企业、年度、语言和页数
→ 用户确认报告信息
→ 编译 577 个标准核查单元并分析 493 个独立 requirement
→ 展示业务阶段进度和部分失败
→ 高优先级队列优先人工复核
→ 独立处理适用性待判定项
→ 按 GRI 主题查看全部结果
→ 形成整改任务
→ 导出完整核查表、管理层摘要和改进任务清单
```

第一版不建设多租户、复杂权限、顾问项目空间、多公司批量分析、同行对标、舆情监测、多标准混合分析或开放式风险规则配置。

## 2. 核心产品原则

1. **范围完整：** 后端固定校验 577 个标准核查单元，并对其中 493 个结构完整的独立 requirement 生成 assessment。
2. **复核聚焦：** 前端以高优先级队列为主，适用性待判定队列和完整核查表为辅。
3. **维度分离：** 披露结论、证据状态、适用性状态和复核优先级分别保存和展示；`unknown` 或无证据不能天然升级为高优先级。
4. **系统与人工分离：** 系统 assessment 保持不可变，人工操作形成只追加 review snapshot。
5. **范围诚实：** “高优先级项目已复核”不表示全部 577 个标准核查单元均已人工确认。
6. **部分失败可用：** 单个 requirement 失败不丢弃其他结果；分析失败单独计数、阻止正式输出并支持重跑。
7. **业务语言：** 普通界面显示中文业务名称，不暴露 profile、ontology、route、evidence kind 等内部实现。
8. **输出可审计：** 草稿和正式版本区分，明确人工确认范围与系统待确认范围。

## 3. 已确认技术选型

| 类别 | 选型 |
| --- | --- |
| 仓库 | Monorepo：`backend`、`frontend`、`docs` |
| 后端 | Python 3.11、FastAPI、Pydantic v2 |
| 数据库 | PostgreSQL、SQLAlchemy 2.0、Alembic，预留 pgvector |
| 前端 | Next.js App Router、TypeScript |
| UI | Tailwind CSS、shadcn/ui、lucide icons |
| 数据请求 | TanStack Query |
| 表格 | TanStack Table |
| 图表 | Recharts，通过业务组件封装 |
| PDF | pypdf、pdfplumber、OCRmyPDF/Tesseract、Docling fallback、授权后 VLM 辅助 |
| 模型 | OpenAI-compatible 薄适配层，默认不调用 |
| 测试 | pytest、Vitest、React Testing Library、typecheck、build |
| 包管理 | 后端 uv，前端 pnpm |

保持当前 Next.js/FastAPI 技术栈。`esg-dashboard` 只作为信息架构、颜色语言和组件风格参考，不迁移其 Vite/React 技术栈。

## 4. 页面信息架构

### 4.1 路由

```text
/reports                         报告列表与上传入口
/reports/[reportId]/confirm      报告信息确认
/reports/[reportId]/progress     分析阶段进度
/reports/[reportId]/dashboard    报告仪表盘
/reports/[reportId]/review       三栏人工复核工作台
/reports/[reportId]/assessments  完整 GRI 核查表
/reports/[reportId]/actions      整改任务清单
/reports/[reportId]/exports      输出与版本记录
/reports/[reportId]/audit        报告审计记录
```

报告列表是产品入口。首次使用显示上传空状态；已有报告时显示报告列表。用户可设置本地偏好，在进入产品时自动打开上次报告。

### 4.2 上传与确认

上传后系统预检测：

- 企业名称；
- 报告年度；
- 主要语言；
- PDF 页数；
- 文件名和 SHA256；
- 文本可用性与扫描风险。

metadata 预检测优先使用文件名和 PDF 前两页可提取文本，识别企业名称、报告年度、主要语言和页数。检测值只作为确认页候选值，用户确认前不写入正式业务字段。无法从本地文本可靠识别时保持空值，不调用外部模型、OCR 或 VLM，不补造企业信息。

用户确认企业、年度和语言后才能启动分析。自动识别值必须允许修改，修改写入审计事件。

### 4.3 报告仪表盘

仪表盘显示：

- 分析状态和最新正式输出版本；
- 493 个独立判断项的结果分布，以及 577/493/78/6 范围说明；
- 高、中、低复核优先级数量；
- 高优先级复核进度；
- 适用性待判定数量；
- GRI 主题分布；
- 部分失败与需要重跑的 requirement；
- 待整改任务摘要。

不得展示无来源的准确率或暗示系统结论已经全部人工确认。

### 4.4 三栏复核工作台

桌面端：

- 左栏：高优先级队列、适用性待判定队列、原因、GRI 主题和复核状态；
- 中栏：requirement 中文名称、披露结论、证据状态、适用性状态、复核优先级、判断依据、缺失项、备注和操作；
- 右栏：PDF 页面、证据片段、页码导航和证据有效性操作。

窄屏端切换 `复核队列 / 核查详情 / PDF 证据` 三个视图。切换不丢失当前 requirement、未保存编辑内容或 PDF 页码。

### 4.5 完整核查表

当前完整核查表承载 493 个独立判断结果，必须分页并支持；78 个上下文项和 6 个方法待确认项通过标准范围说明保留，下一前端计划再补充 577 单元的结构化范围展示：

- GRI 主题；
- 复核优先级；
- 系统结论；
- 人工结论；
- 复核状态；
- 证据状态；
- 整改状态；
- 关键词。

## 5. 业务字段与内部字段

普通界面使用中文业务字段：

| 中文业务名称 | 内部字段 |
| --- | --- |
| 系统结论 | `verdict` |
| 人工结论 | `reviewed_verdict` |
| 复核状态 | `review_status` |
| 复核优先级 | `review_priority`；兼容字段为 `risk_level` |
| 优先级原因 | `risk_reason_codes` |
| 证据状态 | `evidence_status` |
| 适用性状态 | `applicability_status` |
| 判断依据 | `rationale` |
| 缺失项 | `missing_items` |
| PDF 页码 | `source_pdf_page` |
| 报告页码 | `source_report_page` |
| 证据片段 | `evidence_preview` |

高级说明可以显示“中文（字段名）”。profile、ontology、route、candidate pages、evidence kind 和内部 guardrail 只进入诊断日志或管理员级导出，不进入普通产品界面。

## 6. 状态模型

### 6.1 报告状态

```mermaid
stateDiagram-v2
    [*] --> uploaded
    uploaded --> metadata_detected
    metadata_detected --> awaiting_confirmation
    awaiting_confirmation --> ready_for_analysis: 用户确认
    ready_for_analysis --> analyzing
    analyzing --> analysis_completed
    analyzing --> partially_completed
    analyzing --> analysis_failed
    partially_completed --> analyzing: 重跑失败项
    analysis_completed --> high_risk_review_completed: 高优先级 assessment 完成
    partially_completed --> high_risk_review_completed: 高优先级 assessment 完成
    high_risk_review_completed --> formally_exported: 分析完整且输出门禁通过
    formally_exported --> reopened: 填写重开原因
    high_risk_review_completed --> reopened: 填写重开原因
    reopened --> analyzing
    formally_exported --> archived
```

### 6.2 分析阶段

业务阶段固定为：文件检查、PDF 解析、报告结构识别、GRI requirement 匹配、证据与结论生成、风险分级、结果汇总。

阶段状态：`pending / running / completed / partially_failed / failed`。每阶段保存完成数量、总数量、开始时间、结束时间和业务错误摘要。

普通进度页按阶段工作量加权：文件检查 5%、PDF 解析 10%、报告结构识别 5%、GRI requirement 匹配 10%、证据与结论生成 60%、风险分级 5%、结果汇总 5%。阶段内按 `completed_units / total_units` 计算，成功终态强制为 100%，失败终态保留最后真实百分比；不使用定时伪增长或随机增量。running run 的最新有效 stage event 超过 120 秒未更新时，前端提示后台任务可能中断，但不修改数据库状态。上传和 metadata 确认阶段不展示 577 条计数；577 条 eligible requirement 继续作为后端完整性和回归门禁，不作为首次上传时的前端识别结果。

### 6.3 Requirement 复核状态

```text
pending_review
reviewed_approved
reviewed_modified
evidence_invalidated
reopened
```

快速通过生成 `reviewed_approved`；修改任何字段生成 `reviewed_modified`；证据无效生成 `evidence_invalidated` 并重新计算风险。

### 6.4 输出状态

```text
draft
formal
superseded
voided
```

旧正式版本不得覆盖。报告重开并生成新正式版本后，旧版本转为 `superseded`。

## 7. risk-v2.1 四维核查模型

每条 assessment 分开保存和展示四个维度：

1. 披露结论：`disclosed / partially_disclosed / unknown`；
2. 证据状态：有效、缺失、非实质、质量异常或冲突；
3. 适用性状态：适用、企业声称不适用、人工确认不适用或待判定；
4. 复核优先级：`high / medium / low`。

数据库继续保留 `risk_level` 兼容列，risk-v2.1 中该列承载复核优先级；API 同时返回语义明确的 `review_priority`。每次计算只追加保存 `risk_reason_codes`、`risk_rule_version`、`evidence_status` 和 `applicability_status`。历史 risk-v1 数据不回填推测值。

### 7.1 高优先级

高优先级只用于需要立即处理的明确异常：

- 结论与证据充分性冲突；
- 证据被人工判定无效、来源冲突或页码冲突；
- 严重证据质量异常；
- 正式输出后重新开启的项目。

requirement 分析失败或结果未生成在运行维度单独计数，等同高优先级阻断项，但没有伪造 assessment；必须重跑成功后才能生成正式输出。

### 7.2 中优先级

- `unknown` 且仅有索引、从略说明或其他非实质证据；
- `unknown` 且存在直接证据但仍无法形成结论；
- 明确未披露、部分披露仍存在重要缺口，或企业声称不适用但尚未人工确认；
- 一般质量警告或需要人工判断的充分性问题，但没有高优先级异常。

### 7.3 低优先级

- `unknown` 且没有有效证据；该等级只表示复核顺序靠后，不代表已披露或已确认不适用；
- `partially_disclosed` 且直接证据有效、质量正常；
- `disclosed` 且直接证据有效、质量正常；
- 人工确认不适用且没有其他异常。

### 7.4 独立适用性队列

`applicability_status=undetermined` 的项目进入独立队列，不改变复核优先级。队列支持单条确认和当前页批量确认；批量操作要求复核人和备注，每条 assessment 仍追加独立 review snapshot，并共享 `batch_id` 供审计追踪。

高优先级完成率的分母取当前报告最新有效 run 中实际生成 assessment 的高优先级集合。中低优先级或待判定适用性不阻止高优先级完成态；界面和输出必须披露这些未人工确认范围。重开或优先级重算后分母允许变化，变化保留在追加式记录中。

## 8. 人工复核与审计

### 8.1 单用户身份

第一版不建设账号系统。用户首次执行复核时填写复核人名称，前端本地保存便于后续默认填充，服务端每次写操作仍显式接收并保存复核人。

### 8.2 可编辑内容

- 结论；
- 适用性判断；
- 证据页；
- 证据片段；
- 判断依据；
- 缺失项；
- 备注。

系统 assessment 不可覆盖。每次人工操作追加 review snapshot 和字段级 change event，保存原值、新值、复核人、时间、原因、操作类型和上一个 snapshot。

### 8.3 操作规则

- 快速通过：允许预设原因，备注可选；
- 修改：备注必填；
- 无效证据：备注必填；
- 批量操作：备注必填；
- 重开 requirement 或报告：原因必填。

审计记录只追加，不允许更新和删除。

## 9. 部分失败与重跑

分析失败分为：文件、解析、结构识别、route、evidence、assessment 和系统异常。

- 已成功 requirement 的 assessment 保留；
- 失败 requirement 作为分析异常阻断项单独统计，不伪造 assessment；
- 报告状态为 `partially_completed`；
- 用户可只重跑失败项；
- 新 run 与旧 run 分开保存；
- 重跑成功后通过最新有效结果视图合并展示，历史结果仍可审计。

后台分析任务只接收 `report_id/run_id`，在工作线程内创建并关闭独立数据库 session，禁止继续使用请求 session。工作流异常时先 rollback，再追加失败阶段、审计和 run/report 失败状态；服务启动时把遗留 `pending/running` run 收敛为 `failed`，失败原因固定为“分析服务重启，任务已中断”。

同一报告重新解析时，`document_pages` 和 `document_chunks` 在单一事务中按 report 先删后写；失败必须 rollback，避免唯一键冲突或页、分块半更新。

## 10. 后端模块边界

```text
backend/src/
  domain/       状态、DTO 和业务规则
  db/           持久化模型、repository、migration
  standards/    GRI requirement、ontology 和充分性规则
  agents/       系统 assessment
  workflows/    报告分析与失败项重跑
  services/     PDF、风险、复核、整改、导出、审计
  api/          报告、运行、结果、复核、整改和输出接口
```

report profile 只提供当前报告的候选证据路由。通用逻辑依赖行标签、章节语义、年份、单位和证据类型，不依赖固定页码。

## 11. 数据库设计方向

现有 `reports`、`analysis_runs`、`document_pages`、`document_chunks`、`standard_requirements`、`disclosure_tasks`、`assessments`、`evidence_items`、`recommendations`、`review_decisions` 和 `audit_events` 保留。

设计新增：

- `analysis_stage_events`：业务阶段进度；
- `assessment_risks`：复核优先级、证据状态、适用性状态、原因和规则版本；
- `review_snapshots`：人工结果快照；
- `review_change_events`：字段级变更；
- `improvement_actions`：整改任务；
- `export_versions`：草稿和正式输出版本。

`reports` 扩展企业、年度、语言、metadata confirmation 和报告状态；`analysis_runs` 扩展引擎版本、风险规则版本和部分失败统计。具体字段和迁移顺序以 `docs/product/data-model-impact.md` 为准。

`0009_active_analysis_run_gate` 在 `analysis_runs(report_id)` 上增加只覆盖 `pending/running` 的 PostgreSQL 部分唯一索引，数据库负责保证同一报告最多一个 active run；历史终态 run 不受限制。

`0010_risk_v2_dimensions` 为 `assessment_risks` 增加 nullable `evidence_status`、`applicability_status`，并为 `review_snapshots` 增加 nullable `reviewed_applicability_status`。迁移不回填 risk-v1 历史行，不删除旧列；新 risk-v2.1 快照由服务写入明确维度值。

`0011_ai_suggestions` 为 `analysis_runs` 增加 577/493/78/6 范围计数字段，为 `disclosure_tasks` 增加原始文本、父级上下文和结构状态，并新增追加式 `ai_assessment_suggestions`。AI suggestion 记录模型、Prompt 版本、输入哈希、建议 verdict、中文依据、缺失项、证据引用、guardrail、usage、失败和原始响应；外键删除只随所属 report/run 级联，不提供覆盖规则 assessment 或人工 snapshot 的写路径。

替代接口或新表实际启用后，旧接口和旧表进入两个连续阶段验收周期的兼容窗口。每个周期必须有自动回归覆盖；连续两轮通过且历史数据映射一致后，才允许在后续独立迁移中清理。审批日期和仅完成代码定义不计入兼容周期。

## 12. API 边界

API 前缀保持 `/api`。资源分组：

- reports：列表、上传、详情、metadata 确认、分析、重开；
- runs：状态、阶段、失败项重跑；
- assessments：分页列表、详情和筛选；
- review：高优先级队列、适用性队列、决策、适用性批量操作、历史和重开；
- actions：整改任务；
- exports：草稿、正式版本和文件；
- audit：报告级只追加记录。
- demo：仅 demo 环境可用的在线业务数据清理。

报告 metadata 只允许在 `uploaded/metadata_detected/awaiting_confirmation/ready_for_analysis` 写入；进入分析后返回 `409 report_metadata_locked`。分析启动先查询 active run，并由数据库唯一索引处理竞态；冲突返回 `409 analysis_already_running`。

详细请求、响应和错误码以 `docs/product/api-contract.md` 为准。OpenAPI 是前端类型唯一来源。

## 13. PDF 与外部模型边界

PDF 继续采用分级路由：pypdf/pdfplumber 为默认主链路；扫描关键页可显式启用 OCR；复杂失败页允许 Docling fallback；VLM 只有用户显式确认后才允许调用。

DeepSeek 使用 OpenAI-compatible 薄适配层。`confirm_llm=false` 时 AI 阶段记录为 skipped 且不实例化外部调用；`confirm_llm=true` 仍只对结构独立、具有直接证据并进入高/中复核优先级的条目调用。AI 建议只追加保存，不能设置适用性、风险优先级、人工复核状态或正式输出状态；模型失败只使 AI 阶段部分失败，不使确定性分析 run 失败。

硬性原则：

- 原始 PDF 不覆盖；
- OCR 产物作为派生文件保存；
- 外部模型默认不调用；
- AI `disclosed` 不允许直接升级规则的 `partial/unknown`，此类建议进入人工复核 guardrail；
- VLM 输出不直接成为最终合规事实；
- OCR/VLM、低文本和复杂表格风险进入 evidence quality 和风险模型；
- 测试中 mock 外部模型。

## 14. 输出设计

第一版支持：

1. 完整 GRI 核查表：Excel、可打印网页；
2. 管理层摘要：PDF、可打印网页；
3. 改进任务清单：Excel；
4. 审计说明：复核范围、系统待确认范围、版本和生成时间。

草稿输出带草稿标识。正式输出只有在分析结果完整且高优先级复核完成后生成，并绑定：原文件哈希、run、GRI requirement 版本、分析引擎版本、风险规则版本和 review snapshot 版本。

输出必须区分人工确认结果与系统待确认结果，并注明仍未人工复核的中优先级、低优先级和适用性待判定数量。高优先级完成文案不得暗示全部 577 条均已人工确认。

## 15. 前端设计约束

- 工作台式界面，不做聊天入口；
- 报告和核查对象是首屏信号；
- 使用紧凑信息密度，不使用营销式 hero；
- 按钮使用 lucide icons 和明确 tooltip；
- 页面不直接依赖 Recharts API；
- 577 条表格分页和按需加载证据；
- 所有核心指标来自后端 API；
- 空、加载、部分失败、失败和无权限外的单用户状态均有明确呈现；
- 中文业务名称优先，内部字段仅在高级说明出现。

## 16. 测试与验收

后端重点：

- 577 条任务生成；
- 577/493/78/6 结构编译计数和有效 requirement 文本；
- AI 显式授权、追加保存、证据引用、schema 和失败降级；
- 报告 metadata 确认；
- 阶段进度和部分失败；
- risk-v1 兼容与 risk-v2.1 复核优先级规则；
- review snapshot 只追加；
- 必填原因校验；
- 分析完整性和高优先级完成门槛；
- 正式输出版本和复核范围；
- OpenAPI 契约与数据库迁移。

前端重点：

- 报告列表和上传空状态；
- metadata 确认；
- 分析阶段进度；
- 高优先级与适用性队列筛选；
- 三栏与窄屏视图；
- 快速通过和字段编辑；
- 批量操作备注；
- 完整核查表分页；
- 草稿/正式输出门槛。

验收命令：

```powershell
cd backend
uv run pytest

cd ../frontend
pnpm typecheck
pnpm test
pnpm build
```

## 17. 实施顺序

1. 报告列表、metadata 检测与确认；
2. 577 个标准核查单元结构编译、493 个独立判断项后台分析、阶段进度和部分失败；
3. risk-v2.1 四维模型与双队列 API；
4. review snapshot、字段级审计和重开；
5. 报告仪表盘与三栏复核工作台；
6. 完整核查表与整改任务；
7. 草稿和版本化正式输出；
8. 使用不同企业报告验证产品闭环和分析泛化。

## 18. 当前实现与验收状态

截至 2026-07-20，代码迁移 head 为 `0011_ai_suggestions`。报告上传与 metadata 确认、577/493/78/6 标准结构编译、规则分析、后端 AI 辅助阶段、active run 门禁、后台任务恢复、risk-v2.1 四维模型、双队列、追加式复核、三栏工作台、整改任务、版本化输出和 demo 在线重置均已有实现。Envision v2 regeneration gate 与 Goldwind 100 条人工 gold gate 继续独立验证分析事实。

本地确定性产品闭环和 AI 辅助后端冻结验收已经完成。225 条真实 DeepSeek 评估的一致率为 72.32%，guardrail 后 false disclosed、证据越界、可比错页、schema 失败和模型失败均为 0；16 条人工差异继续等待 GRI 方法裁决，4 条人工—AI证据页差异单列展示。后端 626 项测试、前端 19 个测试文件 51 项测试、typecheck、production build、Envision v2 和 Goldwind gate 通过。AI 前端交互、通用 verdict 批量复核、独立 reopen API、report 级审计、单 export 下载和完整整改任务清单导出仍为后续项。

旧 `review_decisions` 已完成两个连续兼容周期的数据映射验证，但旧 API、旧前端页面和旧导出仍有调用者，因此继续保留。验收风险、运行命令和下一步见 `docs/DEVELOPMENT.md`。

## 19. 本地演示环境隔离

项目最终只在本机部署验证，使用一套代码、Alembic migration、GRI 规则、report profile 和只读原始资产。业务数据按用途分为三个 PostgreSQL 数据库：

- `esg_agent`：开发、回归、正式验收和长期保留，禁止自动重置；
- `esg_agent_demo`：产品演示数据；维护人员可在需要时显式重建，不作为普通演示前提；
- `esg_agent_test`：自动测试，测试过程允许清理。

演示环境使用 `APP_ENV=demo`，上传和派生文件只能写入 `backend/data/runtime/demo/`。现有 `esg_agent` 继续使用原运行时目录，不迁移已有文件或数据库路径引用。`backend/data/reports/`、`backend/data/standards/` 和 `backend/data/manifests/` 为共享只读资产，不随演示库重置。

重复上传默认以文件哈希返回 `409 duplicate_report`，响应给出已有报告 ID 和状态；同一哈希已有多份历史时按 `created_at DESC, report_id DESC` 返回最新报告，避免“查看已有结果”回到旧规则版本。前端提供“查看已有结果”和“重新上传并分析”两个产品选项；用户明确选择后，以 `duplicate_policy=create_new` 再次上传并创建新的 `report_id`、metadata 确认和分析 run，已有报告、复核、整改任务和输出版本保持不变。`file_hash` 是重复提醒依据，不是报告唯一键。

`POST /api/demo/reset` 仅作为维护接口保留，不由普通前端流程调用。在线重置必须校验 `APP_ENV=demo`、配置数据库名、`SELECT current_database()` 的实际库名、上传/派生目录边界、精确确认口令和不存在 active run。数据库先在一个事务内追加重置审计并删除 report 根业务数据，再清理 `uploads/derived`；运行时目录包含 reparse point 时拒绝清理。数据库已清空而文件清理失败时返回结构化部分失败，禁止伪装成全部成功。

后端启动不会自动清空 demo；离线 `reset_demo_environment` 继续作为服务停止后的故障恢复路径。外部模型、OCR 和 VLM 继续默认关闭。
