# DeepSeek AI 辅助分析后端冻结 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. 本计划保持在 `main` 分支 inline 执行，不创建 worktree，不自动 push；每项完成后在本文件勾选并记录验证结果。

**Goal:** 在保留确定性分析基线、证据追溯和人工最终裁决的前提下，修复 352 条 GRI 标准结构问题，接入 DeepSeek `deepseek-v4-flash` 生成独立 AI 辅助建议，并完成可冻结的后端数据、API、失败降级和质量门禁。

**Architecture:** 原始 GRI 清单保持只读，新建版本化结构编译产物，将 577 个标准核查单元拆分为独立判断项、父级上下文项和方法待确认项。规则引擎先生成确定性 assessment 和 risk-v2.1 复核优先级；只有结构完整、存在可用证据并进入高/中优先级的独立判断项才调用 DeepSeek。AI 结果写入追加式 `ai_assessment_suggestions`，不覆盖规则 assessment，不直接改变适用性、复核状态、整改任务或正式输出门禁。

**Tech Stack:** Python 3.11、FastAPI、Pydantic v2、SQLAlchemy 2、PostgreSQL JSONB、Alembic、OpenAI Python SDK、DeepSeek OpenAI-compatible API、pytest、openpyxl、现有 Envision regeneration 与 Goldwind holdout 门禁。

---

## 1. 范围与冻结口径

本计划只完成后端和必要的 OpenAPI 类型同步。前端“启用 AI”“规则/AI/人工三层展示”和最终浏览器验收在本计划执行完成后另写下一份计划。

冻结后必须满足：

1. `backend/data/manifests/gri_requirement_checklist.json`、GRI 官方 PDF、远景报告 PDF 均不覆盖、不删改。
2. 577 表示本次标准资产中的核查单元总数；独立判断数由结构编译器计算，禁止继续把 577 写死为独立 assessment 数量。
3. 人工复核工作簿已确认的 352 条结构问题按以下方式处理：
   - 78 条父级或容器条款：`evaluation_role=context_only`，作为子项 Prompt 上下文，不生成独立 assessment。
   - 268 条缺少父级引导语、范围或条件的子项：`evaluation_role=independent`，生成 `effective_requirement_text` 后参与分析。
   - 6 条合并或拆分错误：`evaluation_role=method_pending`，本版不生成披露结论，不进入 AI 调用，保留到标准方法负责人后续裁决。
4. 规则 assessment 是可回放的确定性基线；AI suggestion 是追加的辅助产物；人工 snapshot 是最终产品裁决层。
5. `confirm_llm=false` 的行为保持完全离线，禁止实例化外部客户端或发出网络请求。
6. `confirm_llm=true` 时只发送 requirement、有限证据片段、证据 ID、PDF 页码和必要报告 metadata；不发送整份 PDF、API Key、数据库连接信息、人工姓名或审计备注。
7. DeepSeek 失败、返回空内容、JSON 截断、Schema 错误、证据引用越界或预算达到上限时，当前 requirement 记录失败 suggestion，整份规则分析继续完成。
8. AI 不得写 `review_status`、`applicability_status`、`risk_level`、`action_status` 和正式输出状态。
9. 不启用 OCR 或 VLM，不删除旧 `review_decisions`、旧 API 或历史数据库记录。
10. 本计划允许在 `main` 创建本地 checkpoint commit，禁止 push。

## 2. 文件结构

### 新建文件

- `backend/data/review_inputs/envision_2024/manual/`：本地保存首次和二次人工复核输入；目录内容不提交 Git。
- `backend/data/review_inputs/envision_2024/baselines/`：本地保存已批准 Envision 规则回归基线；目录内容不提交 Git。
- `backend/data/runtime/evaluations/envision_2024/`：本地保存 DeepSeek 真实评估输出；目录内容不提交 Git。
- `backend/src/standards/requirement_structure.py`：结构角色、父级上下文继承和编译校验。
- `backend/src/tools/build_requirement_structure_v2.py`：从人工复核工作簿生成结构决策和 v2 清单。
- `backend/data/manifests/gri_requirement_structure_v2.json`：352 条结构决策及来源哈希。
- `backend/data/manifests/gri_requirement_checklist_v2.json`：运行时使用的版本化编译清单。
- `backend/src/domain/ai_models.py`：AI 请求、结构化响应和持久化领域模型。
- `backend/src/services/ai_assessment_service.py`：Prompt、调用筛选、校验、降级和 bounded concurrency。
- `backend/src/services/ai_evaluation_service.py`：225 条完整人工复核基线的一次性评估。
- `backend/alembic/versions/0011_standard_structure_and_ai_suggestions.py`：追加式数据库迁移。
- `backend/src/tools/evaluate_deepseek_against_manual_review.py`：真实全量评估 CLI。
- `backend/tests/standards/test_requirement_structure.py`。
- `backend/tests/tools/test_build_requirement_structure_v2.py`。
- `backend/tests/services/test_ai_assessment_service.py`。
- `backend/tests/services/test_ai_evaluation_service.py`。
- `backend/tests/tools/test_evaluate_deepseek_against_manual_review.py`。

### 修改文件

- `.gitignore`：忽略本地人工复核输入和真实模型评估产物。
- `backend/data/manifests/assets_manifest.json`：记录人工复核输入、批准基线和AI评估产物的目标路径与SHA256。
- `docs/ASSETS.md`：增加人工复核输入和AI评估产物的资产恢复规则。
- `backend/.env.example`、`backend/.env.demo.example`、`.env.example`：DeepSeek 非密钥配置。
- `backend/src/config/settings.py`：调用参数、并发、预算和重试配置。
- `backend/src/tools/llm_client.py`：消息式调用、thinking、JSON Output、metadata 和重试。
- `backend/src/domain/enums.py`、`backend/src/domain/models.py`：标准结构与 run 统计字段。
- `backend/src/db/models.py`、`backend/src/db/repositories.py`：新表和存取方法。
- `backend/src/standards/gri.py`：读取 v2 编译字段并只创建独立任务。
- `backend/src/services/analysis_runner.py`：注入 DeepSeek client 和 AI service。
- `backend/src/workflows/single_report_workflow.py`：规则分析后执行 AI 辅助阶段。
- `backend/src/api/schemas.py`、`backend/src/api/routes/assessments.py`、`backend/src/api/routes/runs.py`：返回结构统计和 AI suggestion。
- `backend/src/services/export_service.py`、`backend/src/tools/review_csv_export.py`：导出规则/AI分层字段和标准范围摘要。
- `backend/tests/test_settings.py`：配置边界。
- `backend/src/tools/regenerate_review_csv.py`、`backend/tests/tools/test_regenerate_review_csv.py`：支持 v2 标准范围和共同 ID 回归。
- `backend/tests/db/test_repositories.py`、`backend/tests/standards/test_gri_adapter.py`、`backend/tests/workflows/test_single_report_workflow.py`、相关 API/导出测试。
- `frontend/lib/generated/api-types.ts`：由 OpenAPI 自动生成，只同步类型，不实现 UI。
- `README.md`、`docs/DESIGN.md`、`docs/DEVELOPMENT.md`、`docs/product/api-contract.md`、`docs/product/data-model-impact.md`：冻结口径、运行命令、限制和门禁结果。

## 3. 停止条件

出现以下情况立即停止连续执行并向用户报告：

1. 当前未提交工作区无法通过既有后端、前端或 Envision gate，且失败属于业务断言而非已知 Windows 临时目录占用。
2. 人工工作簿 SHA256 与 `f1eeb37444de1eeda86b8ae0813dbfd6e88c94719781b98a8de659d9fbd7ddea` 不一致。
3. 二次复核建议CSV SHA256与 `713505f54e53ecccfe292de7d209126d9293845b0df460b90bf522bca83ac29d` 不一致。
4. 结构分类无法得到 78/268/6，或 577 个 `requirement_id` 不唯一。
5. 需要覆盖原始标准、原始报告、旧 API 或已有人工复核记录才能继续。
6. Alembic upgrade 会删除、重命名或回填历史字段。
7. 首次真实 DeepSeek 调用前 API Key 不存在、余额不足、用户未确认发送限定数据，或 Base URL/模型与本计划不一致。
8. 真实评估发现 AI 引用了输入集合之外的证据，或 guardrail 未能阻止无实质证据的 `disclosed` 建议。
9. Goldwind gate 新增 false disclosed 或 wrong source page。

## 4. 实施任务

### Task 0：把桌面与tmp中的关键验收资产归档到项目目录

**Files:**
- Create local-only: `backend/data/review_inputs/envision_2024/manual/envision_2024_577_manual_review_v1.xlsx`
- Create local-only: `backend/data/review_inputs/envision_2024/manual/envision_2024_577_manual_review_second_review_Pro_20260719.xlsx`
- Create local-only: `backend/data/review_inputs/envision_2024/manual/envision_2024_577_Pro_second_review_recommendations_20260719.csv`
- Create local-only: `backend/data/review_inputs/envision_2024/baselines/current_577_review_after_profile_routing.csv`
- Create local-only: `backend/data/review_inputs/envision_2024/baselines/current_577_review_after_profile_routing_audit.json`
- Create local-only: `backend/data/review_inputs/envision_2024/baselines/current_577_review_profile_routing_diff.csv`
- Create local-only: `backend/data/review_inputs/envision_2024/baselines/current_577_review_profile_routing_diff_summary.json`
- Create local-only: `backend/data/review_inputs/envision_2024/baselines/current_577_review_regenerated.csv`
- Create local-only: `backend/data/review_inputs/envision_2024/baselines/current_577_review_regenerated_audit.json`
- Create local-only: `backend/data/review_inputs/envision_2024/baselines/current_577_review_regeneration_diff_summary.json`
- Modify: `.gitignore`
- Modify: `backend/data/manifests/assets_manifest.json`
- Modify: `docs/ASSETS.md`

- [x] **Step 1：检查两个外部源路径变量和固定哈希**

执行前由用户或当前终端设置：

```powershell
$env:ESG_SECOND_REVIEW_WORKBOOK_SOURCE
$env:ESG_SECOND_REVIEW_RECOMMENDATIONS_SOURCE
```

只读取变量值，不把绝对路径写入docs、manifest或Git。运行：

```powershell
if (-not $env:ESG_SECOND_REVIEW_WORKBOOK_SOURCE) { throw 'ESG_SECOND_REVIEW_WORKBOOK_SOURCE is required' }
if (-not $env:ESG_SECOND_REVIEW_RECOMMENDATIONS_SOURCE) { throw 'ESG_SECOND_REVIEW_RECOMMENDATIONS_SOURCE is required' }
$workbookHash=(Get-FileHash -LiteralPath $env:ESG_SECOND_REVIEW_WORKBOOK_SOURCE -Algorithm SHA256).Hash.ToLower()
$recommendationsHash=(Get-FileHash -LiteralPath $env:ESG_SECOND_REVIEW_RECOMMENDATIONS_SOURCE -Algorithm SHA256).Hash.ToLower()
if ($workbookHash -ne 'f1eeb37444de1eeda86b8ae0813dbfd6e88c94719781b98a8de659d9fbd7ddea') { throw 'second review workbook hash mismatch' }
if ($recommendationsHash -ne '713505f54e53ecccfe292de7d209126d9293845b0df460b90bf522bca83ac29d') { throw 'recommendations csv hash mismatch' }
```

- [x] **Step 2：确认项目内现有首次复核和规则基线齐全**

运行：

```powershell
$required=@(
  'tmp/review/envision_2024_577_manual_review_v1.xlsx',
  'tmp/review/current_577_review_after_profile_routing.csv',
  'tmp/review/current_577_review_after_profile_routing_audit.json',
  'tmp/review/current_577_review_profile_routing_diff.csv',
  'tmp/review/current_577_review_profile_routing_diff_summary.json',
  'tmp/review/current_577_review_regenerated.csv',
  'tmp/review/current_577_review_regenerated_audit.json',
  'tmp/review/current_577_review_regeneration_diff_summary.json'
)
$missing=$required | Where-Object { -not (Test-Path -LiteralPath $_) }
if ($missing) { throw "missing acceptance assets: $($missing -join ', ')" }
```

- [x] **Step 3：创建项目内持久化目录并执行不覆盖复制**

运行：

```powershell
$manualDir='backend/data/review_inputs/envision_2024/manual'
$baselineDir='backend/data/review_inputs/envision_2024/baselines'
New-Item -ItemType Directory -Force -Path $manualDir,$baselineDir | Out-Null

$copies=@(
  @{Source='tmp/review/envision_2024_577_manual_review_v1.xlsx'; Target="$manualDir/envision_2024_577_manual_review_v1.xlsx"},
  @{Source=$env:ESG_SECOND_REVIEW_WORKBOOK_SOURCE; Target="$manualDir/envision_2024_577_manual_review_second_review_Pro_20260719.xlsx"},
  @{Source=$env:ESG_SECOND_REVIEW_RECOMMENDATIONS_SOURCE; Target="$manualDir/envision_2024_577_Pro_second_review_recommendations_20260719.csv"},
  @{Source='tmp/review/current_577_review_after_profile_routing.csv'; Target="$baselineDir/current_577_review_after_profile_routing.csv"},
  @{Source='tmp/review/current_577_review_after_profile_routing_audit.json'; Target="$baselineDir/current_577_review_after_profile_routing_audit.json"},
  @{Source='tmp/review/current_577_review_profile_routing_diff.csv'; Target="$baselineDir/current_577_review_profile_routing_diff.csv"},
  @{Source='tmp/review/current_577_review_profile_routing_diff_summary.json'; Target="$baselineDir/current_577_review_profile_routing_diff_summary.json"},
  @{Source='tmp/review/current_577_review_regenerated.csv'; Target="$baselineDir/current_577_review_regenerated.csv"},
  @{Source='tmp/review/current_577_review_regenerated_audit.json'; Target="$baselineDir/current_577_review_regenerated_audit.json"},
  @{Source='tmp/review/current_577_review_regeneration_diff_summary.json'; Target="$baselineDir/current_577_review_regeneration_diff_summary.json"}
)

foreach($item in $copies){
  $sourceHash=(Get-FileHash -LiteralPath $item.Source -Algorithm SHA256).Hash.ToLower()
  if(Test-Path -LiteralPath $item.Target){
    $targetHash=(Get-FileHash -LiteralPath $item.Target -Algorithm SHA256).Hash.ToLower()
    if($sourceHash -ne $targetHash){ throw "existing target differs: $($item.Target)" }
    continue
  }
  $temporary="$($item.Target).copying"
  Copy-Item -LiteralPath $item.Source -Destination $temporary
  $temporaryHash=(Get-FileHash -LiteralPath $temporary -Algorithm SHA256).Hash.ToLower()
  if($sourceHash -ne $temporaryHash){ Remove-Item -LiteralPath $temporary; throw "copy verification failed: $($item.Target)" }
  Move-Item -LiteralPath $temporary -Destination $item.Target
}
```

本步骤只复制，不移动或删除桌面和`tmp/`源文件。

- [x] **Step 4：登记资产manifest并保护本地输入**

在 `.gitignore` 增加：

```gitignore
# 本地人工复核和验收输入；只提交SHA256资产清单
backend/data/review_inputs/**
```

向 `backend/data/manifests/assets_manifest.json` 追加每个文件的：`source_path`、`target_path`、`sha256`、`size_bytes`、`asset_type`、`migration_reason`、`material_status`、`copied_at`、`source_protection`。外部文件的 `source_path` 使用 `${ESG_SECOND_REVIEW_WORKBOOK_SOURCE}` 或 `${ESG_SECOND_REVIEW_RECOMMENDATIONS_SOURCE}`，不得保存桌面绝对路径；项目内来源使用相对路径，保持现有manifest字段结构。

`docs/ASSETS.md` 增加：人工复核输入位于 `backend/data/review_inputs/`；真实模型评估位于 `backend/data/runtime/evaluations/`；两者均本地保存，通过manifest恢复和校验，不提交二进制文件或外部模型原始响应。

- [x] **Step 5：执行迁移后完整性检查**

运行：

```powershell
$targets=Get-ChildItem 'backend/data/review_inputs/envision_2024' -File -Recurse
if($targets.Count -ne 10){ throw "expected 10 archived assets, got $($targets.Count)" }
$targets | ForEach-Object { Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256 }
git status --short -- .gitignore docs/ASSETS.md backend/data/manifests/assets_manifest.json backend/data/review_inputs
```

期望：10个文件存在；二次复核XLSX和建议CSV哈希与固定值一致；Git只显示 `.gitignore`、`docs/ASSETS.md` 和manifest，不显示本地review input内容。完成本步骤后，桌面源文件才可以由用户人工清理。

### Task 1：封存当前确定性 MVP 基线

**Files:**
- Modify: `docs/DEVELOPMENT.md`
- Verify: 当前全部已修改和未跟踪项目文件

- [x] **Step 1：记录当前 Git 和数据库基线**

运行：

```powershell
git status --short --branch
git log -5 --oneline --decorate
cd backend
uv run --no-sync alembic current
uv run --no-sync alembic heads
```

期望：分支为 `main`；Alembic current 与 heads 均为 `0010_risk_v2_dimensions`；不执行 reset、clean、checkout 或 push。

- [x] **Step 2：运行当前后端与前端全量门禁**

运行：

```powershell
cd backend
uv run --no-sync pytest -q --basetemp=../tmp/pytest-ai-backend-baseline

cd ../frontend
pnpm test -- --run
pnpm typecheck
pnpm build
```

期望：后端至少 555 项通过；前端至少 51 项通过；typecheck 和 production build 成功。实际数量增加可以接受，减少必须解释。

- [x] **Step 3：运行 Envision 577 当前 gate**

运行当前正式 regeneration 命令：

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

要求：

```text
unique_requirement_count=577
audit.ok=true
verdict_delta=0
false_disclosed=0
wrong_source_page=0
```

- [x] **Step 4：建立本地 checkpoint commit**

先检查：

```powershell
git diff --check
git diff --stat
git status --short
```

确认全部现有变更均属于已完成的产品验收范围后运行：

```powershell
git add -- . ':!tmp'
git diff --cached --check
git commit -m "chore: checkpoint accepted deterministic mvp"
```

期望：提交成功，仍停留在 `main`，不 push。

### Task 2：把352条人工结构结论转成可验证数据

**Files:**
- Create: `backend/src/standards/requirement_structure.py`
- Create: `backend/src/tools/build_requirement_structure_v2.py`
- Create: `backend/tests/standards/test_requirement_structure.py`
- Create: `backend/tests/tools/test_build_requirement_structure_v2.py`
- Create: `backend/data/manifests/gri_requirement_structure_v2.json`
- Create: `backend/data/manifests/gri_requirement_checklist_v2.json`

- [ ] **Step 1：先写结构模型和分类失败测试**

测试必须覆盖以下接口：

```python
from src.standards.requirement_structure import (
    EvaluationRole,
    RequirementStructureDecision,
    compile_requirement_structure,
)


def test_parent_container_becomes_context_only():
    decision = RequirementStructureDecision(
        requirement_id="GRI 2-2-c",
        issue_code="parent_container_as_leaf",
        parent_requirement_id=None,
        source_note="父级/容器条款",
    )
    assert decision.evaluation_role is EvaluationRole.CONTEXT_ONLY


def test_child_inherits_parent_scope_and_remains_independent():
    compiled = compile_requirement_structure(
        items=[
            {"requirement_id": "GRI 2-2-c", "requirement_text": "if multiple entities, explain the consolidation approach:"},
            {"requirement_id": "GRI 2-2-c-i", "requirement_text": "adjustments for minority interests;"},
        ],
        decisions=[
            RequirementStructureDecision(
                requirement_id="GRI 2-2-c-i",
                issue_code="missing_parent_context",
                parent_requirement_id="GRI 2-2-c",
                source_note="缺少父级引导语",
            )
        ],
    )
    child = next(item for item in compiled if item["requirement_id"] == "GRI 2-2-c-i")
    assert child["evaluation_role"] == "independent"
    assert child["effective_requirement_text"] == (
        "if multiple entities, explain the consolidation approach: adjustments for minority interests;"
    )


def test_merge_split_error_remains_method_pending():
    decision = RequirementStructureDecision(
        requirement_id="GRI TEST",
        issue_code="merge_split_error",
        parent_requirement_id=None,
        source_note="合并提取或拆分错误",
    )
    assert decision.evaluation_role is EvaluationRole.METHOD_PENDING
```

运行：

```powershell
cd backend
uv run --no-sync pytest tests/standards/test_requirement_structure.py -q
```

期望：因模块尚未存在而失败。

- [ ] **Step 2：实现结构领域模型和编译器**

`requirement_structure.py` 必须定义：

```python
from enum import StrEnum
from pydantic import BaseModel


class EvaluationRole(StrEnum):
    INDEPENDENT = "independent"
    CONTEXT_ONLY = "context_only"
    METHOD_PENDING = "method_pending"


class StructureStatus(StrEnum):
    VERIFIED = "verified"
    NORMALIZED = "normalized"
    METHOD_PENDING = "method_pending"


class RequirementStructureDecision(BaseModel):
    requirement_id: str
    issue_code: str
    parent_requirement_id: str | None = None
    source_note: str
    evaluation_role: EvaluationRole | None = None

    def model_post_init(self, __context) -> None:
        role_by_issue = {
            "parent_container_as_leaf": EvaluationRole.CONTEXT_ONLY,
            "missing_parent_context": EvaluationRole.INDEPENDENT,
            "merge_split_error": EvaluationRole.METHOD_PENDING,
        }
        expected = role_by_issue[self.issue_code]
        if self.evaluation_role is not None and self.evaluation_role is not expected:
            raise ValueError("evaluation_role conflicts with issue_code")
        self.evaluation_role = expected
```

`compile_requirement_structure()` 必须：

- 保留原 `requirement_text`；
- 新增 `effective_requirement_text`、`evaluation_role`、`structure_status`、`context_requirement_ids` 和 `structure_issue_codes`；
- 对子项按根到叶顺序拼接父级上下文，压缩空白但不改写英文事实；
- 检测父级循环、缺失父级、重复 ID 和空文本并抛出明确异常；
- 对无结构问题且 `standard_verified=yes` 的条目标记 `verified`；
- 对自动继承成功的子项标记 `normalized`；
- 对6条合并/拆分问题标记 `method_pending`。
- 使用 `GRIAdapter._requirement_id_from_checklist_item()` 的等价公共 helper，把原始清单中的内部 ID（例如 `current_gap:GRI2:2-2:c:i`）稳定映射为人工工作簿 ID（例如 `GRI 2-2-c-i`）；双向映射不唯一时立即失败。

- [ ] **Step 3：写工作簿导入测试**

使用临时工作簿构造列 `requirement_id`、`standard_verified`、`primary_issue_type`、`review_note`、`second_review_note`，断言：

```python
decisions = read_structure_decisions(workbook_path)
assert [item.issue_code for item in decisions] == [
    "parent_container_as_leaf",
    "missing_parent_context",
    "merge_split_error",
]
```

导入器只读取，不修改或另存人工工作簿。`missing_parent_context` 的父级 ID 优先从人工复核说明中的“依赖上级”提取，并与原始清单 `parent_requirement_id` 映射交叉验证；两者不一致或无法找到父级时停止生成。

- [ ] **Step 4：实现确定性工作簿导入 CLI**

CLI 只读取 Task 0 已归档并通过哈希校验的项目内工作簿：

```powershell
cd backend
uv run --no-sync python -m src.tools.build_requirement_structure_v2 `
  --review-workbook data/review_inputs/envision_2024/manual/envision_2024_577_manual_review_second_review_Pro_20260719.xlsx `
  --source-checklist data/manifests/gri_requirement_checklist.json `
  --output-structure data/manifests/gri_requirement_structure_v2.json `
  --output-checklist data/manifests/gri_requirement_checklist_v2.json
```

生成器必须校验工作簿 SHA256，输出 metadata：

```json
{
  "manifest_version": "gri-requirement-structure-v2",
  "source_review_sha256": "f1eeb37444de1eeda86b8ae0813dbfd6e88c94719781b98a8de659d9fbd7ddea",
  "standard_unit_count": 577,
  "verified_count": 225,
  "context_only_count": 78,
  "normalized_count": 268,
  "method_pending_count": 6,
  "independent_assessment_count": 493
}
```

任一计数不一致时退出码为1，且不得覆盖已有 v2 文件。使用临时文件写完并通过校验后再原子替换目标。

- [ ] **Step 5：运行结构测试和真实生成**

```powershell
cd backend
uv run --no-sync pytest tests/standards/test_requirement_structure.py tests/tools/test_build_requirement_structure_v2.py -q
uv run --no-sync python -m src.tools.build_requirement_structure_v2 `
  --review-workbook data/review_inputs/envision_2024/manual/envision_2024_577_manual_review_second_review_Pro_20260719.xlsx `
  --source-checklist data/manifests/gri_requirement_checklist.json `
  --output-structure data/manifests/gri_requirement_structure_v2.json `
  --output-checklist data/manifests/gri_requirement_checklist_v2.json
```

期望：测试通过；结构计数为 225/78/268/6；独立判断项为493；577个原始核查单元全部可映射。

- [ ] **Step 6：提交标准结构产物**

```powershell
git add backend/src/standards/requirement_structure.py backend/src/tools/build_requirement_structure_v2.py backend/tests/standards/test_requirement_structure.py backend/tests/tools/test_build_requirement_structure_v2.py backend/data/manifests/gri_requirement_structure_v2.json backend/data/manifests/gri_requirement_checklist_v2.json
git diff --cached --check
git commit -m "feat: compile verified GRI requirement structure"
```

### Task 3：迁移结构统计和追加式AI建议数据模型

**Files:**
- Create: `backend/alembic/versions/0011_standard_structure_and_ai_suggestions.py`
- Create: `backend/src/domain/ai_models.py`
- Create local-only: `backend/data/runtime/backups/pre_0011_esg_agent.dump`
- Modify: `backend/src/domain/enums.py`
- Modify: `backend/src/domain/models.py`
- Modify: `backend/src/db/models.py`
- Modify: `backend/src/db/repositories.py`
- Test: `backend/tests/domain/test_models.py`
- Test: `backend/tests/db/test_repositories.py`

- [ ] **Step 1：迁移前保存本地数据库备份**

运行：

```powershell
New-Item -ItemType Directory -Force -Path backend/data/runtime/backups | Out-Null
docker compose exec -T postgres pg_dump -U esg_agent -Fc -f /tmp/pre_0011_esg_agent.dump esg_agent
docker compose cp postgres:/tmp/pre_0011_esg_agent.dump backend/data/runtime/backups/pre_0011_esg_agent.dump
$dumpHash=(Get-FileHash backend/data/runtime/backups/pre_0011_esg_agent.dump -Algorithm SHA256).Hash.ToLower()
if((Get-Item backend/data/runtime/backups/pre_0011_esg_agent.dump).Length -le 0){ throw 'database backup is empty' }
```

把备份目标路径、SHA256、大小、数据库名、迁移前head和生成时间登记到 `backend/data/manifests/assets_manifest.json`；不登记数据库密码或连接URL。

- [ ] **Step 2：先写领域和仓储失败测试**

领域测试构造：

```python
suggestion = AIAssessmentSuggestion(
    suggestion_id="ai-suggestion-1",
    assessment_id="assessment-1",
    run_id="run-1",
    status=AISuggestionStatus.SUCCEEDED,
    provider="deepseek",
    model="deepseek-v4-flash",
    prompt_version="deepseek-gri-assist-v1",
    input_hash="a" * 64,
    suggested_verdict=AssessmentVerdict.PARTIALLY_DISCLOSED,
    rationale_zh="存在部分直接证据，仍缺少范围说明。",
    missing_items_zh=["范围说明"],
    evidence_ids=["evidence-1"],
    evidence_pdf_pages=[41],
    confidence=0.78,
    guardrail_codes=[],
    usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
)
assert suggestion.review_status is None
```

仓储测试必须证明同一 assessment 可以追加多条不同 `prompt_version` 或时间的 suggestion，旧 suggestion 不更新、不删除。

- [ ] **Step 3：实现新增枚举和领域模型**

枚举固定为：

```python
class AISuggestionStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
```

`AIAssessmentSuggestion` 字段固定包括：身份字段、status、provider、model、prompt_version、input_hash、suggested_verdict、rationale_zh、missing_items_zh、evidence_ids、evidence_pdf_pages、confidence、guardrail_codes、usage、finish_reason、latency_ms、retry_count、error_code、error_message、raw_response、created_at。模型中不得出现可由AI赋值的人工复核状态或适用性字段。

- [ ] **Step 4：编写只追加迁移**

`0011` 必须：

- 为 `analysis_runs` 增加 `standard_unit_count`、`context_only_count`、`method_pending_count`，均为非负整数并保留现有 `eligible_requirement_count`；
- 为 `disclosure_tasks` 增加 `source_requirement_text`、`context_requirement_ids`、`structure_status`；
- 新建 `ai_assessment_suggestions`；
- 对 `(assessment_id, created_at DESC)`、`run_id`、`status` 建索引；
- upgrade 不回填推测的结构值，不删除历史列；
- downgrade 只删除本迁移新增表、索引和列，并在文档中标记会丢失 AI suggestion。

- [ ] **Step 5：实现 Repository 追加与查询接口**

接口固定为：

```python
def append_ai_suggestion(self, suggestion: AIAssessmentSuggestion) -> AIAssessmentSuggestion: ...
def get_latest_ai_suggestion(self, assessment_id: str) -> AIAssessmentSuggestion | None: ...
def list_ai_suggestions_for_run(self, run_id: str) -> list[AIAssessmentSuggestion]: ...
```

`append_ai_suggestion()` 遇到重复主键抛错，禁止 upsert。

- [ ] **Step 6：验证 migration 和仓储**

```powershell
cd backend
uv run --no-sync pytest tests/domain/test_models.py tests/db/test_repositories.py -q
uv run --no-sync alembic upgrade head
uv run --no-sync alembic current
```

期望：测试通过；current 为 `0011_standard_structure_and_ai_suggestions`。

### Task 4：切换运行时到493条独立判断并保留577结构范围

**Files:**
- Modify: `backend/src/domain/models.py`
- Modify: `backend/src/standards/gri.py`
- Modify: `backend/src/services/analysis_runner.py`
- Modify: `backend/src/workflows/single_report_workflow.py`
- Modify: `backend/src/tools/regenerate_review_csv.py`
- Modify: `backend/tests/tools/test_regenerate_review_csv.py`
- Modify: `backend/tests/standards/test_gri_adapter.py`
- Modify: `backend/tests/workflows/test_single_report_workflow.py`

- [ ] **Step 1：写 v2 Adapter 失败测试**

测试输入同时包含 `independent`、`context_only`、`method_pending`，断言：

```python
requirements = GRIAdapter(path).load_requirements()
assert [item.requirement_id for item in requirements] == ["GRI CHILD"]
assert requirements[0].requirement_text == "parent scope: child leaf;"
assert requirements[0].source_requirement_text == "child leaf;"
assert requirements[0].context_requirement_ids == ["GRI PARENT"]
assert requirements[0].structure_status == "normalized"
```

- [ ] **Step 2：扩展 requirement/task 数据契约**

`DisclosureRequirement` 和 `DisclosureTask` 增加：

```python
source_requirement_text: str
context_requirement_ids: list[str] = Field(default_factory=list)
structure_status: str
```

`requirement_text` 作为运行时完整有效文本；`source_requirement_text` 保留原始叶子文本。

- [ ] **Step 3：让 GRIAdapter 读取 v2 清单**

修改 `_is_current_gap_requirement()`，除现有条件外必须满足：

```python
item.get("evaluation_role") == "independent"
item.get("structure_status") in {"verified", "normalized"}
```

`analysis_runner.py` 的路径改为 `gri_requirement_checklist_v2.json`。禁止回退读取 v1；文件缺失或 metadata 计数不符时启动分析应失败并记录明确错误。

`regenerate_review_csv.py` 增加 `--requirements` 和 `--scope-summary-output` 参数。使用 v2 清单时从 metadata 读取 577/493/78/6，不再断言独立 assessment 必须为577；与 v1 baseline 比较时只比较 v2 中 `structure_status=verified` 的共同 ID。

- [ ] **Step 4：更新 run 统计与阶段进度**

每个新 run 固定写入：

```text
standard_unit_count=577
eligible_requirement_count=493
context_only_count=78
method_pending_count=6
```

`requirement_matching`、`evidence_assessment`、`risk_classification` 的 `total_units` 使用493；界面未来展示百分比时不会把577误当作待分析叶子数。

- [ ] **Step 5：运行 Adapter 与 workflow 测试**

```powershell
cd backend
uv run --no-sync pytest tests/standards/test_gri_adapter.py tests/workflows/test_single_report_workflow.py -q
```

期望：v2数量和阶段统计断言通过；`confirm_llm=false` 不出现外部调用。

### Task 5：加固 DeepSeek 客户端配置、JSON和重试

**Files:**
- Modify: `.env.example`
- Modify: `backend/.env.example`
- Modify: `backend/.env.demo.example`
- Modify: `backend/src/config/settings.py`
- Modify: `backend/src/tools/llm_client.py`
- Modify: `backend/tests/test_settings.py`
- Modify: `backend/tests/tools/test_llm_client.py`

- [ ] **Step 1：先写客户端失败测试**

测试覆盖：

- `confirm_llm=false` 时 completion factory 调用次数为0；
- `response_format={"type":"json_object"}` 被发送；
- Prompt messages 包含 system 和 user，且包含 `json` 和输出示例；
- thinking enabled 时发送 `extra_body={"thinking":{"type":"enabled"}}` 和 `reasoning_effort="high"`，不发送 temperature；
- `finish_reason="length"`、空 content、429、连接超时、500和503最多重试2次；
- 400、401、402和422不重试；
- 返回 metadata 包含 model、finish_reason、usage、latency_ms 和 retry_count；
- 日志及异常中不出现 API Key。

- [ ] **Step 2：增加非密钥配置**

示例文件使用：

```dotenv
OPENAI_COMPATIBLE_API_BASE=https://api.deepseek.com
OPENAI_COMPATIBLE_API_KEY=
LLM_MODEL=deepseek-v4-flash
LLM_THINKING_TYPE=enabled
LLM_REASONING_EFFORT=high
LLM_RESPONSE_FORMAT=json_object
LLM_MAX_TOKENS=4096
LLM_TIMEOUT_SECONDS=120
LLM_MAX_RETRIES=2
LLM_RETRY_DELAY_SECONDS=2
LLM_MAX_CONCURRENCY=8
LLM_MAX_CALLS_PER_RUN=200
LLM_PROMPT_VERSION=deepseek-gri-assist-v1
```

`Settings` 校验：Base URL 只接受 HTTPS；并发范围1—16；重试范围0—3；max tokens范围512—8192；生产配置检查只返回 `api_key_present`，不返回明文或长度。

- [ ] **Step 3：实现消息式调用结果**

客户端接口改为：

```python
class LLMCompletionResult(BaseModel):
    content: dict[str, Any]
    model: str
    finish_reason: str | None
    usage: dict[str, Any]
    latency_ms: int
    retry_count: int


def complete_json(
    self,
    *,
    messages: list[dict[str, str]],
    confirm_llm: bool,
) -> LLMCompletionResult: ...
```

JSON解析失败和空内容均按可重试输出错误处理；最终失败转成有明确 `error_code` 的领域异常。

- [ ] **Step 4：运行客户端和配置测试**

```powershell
cd backend
uv run --no-sync pytest tests/tools/test_llm_client.py tests/test_settings.py -q
```

期望：全部使用 fake client 通过，不发出网络请求。

### Task 6：实现证据约束的AI建议服务

**Files:**
- Modify: `backend/src/domain/ai_models.py`
- Create: `backend/src/services/ai_assessment_service.py`
- Create: `backend/tests/services/test_ai_assessment_service.py`

- [ ] **Step 1：写 AI 选择和 guardrail 失败测试**

必须覆盖：

```python
assert service.should_call(verified_high_with_direct_evidence) is True
assert service.should_call(normalized_medium_with_direct_evidence) is True
assert service.should_call(context_only_item) is False
assert service.should_call(method_pending_item) is False
assert service.should_call(low_priority_item) is False
assert service.should_call(no_evidence_item) is False
```

以及：

```python
suggestion = service.validate_response(
    response={
        "suggested_verdict": "disclosed",
        "evidence_ids": ["invented-evidence"],
        "evidence_pdf_pages": [999],
        "rationale_zh": "已完整披露。",
        "missing_items_zh": [],
        "confidence": 0.99,
    },
    allowed_evidence=[evidence_1],
)
assert suggestion.status == "failed"
assert "evidence_reference_out_of_scope" in suggestion.guardrail_codes
```

- [ ] **Step 2：实现固定 Prompt contract**

system message 必须明确：

- 输出纯 JSON；
- 只判断当前单条 requirement；
- 只引用输入 evidence ID；
- 索引、从略说明、章节封面和候选页不能单独支撑 disclosed；
- 无有效证据只能建议 unknown；
- partially_disclosed 必须至少有一个 missing item；
- 不得判断适用性、风险优先级、人工复核状态和合规认证；
- 中文理由只陈述输入证据能够支持的事实。

user message 固定包含：

```json
{
  "requirement_id": "GRI 403-9-d",
  "effective_requirement_text": "完整要求文本",
  "source_requirement_text": "原始叶子文本",
  "context_requirement_ids": ["GRI 403-9"],
  "rule_verdict": "partially_disclosed",
  "evidence": [
    {
      "evidence_id": "evidence-1",
      "source_pdf_page": 41,
      "evidence_type": "substantive_report_evidence",
      "quality_flags": [],
      "source_text": "限定长度的报告原文"
    }
  ],
  "required_json_output": {
    "suggested_verdict": "disclosed|partially_disclosed|unknown",
    "evidence_ids": [],
    "evidence_pdf_pages": [],
    "rationale_zh": "",
    "missing_items_zh": [],
    "confidence": 0.0
  }
}
```

单条 evidence `source_text` 最多1200字符，最多5条 evidence；总 Prompt 在发送前计算哈希并记录，不保存 API Key。

- [ ] **Step 3：实现响应校验和安全降级**

响应使用 Pydantic 严格枚举和范围校验。规则固定为：

- evidence ID 必须是输入集合子集；
- PDF 页码必须与引用 evidence 一一对应；
- `disclosed` 至少引用一条 `valid_direct` 或 substantive evidence，且不得只引用 omission/index；
- `partially_disclosed` 的 `missing_items_zh` 不得为空；
- `unknown` 可以没有 evidence；
- confidence 超出0—1直接失败；
-失败 suggestion 保存错误和 raw response，不改变规则 assessment。

- [ ] **Step 4：实现 bounded concurrency 和调用预算**

使用 `ThreadPoolExecutor(max_workers=settings.llm_max_concurrency)` 并发调用，数据库写入仍由 workflow 主线程顺序完成。任务按 `review_priority` 高到中、`requirement_id` 升序稳定排序；达到 `LLM_MAX_CALLS_PER_RUN` 后其余项写 `skipped + call_budget_exhausted`。

- [ ] **Step 5：运行 AI service 测试**

```powershell
cd backend
uv run --no-sync pytest tests/services/test_ai_assessment_service.py -q
```

期望：选择、Prompt、证据校验、失败降级、并发上限和预算全部通过；网络调用数由 fake client 精确断言。

### Task 7：接入工作流、API和导出

**Files:**
- Modify: `backend/src/services/analysis_runner.py`
- Modify: `backend/src/workflows/single_report_workflow.py`
- Modify: `backend/src/api/schemas.py`
- Modify: `backend/src/api/routes/assessments.py`
- Modify: `backend/src/api/routes/runs.py`
- Modify: `backend/src/services/export_service.py`
- Modify: `backend/src/tools/review_csv_export.py`
- Modify: `backend/tests/workflows/test_single_report_workflow.py`
- Modify: `backend/tests/api/test_assessments_api.py`
- Modify: `backend/tests/api/test_runs_api.py`
- Modify: `backend/tests/api/test_exports_api.py`
- Modify: `backend/tests/tools/test_review_csv_export.py`
- Regenerate: `frontend/lib/generated/api-types.ts`

- [ ] **Step 1：写 workflow 失败与降级测试**

测试必须证明：

1. `confirm_llm=false`：493条规则任务可完成，AI client调用0次，`ai_assistance`阶段状态为 `skipped`。
2. `confirm_llm=true` 且2条符合条件：只调用2次，规则 assessment 保持原 verdict，分别追加 suggestion。
3. 一个模型调用超时：run仍为 `completed` 或规则侧原有 `partially_completed`，AI阶段为 `partially_failed`，失败 suggestion 可查询。
4. 全部模型调用失败：规则结果仍完整，run不因AI失败变成 `failed`。
5. `model_called` 只对实际尝试调用的 assessment 为true；预算跳过和结构跳过为false。

- [ ] **Step 2：增加第八阶段 `ai_assistance`**

阶段顺序固定为：

```text
file_validation
pdf_parsing
report_structure
requirement_matching
evidence_assessment
risk_classification
ai_assistance
result_summary
```

`ai_assistance.total_units` 等于本次符合调用条件的条目数；关闭LLM时为 `skipped, 0/0`；失败只影响本阶段摘要。

- [ ] **Step 3：扩展 assessment detail 和 run API**

assessment detail 新增：

```json
{
  "source_requirement_text": "原始叶子文本",
  "effective_requirement_text": "完整有效文本",
  "context_requirement_ids": [],
  "structure_status": "verified|normalized|method_pending",
  "latest_ai_suggestion": null
}
```

run 新增结构统计和 AI 摘要：

```json
{
  "standard_unit_count": 577,
  "eligible_requirement_count": 493,
  "context_only_count": 78,
  "method_pending_count": 6,
  "ai_summary": {
    "eligible": 0,
    "succeeded": 0,
    "failed": 0,
    "skipped": 0
  }
}
```

旧字段和旧路由继续返回。

- [ ] **Step 4：扩展导出**

JSON/CSV/XLSX 输出增加 `structure_status`、`source_requirement_text`、`effective_requirement_text`、`ai_status`、`ai_suggested_verdict`、`ai_rationale_zh`、`ai_missing_items_zh`、`ai_evidence_pdf_pages`、`ai_model`、`ai_prompt_version`。正式导出页首注明：AI建议未经人工确认时不构成最终披露结论。

- [ ] **Step 5：运行 focused API 和 workflow 测试**

```powershell
cd backend
uv run --no-sync pytest tests/workflows/test_single_report_workflow.py tests/api/test_assessments_api.py tests/api/test_runs_api.py tests/api/test_exports_api.py -q
```

期望：全部通过，旧 API 响应字段仍存在。

- [ ] **Step 6：生成并验证前端 API 类型**

后端启动并提供 `/openapi.json` 后运行：

```powershell
cd frontend
pnpm generate:api
pnpm typecheck
```

期望：只更新生成类型及必要兼容调用，不在本计划开发 AI UI。

### Task 8：一次性完成225条DeepSeek人工基线评估

**Files:**
- Create: `backend/src/services/ai_evaluation_service.py`
- Create: `backend/src/tools/evaluate_deepseek_against_manual_review.py`
- Create: `backend/tests/services/test_ai_evaluation_service.py`
- Create: `backend/tests/tools/test_evaluate_deepseek_against_manual_review.py`
- Output local-only: `backend/data/runtime/evaluations/envision_2024/deepseek_225_evaluation.csv`
- Output local-only: `backend/data/runtime/evaluations/envision_2024/deepseek_225_evaluation_summary.json`
- Modify: `backend/data/manifests/assets_manifest.json`

- [ ] **Step 1：写评估读取和指标测试**

评估器只读取工作簿中：

```text
requirement_id
standard_verified
manual_applicability
suggested_verdict
evidence_validity
correct_pdf_pages
rationale_correct
missing_items_correct
review_complete
```

筛选条件为 `standard_verified=yes AND review_complete=complete`，预期225条。指标至少包括：

- `evaluated_count`；
- `exact_verdict_agreement_count/rate`；
- `false_disclosed_count`；
- `unsupported_evidence_reference_count`；
- `wrong_source_page_count`；
- `schema_failure_count`；
- `model_failure_count`；
- `rules_ai_disagreement_count`；
- 按人工 verdict 和系统 risk priority 的交叉分布。

- [ ] **Step 2：实现无网络 dry-run**

CLI 必须支持：

```powershell
uv run --no-sync python -m src.tools.evaluate_deepseek_against_manual_review `
  --review-workbook data/review_inputs/envision_2024/manual/envision_2024_577_manual_review_second_review_Pro_20260719.xlsx `
  --dry-run `
  --output-csv data/runtime/evaluations/envision_2024/deepseek_225_evaluation.csv `
  --output-summary data/runtime/evaluations/envision_2024/deepseek_225_evaluation_summary.json
```

CLI 从工作簿“核查说明”读取 `report_id` 和 `run_id`，并验证数据库中对应报告、run和assessment均存在。评估器以 v2 manifest 的 `effective_requirement_text` 作为标准输入，以工作簿固定 run 的 evidence 作为证据输入，禁止继续使用旧 task 中不完整的叶子文本。dry-run 输出225条选择清单、预计调用数和预计输入字符，不实例化 LLM client。

- [ ] **Step 3：运行 fake client 全量测试**

```powershell
cd backend
uv run --no-sync pytest tests/services/test_ai_evaluation_service.py tests/tools/test_evaluate_deepseek_against_manual_review.py -q
```

期望：模拟225条全部完成；重试、失败、越界引用和摘要计数均精确匹配 fixture。

- [ ] **Step 4：真实调用前人工停止点**

只输出以下非敏感检查：

```text
api_key_present=true
base_url=https://api.deepseek.com
model=deepseek-v4-flash
thinking=enabled
reasoning_effort=high
response_format=json_object
selected_count=225
max_concurrency=8
```

向用户报告预计发送字段、预计调用次数和预算上限。收到明确“批准真实225条评估”后继续；不显示 API Key 明文或长度。

- [ ] **Step 5：一次性运行真实225条评估**

```powershell
cd backend
uv run --no-sync python -m src.tools.evaluate_deepseek_against_manual_review `
  --review-workbook data/review_inputs/envision_2024/manual/envision_2024_577_manual_review_second_review_Pro_20260719.xlsx `
  --confirm-llm `
  --max-calls 225 `
  --output-csv data/runtime/evaluations/envision_2024/deepseek_225_evaluation.csv `
  --output-summary data/runtime/evaluations/envision_2024/deepseek_225_evaluation_summary.json
```

本步骤不进行30条或其他分批试点。

- [ ] **Step 6：执行AI硬门禁**

必须满足：

```text
evaluated_count=225
unsupported_evidence_reference_count=0
wrong_source_page_count=0
schema_failure_count=0
false_disclosed_count=0（guardrail后的最终AI建议）
```

允许记录模型原始建议被 guardrail 降级的数量。`exact_verdict_agreement_rate` 作为质量指标完整披露，不为追求比例而修改人工基线或硬编码答案。模型或网络失败可以重跑失败项，但必须保留第一次失败 suggestion 和 retry audit。

评估完成后，把两个输出文件的 `target_path`、SHA256、大小、模型、Prompt版本、固定报告/run和执行日期追加到 `backend/data/manifests/assets_manifest.json`；manifest不得包含API Key、完整Prompt或模型原始响应。

### Task 9：完成后端冻结回归和文档

**Files:**
- Modify: `README.md`
- Modify: `docs/DESIGN.md`
- Modify: `docs/DEVELOPMENT.md`
- Modify: `docs/product/api-contract.md`
- Modify: `docs/product/data-model-impact.md`
- Modify: `backend/src/tools/regenerate_review_csv.py`
- Modify: `backend/tests/tools/test_regenerate_review_csv.py`
- Modify: `docs/plan/deepseek-ai-backend-freeze-plan.md`
- Output local-only: `backend/data/runtime/evaluations/envision_2024/backend_freeze_acceptance_summary.json`

- [ ] **Step 1：运行全部 focused tests**

```powershell
cd backend
uv run --no-sync pytest tests/standards tests/tools/test_llm_client.py tests/services/test_ai_assessment_service.py tests/services/test_ai_evaluation_service.py tests/workflows/test_single_report_workflow.py tests/api/test_assessments_api.py tests/api/test_runs_api.py tests/api/test_exports_api.py -q
```

- [ ] **Step 2：重新生成 Envision v2 规则基线**

运行：

```powershell
cd backend
uv run --no-sync python -m src.tools.regenerate_review_csv `
  --report-id envision_2024_v2 `
  --pdf "data/reports/Envision Energy 2024-zh.pdf" `
  --profile data/reports/profiles/envision_2024.json `
  --requirements data/manifests/gri_requirement_checklist_v2.json `
  --output data/runtime/evaluations/envision_2024/current_493_review_regenerated.csv `
  --baseline data/review_inputs/envision_2024/baselines/current_577_review_regenerated.csv `
  --audit-output data/runtime/evaluations/envision_2024/current_493_review_regenerated_audit.json `
  --diff-summary-output data/runtime/evaluations/envision_2024/current_493_review_regeneration_diff_summary.json `
  --scope-summary-output data/runtime/evaluations/envision_2024/current_493_review_scope_summary.json `
  --report-total-pages 78
```

要求：

```text
standard_unit_count=577
independent_assessment_count=493
context_only_count=78
method_pending_count=6
unique_assessment_requirement_id_count=493
global_fallback_count=0
225条原standard_verified=yes项目无新增false disclosed或wrong source page
```

268条 normalized 项允许因完整文本产生规则变化，必须输出逐项 diff，不允许无解释的 evidence 页码越界。

- [ ] **Step 3：运行 Goldwind gate**

保持外部模型、OCR和VLM关闭。要求：

```text
false_disclosed_count=0
wrong_source_page_count=0
global_fallback_count=0
```

历史100条 gold 的口径因 context-only 排除发生变化时，报告新旧ID集合和可比样本数量，不伪造原100条可比结论。

- [ ] **Step 4：运行后端全量和前端兼容门禁**

```powershell
cd backend
uv run --no-sync pytest -q --basetemp=../tmp/pytest-ai-backend-final

cd ../frontend
pnpm test -- --run
pnpm typecheck
pnpm build
```

期望：全部通过；测试数量不得低于 Task 1 基线。

- [ ] **Step 5：更新文档事实**

文档必须明确：

- 当前数据库 head 为0011；
- 577标准核查单元、493独立判断项、78上下文项、6方法待确认项；
- DeepSeek只提供独立AI建议；
- 225条评估的真实指标、模型、Prompt版本和执行日期；
- AI失败降级行为；
- OCR/VLM仍未启用；
- 无GRI专家认证，结构修复属于双人复核支持的工程归一化；
- 前端AI交互仍等待下一计划实施。

同时生成 `backend/data/runtime/evaluations/envision_2024/backend_freeze_acceptance_summary.json`，记录结构计数、AI评估指标、Envision/Goldwind gate、后端/前端测试数量、数据库head、Git HEAD和所有最终验收产物SHA256。把最终验收产物和数据库备份的目标路径、SHA256、大小及用途登记到 `backend/data/manifests/assets_manifest.json`。

- [ ] **Step 6：提交后端冻结 checkpoint**

```powershell
git status --short
git diff --check
git add -- . ':!tmp'
git diff --cached --check
git commit -m "feat: freeze DeepSeek-assisted ESG analysis backend"
git status --short --branch
```

期望：工作区干净或只剩明确不提交的 `tmp/` 产物；仍在 `main`；不 push。

## 5. 完成判定

本计划只有同时满足以下条件才能标记完成：

- 当前确定性 MVP 已形成单独 checkpoint；
- v2结构数据可从指定人工工作簿确定性重建；
- 10个关键人工复核和规则基线资产已保存到项目目录并登记SHA256；
- 577/493/78/6计数通过；
- 数据库 head 为0011，迁移只追加；
- `confirm_llm=false` 完全离线；
- `confirm_llm=true` 只调用符合条件的条目；
- AI suggestion追加保存且不覆盖规则 assessment；
- 模型失败不会导致规则分析失败；
- 225条真实评估完成并通过证据、安全硬门禁；
- Envision、Goldwind、后端全量、前端兼容测试全部通过；
- 文档与OpenAPI事实同步；
- 225条AI评估CSV和摘要保存在项目运行时目录并登记SHA256；
- 未启用OCR/VLM，未删除旧API或历史数据，未push。

## 6. 下一计划入口

完成本计划全部执行后，才创建下一份计划。下一计划只处理：

- 上传/metadata页的“启用AI辅助分析”确认；
- 八阶段进度中的“AI辅助分析”；
- 规则结论、AI建议、人工结论三层展示；
- AI证据定位、采纳/修改/拒绝操作；
- 完整浏览器产品验收和最终MVP交付说明。
