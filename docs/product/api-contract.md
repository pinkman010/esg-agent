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

标准错误：

```json
{
  "code": "report_not_ready",
  "message": "报告信息尚未确认",
  "details": {},
  "request_id": "request-id"
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
  "total_units": 577,
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
  "risk_reason_codes": ["direct_disclosure_evidence"],
  "review_status": "pending_review",
  "evidence_count": 1,
  "source_pdf_pages": [6],
  "action_status": null
}
```

### 2.4 AssessmentDetail

在 `AssessmentListItem` 基础上增加：requirement 原文、system rationale、system missing items、evidence items、最新 review snapshot、review history 摘要、recommendation 和 risk rule version。

EvidenceItem 对普通界面只返回：`evidence_id`、`source_pdf_page`、`source_report_page`、`page_label`、`evidence_preview`、`source_method`、`quality_flags`、`bbox`。内部 route metadata 不进入该 DTO。

### 2.5 ReviewSnapshot

```json
{
  "snapshot_id": "snapshot-id",
  "assessment_id": "assessment-id",
  "sequence": 2,
  "operation_type": "modify",
  "reviewer_name": "张三",
  "reviewed_verdict": "partially_disclosed",
  "evidence_pages": [31],
  "evidence_preview": "人工确认后的证据片段",
  "rationale": "人工判断依据",
  "missing_items": ["新供应商百分比"],
  "reviewer_note": "修正证据范围",
  "reason_code": "evidence_scope_corrected",
  "previous_snapshot_id": "snapshot-1",
  "is_batch_operation": false,
  "created_at": "2026-07-11T00:00:00Z"
}
```

## 3. 报告接口

### `GET /api/reports`

当前查询：`page`、`page_size`、`status`。返回分页 `ReportSummary`。`year`、`search`、`sort` 为后续增强。

### `POST /api/reports/upload`

multipart 上传 PDF。返回 `report_id`、文件信息、`status=uploaded`。相同文件哈希已存在时返回 409 和现有 report id，不静默重复创建。

当前前端尚未把该结构化 409 转换为“打开已有报告”提示，人工验收时按已知体验风险处理。

### `GET /api/reports/{report_id}`

返回报告详情、自动识别 metadata 和确认状态。最新 run 通过 run/dashboard 接口获取。

### `GET /api/reports/{report_id}/file`

返回已上传的 PDF 文件，用于证据查看器。

### `POST /api/reports/{report_id}/confirm-metadata`

请求：

```json
{
  "company_name": "企业名称",
  "report_year": 2024,
  "language": "zh-CN"
}
```

当前行为：写入确认后的企业、年度、语言和确认时间，并生成审计事件。

### `POST /api/reports/{report_id}/analyze`

请求保留 `confirm_llm`、`enable_ocr`、`ocr_pages`。报告 metadata 未确认返回 409。当前尚未实现同一报告 running run 的并发启动门禁，该项列入验收风险。

### `POST /api/reports/{report_id}/reopen`（规划中，MVP 当前未实现）

请求：`reviewer_name`、`reason`。两者必填。返回新报告状态和审计事件。

## 4. Run 与进度接口

### `GET /api/runs/{run_id}`

返回 run 状态、引擎版本、风险规则版本、成功/失败 requirement 数和错误摘要。

### `GET /api/runs/{run_id}/stages`

返回七个 `AnalysisStage`，固定顺序。

### `POST /api/runs/{run_id}/retry-failed`

只允许 partially_completed/failed run。请求包含 `reason`，创建新 run 并保存 `parent_run_id` 和待重跑 requirement ids。没有失败项返回 409。

## 5. 仪表盘与 assessment 接口

### `GET /api/reports/{report_id}/dashboard`

当前返回 report/run id、结论分布、风险分布、高风险复核进度和失败项数。GRI 主题分布、整改摘要和最新输出为后续增强。

### `GET /api/reports/{report_id}/assessments`

当前查询：`page`、`page_size`、`risk_level`。`gri_topic`、verdict、review/evidence/action status、`search`、`sort` 为后续增强。

返回分页 `AssessmentListItem`。默认按 requirement 自然顺序；风险队列使用专用接口。

### `GET /api/reports/{report_id}/assessments/{assessment_id}`

返回 `AssessmentDetail`。assessment 必须属于 report，否则返回 404。

## 6. 人工复核接口

### `GET /api/reports/{report_id}/review-queue`

默认 `risk_level=high&review_status=pending_review`。排序固定为分析失败、无证据、证据质量、unknown、充分性冲突、其他高风险。

### `POST /api/assessments/{assessment_id}/review-decisions`

请求：

```json
{
  "operation_type": "approve",
  "reviewer_name": "张三",
  "reason_code": "system_result_confirmed",
  "reviewer_note": "",
  "reviewed_verdict": null,
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

当前允许修改状态、负责人和完成说明。完成、取消、重开必须填写备注；截止日期修改为后续增强。

## 8. 输出接口

### `GET /api/reports/{report_id}/exports`

返回版本列表、状态、格式、复核范围、文件清单和生成时间。

### `POST /api/reports/{report_id}/exports/draft`

当前已验证格式：`assessment_xlsx`、`management_pdf`、`print_html`。允许任意复核进度，输出带草稿标识。`actions_xlsx` 的完整整改任务字段导出尚未完成，不作为当前可交付格式。

### `POST /api/reports/{report_id}/exports/formal`

高风险未全部完成时返回：

```json
{
  "code": "high_risk_review_incomplete",
  "message": "仍有高风险条目未完成复核",
  "details": {"remaining": 12}
}
```

成功后生成不可变版本号和文件清单。

### `GET /api/exports/{export_id}`（规划中，MVP 当前未实现）

返回版本 metadata。文件下载使用 `GET /api/exports/{export_id}/files/{file_id}`。

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
