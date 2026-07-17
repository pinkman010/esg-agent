# 演示数据库与运行时文件隔离实施计划

> **执行约束：** 实施时必须使用测试驱动开发。每个生产代码改动前先添加失败测试并确认失败原因正确，再写最小实现。所有数据库创建、重置、目录清理、提交和推送动作均需单独取得用户授权。

**目标：** 在同一 PostgreSQL 实例中保留长期使用的 `esg_agent`，新增可安全重建的空演示库 `esg_agent_demo`，继续隔离自动测试库 `esg_agent_test`，并防止演示上传、OCR、导出等运行时文件污染现有环境。

**总体设计：** 项目继续使用一套前后端代码、一套 Alembic migration、一套 GRI 规则和只读原始资产。`esg_agent`、`esg_agent_demo`、`esg_agent_test` 只隔离业务数据；演示环境额外使用 `backend/data/runtime/demo/`。现有 `esg_agent` 及 `backend/data/runtime/uploads`、`backend/data/runtime/derived` 保持原状，避免破坏已有数据库路径引用。

**技术栈：** Python 3.11、Pydantic Settings、SQLAlchemy 2.0、psycopg、Alembic、PostgreSQL 16、FastAPI、pytest、Next.js、TypeScript、Vitest。

---

## 一、范围与安全边界

### 1.1 最终环境结构

```text
同一 PostgreSQL 实例
├─ esg_agent       开发、回归、正式验收和长期保留，禁止自动重置
├─ esg_agent_demo  产品演示，每次演示前允许重建为空库
└─ esg_agent_test  pytest 自动测试，测试过程允许清理

同一代码仓库
├─ backend/data/reports/       原始 ESG 报告，只读共享
├─ backend/data/standards/     GRI 标准，只读共享
├─ backend/data/manifests/     checklist 与资产 manifest，只读共享
├─ backend/data/runtime/       现有 esg_agent 运行时目录，暂不迁移
└─ backend/data/runtime/demo/  esg_agent_demo 专属上传和派生文件
```

### 1.2 硬性停止条件

演示重置工具必须同时满足以下条件，否则退出且不修改任何数据库或文件：

1. `APP_ENV=demo`；
2. `DATABASE_URL` 的数据库名严格等于 `esg_agent_demo`；
3. `UPLOAD_DIR` 和 `DERIVED_DIR` 都位于项目根目录下的 `backend/data/runtime/demo/`；
4. 目标路径解析后的绝对路径不能等于 `backend/data/runtime/`、项目根目录或其父目录；
5. 数据库管理连接必须指向同一 PostgreSQL 实例的 `postgres` 管理库；
6. 重置前检测到 demo 后端或分析任务仍占用连接时，默认停止并提示先关闭服务，不静默终止未知连接。

### 1.3 本次不做

- 不创建 `esg_agent_prod`；
- 不重命名或迁移现有 `esg_agent`；
- 不迁移现有运行时文件路径；
- 不删除现有 Envision regeneration 数据；
- 不增加企业级账号、权限、远程备份或对象存储；
- 不开放普通产品页面中的数据库重置按钮；
- 不启用外部模型、OCR 或 VLM；
- 不删除旧 `review_decisions`、旧 API 或旧前端调用者；
- 不改变 577 条 eligible requirement 口径和风险规则。

---

## 二、文件变更总览

| 文件 | 动作 | 责任 |
| --- | --- | --- |
| `docs/DESIGN.md` | 修改 | 记录三库隔离、共享代码/资产和演示重置安全边界 |
| `docs/DEVELOPMENT.md` | 修改 | 增加 demo 初始化、启动、重置、验收命令和停止条件 |
| `.env.example` | 修改 | 保留主库示例并增加 `APP_ENV` 说明 |
| `backend/.env.example` | 修改 | 增加主环境配置变量说明 |
| `backend/.env.demo.example` | 新建 | 提供 demo 数据库和运行时目录示例，不包含密钥 |
| `backend/src/config/settings.py` | 修改 | 增加 `app_env` 和环境安全校验入口 |
| `backend/src/config/environment_safety.py` | 新建 | 集中实现数据库名和路径边界校验 |
| `backend/src/tools/reset_demo_environment.py` | 新建 | 安全创建/重建 demo 库并清理 demo 运行时文件 |
| `backend/tests/test_settings.py` | 修改 | 覆盖默认主环境和 demo 相对路径解析 |
| `backend/tests/config/test_environment_safety.py` | 新建 | 覆盖所有允许和拒绝组合 |
| `backend/tests/tools/test_reset_demo_environment.py` | 新建 | 覆盖 dry-run、错误数据库名、错误目录和重建编排 |
| `frontend/lib/api.ts` | 修改 | 保持结构化 `ApiError`，供上传组件识别重复报告 |
| `frontend/components/upload/report-upload-panel.tsx` | 修改 | 显示“报告已存在”和“打开已有报告” |
| `frontend/components/upload/report-upload-panel.test.tsx` | 修改 | 覆盖 409 恢复交互 |

若实施时发现导出文件实际绕过 `DERIVED_DIR` 写入其他目录，应先停止该阶段，补充目录消费者清单并请示，不扩大脚本删除范围。

---

## 三、实施任务

### 任务1：同步设计与运行约定

**文件：**

- 修改：`docs/DESIGN.md`
- 修改：`docs/DEVELOPMENT.md`
- 修改：`.env.example`
- 修改：`backend/.env.example`
- 新建：`backend/.env.demo.example`

- [ ] **步骤1：更新技术设计唯一源**

在 `docs/DESIGN.md` 增加“本地环境隔离”章节，明确：

```text
代码、migration、GRI规则和原始资产共享；业务数据库和运行时文件隔离。
esg_agent 长期保留，esg_agent_demo 可重建，esg_agent_test 仅供自动测试。
```

- [ ] **步骤2：增加主环境示例**

`.env.example` 和 `backend/.env.example` 使用：

```dotenv
APP_ENV=main
DATABASE_URL=postgresql+psycopg://esg_agent:esg_agent@localhost:5432/esg_agent
UPLOAD_DIR=backend/data/runtime/uploads
DERIVED_DIR=backend/data/runtime/derived
OCR_ENABLED=false
```

保持现有路径，避免使数据库中的 `stored_path` 和导出 manifest 失效。

- [ ] **步骤3：增加演示环境示例**

`backend/.env.demo.example` 使用：

```dotenv
APP_ENV=demo
DATABASE_URL=postgresql+psycopg://esg_agent:esg_agent@localhost:5432/esg_agent_demo
UPLOAD_DIR=backend/data/runtime/demo/uploads
DERIVED_DIR=backend/data/runtime/demo/derived
OCR_ENABLED=false
```

- [ ] **步骤4：记录演示操作顺序**

`docs/DEVELOPMENT.md` 写明：关闭 demo 后端、执行 dry-run、执行显式重置、运行 Alembic、启动后端和前端、上传远景报告。所有路径使用相对路径或环境变量名。

- [ ] **步骤5：人工检查文档边界**

运行：

```powershell
rg -n "esg_agent_demo|APP_ENV|runtime/demo|外部模型|OCR|VLM" docs .env.example backend/.env.example backend/.env.demo.example
```

预期：三库定位一致；demo 仍默认关闭 OCR/VLM/外部模型；文档中没有本机绝对路径。

### 任务2：实现环境安全校验

**文件：**

- 新建：`backend/src/config/environment_safety.py`
- 修改：`backend/src/config/settings.py`
- 新建：`backend/tests/config/test_environment_safety.py`
- 修改：`backend/tests/test_settings.py`

- [ ] **步骤1：先写数据库名校验失败测试**

至少覆盖：

```python
def test_demo_environment_rejects_main_database():
    with pytest.raises(ValueError, match="esg_agent_demo"):
        validate_demo_environment(
            app_env="demo",
            database_url="postgresql+psycopg://esg_agent:esg_agent@localhost:5432/esg_agent",
            upload_dir=PROJECT_ROOT / "backend/data/runtime/demo/uploads",
            derived_dir=PROJECT_ROOT / "backend/data/runtime/demo/derived",
        )
```

- [ ] **步骤2：先写路径越界失败测试**

覆盖 `runtime/` 根目录、主环境目录、项目根目录、绝对路径逃逸和大小写差异。测试不得真实删除文件。

- [ ] **步骤3：运行测试并确认 RED**

运行：

```powershell
cd backend
uv run --no-sync pytest tests/config/test_environment_safety.py tests/test_settings.py -q
```

预期：因校验模块或 `app_env` 尚不存在而失败，失败原因与需求一致。

- [ ] **步骤4：实现最小校验模块**

模块职责限定为：

```python
def validate_demo_environment(*, app_env: str, database_url: str, upload_dir: Path, derived_dir: Path) -> None:
    """仅验证配置，不创建数据库、不删除文件。"""
```

使用 `sqlalchemy.engine.make_url()` 解析数据库名，使用 `Path.resolve()` 和 `Path.is_relative_to()` 校验目录。禁止用字符串前缀判断路径。

- [ ] **步骤5：在 Settings 中增加环境字段**

增加：

```python
app_env: Literal["main", "demo", "test"] = "main"
```

普通后端启动不自动执行删除类动作。demo 启动时可以验证配置一致性，但不得自动重置数据库。

- [ ] **步骤6：运行针对性测试并确认 GREEN**

```powershell
cd backend
uv run --no-sync pytest tests/config/test_environment_safety.py tests/test_settings.py tests/test_database_isolation.py -q
```

预期：全部通过，并继续证明 pytest 数据库与 `esg_agent` 不同。

### 任务3：实现显式演示库初始化与重置工具

**文件：**

- 新建：`backend/src/tools/reset_demo_environment.py`
- 新建：`backend/tests/tools/test_reset_demo_environment.py`

- [ ] **步骤1：先写 dry-run 测试**

测试要求 dry-run 只输出目标数据库、目标目录和计划动作，不调用数据库 DROP/CREATE，也不删除文件。

- [ ] **步骤2：先写危险目标拒绝测试**

至少覆盖：

```text
APP_ENV=main
database=esg_agent
database=postgres
database=esg_agent_test
upload_dir=backend/data/runtime/uploads
derived_dir=backend/data/runtime/derived
```

所有组合必须在任何写操作前失败。

- [ ] **步骤3：先写编排测试**

通过 mock 或可注入 adapter 验证顺序：

```text
validate
→ check active connections
→ drop demo database
→ create demo database
→ alembic upgrade head
→ clear demo runtime children
→ report success
```

禁止在单元测试中真实删除数据库或项目文件。

- [ ] **步骤4：运行测试并确认 RED**

```powershell
cd backend
uv run --no-sync pytest tests/tools/test_reset_demo_environment.py -q
```

- [ ] **步骤5：实现工具的安全CLI**

建议命令接口：

```powershell
uv run --no-sync python -m src.tools.reset_demo_environment --dry-run
uv run --no-sync python -m src.tools.reset_demo_environment --confirm-database esg_agent_demo
```

第二条命令仍需通过所有配置校验。`--confirm-database` 只作为显式确认，不替代 `APP_ENV`、数据库名和路径门禁。

- [ ] **步骤6：处理已有连接**

默认行为：发现除当前管理连接外的 demo 连接时退出，输出连接数量并提示关闭 demo 服务。本次不自动终止连接，降低误伤风险。

- [ ] **步骤7：执行 Alembic**

重建数据库后，使用当前进程的 demo `DATABASE_URL` 调用 Alembic升级到 `head`。Alembic失败时：

- 保留新建的空 demo 数据库用于诊断；
- 不清理 demo 运行时目录；
- 返回非零退出码；
- 不触碰 `esg_agent`。

- [ ] **步骤8：清理文件边界**

仅在数据库重建和 migration成功后，删除 `runtime/demo/uploads/` 与 `runtime/demo/derived/` 的子项，保留目录本身。删除前再次解析最终绝对路径并验证边界。

- [ ] **步骤9：运行针对性测试并确认 GREEN**

```powershell
cd backend
uv run --no-sync pytest tests/tools/test_reset_demo_environment.py tests/config/test_environment_safety.py -q
```

### 任务4：验证运行时文件消费者全部受配置控制

**文件：**

- 可能修改：`backend/src/services/document_store.py`
- 可能修改：`backend/src/services/ocr.py`
- 可能修改：`backend/src/services/exports.py` 或实际导出服务文件
- 修改：对应 service 测试

- [ ] **步骤1：建立消费者清单**

运行：

```powershell
rg -n "data/runtime|upload_dir|derived_dir|exports|ocr" backend/src backend/tests
```

预期：上传、OCR和版本化输出都从 Settings 注入的目录派生，不存在绕过配置的硬编码运行时路径。

- [ ] **步骤2：发现硬编码时先写失败测试**

使用 `tmp_path` 和 demo Settings，断言所有新文件都位于传入的 demo 根目录，不写入主环境目录。

- [ ] **步骤3：做最小修复**

只把硬编码路径改为已有 `upload_dir` 或 `derived_dir` 派生路径，不重构业务逻辑，不迁移旧文件。

- [ ] **步骤4：运行服务测试**

```powershell
cd backend
uv run --no-sync pytest tests/services/test_document_store.py tests/services/test_ocr.py tests/services -q
```

预期：测试文件只写入 pytest 临时目录；主环境和 demo 环境目录均不被测试污染。

### 任务5：修复重复上传409的前端恢复体验

空 demo 库降低重复上传出现频率，但主库和异常演示流程仍可能遇到重复报告，因此保留后端去重门禁并改善前端恢复路径。

**文件：**

- 修改：`frontend/components/upload/report-upload-panel.test.tsx`
- 修改：`frontend/components/upload/report-upload-panel.tsx`
- 可能修改：`frontend/lib/api.test.ts`

- [ ] **步骤1：先写失败测试**

后端响应：

```json
{
  "detail": {
    "code": "duplicate_report",
    "message": "相同报告已存在",
    "report_id": "report-existing"
  }
}
```

测试断言页面显示“报告已存在”，显示“打开已有报告”按钮，点击后导航到：

```text
/reports/report-existing/confirm
```

该路径与当前报告列表统一入口一致，已有报告后续由确认页状态决定下一步。

- [ ] **步骤2：运行测试并确认 RED**

```powershell
cd frontend
pnpm test -- components/upload/report-upload-panel.test.tsx
```

预期：当前只显示 `API request failed with status 409`，新增断言失败。

- [ ] **步骤3：实现最小错误解析**

组件只识别 `ApiError.status === 409` 且 `body.detail.code === "duplicate_report"` 的结构。其他错误继续显示通用上传失败信息，不信任任意响应字段作为导航地址。

- [ ] **步骤4：运行测试并确认 GREEN**

```powershell
cd frontend
pnpm test -- components/upload/report-upload-panel.test.tsx lib/api.test.ts
```

### 任务6：真实创建demo库并完成验收

该任务包含数据库重建和目录清理，执行前必须再次取得用户授权。

- [ ] **步骤1：确认工具路径和服务状态**

当前会话中 `docker` 不在 PATH。实施时先按 `docs/DEVELOPMENT.md` 确认 Docker Desktop/CLI 可用位置，不下载或安装未知工具。

- [ ] **步骤2：启动 PostgreSQL**

```powershell
docker compose up -d postgres
```

- [ ] **步骤3：执行demo重置dry-run**

加载 demo 环境变量后运行：

```powershell
cd backend
uv run --no-sync python -m src.tools.reset_demo_environment --dry-run
```

预期输出只包含 `esg_agent_demo` 和 `backend/data/runtime/demo/`，不包含主库重置动作。

- [ ] **步骤4：取得用户确认后执行真实重置**

```powershell
cd backend
uv run --no-sync python -m src.tools.reset_demo_environment --confirm-database esg_agent_demo
```

预期：demo库为空、Alembic revision为 `0008_export_versions`、demo运行时目录为空。

- [ ] **步骤5：运行后端针对性测试**

```powershell
cd backend
uv run --no-sync pytest tests/config/test_environment_safety.py tests/tools/test_reset_demo_environment.py tests/test_settings.py tests/test_database_isolation.py tests/api/test_reports_api.py -q
```

- [ ] **步骤6：运行后端全量测试**

```powershell
cd backend
uv run --no-sync pytest -q
```

预期：不低于当前444项基线，全部通过；测试必须使用 `esg_agent_test`，不能写入主库或demo库。

- [ ] **步骤7：运行前端门禁**

```powershell
cd frontend
pnpm typecheck
pnpm test
pnpm build
```

预期：typecheck、全部Vitest和production build通过。

- [ ] **步骤8：运行Envision 577 gate**

按 `docs/DEVELOPMENT.md` 的固定命令重新生成并审计：

```powershell
cd backend
uv run --no-sync python -m src.tools.regenerate_review_csv `
  --report-id envision_2024 `
  --pdf "data/reports/Envision Energy 2024-zh.pdf" `
  --profile data/reports/profiles/envision_2024.json `
  --output ../tmp/review/current_577_review_regenerated.csv `
  --baseline ../tmp/review/current_577_review_after_profile_routing.csv `
  --audit-output ../tmp/review/current_577_review_regenerated_audit.json `
  --diff-summary-output ../tmp/review/current_577_review_regeneration_diff_summary.json `
  --report-total-pages 78
```

预期：577条唯一eligible requirement、audit通过、verdict delta为0，且未调用外部模型、OCR或VLM。

- [ ] **步骤9：执行demo人工产品验收**

按照 `docs/DEVELOPMENT.md` 的人工路径：

```text
空报告列表
→ 上传远景2024中文ESG报告
→ metadata确认
→ 577条分析与七阶段进度
→ dashboard
→ 高风险三栏复核
→ 完整核查表
→ 整改任务
→ 草稿与正式输出门禁
```

必须确认“高风险复核已完成”没有表达为577条全部人工确认。

- [ ] **步骤10：记录问题**

每个问题记录：复现步骤、预期、实际、严重程度、影响范围、建议修复和验证结果。阻塞问题修复后先跑相关最小测试，再重复全量门禁。

---

## 四、验收标准

全部满足才可视为完成：

1. 默认主环境仍连接 `esg_agent`，已有数据和路径引用保持可用；
2. demo环境只能连接 `esg_agent_demo`；
3. demo上传、OCR派生和导出只写入 `backend/data/runtime/demo/`；
4. 重置工具无法对 `esg_agent`、`esg_agent_test`、`postgres` 或主运行时目录执行写操作；
5. dry-run无数据库或文件写入；
6. demo重置后数据库处于 Alembic head且没有报告记录；
7. 同一远景PDF可在每次demo重置后重新上传；
8. 未重置时重复上传显示“报告已存在 + 打开已有报告”；
9. 后端全量测试、前端typecheck/test/build和Envision 577 gate全部通过；
10. 全流程不调用外部模型、OCR或VLM；
11. 未删除、覆盖或回退现有主库数据、原始资产和旧兼容接口；
12. 工作区只包含本任务已批准的修改，不自动push。

---

## 五、回滚与恢复

- 配置或代码回滚：恢复代码和示例配置即可，主库未迁移；
- demo数据库失败：删除失败的 `esg_agent_demo` 后重新创建，不影响 `esg_agent`；
- demo运行时清理失败：停止演示，保留现场并记录失败路径，不扩大删除范围；
- Alembic失败：保留空demo库供诊断，不触碰主库；
- 主库出现任何非预期写入：立即停止后续步骤，记录当前连接配置和Git diff，禁止继续重置或清理；
- 不使用 `git reset --hard`、`git checkout --` 或自动push处理失败。

## 六、实施顺序建议

```text
用户审核本计划
→ 更新DESIGN/DEVELOPMENT和环境示例
→ TDD实现环境安全校验
→ TDD实现demo重置工具
→ 验证运行时文件消费者
→ 修复重复上传409体验
→ 取得授权后创建空demo库
→ 自动门禁
→ 人工产品验收
```

每一阶段执行前说明影响文件、运行行为和验证命令；执行后汇报结果和下一步建议。是否创建commit、是否继续下一阶段、是否执行真实demo重置均由用户单独确认。
