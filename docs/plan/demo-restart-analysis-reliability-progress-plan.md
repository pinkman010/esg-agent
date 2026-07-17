# 演示重开、分析可靠性与进度语义修复实施计划

> **执行要求：** 使用 `superpowers:subagent-driven-development` 或 `superpowers:executing-plans` 按任务顺序实施；所有代码改动遵循 TDD。保持在 `main`，不新建分支，不回退现有改动，不自动 commit 或 push。真实清理 `esg_agent_demo` 前必须再次取得用户授权。

**目标：** 让同一份远景 2024 中文 ESG 报告能够通过明确的“开始新演示”流程重新上传和分析；重复分析、事务异常或服务重启不能留下永久 `running` run；进度百分比能够反映各阶段实际工作量。

**架构：** 后台分析任务只接收 ID 和分析参数，并在任务内部创建独立数据库会话。报告解析产物按 `report_id` 事务性替换，保证保存幂等；任何异常先 rollback，再写入 failed run、failed stage 和审计事件。数据库用部分唯一索引限制同一报告最多一个 active run。演示环境提供仅 `APP_ENV=demo + esg_agent_demo + demo runtime` 可用的显式逻辑清理接口，前端二次确认后清理并重新上传用户已经选择的 PDF。进度采用固定阶段权重和阶段内部真实完成量，不使用虚假匀速动画。

**技术栈：** FastAPI、SQLAlchemy、PostgreSQL、Alembic、Pydantic、pytest、Next.js、TanStack Query、Vitest、React Testing Library。

---

## 一、已确认故障与实施边界

### 1. 当前故障证据

- 报告：`report-71dd0d1d45d341cdb1ba225a63708d98`；
- 已完成 run：`run-b632e098ba5b41c797c17bb2fdac172a`，保留 577 条 task、577 条 assessment 和 538 条 recommendation；
- 悬挂 run：`run-c72c57060798400b9bc18585c47fa651`，状态为 `running`，只有 `file_validation` 和 `pdf_parsing` 完成事件，task、assessment、recommendation 均为 0；
- 当前数据库已有 78 条 `document_pages` 和 77 条 `document_chunks`；解析器为同一 `report_id` 生成确定性 `chunk_id`，第二次保存会与已有主键冲突；
- `save_pages_and_chunks()` 提交失败后，当前事务没有 rollback，导致失败阶段、失败审计和 run 终态也无法写入；
- `confirm_report_metadata()` 会把已完成报告无条件改回 `ready_for_analysis`；
- 重复上传仍固定返回 `409 duplicate_report`，前端只提供“打开已有报告”；
- 当前进度模型将七阶段等权计算，因此前两个阶段完成后固定显示 14% 和 28%。

### 2. 产品语义

采用以下明确语义：

1. 主环境继续保留文件哈希去重和已有报告结果；
2. 已分析报告不能通过普通 metadata 确认入口直接重新分析；
3. 失败 requirement 继续使用已有 retry API，旧 API 和旧 `review_decisions` 保留；
4. demo 环境的重复上传页面同时提供“查看已有结果”和“开始新演示”；
5. “开始新演示”必须二次确认，清空 demo 业务数据和 demo runtime 后重新上传当前选择的 PDF；
6. 发现 pending/running run 时，在线 demo 清理接口拒绝执行；服务重启时，上一进程遗留的 active run 自动收敛为 failed；
7. 高风险复核完成不得描述为 577 条均已人工确认；
8. 全程不启用外部模型、OCR 或 VLM。

### 3. 进度权重

首版固定权重如下，总和为 100：

| 阶段 | 权重 |
|---|---:|
| `file_validation` | 5 |
| `pdf_parsing` | 10 |
| `report_structure` | 10 |
| `requirement_matching` | 5 |
| `evidence_assessment` | 60 |
| `risk_classification` | 5 |
| `result_summary` | 5 |

running 阶段使用 `completed_units / total_units` 计算该阶段内部进度。终态 `completed` 和 `partially_completed` 显示 100%；failed 保留失败前真实百分比。两分钟无新阶段事件时只显示异常提示，不擅自把 run 改成 failed。

---

## 二、预计文件影响

| 文件 | 操作 | 责任 |
|---|---|---|
| `backend/alembic/versions/0009_active_analysis_run_gate.py` | 新建 | 同一报告 active run 的数据库唯一门禁 |
| `backend/src/db/repositories.py` | 修改 | active run 查询、解析产物幂等替换、rollback 和 demo 数据清理 |
| `backend/src/services/analysis_job.py` | 新建 | 独立 session 的后台任务和启动时中断 run 恢复 |
| `backend/src/services/analysis_runner.py` | 修改 | 保持分析编排入口并返回可靠终态 |
| `backend/src/workflows/single_report_workflow.py` | 修改 | 事务失败先 rollback，再持久化 failed 状态 |
| `backend/src/services/demo_environment.py` | 新建 | demo 在线逻辑清理的安全校验和编排 |
| `backend/src/tools/reset_demo_environment.py` | 修改 | 复用统一 runtime 清理能力，保留离线 drop/create 工具 |
| `backend/src/api/routes/demo.py` | 新建 | demo capabilities 与显式 reset API |
| `backend/src/api/routes/reports.py` | 修改 | duplicate 详情、metadata 生命周期和 analyze 门禁 |
| `backend/src/api/schemas.py` | 修改 | demo reset 请求/响应模型 |
| `backend/src/main.py` | 修改 | 注册 demo router 和启动时 run 恢复 |
| `backend/tests/db/test_repositories.py` | 修改 | 幂等保存、active run 和状态时间测试 |
| `backend/tests/workflows/test_single_report_workflow.py` | 修改 | 重复解析、异常 rollback 和 failed 收敛测试 |
| `backend/tests/services/test_analysis_job.py` | 新建 | 独立会话、兜底失败和启动恢复测试 |
| `backend/tests/services/test_demo_environment.py` | 新建 | demo 清理安全边界和编排测试 |
| `backend/tests/api/test_demo_api.py` | 新建 | 非 demo 拒绝、确认口令和 active run 门禁测试 |
| `backend/tests/api/test_reports_api.py` | 修改 | duplicate 详情、metadata 锁定和并发分析 API 测试 |
| `backend/tests/api/test_product_closure_e2e.py` | 修改 | 新报告完整闭环与生命周期回归 |
| `frontend/components/upload/report-upload-panel.tsx` | 修改 | 查看已有结果、开始新演示和二次确认 |
| `frontend/components/upload/report-upload-panel.test.tsx` | 修改 | demo 重置成功、失败和重新上传测试 |
| `frontend/components/reports/report-metadata-confirmation.tsx` | 修改 | 已分析/分析中报告的只读导航状态 |
| `frontend/components/reports/report-metadata-confirmation.test.tsx` | 修改 | 禁止旧报告从确认页重新启动分析 |
| `frontend/components/analysis/progress-model.ts` | 修改 | 权重进度与 stalled 判断 |
| `frontend/components/analysis/progress-model.test.ts` | 修改 | 权重、单位进度、失败与 stalled 测试 |
| `frontend/components/analysis/analysis-progress.tsx` | 修改 | 新进度、异常提示和失败反馈 |
| `frontend/components/analysis/analysis-progress.test.tsx` | 修改 | 进度显示与长时间无事件提示 |
| `frontend/lib/api.ts` | 修改 | demo capabilities/reset 调用 |
| `frontend/lib/types.ts` | 修改 | 生成类型导出或临时显式类型 |
| `docs/DESIGN.md` | 修改 | 后台任务、run 门禁、demo 在线清理和进度语义 |
| `docs/DEVELOPMENT.md` | 修改 | 新演示操作、恢复路径和验收命令 |
| `docs/product/api-contract.md` | 修改 | duplicate、demo reset 和生命周期 409 契约 |
| `docs/product/data-model-impact.md` | 修改 | `0009` 部分唯一索引影响 |

禁止删除旧 review API、旧 `review_decisions`、原始报告、GRI 标准文件和历史已完成 run。

---

## 三、实施任务

### 任务 1：为同一报告 active run 增加数据库门禁

**文件：**

- 新建：`backend/alembic/versions/0009_active_analysis_run_gate.py`
- 修改：`backend/src/db/repositories.py`
- 修改：`backend/tests/db/test_repositories.py`

- [ ] **步骤 1：先写 active run 查询与冲突测试**

测试建立同一报告的一个 `pending` run 后，第二个 `pending` 或 `running` run 必须失败；已有 `completed`、`partially_completed` 或 `failed` run 不阻塞新 run。

核心断言：

```python
active = repo.get_active_run_for_report("report-1")
assert active.run_id == "run-active"

with pytest.raises(ValueError, match="active analysis run"):
    repo.create_run(AnalysisRun(run_id="run-second", report_id="report-1"))
```

- [ ] **步骤 2：运行测试并确认 RED**

```powershell
cd backend
uv run --no-sync pytest tests/db/test_repositories.py -q --basetemp=../tmp/pytest-active-run-red
```

预期：第二个 active run 仍可创建，新增断言失败。

- [ ] **步骤 3：增加 Alembic 部分唯一索引**

迁移使用 PostgreSQL 条件索引：

```python
op.create_index(
    "uq_analysis_runs_one_active_per_report",
    "analysis_runs",
    ["report_id"],
    unique=True,
    postgresql_where=sa.text("status IN ('pending', 'running')"),
)
```

`downgrade()` 只删除该索引，不改动业务数据。

- [ ] **步骤 4：实现 repository 门禁**

增加：

```python
def get_active_run_for_report(self, report_id: str) -> AnalysisRun | None: ...
```

`create_run()` 捕获该唯一索引的 `IntegrityError` 后必须 rollback，并转换为可识别的 `ValueError("active analysis run already exists")`。不得吞掉其他完整性错误。

- [ ] **步骤 5：补状态时间语义**

`update_run_status()` 在首次进入 `RUNNING` 时写 `started_at`，进入任一终态时写 `completed_at`。重复终态更新不得覆盖原完成时间。

- [ ] **步骤 6：运行 migration 与 repository 测试**

```powershell
cd backend
uv run --no-sync alembic upgrade head
uv run --no-sync pytest tests/db/test_repositories.py -q --basetemp=../tmp/pytest-active-run-green
```

预期：数据库 head 为 `0009_active_analysis_run_gate`，repository 测试全部通过。

### 任务 2：让报告解析产物保存幂等

**文件：**

- 修改：`backend/src/db/repositories.py`
- 修改：`backend/tests/db/test_repositories.py`

- [ ] **步骤 1：写重复保存失败测试**

同一 `report_id` 连续保存两组相同 `chunk_id`，第二次文本改为 `updated text`。测试要求最终只有一页和一个 chunk，内容为第二次结果。

```python
repo.save_pages_and_chunks(first_pages, first_chunks)
repo.save_pages_and_chunks(updated_pages, updated_chunks)

assert session.scalar(select(func.count()).select_from(DocumentPageRecord)) == 1
assert session.scalar(select(func.count()).select_from(DocumentChunkRecord)) == 1
assert session.get(DocumentChunkRecord, "report-1-p1-pdfplumber").text == "updated text"
```

- [ ] **步骤 2：运行测试并确认 RED**

```powershell
cd backend
uv run --no-sync pytest tests/db/test_repositories.py -q --basetemp=../tmp/pytest-document-idempotency-red
```

预期：当前实现因 `document_chunks_pkey` 冲突失败。

- [ ] **步骤 3：实现事务性替换**

`save_pages_and_chunks()` 在同一事务中按 `report_id` 删除已有 `DocumentPageRecord` 和 `DocumentChunkRecord`，执行 `flush()` 后插入新记录，最后只 commit 一次。并发分析由任务 1 的 active run 门禁阻止。

- [ ] **步骤 4：增加失败 rollback 测试**

人为提供非法 chunk 数据触发提交失败，调用显式 `repo.rollback()` 后必须能够继续写 audit event 和更新 run。

- [ ] **步骤 5：运行针对性测试**

```powershell
cd backend
uv run --no-sync pytest tests/db/test_repositories.py -q --basetemp=../tmp/pytest-document-idempotency-green
```

### 任务 3：让工作流异常可靠收敛为 failed

**文件：**

- 修改：`backend/src/workflows/single_report_workflow.py`
- 修改：`backend/tests/workflows/test_single_report_workflow.py`

- [ ] **步骤 1：写保存解析产物异常测试**

构造 repository，使 `save_pages_and_chunks()` 抛出异常并把会话标记为需要 rollback。断言执行顺序包含：

```text
save_pages_and_chunks raises
→ rollback
→ result_summary failed
→ analysis_failed audit
→ run status failed
```

最终断言：

```python
assert result.status is RunStatus.FAILED
assert result.error_message
assert repository.rollback_called is True
assert repository.latest_stage("result_summary").status == "failed"
```

- [ ] **步骤 2：运行测试并确认 RED**

```powershell
cd backend
uv run --no-sync pytest tests/workflows/test_single_report_workflow.py -q --basetemp=../tmp/pytest-workflow-rollback-red
```

- [ ] **步骤 3：实现最小异常收敛**

`SingleReportWorkflow.run()` 的总异常分支先调用 `repository.rollback()`，再追加失败 stage、失败审计并更新 run。若持久化失败状态再次失败，执行第二次 rollback 并把原始异常向上抛出，交给任务 4 的 job wrapper 兜底。

- [ ] **步骤 4：验证已存在解析数据的第二次工作流**

增加同一报告连续运行两次的集成测试。两个 run 都必须进入终态，第二次不得停在 `pdf_parsing` 后。

- [ ] **步骤 5：运行 workflow 测试**

```powershell
cd backend
uv run --no-sync pytest tests/workflows/test_single_report_workflow.py -q --basetemp=../tmp/pytest-workflow-rollback-green
```

### 任务 4：后台任务使用独立 session，并恢复服务重启遗留 run

**文件：**

- 新建：`backend/src/services/analysis_job.py`
- 修改：`backend/src/services/analysis_runner.py`
- 修改：`backend/src/api/routes/reports.py`
- 修改：`backend/src/api/routes/runs.py`
- 修改：`backend/src/main.py`
- 新建：`backend/tests/services/test_analysis_job.py`
- 修改：`backend/tests/api/test_reports_api.py`
- 修改：`backend/tests/api/test_runs_api.py`

- [ ] **步骤 1：写独立会话测试**

测试 route 只把 `report_id`、`run_id` 和显式分析参数交给后台任务，不再传递请求级 `Repository` 或 ORM/领域 report 实例。

计划接口：

```python
def execute_analysis_job(
    *,
    report_id: str,
    run_id: str,
    confirm_llm: bool,
    enable_ocr: bool = False,
    ocr_pages: list[int] | None = None,
    requirement_ids: set[str] | None = None,
) -> None: ...
```

- [ ] **步骤 2：写 job 兜底失败测试**

模拟 `execute_analysis()` 抛出未处理异常。job 必须 rollback，并在同一个独立会话中把 run、`result_summary` 和 report 分别更新为 failed、failed、`analysis_failed`。

- [ ] **步骤 3：写启动恢复测试**

`recover_interrupted_analysis_runs()` 只处理启动前已经存在的 `pending` 和 `running` run，写入固定原因“分析服务重启，任务已中断”。已完成和已失败 run 保持不变。

- [ ] **步骤 4：运行测试并确认 RED**

```powershell
cd backend
uv run --no-sync pytest tests/services/test_analysis_job.py tests/api/test_reports_api.py tests/api/test_runs_api.py -q --basetemp=../tmp/pytest-analysis-job-red
```

- [ ] **步骤 5：实现 job wrapper**

job 内部使用 `SessionLocal()` 创建和关闭会话；从数据库重新读取 report；任何异常先 rollback，再调用统一失败持久化函数。日志不得包含 PDF 正文、密钥或外部服务数据。

- [ ] **步骤 6：接入 route**

报告首次分析和失败项 retry 都改用 `execute_analysis_job`。请求完成后关闭原请求会话，不影响后台任务。

- [ ] **步骤 7：接入 FastAPI lifespan**

`create_app()` 使用 lifespan，在开始接收请求前调用一次 `recover_interrupted_analysis_runs()`。恢复失败阻止应用启动并保留错误日志，不能带着未知 active run 继续服务。

- [ ] **步骤 8：运行针对性测试**

```powershell
cd backend
uv run --no-sync pytest tests/services/test_analysis_job.py tests/api/test_reports_api.py tests/api/test_runs_api.py -q --basetemp=../tmp/pytest-analysis-job-green
```

### 任务 5：锁定 metadata 与分析生命周期

**文件：**

- 修改：`backend/src/db/repositories.py`
- 修改：`backend/src/api/routes/reports.py`
- 修改：`backend/tests/api/test_reports_api.py`
- 修改：`backend/tests/api/test_product_closure_e2e.py`

- [ ] **步骤 1：写已完成报告 metadata 锁定测试**

对 `analysis_completed`、`partially_completed`、`analysis_failed` 和 `analyzing` 报告调用 confirm metadata，预期返回：

```json
{
  "detail": {
    "code": "report_metadata_locked",
    "message": "报告已进入分析流程"
  }
}
```

HTTP 状态为 409。`uploaded` 和 `ready_for_analysis` 仍可确认或更正 metadata。

- [ ] **步骤 2：写 active run API 门禁测试**

同一报告已存在 pending/running run 时再次调用 analyze，返回 409：

```json
{
  "detail": {
    "code": "analysis_already_running",
    "run_id": "run-active"
  }
}
```

- [ ] **步骤 3：运行测试并确认 RED**

```powershell
cd backend
uv run --no-sync pytest tests/api/test_reports_api.py tests/api/test_product_closure_e2e.py -q --basetemp=../tmp/pytest-report-lifecycle-red
```

- [ ] **步骤 4：实现 repository 与 API 门禁**

确认 metadata 前验证当前 report status；创建 run 前查询 active run，并依赖任务 1 的唯一索引处理并发竞态。409 错误必须使用结构化 code，前端不得解析数据库错误文本。

- [ ] **步骤 5：扩展重复上传错误详情**

重复响应增加：

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

`can_start_new_demo` 仅在当前配置通过完整 demo 环境校验时为 true。

- [ ] **步骤 6：运行生命周期测试**

```powershell
cd backend
uv run --no-sync pytest tests/api/test_reports_api.py tests/api/test_product_closure_e2e.py -q --basetemp=../tmp/pytest-report-lifecycle-green
```

### 任务 6：实现仅 demo 可用的在线逻辑清理 API

**文件：**

- 新建：`backend/src/services/demo_environment.py`
- 修改：`backend/src/tools/reset_demo_environment.py`
- 新建：`backend/src/api/routes/demo.py`
- 修改：`backend/src/api/schemas.py`
- 修改：`backend/src/main.py`
- 修改：`backend/src/db/repositories.py`
- 新建：`backend/tests/services/test_demo_environment.py`
- 新建：`backend/tests/api/test_demo_api.py`

- [ ] **步骤 1：写安全边界测试**

以下任一条件不满足时，服务必须在任何数据库或文件写入前失败：

```text
APP_ENV=demo
URL database=esg_agent_demo
SELECT current_database()=esg_agent_demo
UPLOAD_DIR 和 DERIVED_DIR 均位于 backend/data/runtime/demo/ 的子目录
confirmation=RESET_DEMO
不存在 pending/running run
```

- [ ] **步骤 2：写清理编排测试**

用 fake repository 和临时目录验证顺序：

```text
validate config and actual database
→ reject active runs
→ delete audit events and report roots in one transaction
→ commit
→ validate runtime paths again
→ clear upload/derived children
→ return cleared counts
```

数据库清理成功但文件清理失败时返回 500 和结构化 `demo_runtime_cleanup_failed`；数据库保持空，遗留文件保留现场供诊断。

- [ ] **步骤 3：运行测试并确认 RED**

```powershell
cd backend
uv run --no-sync pytest tests/services/test_demo_environment.py tests/api/test_demo_api.py -q --basetemp=../tmp/pytest-demo-reset-api-red
```

- [ ] **步骤 4：抽取统一 runtime 清理函数**

把现有 reparse point、路径解析和只删除目录子项的逻辑移入 `services/demo_environment.py`。离线 `reset_demo_environment` 工具和在线 API 共用该函数，不能复制一套较弱校验。

- [ ] **步骤 5：实现逻辑数据清理**

只删除 demo 业务数据：先删除无外键级联的 audit events，再删除 report roots，让数据库外键级联清除 runs、stages、pages、chunks、assessments、review snapshots、actions 和 exports。GRI 标准资产、migration 表和原始来源资产保持不变。

- [ ] **步骤 6：实现 API**

```http
POST /api/demo/reset
Content-Type: application/json

{"confirmation":"RESET_DEMO"}
```

成功返回报告数和已清理目录，不返回本机绝对路径。非 demo 环境返回 404 或 403；推荐 404，减少主环境暴露面。

- [ ] **步骤 7：运行 demo 服务测试**

```powershell
cd backend
uv run --no-sync pytest tests/services/test_demo_environment.py tests/api/test_demo_api.py tests/tools/test_reset_demo_environment.py tests/config/test_environment_safety.py -q --basetemp=../tmp/pytest-demo-reset-api-green
```

### 任务 7：改造重复上传与 metadata 页面交互

**文件：**

- 修改：`frontend/lib/api.ts`
- 修改：`frontend/lib/types.ts`
- 修改：`frontend/components/upload/report-upload-panel.tsx`
- 修改：`frontend/components/upload/report-upload-panel.test.tsx`
- 修改：`frontend/components/reports/report-metadata-confirmation.tsx`
- 修改：`frontend/components/reports/report-metadata-confirmation.test.tsx`

- [ ] **步骤 1：写 duplicate 两条路径测试**

409 后断言显示：

```text
报告已存在
查看已有结果
开始新演示
```

“查看已有结果”导航到 `/reports/{report_id}/dashboard`，不能再导航到 metadata 确认页。

- [ ] **步骤 2：写二次确认测试**

首次点击“开始新演示”只展示警告：

```text
这会清除演示库中的报告、复核、整改任务和输出版本。
```

只有点击“确认清空并重新上传”才调用 `/api/demo/reset`。reset 成功后自动重新上传当前仍在内存中的 `selectedFile`，再进入新 report 的 metadata 确认页。

- [ ] **步骤 3：写失败状态测试**

覆盖：active run 拒绝清理、reset 网络失败、reset 成功但重新上传失败。错误消息必须说明发生在哪一步，不得显示原始内部枚举或堆栈。

- [ ] **步骤 4：写旧报告确认页锁定测试**

当 report status 为 `analysis_completed` 或 `partially_completed` 时，页面显示“该报告已有分析结果”和查看结果/高风险复核按钮，隐藏“确认报告信息”和“启动分析”。`analyzing` 状态显示“分析正在进行”，同样隐藏两个写按钮。

- [ ] **步骤 5：运行测试并确认 RED**

```powershell
cd frontend
pnpm exec vitest run components/upload/report-upload-panel.test.tsx components/reports/report-metadata-confirmation.test.tsx
```

- [ ] **步骤 6：实现 API 客户端与最小状态机**

增加：

```typescript
export function resetDemoEnvironment(): Promise<DemoResetResponse> {
  return request<DemoResetResponse>("/api/demo/reset", {
    method: "POST",
    body: { confirmation: "RESET_DEMO" },
  });
}
```

上传组件使用独立 reset mutation；禁止把清理和上传压成无法区分失败原因的单一通用错误。

- [ ] **步骤 7：运行组件测试**

```powershell
cd frontend
pnpm exec vitest run components/upload/report-upload-panel.test.tsx components/reports/report-metadata-confirmation.test.tsx
```

### 任务 8：改为权重进度并增加 stalled 提示

**文件：**

- 修改：`frontend/components/analysis/progress-model.ts`
- 修改：`frontend/components/analysis/progress-model.test.ts`
- 修改：`frontend/components/analysis/analysis-progress.tsx`
- 修改：`frontend/components/analysis/analysis-progress.test.tsx`

- [ ] **步骤 1：写权重模型测试**

至少覆盖：

```typescript
expect(progress([completed("file_validation")])).toBe(5);
expect(progress([
  completed("file_validation"),
  completed("pdf_parsing"),
])).toBe(15);
expect(progress([
  completed("file_validation"),
  completed("pdf_parsing"),
  completed("report_structure"),
  completed("requirement_matching"),
  running("evidence_assessment", 288, 577),
])).toBe(59);
```

最后一个期望值按 `30 + floor(60 * 288 / 577)` 计算。所有结果限制在 0—100 且保持单次 run 内单调不下降。

- [ ] **步骤 2：写失败与终态测试**

failed run 保留最后真实百分比；completed 和 partially_completed 强制为 100；缺失阶段不能凭 run 状态伪装成 completed stage。

- [ ] **步骤 3：写 stalled 判断测试**

running run 的最新 stage event 超过 120 秒没有更新时返回 true；pending、failed 和 completed 返回 false；没有有效 `created_at` 时不误报。

- [ ] **步骤 4：运行测试并确认 RED**

```powershell
cd frontend
pnpm exec vitest run components/analysis/progress-model.test.ts components/analysis/analysis-progress.test.tsx
```

- [ ] **步骤 5：实现权重纯函数**

权重定义与计算保持在 `progress-model.ts`，组件只负责显示。不得使用定时伪增长或随机增量。

- [ ] **步骤 6：实现 stalled 提示**

提示文本：

```text
分析进度长时间没有更新，后台任务可能已中断。请返回报告列表查看状态。
```

该提示不改变数据库状态。后台异常的真实终态由任务 3 和任务 4 写入。

- [ ] **步骤 7：运行组件测试**

```powershell
cd frontend
pnpm exec vitest run components/analysis/progress-model.test.ts components/analysis/analysis-progress.test.tsx
```

### 任务 9：同步设计、API 与开发文档

**文件：**

- 修改：`docs/DESIGN.md`
- 修改：`docs/DEVELOPMENT.md`
- 修改：`docs/product/api-contract.md`
- 修改：`docs/product/data-model-impact.md`

- [ ] **步骤 1：更新技术设计唯一源**

记录：独立后台 session、解析产物幂等替换、active run 部分唯一索引、启动恢复、demo 在线逻辑清理和权重进度。

- [ ] **步骤 2：更新 API contract**

明确以下结构化错误：

```text
duplicate_report
report_metadata_locked
analysis_already_running
demo_reset_forbidden
demo_reset_active_run
demo_runtime_cleanup_failed
```

记录 `/api/demo/reset` 请求、响应、环境限制和二次确认要求。

- [ ] **步骤 3：更新 data model impact**

记录 `0009_active_analysis_run_gate` 只增加部分唯一索引，不删除历史 run，不修改 assessment/review/action/export 字段。

- [ ] **步骤 4：更新本地演示手册**

增加两条路径：

```text
普通演示：重复上传 → 开始新演示 → 二次确认 → 自动重新上传
故障恢复：停止服务 → 离线 reset_demo_environment → 重启服务
```

明确在线逻辑清理不能在 active run 存在时执行。

- [ ] **步骤 5：文档边界检查**

```powershell
rg -n "0009_active_analysis_run_gate|/api/demo/reset|analysis_already_running|阶段权重|外部模型|OCR|VLM" docs
```

预期：设计、API、数据模型和开发手册一致；没有本机绝对路径。

### 任务 10：自动回归、当前 demo 恢复和完整产品验收

当前 demo 恢复会删除悬挂 run、旧报告、复核、整改和输出记录，执行真实重置前必须再次取得用户授权。

- [ ] **步骤 1：运行后端针对性测试**

```powershell
cd backend
uv run --no-sync pytest `
  tests/db/test_repositories.py `
  tests/workflows/test_single_report_workflow.py `
  tests/services/test_analysis_job.py `
  tests/services/test_demo_environment.py `
  tests/api/test_demo_api.py `
  tests/api/test_reports_api.py `
  tests/api/test_runs_api.py `
  tests/api/test_product_closure_e2e.py `
  -q --basetemp=../tmp/pytest-analysis-reliability-focused
```

- [ ] **步骤 2：运行后端全量测试**

```powershell
cd backend
uv run --no-sync pytest -q --basetemp=../tmp/pytest-analysis-reliability-full
```

预期：不低于当前 476 项基线，全部通过。

- [ ] **步骤 3：运行前端门禁**

```powershell
cd frontend
pnpm typecheck
pnpm test
pnpm build
```

预期：不低于当前 32 项基线，typecheck、全部测试和 production build 通过。

- [ ] **步骤 4：运行 Envision 577 gate**

使用 `docs/DEVELOPMENT.md` 固定命令和测试库，要求：577 个唯一 eligible requirement、audit `ok=true`、verdict delta 为 0，且没有外部模型、OCR 或 VLM 调用。

- [ ] **步骤 5：停止 demo 服务并执行 dry-run**

```powershell
cd backend
uv run --no-sync python -m src.tools.reset_demo_environment --dry-run
```

预期目标仅包含 `esg_agent_demo` 和 demo runtime。

- [ ] **步骤 6：取得用户确认后执行真实离线重置**

```powershell
cd backend
uv run --no-sync python -m src.tools.reset_demo_environment --confirm-database esg_agent_demo
```

预期：数据库为空并升级到 `0009_active_analysis_run_gate`，demo runtime 为空；主库和原始资产不变。

- [ ] **步骤 7：启动服务并完成第一次全新分析**

```text
空报告列表
→ 上传 Envision Energy 2024-zh.pdf
→ 确认 metadata
→ 启动分析
→ 进度从 5%、15%按权重推进
→ 七阶段进入终态
→ dashboard、三栏复核、完整核查表可访问
```

必须确认 run 生成 577 条 assessment，报告结构阶段不长期停留在等待中。

- [ ] **步骤 8：完成重复上传新演示验收**

```text
再次上传同一 PDF
→ 显示“报告已存在”
→ “查看已有结果”进入 dashboard
→ 返回并选择“开始新演示”
→ 第一次点击只显示风险说明
→ 二次确认后清空 demo 并自动重新上传
→ 获得新的 report_id
→ 再次完成 577 条分析
```

- [ ] **步骤 9：验证并发和失败恢复**

通过自动测试或受控 API 验证：同一报告第二个 active run 返回 409；模拟保存异常后 run 进入 failed；服务重启后遗留 active run 自动进入 failed。禁止在真实远景分析过程中人为终止数据库。

- [ ] **步骤 10：独立 Edge 人工验收**

不使用 Codex 内置浏览器。人工检查上传、metadata、进度、dashboard、高风险三栏、整改任务和版本化输出；PDF 不自动下载；高风险复核完成不表达为 577 条全部人工确认。

---

## 四、停止条件

出现以下任一情况立即停止并请示：

1. `0009` 迁移前发现同一 report 已有两个及以上 pending/running run；
2. demo 在线清理的实际数据库名不是 `esg_agent_demo`；
3. demo runtime 最终解析路径超出 `backend/data/runtime/demo/`；
4. 需要删除或修改旧 `review_decisions`、旧 API、原始报告或标准资产；
5. 需要启用外部模型、OCR 或 VLM；
6. 全量测试或 Envision gate 出现 verdict、source page、quality flag 回退；
7. 真实 demo 重置尚未取得用户当次明确授权；
8. 需要执行 commit、push、破坏性 Git 操作或扩大到主库。

## 五、完成标准

全部满足后才可视为完成：

1. 同一报告最多存在一个 pending/running run，API 竞态由数据库索引兜底；
2. 同一 report 的解析产物可重复保存，不产生 chunk 主键冲突或重复 page；
3. 任意分析异常都能可靠写入 failed run、failed stage、audit 和 report status；
4. 后台任务不持有请求级数据库 session；
5. 服务重启遗留 active run 自动收敛为 failed；
6. 已进入分析流程的报告不能从普通 metadata 页面重新开启；
7. duplicate 页面可以查看已有结果；demo 环境可以二次确认后开始全新演示；
8. demo 在线清理无法作用于主库、测试库或主 runtime，active run 存在时拒绝执行；
9. 进度按固定权重和真实 units 计算，前两个完成阶段显示 5%和 15%，不再显示 14%和 28%；
10. 两次连续的远景全新演示都完成 577 条分析；
11. 后端全量、前端 typecheck/test/build 和 Envision 577 gate 全部通过；
12. 不调用外部模型、OCR 或 VLM；
13. 不删除旧兼容接口，不自动 commit 或 push。

## 六、执行顺序

```text
用户审核本计划
→ 任务 1 active run 数据库门禁
→ 任务 2 解析产物幂等
→ 任务 3 workflow 事务失败收敛
→ 任务 4 独立后台 session 与启动恢复
→ 任务 5 metadata/analyze 生命周期
→ 任务 6 demo 在线逻辑清理 API
→ 任务 7 重复上传和确认页交互
→ 任务 8 权重进度与 stalled 提示
→ 任务 9 文档同步
→ 自动门禁
→ 再次授权后重置当前 demo
→ 两轮远景完整人工验收
```

每个任务先运行失败测试确认 RED，再做最小实现并确认 GREEN。发现阻塞问题先记录复现步骤、严重程度、影响范围和建议修复，再决定是否继续。
