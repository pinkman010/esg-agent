# Phase 1.6 产品闭环补全实施计划

> **For agentic workers:** 只有用户明确批准执行本计划后，才允许使用 `superpowers:executing-plans` 在当前工作区逐项实施。步骤使用复选框跟踪；本文件当前只授权计划编写，不授权代码修改、数据库写入、浏览器业务写入、外部调用、push 或扩大范围。

**目标：** 在一次受控后端解冻中完成安全 export 文件交付、577 项全局搜索与组合筛选、整改截止日期更新和 `actions_xlsx` 整改任务清单导出，补齐产品主闭环后重新冻结 Envision v1.1 后端基线。

**架构：** 保留现有 PostgreSQL 表结构和版本化 export 记录，通过 JSONB manifest 的兼容投影隐藏存储定位信息；新增按 `export_id/file_id` 下载的安全解析层。完整核查搜索在现有 `/scope-items` 结果上先过滤后分页，继续覆盖 `577/499/78/0`。整改任务 PATCH 使用“字段未提供”和“显式 null”可区分的部分更新语义，`actions_xlsx` 复用现有版本化 export 管线。

**技术栈：** Python 3.11、FastAPI、Pydantic v2、SQLAlchemy 2.0、PostgreSQL JSONB、openpyxl、pytest、Next.js、TypeScript、TanStack Query、Vitest、React Testing Library、OpenAPI TypeScript。

**计划状态（2026-07-29）：** 已批准编写，尚未批准执行。当前 `main` 工作区基线在计划编写前保持干净。

---

## 1. 最终范围

### 1.1 本轮必须完成

1. **OBS-001/OBS-002：安全 export 文件交付**
   - 新增 `GET /api/exports/{export_id}/files/{file_id}`。
   - export 列表和生成响应不再暴露服务器绝对路径或内部相对路径。
   - manifest 对外只提供 `file_id`、`filename`、`format`、`size`、`sha256`。
   - 下载时校验 export 归属、manifest 归属、目录边界、文件存在和 SHA256。
   - 兼容已有只含 `format/path/size/sha256` 的历史 manifest。
   - 前端逐文件显示下载入口、格式和大小。

2. **OBS-004：完整 577 项全局搜索和组合筛选**
   - 在 `GET /api/reports/{report_id}/scope-items` 增加查询参数。
   - 搜索覆盖 requirement ID、GRI 主题、原始 requirement 文本和有效 requirement 文本。
   - 筛选覆盖单元类型、有效结论、复核优先级、复核状态和适用性状态。
   - 所有过滤在分页前执行，返回过滤后的 `total`。
   - 499 个独立判断项和 78 个上下文项继续使用同一稳定排序。

3. **OBS-007：整改任务截止日期更新**
   - `UpdateActionRequest` 增加 `due_date`。
   - 支持新增、修改和显式清空截止日期。
   - 同时修正 PATCH 对可空字段“未提供/显式 null”的区分，避免清空请求被静默忽略。
   - 审计记录变更字段和截止日期前后值，不记录内部路径。
   - 前端提供日期输入、保存状态和空值展示。

4. **`actions_xlsx` 整改任务清单导出**
   - Versioned export 支持 `actions_xlsx`。
   - 草稿和正式版本均可包含该文件，继续服从现有正式输出门禁。
   - 无整改任务时生成只有说明和表头的有效工作簿。
   - 工作簿不包含数据库 ID 之外的内部实现字段、服务器路径或密钥。

### 1.2 明确排除

- 不修改 OCR、Ghostscript、Docling、PaddleOCR 或 VLM。
- 不进入 RAG Phase 2，不读取影子向量结果。
- 不修改 DeepSeek 模型、Prompt、参数、候选筛选或 AI 状态。
- 不修改 GRI checklist、`577/499/78/0`、evidence contract、ontology、规则 verdict、risk-v2.1 或人工最终裁决。
- 不新增 Alembic migration，不重建或清空 main/demo 数据库。
- 不实现通用 verdict 批量复核、独立 reopen 或 report 级审计页面。
- 不改变 export 中 assessment、management summary 和 print HTML 的业务结论口径。
- 不调用 SiliconFlow、DeepSeek、OCR 或 VLM。
- 不自动 push。

## 2. 已确认现状与设计决定

### 2.1 Export

- 当前 `VersionedExportService` 支持 `assessment_xlsx`、`management_pdf`、`print_html`。
- 当前 manifest 将 `path.as_posix()` 直接写入 JSONB，并由 `ExportVersion` 原样暴露。
- 当前 repository 没有按 `export_id` 查询单个 export 的方法。
- 当前前端只显示“共 N 个文件”，没有下载入口。
- `docs/product/api-contract.md` 已规划 `GET /api/exports/{export_id}/files/{file_id}`。

本计划采用以下兼容结构：

```json
{
  "file_id": "file-<随机标识>",
  "format": "assessment_xlsx",
  "filename": "assessment_xlsx.xlsx",
  "relative_path": "exports/<report_id>/<export_id>/assessment_xlsx.xlsx",
  "size": 12345,
  "sha256": "<64位十六进制摘要>"
}
```

- `relative_path` 只保存在 JSONB，不进入 API response。
- 新增 API response schema 对 manifest 执行白名单投影。
- 历史 manifest 的 `path` 只在服务内部解析；对外生成稳定的 legacy `file_id`。
- 下载安全不依赖 `file_id` 难猜，必须依赖 export/manifest 归属和目录边界校验。
- 下载前重新计算 SHA256；不一致返回稳定错误，不返回真实路径。

### 2.2 完整核查搜索

- 产品完整核查表读取 `/scope-items`，该接口同时返回独立项和上下文项。
- `/assessments` 只覆盖独立 assessment，不能满足 577 项全范围搜索。
- 当前 `RequirementScopeService.list_items()` 已一次性构造最多 577 条稳定排序结果。
- 本轮继续在内存中对最多 577 条结果过滤，避免引入 SQL/manifest 双源查询和新索引。

新增参数：

```text
query
unit_status
effective_verdict
review_priority
review_status
applicability_status
```

约束：

- `query` 去除首尾空白，长度 1–100；空字符串按未筛选处理。
- 英文使用 `casefold()`，中文按原字符包含匹配。
- `unit_status=context_incorporated` 可返回上下文项。
- `unit_status` 只接受 `assessed/context_incorporated`；`effective_verdict` 使用 `AssessmentVerdict`；`review_priority` 使用 `RiskLevel`；`applicability_status` 使用 `ApplicabilityStatus`。
- `review_status` 只接受 `pending_review/reviewed_approved/reviewed_modified/evidence_invalidated/reopened`。
- verdict、priority、review 和 applicability 筛选自然排除对应字段为空的上下文项。
- 筛选后保持 `_requirement_sort_key()` 顺序。

### 2.3 整改任务 PATCH

- 数据库和领域模型已经存在 `due_date`，无需 migration。
- 当前 `UpdateActionRequest` 缺少 `due_date`。
- 当前 repository 只在值非 `None` 时更新，无法区分字段未提供和显式清空。

本轮使用 Pydantic `model_fields_set` 或 `model_dump(exclude_unset=True)` 传递实际提供字段；repository 仅更新这些字段。`due_date=null` 表示清空，未提供 `due_date` 表示保持原值。

### 2.4 `actions_xlsx`

固定列顺序：

```text
整改任务 ID
Requirement ID
任务标题
优先级
状态
负责人
截止日期
建议内容
完成说明
创建人
创建时间
更新时间
```

第一行写明：

```text
本清单为整改任务跟踪材料；任务状态和截止日期不构成 GRI 认证或外部鉴证结论。
```

## 3. 文件影响图

### 3.1 后端

**修改：**

- `backend/src/api/routes/exports.py`
- `backend/src/api/routes/assessments.py`
- `backend/src/api/routes/actions.py`
- `backend/src/api/schemas.py`
- `backend/src/db/repositories.py`
- `backend/src/services/export_service.py`
- `backend/src/services/requirement_scope_service.py`
- `backend/tests/api/test_exports_api.py`
- `backend/tests/api/test_assessments_api.py`
- `backend/tests/api/test_actions_api.py`
- `backend/tests/api/test_openapi_contract.py`
- `backend/tests/api/test_product_closure_e2e.py`

**不新增：**

- Alembic migration。
- 后台任务表。
- export 文件独立数据库表。

### 3.2 前端

**修改：**

- `frontend/lib/api.ts`
- `frontend/lib/generated/api-types.ts`
- `frontend/components/exports/export-versions.tsx`
- `frontend/components/exports/export-versions.test.tsx`
- `frontend/components/analysis/assessment-table.tsx`
- `frontend/components/analysis/assessment-table.test.tsx`
- `frontend/components/actions/action-list.tsx`
- `frontend/components/actions/action-list.test.tsx`

### 3.3 文档

**修改：**

- `README.md`
- `docs/DESIGN.md`
- `docs/DEVELOPMENT.md`
- `docs/product/api-contract.md`
- `docs/product/phase1.5-product-observation-backlog.md`

**新增：**

- `docs/product/phase1.6-product-closure-acceptance.md`

## 4. 执行任务

### Task 1：记录解冻前基线

**Files：**

- Read: `README.md`
- Read: `docs/DESIGN.md`
- Read: `docs/DEVELOPMENT.md`
- Read: `docs/product/phase1.5-product-observation-backlog.md`

- [ ] **Step 1：确认工作区**

  运行：

  ```powershell
  git status --short --branch
  git rev-parse HEAD
  ```

  预期：工作区没有未分类改动；记录解冻起点 commit。

- [ ] **Step 2：记录当前测试发现数**

  运行：

  ```powershell
  cd backend
  uv run pytest --collect-only -q
  ```

  预期：收集数量不低于已冻结的 709 项；差异必须先解释。

- [ ] **Step 3：运行四个纵向功能的现有目标测试**

  运行：

  ```powershell
  cd backend
  uv run pytest tests/api/test_exports_api.py tests/api/test_assessments_api.py tests/api/test_actions_api.py tests/api/test_product_closure_e2e.py -q
  ```

  运行：

  ```powershell
  cd frontend
  pnpm test -- components/exports/export-versions.test.tsx components/analysis/assessment-table.test.tsx components/actions/action-list.test.tsx
  ```

  预期：现有目标测试全部通过。

### Task 2：先写安全 manifest 和下载 API 失败测试

**Files：**

- Modify: `backend/tests/api/test_exports_api.py`
- Modify: `backend/tests/api/test_openapi_contract.py`

- [ ] **Step 1：写 manifest 脱敏测试**

  新增测试数据生成一个 export，断言：

  ```python
  body = response.json()
  item = body["file_manifest"][0]
  assert set(item) == {
      "file_id",
      "filename",
      "format",
      "size",
      "sha256",
  }
  assert "path" not in item
  assert "relative_path" not in item
  ```

- [ ] **Step 2：写下载成功测试**

  对响应中的 `file_id` 请求：

  ```python
  download = await api_client.get(
      f"/api/exports/{body['export_id']}/files/{item['file_id']}"
  )
  assert download.status_code == 200
  assert download.headers["content-disposition"].startswith("attachment;")
  assert len(download.content) == item["size"]
  assert sha256(download.content).hexdigest() == item["sha256"]
  ```

- [ ] **Step 3：写安全失败测试**

  覆盖：

  - export 不存在返回 404；
  - file_id 不属于 export 返回 404；
  - legacy path 位于允许目录外时拒绝；
  - 文件缺失时返回稳定 404；
  - SHA256 不一致时返回 `409 export_file_integrity_mismatch`；
  - 错误响应不包含 `derived_dir`、绝对路径或文件系统异常全文。

- [ ] **Step 4：写历史 manifest 兼容测试**

  直接保存旧结构：

  ```python
  legacy_manifest = [
      {
          "format": "assessment_xlsx",
          "path": legacy_path.as_posix(),
          "size": legacy_path.stat().st_size,
          "sha256": sha256(legacy_path.read_bytes()).hexdigest(),
      }
  ]
  ```

  列表响应必须投影出安全字段，返回的 legacy `file_id` 可下载同一文件。

- [ ] **Step 5：验证新测试先失败**

  运行：

  ```powershell
  cd backend
  uv run pytest tests/api/test_exports_api.py tests/api/test_openapi_contract.py -q
  ```

  预期：新测试因 response schema、repository lookup 和下载端点尚未实现而失败。

### Task 3：实现安全 manifest 和下载 API

**Files：**

- Modify: `backend/src/api/routes/exports.py`
- Modify: `backend/src/api/schemas.py`
- Modify: `backend/src/db/repositories.py`
- Modify: `backend/src/services/export_service.py`

- [ ] **Step 1：增加对外 schema**

  在 `backend/src/api/schemas.py` 增加：

  ```python
  class ExportFileResponse(BaseModel):
      file_id: str
      filename: str
      format: str
      size: int
      sha256: str


  class ExportVersionResponse(ExportVersion):
      file_manifest: list[ExportFileResponse]
  ```

  export 列表、草稿和正式生成接口统一使用 `ExportVersionResponse`。

- [ ] **Step 2：增加 repository 查询**

  在 `backend/src/db/repositories.py` 增加：

  ```python
  def get_export_version(self, export_id: str) -> ExportVersion | None:
      record = self.session.get(ExportVersionRecord, export_id)
      return self._export_from_record(record) if record is not None else None
  ```

- [ ] **Step 3：写入新 manifest**

  `_write_format()` 返回内部结构：

  ```python
  {
      "file_id": new_id("file"),
      "format": format_name,
      "filename": path.name,
      "relative_path": path.relative_to(self.output_root).as_posix(),
      "size": len(content),
      "sha256": sha256(content).hexdigest(),
  }
  ```

  同一次请求的 `formats` 必须非空且不能重复；无效请求返回 422。

- [ ] **Step 4：增加安全投影和解析**

  在 export service 中增加 `public_export_manifest(export: ExportVersion) -> list[dict[str, object]]` 和 `resolve_export_file(export: ExportVersion, file_id: str, *, output_root: Path) -> ResolvedExportFile` 两个纯函数，并定义只含 `path`、`filename`、`format`、`size`、`sha256` 的冻结 dataclass `ResolvedExportFile`。

  实现要求：

  - 新 manifest 使用 `relative_path`；
  - legacy manifest 使用旧 `path`；
  - legacy `file_id` 由 `export_id`、manifest index、format 和 sha256 计算稳定摘要；
  - `Path.resolve(strict=True)` 后必须位于 `output_root/exports/<report_id>/<export_id>`；
  - 文件名只使用 `Path.name`；
  - 下载前重新计算大小和 SHA256。

- [ ] **Step 5：实现下载路由**

  路由：

  ```text
  GET /api/exports/{export_id}/files/{file_id}
  ```

  响应规则：

  - XLSX：`application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`；
  - PDF：`application/pdf`；
  - HTML：`text/html; charset=utf-8`；
  - `Content-Disposition` 使用 attachment 和安全文件名；
  - 成功后追加 `export_file_downloaded` audit，payload 只含 `export_id`、`file_id`、`format`、`size`、`sha256`。

- [ ] **Step 6：运行目标测试**

  运行：

  ```powershell
  cd backend
  uv run pytest tests/api/test_exports_api.py tests/api/test_openapi_contract.py -q
  ```

  预期：全部通过。

- [ ] **Step 7：提交 export 安全交付后端**

  ```powershell
  git add backend/src/api/routes/exports.py backend/src/api/schemas.py backend/src/db/repositories.py backend/src/services/export_service.py backend/tests/api/test_exports_api.py backend/tests/api/test_openapi_contract.py
  git diff --cached --check
  git commit -m "feat: add secure export file delivery"
  ```

### Task 4：增加 `actions_xlsx`

**Files：**

- Modify: `backend/src/services/export_service.py`
- Modify: `backend/tests/api/test_exports_api.py`
- Modify: `backend/tests/api/test_product_closure_e2e.py`

- [ ] **Step 1：写失败测试**

  覆盖：

  - `formats=["actions_xlsx"]` 返回一个安全 manifest；
  - 下载得到可打开的 XLSX；
  - 第一行是整改清单免责声明；
  - 第二行严格等于第 2.4 节固定列；
  - 有任务时 requirement、负责人、截止日期和状态正确；
  - 无任务时仍有免责声明和表头；
  - 正式输出仍受现有 analysis/high-priority gate 约束。

- [ ] **Step 2：实现 action 行构造**

  新增纯函数 `action_export_rows(actions: list[ImprovementAction], requirement_ids_by_assessment: dict[str, str]) -> list[dict[str, object]]`。export service 先按 action 的 `assessment_id` 查询并构造 requirement ID 映射，再交给纯函数生成行。

  日期使用 ISO `YYYY-MM-DD`，时间使用带时区 ISO 字符串；空值输出空单元格。

- [ ] **Step 3：实现工作簿**

  `supported_formats` 增加 `actions_xlsx`，并把 `GenerateExportRequest.formats` 限定为包含四种正式格式的 `Literal` 列表。生成逻辑读取当前 report 的整改任务，写入免责声明、固定表头和数据行，不改变 assessment export 行。

- [ ] **Step 4：运行 export 目标测试**

  ```powershell
  cd backend
  uv run pytest tests/api/test_exports_api.py tests/api/test_product_closure_e2e.py -q
  ```

  预期：全部通过。

- [ ] **Step 5：提交整改清单导出**

  ```powershell
  git add backend/src/services/export_service.py backend/tests/api/test_exports_api.py backend/tests/api/test_product_closure_e2e.py
  git diff --cached --check
  git commit -m "feat: add improvement action export"
  ```

### Task 5：先写 577 项搜索和筛选失败测试

**Files：**

- Modify: `backend/tests/api/test_assessments_api.py`

- [ ] **Step 1：写 query 搜索测试**

  断言：

  - `query=GRI 2-1` 匹配 requirement ID；
  - 英文 requirement 文本搜索忽略大小写；
  - 中文有效文本使用包含匹配；
  - query 同时覆盖 assessed 和 context item；
  - 无匹配时返回 `items=[]`、`total=0`。

- [ ] **Step 2：写组合筛选测试**

  请求示例：

  ```text
  /api/reports/report-1/scope-items
    ?effective_verdict=unknown
    &review_priority=high
    &review_status=pending_review
    &applicability_status=undetermined
  ```

  断言所有返回项同时满足条件。

- [ ] **Step 3：写过滤后分页测试**

  构造超过一页的匹配项，断言：

  ```python
  assert page_1["total"] == expected_filtered_total
  assert page_1["items"] != page_2["items"]
  assert all(item_matches_filters(item) for item in page_1["items"])
  ```

- [ ] **Step 4：写上下文语义测试**

  `unit_status=context_incorporated` 只返回上下文项；加 verdict 或 applicability 筛选后不产生伪 verdict、伪复核状态或伪适用性。

- [ ] **Step 5：验证新测试先失败**

  ```powershell
  cd backend
  uv run pytest tests/api/test_assessments_api.py -q
  ```

  预期：新测试因 query/filter 参数尚未实现而失败。

### Task 6：实现 577 项搜索和筛选

**Files：**

- Modify: `backend/src/api/routes/assessments.py`
- Modify: `backend/src/api/schemas.py`
- Modify: `backend/src/services/requirement_scope_service.py`
- Modify: `backend/tests/api/test_assessments_api.py`

- [ ] **Step 1：补充 applicability 字段**

  `RequirementScopeItemResponse` 增加：

  ```python
  applicability_status: str | None = None
  ```

  `RequirementScopeService` 对独立项返回 risk 的 applicability；上下文项返回 `None`。

- [ ] **Step 2：增加过滤纯函数**

  在 assessments route 或 scope service 中增加 `filter_scope_items()` 纯函数，参数固定为 `items`、`query`、`unit_status`、`effective_verdict`、`review_priority`、`review_status`、`applicability_status`，返回过滤后的 `list[dict]`。

  先过滤、后调用 `_paginate()`，不得改变原列表排序。

- [ ] **Step 3：限制参数**

  使用 FastAPI/Pydantic 枚举或 Literal 拒绝未知状态；`query` 最大 100 字符。非法值返回 422。

- [ ] **Step 4：运行目标测试**

  ```powershell
  cd backend
  uv run pytest tests/api/test_assessments_api.py tests/api/test_openapi_contract.py -q
  ```

  预期：全部通过。

- [ ] **Step 5：提交范围查询后端**

  ```powershell
  git add backend/src/api/routes/assessments.py backend/src/api/schemas.py backend/src/services/requirement_scope_service.py backend/tests/api/test_assessments_api.py backend/tests/api/test_openapi_contract.py
  git diff --cached --check
  git commit -m "feat: add complete scope search and filters"
  ```

### Task 7：先写截止日期 PATCH 失败测试

**Files：**

- Modify: `backend/tests/api/test_actions_api.py`
- Modify: `backend/tests/db/test_repositories.py`

- [ ] **Step 1：写新增和修改日期测试**

  创建无日期任务，依次 PATCH：

  ```json
  {"due_date": "2026-08-15"}
  ```

  ```json
  {"due_date": "2026-09-01"}
  ```

  断言响应和重新查询结果一致。

- [ ] **Step 2：写显式清空测试**

  PATCH：

  ```json
  {"due_date": null}
  ```

  断言数据库和响应均为 `null`。

- [ ] **Step 3：写未提供字段保持测试**

  只更新 owner 或 status 时，原 due_date 不变。

- [ ] **Step 4：写审计测试**

  断言 `improvement_action_updated` payload 包含：

  ```json
  {
    "action_id": "<action-id>",
    "changed_fields": ["due_date"],
    "old_due_date": "2026-08-15",
    "new_due_date": null
  }
  ```

  audit 关联 assessment 所属 run。

- [ ] **Step 5：写 repository 显式 null 测试**

  直接调用 repository 更新 due_date，覆盖“字段未提供保持原值”和“字段显式为 `None` 清空”两条路径。

- [ ] **Step 6：验证测试先失败**

  ```powershell
  cd backend
  uv run pytest tests/api/test_actions_api.py -q
  ```

  预期：新测试因 request/repository 未支持 due_date 和显式 null 而失败。

### Task 8：实现截止日期 PATCH

**Files：**

- Modify: `backend/src/api/routes/actions.py`
- Modify: `backend/src/db/repositories.py`
- Modify: `backend/tests/api/test_actions_api.py`

- [ ] **Step 1：扩展请求 schema**

  ```python
  class UpdateActionRequest(BaseModel):
      status: ActionStatus | None = None
      owner_name: str | None = None
      due_date: date | None = None
      completion_note: str | None = None
  ```

- [ ] **Step 2：增加单个 action 查询**

  repository 增加 `get_improvement_action(action_id)`，供更新前快照和审计关联使用。

- [ ] **Step 3：实现字段存在性语义**

  route 只把 `request.model_fields_set` 中的字段传给 repository。repository 使用明确 updates 字典更新；允许 `owner_name`、`due_date`、`completion_note` 显式清空。

- [ ] **Step 4：保持状态说明门禁**

  只有请求实际改变 status 且目标状态需要说明时，才要求非空 `completion_note`。单独修改日期不得要求完成说明。

- [ ] **Step 5：写结构化审计**

  audit 记录 `changed_fields`；日期记录前后 ISO 值。状态和负责人继续记录安全业务值，不记录请求全文。

- [ ] **Step 6：运行目标测试**

  ```powershell
  cd backend
  uv run pytest tests/api/test_actions_api.py tests/db/test_repositories.py -q
  ```

  预期：全部通过。

- [ ] **Step 7：提交整改日期后端**

  ```powershell
  git add backend/src/api/routes/actions.py backend/src/db/repositories.py backend/tests/api/test_actions_api.py backend/tests/db/test_repositories.py
  git diff --cached --check
  git commit -m "feat: allow action due date updates"
  ```

### Task 9：同步 OpenAPI 和前端 API

**Files：**

- Modify: `frontend/lib/generated/api-types.ts`
- Modify: `frontend/lib/api.ts`
- Modify: `backend/tests/api/test_openapi_contract.py`

- [ ] **Step 1：加强 OpenAPI 契约测试**

  断言 OpenAPI 包含：

  - export 下载 path；
  - `ExportFileResponse`；
  - scope-items 新查询参数；
  - `UpdateActionRequest.due_date`；
  - `actions_xlsx` 可接受格式。

- [ ] **Step 2：启动本地后端并确认来源**

  在与实施环境一致的配置下启动后端，先请求：

  ```powershell
  Invoke-RestMethod http://localhost:8000/api/health
  ```

  预期：`status=ok`。禁止从旧进程生成类型。

- [ ] **Step 3：重新生成类型**

  ```powershell
  cd frontend
  pnpm generate:api
  ```

  预期：生成文件只出现本轮契约差异。

- [ ] **Step 4：扩展 API client**

  - `listReportScopeItems()` 接受结构化 filters，并使用 `URLSearchParams`。
  - 增加 `exportFileUrl(exportId, fileId)`，只拼接编码后的 API 标识。
  - `generateExport()` formats 增加 `actions_xlsx`。
  - `updateAction()` 使用生成的 `UpdateActionRequest`。

- [ ] **Step 5：运行类型检查**

  ```powershell
  cd frontend
  pnpm typecheck
  ```

  预期：通过。

### Task 10：实现前端 export 文件列表和下载

**Files：**

- Modify: `frontend/components/exports/export-versions.tsx`
- Modify: `frontend/components/exports/export-versions.test.tsx`
- Modify: `frontend/lib/api.ts`

- [ ] **Step 1：写失败测试**

  测试一个 export 含四个文件时：

  - 显示中文格式名称；
  - 显示格式化大小；
  - 每个文件有可访问的下载链接；
  - href 只包含 API endpoint、export_id 和 file_id；
  - DOM 不显示 `path` 或 `relative_path`；
  - 历史 export 投影后的文件同样可下载。

- [ ] **Step 2：实现文件卡片**

  每个 export 下展示文件列表：

  ```text
  GRI 核查表（XLSX）
  管理层摘要（PDF）
  可打印核查表（HTML）
  整改任务清单（XLSX）
  ```

  下载使用普通 `<a>`，保留浏览器下载行为和键盘访问；不把服务器路径传给前端。

- [ ] **Step 3：运行组件测试**

  ```powershell
  cd frontend
  pnpm test -- components/exports/export-versions.test.tsx
  ```

  预期：通过。

- [ ] **Step 4：提交 export 前端**

  ```powershell
  git add frontend/lib/api.ts frontend/lib/generated/api-types.ts frontend/components/exports/export-versions.tsx frontend/components/exports/export-versions.test.tsx
  git diff --cached --check
  git commit -m "feat: expose export file downloads"
  ```

### Task 11：实现完整核查搜索和筛选 UI

**Files：**

- Modify: `frontend/components/analysis/assessment-table.tsx`
- Modify: `frontend/components/analysis/assessment-table.test.tsx`
- Modify: `frontend/lib/api.ts`

- [ ] **Step 1：写失败测试**

  覆盖：

  - 输入关键词并提交后请求包含 `query`；
  - 选择结论、优先级、复核、适用性或单元类型后请求包含对应参数；
  - 任一条件改变时页码重置为 1；
  - “清空筛选”恢复 577 总范围请求；
  - 无结果显示当前筛选无匹配，不显示“暂无 GRI 范围”；
  - 上下文项仍显示“已纳入相关判断”。

- [ ] **Step 2：实现筛选状态**

  使用“输入状态 + 已应用 query”避免每次按键请求；筛选 select 变化即时应用。TanStack Query key 必须包含全部已应用条件。

- [ ] **Step 3：保持分页和访问性**

  - filter 前先 `setPage(1)`；
  - 搜索使用 `<form>`，Enter 可提交；
  - input/select 具有中文 label；
  - loading、error、empty 状态可区分。

- [ ] **Step 4：运行组件测试**

  ```powershell
  cd frontend
  pnpm test -- components/analysis/assessment-table.test.tsx
  ```

  预期：通过。

- [ ] **Step 5：提交搜索筛选前端**

  ```powershell
  git add frontend/lib/api.ts frontend/components/analysis/assessment-table.tsx frontend/components/analysis/assessment-table.test.tsx
  git diff --cached --check
  git commit -m "feat: add complete scope search controls"
  ```

### Task 12：实现整改日期编辑 UI

**Files：**

- Modify: `frontend/components/actions/action-list.tsx`
- Modify: `frontend/components/actions/action-list.test.tsx`

- [ ] **Step 1：写失败测试**

  覆盖：

  - 现有日期进入 `<input type="date">`；
  - 修改日期发送新值；
  - 清空日期发送 `due_date:null`；
  - 未修改日期时 payload 不包含 `due_date`；
  - 只修改日期不要求状态变更说明；
  - 保存成功后刷新 action 列表。

- [ ] **Step 2：实现日期状态**

  `ActionItem` 增加 `dueDate` state 和 `dueDateChanged`。构建 payload 时只发送实际变化字段，避免把未变化的可空字段写回。

- [ ] **Step 3：运行组件测试**

  ```powershell
  cd frontend
  pnpm test -- components/actions/action-list.test.tsx
  ```

  预期：通过。

- [ ] **Step 4：提交整改日期前端**

  ```powershell
  git add frontend/components/actions/action-list.tsx frontend/components/actions/action-list.test.tsx
  git diff --cached --check
  git commit -m "feat: add action due date editing"
  ```

### Task 13：执行纵向闭环测试

**Files：**

- Modify: `backend/tests/api/test_product_closure_e2e.py`

- [ ] **Step 1：扩展产品闭环 E2E**

  单个测试流程覆盖：

  1. 创建报告和完整分析结果；
  2. 创建带截止日期的整改任务；
  3. 搜索完整范围并验证过滤后 total；
  4. 修改和清空截止日期；
  5. 生成包含四种格式的草稿 export；
  6. 下载四个文件并核验大小和 SHA256；
  7. 确认 API 响应不含绝对路径；
  8. 确认 assessment verdict、risk 和 review snapshot 未被上述操作修改。

- [ ] **Step 2：运行后端纵向测试**

  ```powershell
  cd backend
  uv run pytest tests/api/test_product_closure_e2e.py tests/api/test_exports_api.py tests/api/test_assessments_api.py tests/api/test_actions_api.py tests/api/test_openapi_contract.py -q
  ```

  预期：全部通过。

- [ ] **Step 3：运行前端纵向测试**

  ```powershell
  cd frontend
  pnpm test -- components/exports/export-versions.test.tsx components/analysis/assessment-table.test.tsx components/actions/action-list.test.tsx
  ```

  预期：全部通过。

### Task 14：完整门禁与 Envision v3 回归

**Files：**

- Runtime output only: `tmp/`
- Runtime evaluation only: `backend/data/runtime/evaluations/envision_2024/`

- [ ] **Step 1：后端全量和 Ruff**

  ```powershell
  cd backend
  uv run pytest -q --basetemp=../tmp/pytest-phase1-6-full
  uv run ruff check src tests
  ```

  预期：全部通过；新增测试使总数不低于解冻前基线。

- [ ] **Step 2：前端完整门禁**

  ```powershell
  cd frontend
  pnpm test
  pnpm typecheck
  pnpm build
  ```

  预期：全部通过。

- [ ] **Step 3：运行 Envision v3 regeneration gate**

  ```powershell
  cd backend
  uv run --no-sync python -m src.tools.regenerate_review_csv `
    --report-id envision_2024_v3 `
    --pdf "data/reports/Envision Energy 2024-zh.pdf" `
    --profile data/reports/profiles/envision_2024.json `
    --requirements data/manifests/gri_requirement_checklist_v3.json `
    --manual-review-workbook data/review_inputs/envision_2024/manual/envision_2024_577_manual_review_second_review_Pro_20260719.xlsx `
    --final-adjudications data/review_inputs/envision_2024/adjudication/envision_2024_result_adjudication_v1.csv `
    --output data/runtime/evaluations/envision_2024/current_499_review_regenerated.csv `
    --baseline data/review_inputs/envision_2024/baselines/current_577_review_regenerated.csv `
    --audit-output data/runtime/evaluations/envision_2024/current_499_review_regenerated_audit.json `
    --diff-summary-output data/runtime/evaluations/envision_2024/current_499_review_regeneration_diff_summary.json `
    --scope-summary-output data/runtime/evaluations/envision_2024/current_499_review_scope_summary.json `
    --report-total-pages 78
  ```

  通过标准：

  - `577/499/78/0`；
  - global fallback 0；
  - 新增 false disclosed 0；
  - 新增 wrong source page 0；
  - final adjudication pending 0；
  - audit 0 error、0 warning；
  - 不调用外部模型、OCR 或 VLM。

- [ ] **Step 4：执行路径泄露扫描**

  对 OpenAPI、API 测试响应、前端构建产物和新生成 export metadata 搜索 Windows drive path、UNC path 和 `relative_path`。任何面向用户响应中的命中均阻断重新冻结。

### Task 15：Chrome 自动验收

**Files：**

- Read/write only after execution approval: existing demo environment
- Download output: `tmp/phase1.6-downloads/`

- [ ] **Step 1：记录验收前业务表计数**

  记录 reports、runs、stages、assessments、risks、review snapshots、actions、exports 和 audit events。

- [ ] **Step 2：只读验收搜索筛选**

  在完整核查页面验证：

  - requirement ID 搜索；
  - 中文关键词搜索；
  - 独立项/上下文项筛选；
  - 结论、优先级、复核和适用性组合；
  - 清空后恢复 577 项；
  - 分页、键盘操作和空结果文案。

- [ ] **Step 3：验收 export 下载**

  使用已有 export 验证 legacy 下载；经执行阶段再次批准后生成一个 Phase 1.6 草稿，下载四个文件到 `tmp/phase1.6-downloads/`，核对文件名、大小、SHA256、XLSX 可打开和 HTML/PDF 类型。

- [ ] **Step 4：验收整改日期**

  优先使用自动测试环境完成写入验收。需要在 demo 修改现有 action 时，先记录旧值，执行后恢复旧值并保留审计；该 demo 写入需要执行阶段单独说明。

- [ ] **Step 5：检查控制台和数据**

  Chrome console error/warning 为 0。除明确批准的草稿 export、下载审计和日期验收审计外，正式业务表不产生意外变化。

### Task 16：更新文档并重新冻结

**Files：**

- Modify: `README.md`
- Modify: `docs/DESIGN.md`
- Modify: `docs/DEVELOPMENT.md`
- Modify: `docs/product/api-contract.md`
- Modify: `docs/product/phase1.5-product-observation-backlog.md`
- Create: `docs/product/phase1.6-product-closure-acceptance.md`

- [ ] **Step 1：更新 API 和运行说明**

  记录安全 manifest、下载端点、scope filters、due_date PATCH、`actions_xlsx`、历史 export 兼容和已知限制。

- [ ] **Step 2：关闭观察项**

  将 OBS-001、OBS-002、OBS-004、OBS-007 标记为已关闭，附 commit、目标测试、全量门禁和 Chrome 证据。

- [ ] **Step 3：写验收报告**

  报告至少包含：

  - 解冻起点和最终 head；
  - 文件和 API 变更；
  - 无 migration 证明；
  - 后端/前端测试数量；
  - Envision v3 gate；
  - 路径泄露检查；
  - Chrome 下载、搜索和整改日期结果；
  - 外部调用为 0；
  - 剩余延期项。

- [ ] **Step 4：文档检查**

  ```powershell
  git diff --check
  rg -n "[A-Za-z]:\\\\|file://" README.md docs
  ```

  预期：项目文档不包含本机绝对路径，API 文档明确内部 locator 不进入 response。

- [ ] **Step 5：提交重新冻结文档**

  ```powershell
  git add README.md docs/DESIGN.md docs/DEVELOPMENT.md docs/product/api-contract.md docs/product/phase1.5-product-observation-backlog.md docs/product/phase1.6-product-closure-acceptance.md
  git diff --cached --check
  git commit -m "docs: freeze phase 1.6 product closure baseline"
  ```

## 5. Commit 顺序

1. `feat: add secure export file delivery`
2. `feat: add improvement action export`
3. `feat: add complete scope search and filters`
4. `feat: allow action due date updates`
5. `feat: expose export file downloads`
6. `feat: add complete scope search controls`
7. `feat: add action due date editing`
8. `docs: freeze phase 1.6 product closure baseline`

每个 commit 前运行对应目标测试和 `git diff --cached --check`。完整门禁在最终文档 commit 前执行。未经用户批准不 push。

## 6. 重新冻结硬门槛

必须全部满足：

1. 默认分析、`confirm_llm=false`、`enable_ocr=false` 行为不变。
2. 数据库 migration head 不变，仍为 `0012_chunk_embeddings`。
3. 577 个标准单元、499 个独立判断项、78 个上下文项、0 个 method pending。
4. export list/generate/download 响应不含服务器绝对路径和内部 relative path。
5. 历史 export 可以通过安全投影和 legacy file_id 下载。
6. 四种 export 文件可下载并通过大小与 SHA256 校验。
7. 搜索和筛选在分页前执行，清空后恢复 577 项。
8. 上下文项不产生伪 verdict、priority、review 或 applicability。
9. due_date 支持新增、修改、清空和未提供保持。
10. assessment、risk、AI suggestion 和人工 snapshot 不因本轮功能变化。
11. 后端全量测试、Ruff、前端 test/typecheck/build 全部通过。
12. Envision v3 新增 false disclosed、wrong source page、global fallback、audit error、audit warning 均为 0。
13. Chrome console error/warning 为 0。
14. DeepSeek、SiliconFlow、OCR 和 VLM 调用数为 0。
15. 文档记录真实测试数量、commit 和限制后，后端重新冻结。

## 7. 停止和回退条件

出现以下任一情况立即停止扩大实施：

- 需要新增数据库 migration；
- 历史 export 无法在不暴露路径的条件下兼容；
- 搜索需要改变 assessment、risk 或 review snapshot 数据模型；
- due_date 更新需要改变任务状态机；
- `actions_xlsx` 需要改变正式输出门禁或 GRI 结论口径；
- Envision v3 出现任何结构、verdict、证据页、风险或裁决差异；
- 需要真实外部模型、OCR 或 VLM；
- 发现用户未授权的 main/demo 数据写入。

停止后保留已通过的独立 commit，不使用 destructive reset；向用户报告阻塞点和可选取舍。

## 8. 本计划完成后的剩余事项

继续延期：

- OCR 生产就绪，按 `docs/plan/ocr-production-readiness-deferred-plan.md` 的触发条件执行；
- RAG Phase 2 正式接入；
- AI 运行观测和后端状态语义；
- 通用 verdict 批量复核；
- 独立 reopen；
- report 级审计页面；
- Docling、PaddleOCR、VLM 和后台队列。

Phase 1.6 完成只代表产品操作闭环和工程完整性提高，不构成 GRI 认证、外部鉴证、企业部署承诺或新增 ESG 专家判断。
