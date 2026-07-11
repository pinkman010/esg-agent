# 企业 ESG 产品闭环设计校准计划

> **执行要求：** 使用 `executing-plans` 在 `main` 分支按任务顺序 inline 执行。本阶段只修改文档并读取现有实现，不修改业务代码、数据库迁移、API、前端页面或测试。本计划结束时必须暂停，等待人工批准设计冻结结果。

**目标：** 将项目第一版重新聚焦为面向企业 ESG 团队的单报告 GRI 核查产品，完成产品范围、页面信息架构、状态模型、固定风险规则、API 契约和数据库影响设计，并在人工批准前停止实现。

**架构：** 后端继续分析全部 577 条 eligible GRI requirement，系统 assessment 与人工 review snapshot 分离；前端以报告列表为入口、高风险队列为主、完整核查表为辅。现有 report profile、ontology、route 和 evidence kind 保留为内部分析实现，不进入普通业务界面。

**技术栈：** Next.js App Router、TypeScript、Tailwind CSS、shadcn/ui、TanStack Query、TanStack Table、FastAPI、Pydantic v2、PostgreSQL、SQLAlchemy 2.0、Alembic。

**执行状态：** 已完成。设计于 2026-07-11 获得人工批准，后续阶段 0-8 已执行；本文件保留为设计校准历史，当前实现与验收状态以 `README.md`、`docs/DESIGN.md` 和 `docs/DEVELOPMENT.md` 为准。

---

## 1. 权威决策与当前基线

### 1.1 第一版产品目标

第一版服务企业 ESG 团队，提供以下闭环：

```text
报告列表或上传空状态
→ 上传 PDF
→ 自动识别企业、年度、语言和页数
→ 用户确认报告信息
→ 后台分析 577 条 eligible GRI requirement
→ 展示业务阶段进度和部分失败
→ 高风险队列优先人工复核
→ 按需查看全部 GRI 结果
→ 形成整改任务
→ 导出完整核查表、管理层摘要和改进任务清单
```

第一版保留跨企业、跨报告格式的证据识别泛化能力，不建设多租户、复杂权限、顾问项目空间、同行对标、多标准混合分析或开放式风险规则配置。

### 1.2 设计冻结时的实现事实

以下内容记录设计冻结时的历史基线，不代表当前实现状态：

- 后端已能解析报告、建立 run、生成 eligible GRI task、保存 assessment/evidence/recommendation、执行基础人工复核并导出 JSON/CSV。
- Envision 577 条回归链路已经跑通；Goldwind 验证了 report profile、KPI 行匹配和跨报告路由能力。
- 前端已有 `/reports`、`/runs`、`/runs/[runId]`、`/review`、`/audit` 页面和基础工作台组件。
- 当前复核 API 只保存 `assessment_id`、`review_status` 和 `reviewer_note`，不能表达字段级修改、快速通过原因、批量操作、重开和版本化正式结果。
- 当前导出只覆盖 JSON/CSV，尚未区分系统待确认结果、人工确认结果、草稿和正式版本。
- 当前风险入口主要依赖 `needs_manual_review`，没有独立且版本化的业务风险等级。
- 当前工作树包含尚未提交的 Goldwind/ontology/profile/routing 改动；本阶段不得覆盖、回退或继续扩展这些改动。

### 1.3 文档职责

- `README.md`：第一版产品定位、用户流程、仓库入口和启动方式。
- `docs/DESIGN.md`：产品与技术设计唯一源，包括范围、状态模型、页面、API、数据库和输出。
- `docs/DEVELOPMENT.md`：当前实现状态、暂停点、运行命令、测试命令和恢复入口。
- `docs/plan/product-closure-realignment-plan.md`：本次设计校准过程和人工停止条件。

## 2. 硬性边界

1. 后端分析范围固定为 577 条 eligible GRI requirement。
2. 前端高风险队列是主要复核入口，GRI 主题筛选和完整核查表是辅助入口。
3. “高风险复核已完成”只表示全部高风险项已完成，不得暗示 577 条全部人工确认。
4. 系统原始 assessment 不得被人工修改覆盖；人工修改形成只追加的 review snapshot 或 decision。
5. 普通界面不展示 profile、ontology、route、evidence kind、candidate pages 等内部实现字段。
6. 业务界面使用中文名称；高级说明可使用“中文（字段名）”。
7. 第一版单用户运行，首次复核填写复核人名称；不实现账号、角色和权限系统。
8. 修改、无效证据、批量操作和重新开启报告必须填写原因或备注。
9. 报告分析部分失败时保留可用结果，受影响 requirement 自动进入高风险队列。
10. 第一版风险规则由系统固定并版本化，不提供前端配置入口。
11. 草稿输出必须带草稿标识；正式输出只能在高风险复核完成后生成。
12. 本阶段不修改代码和数据库，只完成设计冻结材料。

## 3. 目标页面信息架构

### 3.1 一级页面

```text
/reports                         报告列表与上传入口
/reports/[reportId]/confirm      报告信息确认
/reports/[reportId]/progress     分析阶段进度
/reports/[reportId]/dashboard    报告仪表盘
/reports/[reportId]/review       三栏人工复核工作台
/reports/[reportId]/assessments  完整 GRI 核查表
/reports/[reportId]/actions      整改任务清单
/reports/[reportId]/exports      草稿与正式输出版本
/reports/[reportId]/audit        报告审计记录
```

报告列表是默认入口。无报告时显示上传空状态；已有报告时显示报告列表，并允许本地偏好决定是否自动打开上次报告。

### 3.2 三栏复核工作台

桌面端：

```text
左栏：风险队列、风险原因、GRI 主题筛选、完成状态
中栏：requirement 中文业务名称、系统结论、人工结论、依据、缺失项、备注
右栏：PDF 页面、证据片段、页码导航、证据有效性操作
```

窄屏端使用三个稳定视图切换：`风险队列`、`核查详情`、`PDF 证据`。视图切换不得丢失当前 requirement、编辑草稿或 PDF 页码。

### 3.3 页面业务字段

普通界面显示：

- GRI 主题和 requirement 中文业务名称；
- 系统结论、人工结论、风险等级和风险原因；
- 证据页、证据片段、判断依据、缺失项和复核备注；
- 分析状态、复核状态、整改状态和输出状态。

高级说明允许显示：

- `系统结论（verdict）`；
- `复核状态（review_status）`；
- `PDF 页码（source_pdf_page）`；
- `报告页码（source_report_page）`。

## 4. 状态模型设计

### 4.1 报告状态

```text
uploaded
→ metadata_detected
→ awaiting_confirmation
→ ready_for_analysis
→ analyzing
→ partially_completed | analysis_completed | analysis_failed
→ high_risk_review_completed
→ formally_exported
→ archived
```

允许从 `high_risk_review_completed` 或 `formally_exported` 进入 `reopened`，必须记录重开原因；重开后继续保留原正式版本。

### 4.2 分析阶段

业务阶段固定为：

1. 文件检查；
2. PDF 解析；
3. 报告结构识别；
4. GRI requirement 匹配；
5. 证据与结论生成；
6. 风险分级；
7. 结果汇总。

每个阶段至少包含 `pending / running / completed / partially_failed / failed`、完成数量、总数量、开始时间、结束时间和可读错误摘要。

### 4.3 Requirement 复核状态

```text
pending_review
reviewed_approved
reviewed_modified
evidence_invalidated
reopened
```

系统 assessment 的 `verdict` 与人工复核状态分开保存。`reviewed_approved` 表示快速通过系统结果；`reviewed_modified` 表示至少一个业务字段被人工修改。

### 4.4 输出状态

```text
draft
formal
superseded
voided
```

正式输出绑定文件哈希、run、GRI requirement 版本、分析引擎版本、风险规则版本和 review snapshot 版本。

## 5. 固定高风险规则草案

风险等级独立于披露结论。第一版采用 `high / medium / low`。

### 5.1 高风险

满足任一条件：

- requirement 分析失败或没有生成 assessment；
- `verdict=unknown`；
- 无有效 source evidence；
- 证据需要 OCR/VLM 或存在正文未抽取、页码冲突、证据错页风险；
- omission note、index statement 或非 substantive evidence 是唯一依据；
- 系统检测到结论与证据充分性冲突；
- 人工将证据标记为无效；
- 批量操作产生待确认结果；
- 正式输出后 requirement 被重新开启。

### 5.2 中风险

- `verdict=partially_disclosed` 且存在有效 substantive evidence；
- 证据充分但仍缺拆分维度、方法、假设或边界；
- requirement 存在明确整改项但不影响核心证据有效性。

### 5.3 低风险

- `verdict=disclosed`；
- 有直接、可定位且质量合格的 substantive evidence；
- 没有解析失败、质量风险或充分性冲突。

规则输出必须包含 `risk_level`、`risk_reason_codes`、`risk_rule_version`。人工不能直接修改风险规则，但人工编辑结果后系统应重新计算风险等级并保留前后值。

## 6. 系统结果与人工结果模型

### 6.1 系统 assessment

系统结果保持不可变事实记录：

- requirement identity；
- system verdict；
- system rationale；
- system missing items；
- evidence items；
- quality flags；
- engine/rule version；
- generated timestamp。

### 6.2 Review snapshot

人工复核允许编辑：

- 结论；
- 证据页；
- 证据片段；
- 判断依据；
- 缺失项；
- 备注。

每次保存追加新记录，至少包含：

- 原值和新值；
- 复核人；
- 操作类型；
- 原因或预设原因；
- 时间；
- 上一个 snapshot；
- 是否批量操作；
- 是否重新开启。

读取当前人工结果时使用最新有效 snapshot；历史记录不能更新或删除。

### 6.3 快速通过与备注规则

- 快速通过：允许选择预设原因，备注可选。
- 字段修改：备注必填。
- 证据无效：备注必填。
- 批量通过或批量修改：备注必填。
- 重新开启报告或 requirement：原因必填。

## 7. API 数据契约草案

设计阶段需要在 `docs/DESIGN.md` 中冻结以下资源，不在本阶段实现：

### 7.1 报告与确认

```text
GET  /api/reports
POST /api/reports/upload
GET  /api/reports/{report_id}
POST /api/reports/{report_id}/confirm-metadata
POST /api/reports/{report_id}/analyze
POST /api/reports/{report_id}/reopen
```

报告摘要至少返回企业名称、报告年度、语言、PDF 页数、状态、最新 run、高风险数量和高风险复核进度。

### 7.2 分析进度与结果

```text
GET  /api/runs/{run_id}
GET  /api/runs/{run_id}/stages
GET  /api/reports/{report_id}/dashboard
GET  /api/reports/{report_id}/assessments
GET  /api/reports/{report_id}/assessments/{assessment_id}
POST /api/runs/{run_id}/retry-failed
```

assessment 列表支持风险等级、GRI 主题、结论、复核状态和关键词筛选，并采用分页响应。

### 7.3 人工复核

```text
GET  /api/reports/{report_id}/review-queue
GET  /api/assessments/{assessment_id}/review-history
POST /api/assessments/{assessment_id}/review-decisions
POST /api/reports/{report_id}/review-decisions/batch
POST /api/assessments/{assessment_id}/reopen
```

写接口使用明确的操作类型：`approve / modify / invalidate_evidence / batch_approve / batch_modify / reopen`。服务端根据操作类型校验复核人和备注。

### 7.4 整改与输出

```text
GET  /api/reports/{report_id}/actions
POST /api/reports/{report_id}/actions
PATCH /api/actions/{action_id}
GET  /api/reports/{report_id}/exports
POST /api/reports/{report_id}/exports/draft
POST /api/reports/{report_id}/exports/formal
GET  /api/exports/{export_id}
```

正式输出接口必须校验全部高风险 requirement 已完成复核，并返回版本号、复核范围和文件清单。

## 8. 数据库影响草案

现有表保留。设计阶段评估新增或扩展：

- `reports`：企业、年度、语言、metadata confirmation、报告状态和重开状态；
- `analysis_runs`：引擎版本、风险规则版本、部分失败统计；
- `analysis_stage_events`：业务阶段进度；
- `assessment_risks`：风险等级、原因代码和规则版本；
- `review_snapshots`：人工字段快照和前序 snapshot；
- `review_change_events`：字段级原值、新值、原因和复核人；
- `improvement_actions`：整改任务、状态、优先级和来源 requirement；
- `export_versions`：草稿/正式版本、复核范围、文件清单和版本关系。

设计必须说明哪些字段进入新表、哪些保留在现有表，并给出追加式审计约束。人工批准前不得创建 Alembic migration。

## 9. 输出设计

第一版输出四类：

1. 完整 GRI 核查表：Excel、可打印网页；
2. 管理层摘要：PDF、可打印网页；
3. 改进任务清单：Excel；
4. 审计说明：复核范围、系统待确认范围、版本和生成时间。

所有输出必须区分：

- 人工确认结果；
- 系统待确认结果；
- 本次正式输出覆盖的高风险复核范围；
- 仍未人工复核的中低风险数量。

草稿显示草稿标识和生成时间；正式输出使用不可变版本号，后续重开生成新版本，旧版本标记为 `superseded`，不覆盖文件。

## 10. 执行任务

### Task 1：冻结当前现场并建立差距清单

**读取：**

- `README.md`
- `docs/DESIGN.md`
- `docs/DEVELOPMENT.md`
- `backend/src/domain/enums.py`
- `backend/src/domain/models.py`
- `backend/src/db/models.py`
- `backend/src/api/schemas.py`
- `backend/src/api/routes/`
- `frontend/app/`
- `frontend/components/`
- `frontend/lib/api.ts`

- [ ] 记录当前未提交文件，不覆盖 Goldwind/ontology/profile/routing 改动。
- [ ] 输出 `tmp/product-realignment/current-scope-gap.md`。
- [ ] 按报告管理、分析进度、风险、复核、审计、整改、输出和前端体验分类差距。
- [ ] 每项注明“已有、部分已有、缺失”和对应代码位置。

### Task 2：更新 README 产品定位

**修改：** `README.md`

- [ ] 将第一版目标改为企业 ESG 团队的单报告 GRI 核查闭环。
- [ ] 明确后端覆盖 577 条 eligible requirement。
- [ ] 明确高风险优先复核和完整结果辅助查看。
- [ ] 明确第一版排除多租户、复杂权限和顾问空间。
- [ ] 保留现有技术栈、资产保护和本地启动说明。

### Task 3：重构 DESIGN 产品与架构设计

**修改：** `docs/DESIGN.md`

- [ ] 替换“不追求完整 GRI 覆盖”的过期范围。
- [ ] 写入本计划第 3 至第 9 节的页面、状态、风险、复核、API、数据库和输出设计。
- [ ] 明确系统 assessment 与人工 review snapshot 分离。
- [ ] 明确部分失败、失败项重跑和高风险自动进入队列。
- [ ] 明确普通界面隐藏内部分析实现字段。
- [ ] 保留 PDF、外部模型确认、原始资产保护和可追溯原则。

### Task 4：更新 DEVELOPMENT 暂停点与恢复入口

**修改：** `docs/DEVELOPMENT.md`

- [ ] 记录 holdout/review-pack 扩展暂停。
- [ ] 记录 Goldwind 100 条 gate、Envision 577 零回归和定向 50 条产物均保留。
- [ ] 声明下一阶段转向产品闭环设计与实现。
- [ ] 保留现有运行、测试和 review CSV 工具命令，标记其为分析引擎维护工具。
- [ ] 写明设计批准前不得创建数据库迁移或修改正式 API。

### Task 5：输出页面与交互规格

**创建：** `docs/product/page-architecture.md`

- [ ] 定义报告列表、上传确认、分析进度、仪表盘、三栏复核、完整核查表、整改、输出和审计页面。
- [ ] 为每页列出入口、主要任务、数据状态、空状态、加载状态、错误状态和离开条件。
- [ ] 定义桌面三栏和窄屏视图切换。
- [ ] 建立内部字段到中文业务名称的显示映射。
- [ ] 说明参考 `esg-dashboard` 的信息架构、颜色语言和组件风格，不复制其技术栈。

### Task 6：输出状态机和风险规则规格

**创建：**

- `docs/product/state-model.md`
- `docs/product/risk-model.md`

- [ ] 使用 Mermaid 绘制报告、运行、复核和输出状态图。
- [ ] 为每个状态转换写触发条件、权限前提、审计事件和失败行为。
- [ ] 将本计划第 5 节风险规则转换为优先级明确的决策表。
- [ ] 定义 `risk_reason_codes` 的中文名称和内部代码。
- [ ] 定义高风险复核完成率计算公式，明确分母冻结规则和重开后的变化。

### Task 7：输出 API 和数据库契约规格

**创建：**

- `docs/product/api-contract.md`
- `docs/product/data-model-impact.md`

- [ ] 为本计划第 7 节接口定义请求、响应、分页、筛选、错误码和幂等要求。
- [ ] 定义报告摘要、风险队列项、复核详情、review snapshot、整改任务和输出版本 DTO。
- [ ] 逐表列出现有字段复用、新增表、唯一约束、外键、只追加约束和索引。
- [ ] 列出预计 Alembic migration 顺序，但不创建 migration。
- [ ] 明确 OpenAPI 类型生成对 `frontend/lib/generated/api-types.ts` 的影响。

### Task 8：形成编码阶段实施拆分

**创建：** `docs/plan/product-closure-implementation-plan.md`

- [ ] 按可独立验收的纵向阶段拆分：报告列表与确认、进度与部分失败、风险队列、复核快照与审计、三栏工作台、整改、版本化输出。
- [ ] 每个阶段列出精确后端、前端、迁移和测试文件。
- [ ] 每个行为修改采用 TDD，先列失败测试和验证命令。
- [ ] 第一轮实现不得同时启动全部阶段，必须给出依赖顺序和提交边界。
- [ ] 将 holdout 泛化验证安排在产品闭环后，不继续扩展 Goldwind per-ID 规则。

### Task 9：文档一致性检查

- [ ] 检查 README、DESIGN、DEVELOPMENT 和 `docs/product/` 无范围冲突。
- [ ] 检查文档无本机绝对路径。
- [ ] 检查普通产品字段没有暴露 profile、ontology、route 和 evidence kind。
- [ ] 检查“高风险复核已完成”没有被描述为“全部 577 条已人工确认”。
- [ ] 检查所有状态、API DTO 和数据库字段命名一致。
- [ ] 执行 `git diff --check`。

### Task 10：生成设计冻结审批包并停止

**创建：** `tmp/product-realignment/design-approval-checklist.md`

- [ ] 汇总页面结构、风险规则、状态模型、系统/人工结果关系、API 和数据库变更。
- [ ] 列出第一轮建议实施范围及明确不实施项。
- [ ] 列出仍需人工选择的取舍，不提供隐式默认批准。
- [ ] 暂停执行，等待人工审批。

## 11. 人工停止条件

完成 Task 10 后必须停止，不得进入代码实现。人工需要逐项批准：

1. 页面信息架构；
2. 高风险规则和完成门槛；
3. 报告、运行、复核和输出状态机；
4. 系统 assessment 与人工 review snapshot 的保存方式；
5. API 资源和写操作边界；
6. 数据库新增表与迁移范围；
7. 第一轮编码阶段及优先级。

执行过程中遇到以下情况也必须提前停止：

- 产品决策之间存在无法同时满足的冲突；
- 需要修改现有代码、数据库或 API 才能完成设计验证；
- 需要覆盖或回退用户未提交改动；
- 需要引入多租户、权限系统或新技术栈；
- 需要改变 577 条 eligible requirement 的后端分析范围；
- 需要继续扩展 Goldwind holdout/review-pack 工具链；
- 发现当前数据库无法保留系统原始结果与追加式人工历史，且存在两种以上影响显著的建模方案需要人工选择。

## 12. 设计阶段验收标准

- README、DESIGN、DEVELOPMENT 职责清楚且内容一致；
- 页面、状态、风险、API、数据库和输出均有独立规格；
- 577 条分析、高风险优先复核和中低风险可继续复核被完整表达；
- 系统结果、人工结果和正式输出版本边界清楚；
- 部分失败、失败项重跑、重开和追加式审计有明确行为；
- 普通界面只出现业务语言；
- 编码实施计划具有精确文件、依赖、测试和提交边界；
- 未修改业务代码、数据库迁移、API 或前端页面；
- 最终停在人工审批点。
