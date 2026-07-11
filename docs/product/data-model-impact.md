# 数据模型影响与迁移设计

## 1. 设计结论

保留现有系统 assessment/evidence 表作为不可变分析结果。人工结果、风险、阶段、整改和输出使用独立表。现有 `review_decisions` 在迁移期保留只读兼容，新写操作切换到 `review_snapshots` 和 `review_change_events`。

## 2. 现有表扩展

### `reports`

新增：

- `company_name VARCHAR(255)`；
- `report_year INTEGER`；
- `language VARCHAR(32)`；
- `status VARCHAR(32) NOT NULL DEFAULT 'uploaded'`；
- `metadata_detected JSONB NOT NULL DEFAULT '{}'`；
- `metadata_confirmed_at TIMESTAMPTZ`；
- `updated_at TIMESTAMPTZ NOT NULL`；
- `reopened_at TIMESTAMPTZ`；
- `reopen_reason TEXT`。

约束：report_year 在 1900-2100；ready_for_analysis 后 company/year/language 非空。文件哈希保留索引，产品层对重复上传返回冲突。

### `analysis_runs`

新增：

- `parent_run_id`，自引用；
- `engine_version VARCHAR(64)`；
- `risk_rule_version VARCHAR(64)`；
- `eligible_requirement_count INTEGER NOT NULL DEFAULT 577`；
- `succeeded_requirement_count INTEGER NOT NULL DEFAULT 0`；
- `failed_requirement_count INTEGER NOT NULL DEFAULT 0`；
- `failure_summary JSONB NOT NULL DEFAULT '{}'`。

RunStatus 扩展 `partially_completed`。父 run 用于失败项重跑，不覆盖旧 run。

### `recommendations`

保留为系统建议来源，不直接作为可管理整改任务。增加可选 `assessment_id` 外键，便于迁移为 action。

## 3. 新表

### `analysis_stage_events`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `stage_event_id` | BIGSERIAL PK | 事件 id |
| `run_id` | FK | 所属 run |
| `stage_code` | VARCHAR(64) | 七阶段代码 |
| `status` | VARCHAR(32) | 阶段状态 |
| `completed_units` | INTEGER | 完成量 |
| `total_units` | INTEGER | 总量 |
| `error_summary` | TEXT | 业务错误摘要 |
| `created_at` | TIMESTAMPTZ | 事件时间 |

只追加。当前阶段状态通过每个 stage 最新事件计算。索引：`(run_id, stage_code, created_at DESC)`。

### `assessment_risks`

| 字段 | 类型 |
| --- | --- |
| `risk_id` | VARCHAR(64) PK |
| `assessment_id` | FK |
| `snapshot_id` | nullable FK |
| `risk_level` | VARCHAR(16) |
| `reason_codes` | JSONB |
| `risk_rule_version` | VARCHAR(64) |
| `trigger_event` | VARCHAR(64) |
| `calculated_at` | TIMESTAMPTZ |

只追加。系统 assessment 初次计算时 snapshot_id 为空；人工操作后指向新 snapshot。索引：`(assessment_id, calculated_at DESC)`、`(risk_level)`。

### `review_snapshots`

| 字段 | 类型 |
| --- | --- |
| `snapshot_id` | VARCHAR(64) PK |
| `assessment_id` | FK |
| `run_id` | FK |
| `sequence` | INTEGER |
| `previous_snapshot_id` | nullable self FK |
| `operation_type` | VARCHAR(32) |
| `reviewer_name` | VARCHAR(128) |
| `reason_code` | VARCHAR(64) |
| `reviewer_note` | TEXT |
| `reviewed_verdict` | VARCHAR(64) |
| `evidence_pages` | JSONB |
| `evidence_preview` | TEXT |
| `rationale` | TEXT |
| `missing_items` | JSONB |
| `is_batch_operation` | BOOLEAN |
| `batch_id` | nullable VARCHAR(64) |
| `created_at` | TIMESTAMPTZ |

唯一约束：`(assessment_id, sequence)`。previous snapshot 必须属于同一 assessment。记录不可更新和删除。

### `review_change_events`

字段：`change_event_id`、`snapshot_id`、`field_name`、`old_value JSONB`、`new_value JSONB`、`created_at`。每个发生变化的业务字段一行。索引：`snapshot_id`。

### `improvement_actions`

字段：`action_id`、`report_id`、`assessment_id`、`title`、`priority`、`status`、`owner_name`、`due_date`、`recommendation_text`、`completion_note`、`created_by`、`created_at`、`updated_at`。

状态转换写入 audit event。第一版 owner_name 是文本，不关联用户表。

### `export_versions`

字段：

- `export_id` PK；
- `report_id` FK；
- `run_id` FK；
- `version_number INTEGER`；
- `status`；
- `is_draft`；
- `file_hash`；
- `engine_version`；
- `risk_rule_version`；
- `requirement_version`；
- `review_scope JSONB`；
- `file_manifest JSONB`；
- `supersedes_export_id`；
- `created_by`；
- `created_at`。

正式版本唯一约束：`(report_id, version_number)`。文件 manifest 只保存派生文件路径、格式、哈希和大小；原始报告不复制或覆盖。

## 4. 当前有效结果视图

建议 repository 查询层提供逻辑视图，不创建可写数据库 view：

```text
effective_verdict = latest review snapshot reviewed_verdict ?? assessment.verdict
effective_evidence = latest snapshot evidence override ?? assessment evidence
effective_risk = latest assessment_risk
effective_review_status = latest snapshot operation-derived status ?? pending_review
```

API 只通过 repository/service 组装该视图，避免前端合并历史。

## 5. 追加式约束

- `assessments`、`evidence_items`、`analysis_stage_events`、`assessment_risks`、`review_snapshots`、`review_change_events` 和 `export_versions` 不提供 update/delete repository 方法；
- 更正通过追加新记录；
- 允许 GDPR 或运维删除的场景不属于第一版产品接口；
- 数据库角色权限优化留到多用户阶段。

## 6. 迁移顺序

1. 扩展 reports 和 analysis_runs 枚举兼容字段；
2. 创建 analysis_stage_events 和 assessment_risks；
3. 创建 review_snapshots 和 review_change_events；
4. 创建 improvement_actions；
5. 创建 export_versions；
6. 回填现有 report/run 默认状态和版本；
7. 将现有 review_decisions 转为 review snapshot，保留原表；
8. 切换 API 写路径；
9. 新写路径启用后，将旧 `review_decisions` 标记 deprecated，并开始两个连续切片验收周期；每轮验证历史记录映射、只读查询和新旧结果一致性；
10. 两轮均通过且备份、行数、主键关联和字段映射一致后，在独立 Alembic revision 中清理旧表。任一检查失败时停止清理并保留旧表。

每步独立 Alembic revision，支持前滚和结构回滚。包含数据回填的 revision 在 downgrade 时不得静默丢失人工记录，应阻止 downgrade 并提示先导出备份。

## 7. 兼容周期定义

- 兼容周期从替代表或替代写路径实际启用开始计算，不从设计批准或 migration 文件创建开始计算。
- 一个周期对应一个后续切片的完整自动验收，包括 migration、repository、API 和历史数据一致性测试。
- `review_snapshots` 在切片 4 启用后，切片 5 和切片 6 可作为两个连续兼容周期；均通过后，最早在切片 7 执行独立清理。
- 清理前必须生成数据库备份或可复现导出，并验证旧记录全部映射到新快照；发现无法映射记录属于停止条件。

## 8. 尚未实施

本文件是设计输入。人工批准前：

- 不修改 `backend/src/db/models.py`；
- 不修改 repository；
- 不创建 Alembic revision；
- 不更新 OpenAPI；
- 不回填本地数据库。
