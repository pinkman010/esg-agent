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

`0009_active_analysis_run_gate` 增加唯一索引 `uq_analysis_runs_one_active_per_report`，键为 `report_id`，条件为 `status IN ('pending', 'running')`。该索引只限制 active run，不删除或合并任何历史终态 run；repository 把该索引的竞态冲突转换为 `analysis_already_running`。

### `recommendations`

保留为系统建议来源，不直接作为可管理整改任务。增加可选 `assessment_id` 外键，便于迁移为 action。

### `document_pages` / `document_chunks`

本轮不改字段和约束。保存语义改为以 report 为单位在单一事务内先删除旧 pages/chunks、flush 后写入新解析产物；任一步失败整体 rollback，支持同一报告安全重新分析。

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
| `evidence_status` | nullable VARCHAR(32) |
| `applicability_status` | nullable VARCHAR(32) |
| `trigger_event` | VARCHAR(64) |
| `calculated_at` | TIMESTAMPTZ |

只追加。系统 assessment 初次计算时 snapshot_id 为空；人工操作后指向新 snapshot。risk-v2.1 中 `risk_level` 兼容承载复核优先级，API 另提供 `review_priority` 别名。`evidence_status` 和 `applicability_status` 只对新 risk-v2.1 风险快照强制写入；risk-v1 历史行保持 `NULL`，避免把未知历史状态误标成缺失或待判定。索引：`(assessment_id, calculated_at DESC)`、`(risk_level)`、`(evidence_status)`、`(applicability_status)`。

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
| `reviewed_applicability_status` | nullable VARCHAR(32) |
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
effective_review_priority = latest assessment_risk risk_level
effective_evidence_status = latest assessment_risk evidence_status
effective_applicability_status = latest assessment_risk applicability_status
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
6. 为 `analysis_runs(report_id)` 增加 active 状态部分唯一索引；
7. 为风险快照和人工快照增加 risk-v2.1 三个 nullable 维度字段；
8. 回填现有 report/run 默认状态和版本；
9. 将现有 review_decisions 转为 review snapshot，保留原表；
10. 切换 API 写路径；
11. 新写路径启用后，将旧 `review_decisions` 标记 deprecated，并开始两个连续阶段验收周期；每轮验证历史记录映射、只读查询和新旧结果一致性；
12. 两轮均通过且备份、行数、主键关联和字段映射一致后，在独立 Alembic revision 中清理旧表。任一检查失败时停止清理并保留旧表。

每步独立 Alembic revision，支持前滚和结构回滚。包含数据回填的 revision 在 downgrade 时不得静默丢失人工记录，应阻止 downgrade 并提示先导出备份。

## 7. 兼容周期定义

- 兼容周期从替代表或替代写路径实际启用开始计算，不从设计批准或 migration 文件创建开始计算。
- 一个周期对应一个后续阶段的完整自动验收，包括 migration、repository、API 和历史数据一致性测试。
- `review_snapshots` 在阶段 4 启用后，阶段 5 和阶段 6 可作为两个连续兼容周期；均通过后，最早在阶段 7 执行独立清理。
- 清理前必须生成数据库备份或可复现导出，并验证旧记录全部映射到新快照；发现无法映射记录属于停止条件。

## 8. 当前实施状态

截至 2026-07-18，代码 migration head 为 `0010_risk_v2_dimensions`。`0010` 只为 `assessment_risks` 增加 `evidence_status`、`applicability_status`，为 `review_snapshots` 增加 `reviewed_applicability_status`，并增加必要索引；不回填历史数据，不删除或重命名旧列。`downgrade()` 只删除新增索引和三列，因此会丢失升级后写入的 risk-v2.1 维度与人工适用性判断；存在此类记录时应先导出审计数据，生产验收期间不执行 downgrade。新写路径继续使用 `review_snapshots` 和 `review_change_events`，风险、整改和输出分别写入独立表。

demo 在线重置不新增业务表：同一事务内先删除 `audit_events`，再删除 `reports` 根记录并依赖外键 cascade 清理报告、run、assessment、复核、整改和输出数据。该路径只允许 `esg_agent_demo`；`esg_agent` 不提供清理入口。

旧 `review_decisions` 已完成阶段 5、阶段 6 两个连续兼容周期，3 条旧记录与 3 条 `legacy_import` snapshot 映射一致。由于旧 API、旧前端工作台和旧导出仍有调用者，尚未满足清理条件，旧表继续保留。后续清理必须先迁移调用者，再使用独立 Alembic revision 验证 upgrade/downgrade。
