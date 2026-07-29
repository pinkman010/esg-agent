# API 数据契约

## 1. 通用约定

- API 前缀：`/api`；
- JSON 字段使用 snake_case；
- 时间使用 ISO 8601 UTC；
- 分页参数：`page` 从 1 开始，`page_size` 默认 50、最大 100；
- 分页响应：`items`、`page`、`page_size`、`total`；
- 写操作返回最新资源和 `audit_event_id`；
- 冲突返回 409，字段校验返回 422，正式输出门槛未满足返回 409；
- 客户端通过 OpenAPI 生成 TypeScript 类型，不手写重复 DTO。

接口状态标记：未特别标注的接口已进入当前 OpenAPI；标题包含“规划中”的接口尚未实现，不得作为 MVP 验收前提。后端 `/openapi.json` 是运行时契约唯一事实源。

当前 FastAPI 结构化业务错误：

```json
{
  "detail": {
    "code": "report_not_ready",
    "message": "报告信息尚未确认"
  }
}
```

## 2. 核心 DTO

### 2.1 ReportSummary

```json
{
  "report_id": "report-id",
  "company_name": "企业名称",
  "report_year": 2024,
  "language": "zh-CN",
  "original_filename": "report.pdf",
  "page_count": 78,
  "status": "analysis_completed",
  "latest_run_id": "run-id",
  "high_risk_total": 120,
  "high_risk_reviewed": 20,
  "latest_formal_export_version": null,
  "created_at": "2026-07-11T00:00:00Z",
  "updated_at": "2026-07-11T00:00:00Z"
}
```

### 2.2 AnalysisStage

```json
{
  "stage_code": "evidence_assessment",
  "status": "running",
  "completed_units": 240,
  "total_units": 499,
  "error_summary": null,
  "started_at": "2026-07-11T00:00:00Z",
  "completed_at": null
}
```

### 2.3 AssessmentListItem

```json
{
  "assessment_id": "assessment-id",
  "requirement_id": "GRI 2-1-a",
  "requirement_name_zh": "组织法定名称",
  "gri_topic": "GRI 2",
  "system_verdict": "disclosed",
  "reviewed_verdict": null,
  "effective_verdict": "disclosed",
  "risk_level": "low",
  "review_priority": "low",
  "evidence_status": "valid",
  "applicability_status": "applicable",
  "risk_reason_codes": ["direct_disclosure_evidence"],
  "review_status": "pending_review",
  "evidence_count": 1,
  "source_pdf_pages": [6],
  "action_status": null
}
```

### 2.4 AssessmentDetail

在 `AssessmentListItem` 基础上增加：`source_requirement_text`、`effective_requirement_text`、`context_requirement_ids`、`structure_status`、原始规则字段 `system_rationale` / `system_missing_items` 及中文展示字段、当前有效 `rationale` / `missing_items` 及中文展示字段、evidence items、最新 snapshot id 和 `latest_ai_suggestion`。规则字段不随人工 snapshot 改变；当前有效字段允许反映最新人工结果。`risk_level` 为旧调用者保留，risk-v2.1 中与 `review_priority` 值相同。

EvidenceItem 对普通界面只返回：`evidence_id`、`source_pdf_page`、`source_report_page`、`page_label`、`evidence_preview`、`source_method`、`quality_flags`、`bbox`。内部 route metadata 不进入该 DTO。

`latest_ai_suggestion` 为追加式辅助结果，字段包括 `status`、provider/model、Prompt 版本、输入哈希、建议 verdict、中文依据、缺失项、证据 ID/页码、置信度、guardrail、usage、重试与错误。该对象没有可写的人工复核状态或适用性字段；`failed/skipped` 结果同样保留，前端不得把 AI 建议当作有效人工结论。

### 2.5 ReviewSnapshot

```json
{
  "snapshot_id": "snapshot-id",
  "assessment_id": "assessment-id",
  "sequence": 2,
  "operation_type": "modify",
  "reviewer_name": "张三",
  "reviewed_verdict": "partially_disclosed",
  "reviewed_applicability_status": "applicable",
  "evidence_pages": [31],
  "evidence_preview": "人工确认后的证据片段",
  "rationale": "人工判断依据",
  "missing_items": ["新供应商百分比"],
  "reviewer_note": "修正证据范围",
  "reason_code": "evidence_scope_corrected",
  "previous_snapshot_id": "snapshot-1",
  "is_batch_operation": false,
  "batch_id": null,
  "created_at": "2026-07-11T00:00:00Z"
}
```

### 2.6 RequirementScopeItem

完整产品范围行：

```json
{
  "requirement_id": "GRI 2-1",
  "gri_topic": "GRI 2",
  "unit_status": "context_incorporated",
  "source_requirement_text": "原始标准文本",
  "effective_requirement_text": "纳入相关独立判断的上下文文本",
  "component_requirement_ids": [],
  "incorporated_into_requirement_ids": ["GRI 2-1-a"],
  "assessment_id": null,
  "effective_verdict": null,
  "review_priority": null,
  "review_status": null,
  "applicability_status": null,
  "source_pdf_pages": []
}
```

`unit_status` 只有 `assessed | context_incorporated`。上下文行的 assessment、结论、优先级、复核状态和证据页必须为空。

## 3. 报告接口

### `GET /api/reports`

当前查询：`page`、`page_size`、`status`。返回分页 `ReportSummary`。`year`、`search`、`sort` 为后续增强。

### `POST /api/reports/upload`

multipart 上传 PDF。查询参数 `duplicate_policy` 取值为 `reject | create_new`，默认 `reject`。返回 `report_id`、文件信息、`status=uploaded`。

- `reject`：相同文件哈希已存在时返回 409 和最新 report id，不静默重复创建；同一哈希存在多份历史时按 `created_at DESC, report_id DESC` 选择；
- `create_new`：仅在用户明确选择“重新上传并分析”后使用，创建新的 `report_id` 和独立分析生命周期，保留已有报告；新旧报告允许拥有相同 `file_hash`。

`409 duplicate_report` 响应：

```json
{
  "detail": {
    "code": "duplicate_report",
    "message": "相同报告已存在",
    "report_id": "report-existing",
    "existing_report_status": "analysis_completed",
    "can_start_new_demo": true
  }
}
```

`can_start_new_demo` 为现有客户端兼容字段，仅表示后端配置和实际数据库连接是否通过 demo reset 安全校验。当前前端不依赖该字段决定是否允许 `create_new`。

前端提供“查看已有结果”和“重新上传并分析”两条路径；后者显式使用 `duplicate_policy=create_new`，直接创建新报告，不调用 demo reset。

### `GET /api/reports/{report_id}`

返回报告详情、自动识别 metadata 和确认状态。最新 run 通过 run/dashboard 接口获取。

### `GET /api/reports/{report_id}/file`

返回已上传的 PDF 文件，用于证据查看器。

### `GET /api/reports/{report_id}/pages/{page_number}/image`

返回指定 PDF 页的只读 PNG 预览，用于三栏工作台内联显示。`page_number` 从 1 开始；报告、文件或页码不存在时返回 404。响应允许 `private, max-age=3600` 缓存，不修改原始 PDF，也不触发 OCR、VLM 或外部模型。

### `POST /api/reports/{report_id}/confirm-metadata`

请求：

```json
{
  "company_name": "企业名称",
  "report_year": 2024,
  "language": "zh-CN"
}
```

只允许报告处于 `uploaded`、`metadata_detected`、`awaiting_confirmation` 或 `ready_for_analysis` 时写入；进入分析流程后的任何状态返回 `409`，`detail.code=report_metadata_locked`。成功时写入确认后的企业、年度、语言、确认时间和审计事件。

### `POST /api/reports/{report_id}/analyze`

请求保留 `confirm_llm`、`enable_ocr`、`ocr_pages`。`confirm_llm` 默认 false；只有用户明确授权后才能传 true。报告必须处于 `ready_for_analysis`；否则返回 `409 report_not_ready`。同一报告已有 `pending/running` run 时返回 `409 analysis_already_running` 和已有 `run_id`，并发竞态由 `0009` 数据库部分唯一索引兜底。成功响应为新建的 `pending` run；后台任务只接收 ID 并使用独立数据库 session。

### `POST /api/reports/{report_id}/reopen`（规划中，MVP 当前未实现）

请求：`reviewer_name`、`reason`。两者必填。返回新报告状态和审计事件。

## 3.1 演示环境接口

### `POST /api/demo/reset`

维护接口。仅 `APP_ENV=demo`、配置数据库名和 `SELECT current_database()` 均为 `esg_agent_demo`、且运行时目录通过边界校验时可用。普通产品页面不调用；维护人员执行时必须提供精确确认口令：

```json
{
  "confirmation": "RESET_DEMO"
}
```

成功返回：

```json
{
  "cleared_report_count": 1,
  "cleared_runtime_directories": ["uploads", "derived"]
}
```

结构化错误：

- `400 demo_reset_confirmation_invalid`：确认口令不精确；
- `404 demo_reset_unavailable`：环境、配置数据库、实际数据库或目录边界不满足；
- `409 demo_reset_blocked_active_run`：存在 active run，并返回 `run_id`；
- `500 demo_database_cleanup_failed`：数据库事务已回滚；
- `500 demo_runtime_cleanup_failed`：数据库已清空，但运行时文件清理失败，并返回 `cleared_report_count`。

## 4. Run 与进度接口

### `GET /api/runs/{run_id}`

返回 run 状态、引擎版本、风险规则版本、标准单元/独立判断/上下文/方法待确认范围计数、成功/失败 requirement 数、错误摘要和 `ai_summary`。当前 v3 技术计数为 `577/499/78/0`。`ai_summary` 包含 eligible、succeeded、failed、skipped；AI 失败不改变确定性 run 的 completed/partially_completed 判定。

### `GET /api/runs/{run_id}/stages`

返回已产生阶段的最新 `AnalysisStage` 事件，后端和前端顺序均为文件检查、PDF 解析、报告结构、requirement 匹配、证据判断、风险分级、AI 辅助、结果汇总。`confirm_llm=false` 时 AI 阶段为 skipped；尚未产生的阶段不由后端伪造。前端按八阶段权重和真实 units 计算进度，终态强制 100% 且不保留运行转圈。服务启动时遗留的 `pending/running` run 会转为 `failed`。

### `POST /api/runs/{run_id}/retry-failed`

只允许 partially_completed/failed run。请求包含 `reason`，创建新 run 并保存 `parent_run_id` 和待重跑 requirement ids。没有失败项返回 409。

## 5. 仪表盘与 assessment 接口

### `GET /api/reports/{report_id}/dashboard`

当前返回 report/run id、`standard_unit_count`、结论分布、兼容风险分布、复核优先级分布、高优先级复核进度、适用性分布/待判定数量和分析失败项数。普通产品页面使用 `standard_unit_count=577` 作为核查范围。GRI 主题分布、整改摘要和最新输出为后续增强。

### `GET /api/reports/{report_id}/scope-items`

查询参数：`page`、`page_size`、`query`、`unit_status`、`effective_verdict`、`review_priority`、`review_status`、`applicability_status`。返回分页 `RequirementScopeItem`，当前 v3 完整 run 总数固定为 577。搜索覆盖 requirement ID、GRI 主题、原始/有效 requirement 文本和结构关联 ID；组合过滤在分页前执行，`total` 为过滤后的数量。499 个独立判断项的 `unit_status=assessed`，可关联 assessment；78 个上下文项的 `unit_status=context_incorporated`，不生成伪 verdict、priority、review 或 applicability。默认使用 GRI requirement 自然顺序，供完整核查页面和输出服务复用。当前最新 run 缺少任一独立 assessment 时返回 409；部分失败项由 run/dashboard 和正式输出门禁披露，尚不在范围表中伪造失败行。

### `GET /api/reports/{report_id}/assessments`

当前查询：`page`、`page_size`、`review_priority`、兼容别名 `risk_level`、`applicability_status`。两个优先级参数同时提交且值冲突时返回 422。`gri_topic`、verdict、review/evidence/action status、`search`、`sort` 为后续增强。

返回分页 `AssessmentListItem`。默认按 requirement 自然顺序；风险队列使用专用接口。

### `GET /api/reports/{report_id}/assessments/{assessment_id}`

返回 `AssessmentDetail`。assessment 必须属于 report，否则返回 404。v3 新 run 为 499 个独立判断项创建 assessment；78 个上下文项通过范围接口展示且不生成伪 verdict。当前方法待确认项为 0。

## 6. 人工复核接口

### `GET /api/reports/{report_id}/review-queue`

只返回最新 run 中未解决的 `review_priority=high` assessment，先完成全量过滤和真实计数，再分页；排序使用稳定的 requirement 自然顺序。响应为标准分页结构。分析失败且没有 assessment 的项目通过 run 失败统计和正式输出门禁处理，不伪造队列行。

### `GET /api/reports/{report_id}/applicability-queue`

只返回最新 run 中 `applicability_status=undetermined` 的 assessment，先过滤和计数再分页；排序和分页规则与完整核查表一致。该队列不改变 `review_priority`。

### `POST /api/assessments/{assessment_id}/review-decisions`

请求：

```json
{
  "operation_type": "approve",
  "reviewer_name": "张三",
  "reason_code": "system_result_confirmed",
  "reviewer_note": "",
  "reviewed_verdict": null,
  "reviewed_applicability_status": null,
  "evidence_pages": null,
  "evidence_preview": null,
  "rationale": null,
  "missing_items": null
}
```

规则：

- approve 可使用预设原因，备注可空；
- modify 必须提交至少一个修改字段且备注必填；
- invalidate_evidence 备注必填；
- reopen 原因和备注必填；
- 使用 `expected_previous_snapshot_id` 做乐观并发控制，冲突返回 409。

### `POST /api/reports/{report_id}/applicability-decisions`

用于当前页或显式选择项的批量适用性确认，单次最多 100 条。只接受最新 run 中仍为 `undetermined` 的 assessment；任何一条已变化时返回 409，写入前完成全量校验，禁止静默部分成功。

```json
{
  "assessment_ids": ["assessment-1", "assessment-2"],
  "reviewed_applicability_status": "applicable",
  "reviewer_name": "张三",
  "reviewer_note": "本页项目均适用于企业"
}
```

人工批量结果只允许 `applicable` 或 `not_applicable_confirmed`。每条 assessment 追加独立 snapshot，`is_batch_operation=true`，同一请求共享 `batch_id`；响应返回 `batch_id`、`updated_count` 和 assessment ids。

### `POST /api/reports/{report_id}/review-decisions/batch`（规划中，MVP 当前未实现）

请求包含 assessment ids、操作类型、复核人、原因和备注。只允许 approve 或统一字段修改。备注必填。返回成功项、失败项和批量审计 id，不做静默部分成功。

### `GET /api/assessments/{assessment_id}/review-history`

返回按 sequence 倒序的 snapshot 和字段变更，不返回内部 profile/route 信息。

### `POST /api/assessments/{assessment_id}/reopen`（规划中，MVP 当前未实现）

复核人和原因必填。正式输出后的重开同时使报告回到 reopened，并标记现有正式版本待 supersede。

## 7. 整改任务接口

### `GET /api/reports/{report_id}/actions`

当前返回报告下全部整改任务。状态、优先级、GRI 主题和 requirement 筛选为后续增强。

### `POST /api/reports/{report_id}/actions`

请求：标题、来源 assessment、优先级、负责人文本、截止日期、建议和备注。

### `PATCH /api/actions/{action_id}`

当前允许修改状态、负责人、截止日期和完成说明。`due_date` 未提供时保持原值，显式传 `null` 时清空；为兼容旧客户端，`status=null` 按未提供处理并保持原状态。只有实际状态发生变化且进入完成、取消或重开语义时才要求完成说明。响应和审计记录实际变化字段。

## 8. 输出接口

### `GET /api/reports/{report_id}/exports`

返回版本列表、状态、格式、复核范围、文件清单和生成时间。

### `POST /api/reports/{report_id}/exports/draft`

当前支持格式：`assessment_xlsx`、`actions_xlsx`、`management_pdf`、`print_html`。允许任意复核进度，输出带草稿标识。无整改任务时，`actions_xlsx` 仍生成包含免责声明和固定表头的有效工作簿。写入 XLSX 的字符串若以 `= + - @` 开头，会增加文本前缀，避免被表格软件解释为公式。

### `POST /api/reports/{report_id}/exports/formal`

分析失败或结果未完整生成时返回：

```json
{
  "detail": {
    "code": "analysis_incomplete",
    "remaining": 1
  }
}
```

高优先级 assessment 未全部完成复核时返回同样结构，`code=high_risk_review_incomplete`。旧错误码为兼容调用者保留，其业务含义为高复核优先级。

成功后生成不可变版本号和文件清单。`review_scope` 同时记录高/中优先级的总数、已复核/未复核数、适用性待判定数、分析不完整数、独立 assessment 总数和实际人工复核总数，并明确说明高优先级完成不代表 577 个标准核查单元均已人工确认。JSON/CSV/XLSX 导出包含结构字段和最新 AI 建议字段，并注明未经人工确认的 AI 建议不构成最终披露结论。

### `GET /api/exports/{export_id}`（规划中，MVP 当前未实现）

返回版本 metadata。文件下载使用 `GET /api/exports/{export_id}/files/{file_id}`。

### `GET /api/exports/{export_id}/files/{file_id}`

下载 export manifest 中的单个文件。对外 manifest 只返回 `file_id`、`filename`、`format`、`size` 和 `sha256`，不返回服务器 `path` 或 `relative_path`。下载前校验 export/manifest 归属、允许目录边界、文件存在、大小和 SHA256；历史 manifest 通过稳定 legacy `file_id` 兼容。文件不存在返回 404，完整性不一致返回 `409 export_file_integrity_mismatch`，错误响应不包含本机绝对路径。

## 9. 审计接口

### `GET /api/reports/{report_id}/audit`（规划中，MVP 当前未实现）

查询：事件类型、复核人、起止时间和分页。响应只追加排序，不提供更新或删除接口。

当前兼容接口为 `GET /api/audit/runs`，普通产品导航已隐藏旧审计入口。

## 10. OpenAPI 与前端影响

后端 schema 是唯一契约源。实现每个纵向阶段后执行：

```powershell
cd frontend
pnpm generate:api
pnpm typecheck
```

前端 `lib/api.ts` 只封装业务调用，组件不得声明重复 response type。

## 11. 旧 API 兼容窗口

- 替代接口实际上线并被产品调用时，旧接口进入兼容窗口；设计批准、schema 定义或未启用代码不计入起点。
- 兼容窗口持续两个连续阶段验收周期。每个周期都必须执行旧接口自动回归、替代接口契约测试和 OpenAPI 类型生成。
- 两轮均通过后，旧接口可在后续独立清理步骤中移除；移除前必须确认前端、测试、脚本和文档均无调用。
- 任一周期出现行为差异、数据缺失或仍有调用，兼容计数归零，并保留旧接口直至修复后重新完成两轮。
- 清理旧接口不得与新增产品能力混在同一迁移或提交中。
