# Envision 577 项最终裁决与后端冻结实施计划

> **For agentic workers（执行要求）：** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` 按任务顺序实施；使用 checkbox 跟踪步骤。保持 `main` inline 执行，不创建分支或 worktree，不自动 push。所有结构、规则和展示修改使用 TDD；原始报告、Sol/Pro 工作簿和历史 baseline 只读保留。

**Goal（目标）：** 将 Envision 2024 中文报告统一收敛为“577 项 GRI 核查”产品口径，完成 6 条结构方法裁决和 16 条结果差异裁决，形成可追溯、无公开未决项的 MVP 后端冻结基线 v1.1。

**Architecture（架构）：** 保留 577 个来源核查单元，不拆增来源行；6 条合并提取项通过版本化“复合完整性判断”裁决转为独立 assessment，内部结构收敛为 499 个独立判断项、78 个上下文项、0 个方法待确认项。新增只读的 577 项范围接口，将独立 assessment 与上下文单元统一展示和导出；规则 assessment、AI suggestion、人工 snapshot 继续分层且只追加。16 条 Sol/Pro 差异写入独立最终裁决资产，不覆盖原工作簿，并作为 Envision 冻结回归的最终人工基准。

**Tech Stack（技术栈）：** Python 3.11、FastAPI、Pydantic、SQLAlchemy、PostgreSQL、openpyxl、pypdf/pdfplumber、Pytest、Next.js App Router、React 19、TypeScript、TanStack Query、Vitest、OpenAPI 类型生成、普通 Chrome。

**执行状态：** 执行中。Task 0 已完成，现场、资产、数据库迁移和服务状态符合预期。

---

## 一、最终产品口径

### 1. 唯一公开总数

普通产品页面、演示材料、管理层输出和简历只使用：

```text
完成远景能源 2024 中文报告的 577 项 GRI 核查。
```

禁止在普通产品界面并列宣传 `493 / 499 / 78 / 6 / 16 / 225 / 352 / 541 / 627`。这些数字只允许出现在内部技术、测试或审计材料中。

### 2. 内部结构

冻结后的结构必须满足：

```text
standard_unit_count = 577
independent_assessment_count = 499
context_only_count = 78
method_pending_count = 0
compound_adjudicated_count = 6
```

解释：

- 499 个独立判断项生成 assessment、verdict、证据状态、适用性和复核优先级；
- 78 个上下文项不生成独立 verdict，通过 `context_requirement_ids` 纳入对应独立判断；
- 6 个原 `merge_split_error` 项改为复合完整性判断，包含多个官方组成要求；
- 产品范围接口和完整核查输出覆盖全部 577 个单元；
- 高中低优先级、AI 建议和人工复核只作用于 499 个独立判断项。

### 3. 复合完整性判断规则

6 个最终裁决如下：

| Requirement | 最终角色 | 官方组成要求 | 冻结规则 |
| --- | --- | --- | --- |
| `GRI 302-1-c` | `independent` | 电力、供热、制冷、蒸汽消费 | 四项全部有直接证据才能 `disclosed`；部分存在为 `partially_disclosed` |
| `GRI 302-1-d` | `independent` | 电力、供热、制冷、蒸汽销售 | 四项全部有直接证据才能 `disclosed`；部分存在为 `partially_disclosed` |
| `GRI 304-4-a` | `independent` | 五类灭绝风险等级 | 五类全部覆盖才能 `disclosed`；部分存在为 `partially_disclosed` |
| `GRI 305-3-d` | `independent` | 官方 `305-3-c` 生物源 CO₂ 与 `305-3-d` Scope 3 类别/活动 | 记录 `component_requirement_ids=["GRI 305-3-c","GRI 305-3-d"]` |
| `GRI 305-5-c` | `independent` | 官方 `305-5-b` 基准年/理由与 `305-5-c` 气体种类 | 记录 `component_requirement_ids=["GRI 305-5-b","GRI 305-5-c"]` |
| `GRI 305-7-a` | `independent` | NOx、SOx、POPs、VOCs、HAP、PM、其他重大空气排放 | 七类全部覆盖才能 `disclosed`；部分存在为 `partially_disclosed` |

原始 `requirement_id` 保持不变，避免破坏历史数据、证据路由和旧 API；官方组成通过新 manifest 字段表达。该裁决称为“产品方法裁决”，不称为 GRI 官方或专家认证。

### 4. 16 条最终结果裁决

最终裁决资产必须包含下表，不能继续把这些 ID 全部标为 `adjudication_pending`：

| Requirement | 最终适用性 | 最终 verdict | PDF 页 | 最终处理 |
| --- | --- | --- | --- | --- |
| `GRI 2-17-a` | `applicable` | `unknown` | `[]` | 采纳 Pro；报告未明确董事会/最高治理机构能力建设 |
| `GRI 2-20-b` | `undetermined` | `unknown` | `[]` | 条件适用性需要企业事实；`decision_basis=requires_company_confirmation` |
| `GRI 2-22-a` | `applicable` | `disclosed` | `[4,9]` | 声明与 CEO 身份组合形成证据 |
| `GRI 2-23-d` | `applicable` | `unknown` | `[]` | 未逐项披露政策批准层级 |
| `GRI 201-1-b` | `undetermined` | `unknown` | `[]` | “重大”触发条件需要企业确认；`decision_basis=requires_company_confirmation` |
| `GRI 203-2-a` | `applicable` | `partially_disclosed` | `[4,12,42,43,44]` | 有正面实例，缺少重大负面实例 |
| `GRI 303-3-d` | `applicable` | `partially_disclosed` | `[25,63]` | 有数据背景，编制方法不完整 |
| `GRI 303-4-e` | `applicable` | `partially_disclosed` | `[22,25,63]` | 有排水分类/处理/数据，方法和假设不完整 |
| `GRI 303-5-d` | `applicable` | `partially_disclosed` | `[25,63]` | 数据可核对，来源和测量方法不完整 |
| `GRI 305-2-c` | `undetermined` | `unknown` | `[]` | “如数据可得”需要企业确认；`decision_basis=requires_company_confirmation` |
| `GRI 305-3-b` | `undetermined` | `unknown` | `[]` | “如数据可得”需要企业确认；`decision_basis=requires_company_confirmation` |
| `GRI 306-3-b` | `applicable` | `unknown` | `[]` | 一般数字化流程不能替代废弃物数据编制方法证据 |
| `GRI 306-4-e` | `applicable` | `unknown` | `[]` | 一般数字化流程不能替代废弃物转移数据编制方法证据 |
| `GRI 403-9-d` | `applicable` | `disclosed` | `[41]` | 控制层级行动有直接证据 |
| `GRI 403-9-e` | `applicable` | `disclosed` | `[67]` | 百万工时 TRIR/LTIR 直接给出计算基数 |
| `GRI 414-1-a` | `applicable` | `disclosed` | `[67]` | 100% 社会评价维度筛选；修正矛盾 rationale/missing-items |

4 个 `undetermined` 是合法终态，配合 `decision_basis=requires_company_confirmation` 表示“产品裁决已经完成，但企业事实仍待确认”，不再称为 Sol/Pro 未决。继续使用现有 `ApplicabilityStatus.UNDETERMINED`，不增加枚举或数据库字段。

---

## 二、硬性边界与停止条件

### 1. 禁止事项

- 不覆盖或修改 `envision_2024_577_manual_review_second_review_Pro_20260719.xlsx`；
- 不覆盖或删除 Sol、Pro 原始判断；
- 不覆盖 `gri_requirement_checklist_v2.json` 和 `gri_requirement_structure_v2.json`；
- 不清空数据库，不删除已有 report/run/snapshot/export；
- 不删除旧 `review_decisions`、旧 API 或旧页面；
- 不改变 risk-v2.1；
- 不改变 DeepSeek Prompt、模型、guardrail 或调用范围；
- 不启用 OCR 或 VLM；
- 不调用真实外部模型，除非用户在执行阶段再次明确批准；
- 不运行 Goldwind 新回归，Goldwind 保持低优先级历史证据；
- 不自动 push。

### 2. 必须暂停并报告

出现以下任一情况立即暂停：

1. 分支不是 `main`；
2. 存在无法隔离的非本计划工作区改动；
3. 关键源资产 SHA256 与 manifest 不一致；
4. PDF 第 4、9、41、67 页视觉事实与裁决表矛盾；
5. v3 编译结果不是 `577 / 499 / 78 / 0`；
6. 需要新增数据库 migration 才能完成；
7. Envision gate 出现新增 false disclosed 或新增 wrong source page；
8. 规则修复造成非目标 requirement verdict delta；
9. 需要真实 DeepSeek、OCR 或 VLM 才能继续；
10. 任何操作可能覆盖原始 PDF、人工工作簿或历史审计记录。

### 3. 原始资产保护

执行前后必须计算并核对：

```powershell
Get-FileHash "backend/data/reports/Envision Energy 2024-zh.pdf" -Algorithm SHA256
Get-FileHash "backend/data/review_inputs/envision_2024/manual/envision_2024_577_manual_review_second_review_Pro_20260719.xlsx" -Algorithm SHA256
```

期望：

```text
PDF: 57360dcda8e6256726be5d2a49f8921e13187b40ae44661549903f702df38068
Workbook: f1eeb37444de1eeda86b8ae0813dbfd6e88c94719781b98a8de659d9fbd7ddea
```

---

## 三、文件职责

### 新增文件

| 文件 | 职责 |
| --- | --- |
| `backend/data/review_inputs/envision_2024/adjudication/envision_2024_compound_structure_adjudication_v1.csv` | 6 条复合结构裁决 |
| `backend/data/review_inputs/envision_2024/adjudication/envision_2024_result_adjudication_v1.csv` | 16 条最终结果裁决 |
| `backend/data/manifests/gri_requirement_structure_v3.json` | 577 项 v3 结构决策与来源哈希 |
| `backend/data/manifests/gri_requirement_checklist_v3.json` | 运行时 v3 编译清单 |
| `backend/src/services/requirement_scope_service.py` | 将 577 个 manifest 单元与当前 run assessment 合并为产品范围行 |
| `backend/tests/services/test_requirement_scope_service.py` | 577 范围合并、上下文状态和分页测试 |

### 修改文件

| 文件 | 职责 |
| --- | --- |
| `backend/src/standards/requirement_structure.py` | 支持已裁决复合结构和官方组成 IDs |
| `backend/src/tools/build_requirement_structure_v2.py` | 读取独立裁决 CSV，生成 v3 资产；保留旧入口兼容 |
| `backend/tests/standards/test_requirement_structure.py` | 复合裁决角色和校验测试 |
| `backend/tests/tools/test_build_requirement_structure_v2.py` | v3 计数、来源哈希、原文件不覆盖测试 |
| `backend/src/standards/gri.py` | 识别 v3 manifest，分析 499 个独立项并提供 577 范围项 |
| `backend/src/services/analysis_runner.py` | 运行时切换到 v3 清单 |
| `backend/tests/standards/test_gri_adapter.py` | v3 的 `577/499/78/0` 验证 |
| `backend/src/services/ai_evaluation_service.py` | 加载最终裁决资产并覆盖评估基准视图，不修改原工作簿 |
| `backend/src/tools/evaluate_deepseek_against_manual_review.py` | 使用最终裁决，待裁决计数归零 |
| `backend/tests/services/test_ai_evaluation_service.py` | 16 条覆盖、唯一性和非法值测试 |
| `backend/tests/tools/test_evaluate_deepseek_against_manual_review.py` | CLI 默认最终裁决资产测试 |
| `backend/src/agents/disclosure_agent.py` | 2-22、303 方法项、403-9-d、414-1-a 的最小规则修复 |
| `backend/src/standards/evidence_contracts.py` | 证据页、证据类型、rationale 和 missing-items 契约修复 |
| `backend/tests/agents/test_disclosure_agent.py` | 目标 requirement verdict/证据回归 |
| `backend/src/api/schemas.py` | 新增 577 范围行 DTO 和 dashboard `standard_unit_count` |
| `backend/src/api/routes/assessments.py` | 新增 `GET /api/reports/{report_id}/scope-items` |
| `backend/tests/api/test_assessments_api.py` | 577 总数、上下文行无伪 verdict、稳定分页测试 |
| `backend/src/services/export_service.py` | assessment XLSX/print HTML 覆盖 577 范围行 |
| `backend/tests/api/test_exports_api.py` | 577 行输出、上下文状态和免责声明测试 |
| `frontend/lib/api.ts` | 调用 577 范围接口 |
| `frontend/lib/types.ts` | 暴露 OpenAPI 生成的范围类型 |
| `frontend/components/analysis/assessment-table.tsx` | 展示 577 项完整范围，只有独立项可进入复核 |
| `frontend/components/analysis/assessment-table.test.tsx` | 577 总数、上下文行和分页测试 |
| `frontend/components/analysis/report-dashboard.tsx` | 只显示“核查范围 577 项” |
| `frontend/components/analysis/report-dashboard.test.tsx` | 单一口径测试 |
| `docs/DESIGN.md` | 冻结 v1.1、复合裁决和 577 口径 |
| `docs/DEVELOPMENT.md` | v3 构建、验证和验收命令 |
| `docs/product/api-contract.md` | 范围接口与公开/内部字段边界 |
| `docs/product/data-model-impact.md` | 明确无新 migration，内部计数字段继续兼容 |
| `docs/product/page-architecture.md` | 577 项完整核查页面 |
| `docs/product/mvp-acceptance-report.md` | 最终冻结事实和限制 |
| `backend/data/manifests/assets_manifest.json` | 新裁决和 v3 资产 SHA256 |

---

## 四、实施任务

### Task 0：冻结前现场与资产校验

**Files：** 只读，无修改。

- [x] **Step 1：确认 Git 和数据库状态**

```powershell
git branch --show-current
git status --short
git rev-parse HEAD
cd backend
uv run --no-sync alembic current
```

期望：

- 分支为 `main`；
- 工作区干净；
- Alembic 为 `0011_ai_suggestions (head)`；
- 不执行 pull、reset、clean 或数据库清理。

- [x] **Step 2：校验原始资产 SHA256**

运行本计划“原始资产保护”中的两个 `Get-FileHash` 命令。任一不匹配立即停止。

- [x] **Step 3：确认服务环境**

```powershell
Invoke-RestMethod http://localhost:8000/api/health
Invoke-WebRequest http://localhost:3000 -UseBasicParsing
```

期望：后端 `{"status":"ok"}`，前端 HTTP 200。服务未运行时只按 `docs/DEVELOPMENT.md` 启动，不重建或清空数据库。

### Task 1：建立只追加的最终裁决资产

**Files：**

- Create: `backend/data/review_inputs/envision_2024/adjudication/envision_2024_compound_structure_adjudication_v1.csv`
- Create: `backend/data/review_inputs/envision_2024/adjudication/envision_2024_result_adjudication_v1.csv`
- Modify: `backend/data/manifests/assets_manifest.json`

- [x] **Step 1：创建结构裁决 CSV**

列固定为：

```csv
requirement_id,final_evaluation_role,component_requirement_ids,completeness_policy,adjudication_rationale,adjudicator_role,adjudication_version
```

必须写入本计划第一部分的 6 条；`final_evaluation_role` 全部为 `independent`，`adjudicator_role=product_method_owner`，`adjudication_version=envision-method-v1.1`。`component_requirement_ids` 使用 JSON 数组，至少包含当前官方组成；完整性策略固定为：

```text
all components supported => disclosed;
some components supported => partially_disclosed;
no valid component evidence => unknown
```

- [x] **Step 2：创建结果裁决 CSV**

列固定为：

```csv
requirement_id,final_applicability,final_verdict,final_pdf_pages,final_evidence_validity,final_rationale,final_missing_items,decision_basis,adjudicator_role,adjudication_version
```

写入本计划第一部分的 16 条。`final_pdf_pages` 和 `final_missing_items` 使用 JSON 数组。`adjudicator_role=product_method_owner`，`adjudication_version=envision-result-v1.1`。

- [x] **Step 3：视觉复核关键 PDF 页**

使用项目 `pdf` 技能和 Poppler 渲染 PDF 第 4、9、41、67 页，保存临时图像到 `tmp/envision-freeze-v1.1/pdf-review/`，检查：

- 第 4 页存在最高治理机构或最高管理者的可持续发展声明；
- 第 9 页能证明声明签署人的 CEO/最高管理者身份；
- 第 41 页存在消除、替代、工程控制、行政管理、个体防护等控制层级行动；
- 第 67 页存在“百万工时 TRIR/LTIR”和“社会评价维度筛选的新供应商百分比 100%”。

临时渲染图不提交。事实不一致立即停止，不调整裁决去迎合预期。

- [x] **Step 4：登记资产**

为两个 CSV 记录相对路径、SHA256、大小、日期、用途和“原始工作簿未修改”说明。

- [x] **Step 5：提交裁决资产 checkpoint**

```powershell
git add backend/data/review_inputs/envision_2024/adjudication backend/data/manifests/assets_manifest.json
git diff --cached --check
git commit -m "data: adjudicate Envision structure and review differences"
```

### Task 2：TDD 支持复合结构裁决

**Files：**

- Modify: `backend/src/standards/requirement_structure.py`
- Modify: `backend/src/tools/build_requirement_structure_v2.py`
- Test: `backend/tests/standards/test_requirement_structure.py`
- Test: `backend/tests/tools/test_build_requirement_structure_v2.py`

- [x] **Step 1：先写失败测试**

新增测试断言：

```python
def test_compound_adjudication_becomes_independent_with_components():
    decision = RequirementStructureDecision(
        requirement_id="GRI 302-1-c",
        issue_code="compound_requirement_adjudicated",
        source_note="product method adjudication",
        component_requirement_ids=[
            "GRI 302-1-c-i",
            "GRI 302-1-c-ii",
            "GRI 302-1-c-iii",
            "GRI 302-1-c-iv",
        ],
        adjudication_version="envision-method-v1.1",
    )
    assert decision.evaluation_role is EvaluationRole.INDEPENDENT
```

构建器测试必须断言：

```python
assert metadata["standard_unit_count"] == 577
assert metadata["independent_assessment_count"] == 499
assert metadata["context_only_count"] == 78
assert metadata["method_pending_count"] == 0
assert metadata["compound_adjudicated_count"] == 6
```

- [x] **Step 2：运行红灯测试**

```powershell
cd backend
uv run --no-sync pytest tests/standards/test_requirement_structure.py tests/tools/test_build_requirement_structure_v2.py -q --basetemp=../tmp/pytest-envision-577-structure-red
```

期望：因不支持 `compound_requirement_adjudicated`、组件字段和裁决 CSV 而失败。

- [x] **Step 3：实现最小结构扩展**

在 `RequirementStructureDecision` 增加（同时从 Pydantic 导入 `Field`）：

```python
component_requirement_ids: list[str] = Field(default_factory=list)
adjudication_version: str | None = None
```

为 `_ROLE_BY_ISSUE` 增加：

```python
"compound_requirement_adjudicated": EvaluationRole.INDEPENDENT
```

校验规则：

- 复合裁决必须至少有两个 `component_requirement_ids`；
- 必须有 `adjudication_version`；
- 组件 ID 不允许重复；
- 普通结构决策不允许携带组件 IDs；
- 编译结果写入 `component_requirement_ids`；
- `structure_status` 使用现有 `normalized`，避免扩大 API 枚举；
- `structure_issue_codes` 保留 `compound_requirement_adjudicated`。

- [x] **Step 4：让构建器读取裁决 CSV**

为 `build_requirement_structure_assets` 增加参数：

```python
structure_adjudication_csv: str | Path | None = None
manifest_version: str = "gri-requirement-checklist-v3"
```

加载后只允许覆盖 `issue_code=merge_split_error` 的 6 条，其他 ID、重复 ID、缺失 ID、非 independent 最终角色均报错。原工作簿读出的决策和裁决 CSV 均保留在结构 manifest 的 provenance 中。

- [x] **Step 5：运行绿灯测试**

```powershell
uv run --no-sync pytest tests/standards/test_requirement_structure.py tests/tools/test_build_requirement_structure_v2.py -q --basetemp=../tmp/pytest-envision-577-structure-green
```

期望：全部通过。

### Task 3：生成并启用 v3 清单

**Files：**

- Create: `backend/data/manifests/gri_requirement_structure_v3.json`
- Create: `backend/data/manifests/gri_requirement_checklist_v3.json`
- Modify: `backend/src/standards/gri.py`
- Modify: `backend/src/services/analysis_runner.py`
- Modify: `backend/tests/standards/test_gri_adapter.py`
- Modify: `backend/data/manifests/assets_manifest.json`

- [x] **Step 1：写 v3 adapter 失败测试**

测试文档使用：

```json
{
  "metadata": {
    "manifest_version": "gri-requirement-checklist-v3",
    "standard_unit_count": 577,
    "independent_assessment_count": 499,
    "context_only_count": 78,
    "method_pending_count": 0,
    "compound_adjudicated_count": 6
  }
}
```

断言：

- `load_requirements()` 只返回 499 个 independent；
- `load_scope_items()` 返回 577 个 current-scope 单元；
- 复合项携带组件 IDs；
- metadata 与实际统计不一致时抛出 `invalid GRI v3 structure counts`。

- [x] **Step 2：运行红灯测试**

```powershell
uv run --no-sync pytest tests/standards/test_gri_adapter.py -q --basetemp=../tmp/pytest-envision-577-adapter-red
```

- [x] **Step 3：实现 v3 adapter**

保留 v1/v2 兼容读取；增加 `gri-requirement-checklist-v3` 校验。新增：

```python
def load_scope_items(self) -> list[dict[str, Any]]:
    """Return all 577 current-scope units without turning context rows into assessments."""
```

`load_requirements()` 继续只返回 `evaluation_role=independent` 且 `structure_status in {"verified","normalized"}` 的项目。

- [x] **Step 4：生成 v3 资产**

```powershell
uv run --no-sync python -m src.tools.build_requirement_structure_v2 `
  --review-workbook data/review_inputs/envision_2024/manual/envision_2024_577_manual_review_second_review_Pro_20260719.xlsx `
  --source-checklist data/manifests/gri_requirement_checklist.json `
  --structure-adjudication-csv data/review_inputs/envision_2024/adjudication/envision_2024_compound_structure_adjudication_v1.csv `
  --output-structure data/manifests/gri_requirement_structure_v3.json `
  --output-checklist data/manifests/gri_requirement_checklist_v3.json
```

期望输出包含：

```json
{
  "standard_unit_count": 577,
  "independent_assessment_count": 499,
  "context_only_count": 78,
  "method_pending_count": 0,
  "compound_adjudicated_count": 6
}
```

- [x] **Step 5：切换运行入口**

将 `GRI_REQUIREMENTS_PATH` 改为 `gri_requirement_checklist_v3.json`。不回退读取 v2；v3 缺失或计数错误时分析应明确失败。

- [x] **Step 6：登记新资产并提交**

```powershell
git add backend/src/standards backend/src/services/analysis_runner.py backend/src/tools/build_requirement_structure_v2.py backend/tests/standards backend/tests/tools/test_build_requirement_structure_v2.py backend/data/manifests/gri_requirement_*_v3.json backend/data/manifests/assets_manifest.json
git diff --cached --check
git commit -m "feat: adjudicate 577-unit GRI structure"
```

### Task 4：将 16 条最终裁决变成冻结回归基准

**Files：**

- Modify: `backend/src/services/ai_evaluation_service.py`
- Modify: `backend/src/tools/evaluate_deepseek_against_manual_review.py`
- Modify: `backend/src/tools/regenerate_review_csv.py`
- Test: `backend/tests/services/test_ai_evaluation_service.py`
- Test: `backend/tests/tools/test_evaluate_deepseek_against_manual_review.py`
- Test: `backend/tests/tools/test_regenerate_review_csv.py`

- [x] **Step 1：写失败测试**

新增：

```python
def test_final_adjudication_overlays_manual_baseline_without_mutating_workbook():
    baseline = load_manual_review_baseline(workbook_path, expected_count=225)
    final = load_final_adjudications(adjudication_csv)
    resolved = apply_final_adjudications(baseline, final)
    assert resolved.by_id["GRI 2-17-a"].suggested_verdict is AssessmentVerdict.UNKNOWN
    assert resolved.by_id["GRI 2-22-a"].correct_pdf_pages == [4, 9]
    assert resolved.by_id["GRI 305-2-c"].manual_applicability == (
        "undetermined"
    )
    assert sha256(workbook_path.read_bytes()).hexdigest() == original_hash
```

还要测试：

- 恰好 16 个唯一 ID；
- 所有 ID 存在于 577 清单；
- verdict、适用性和页码类型合法；
- 16 条全部覆盖后 `adjudication_pending_count=0`；
- 未列入裁决的 209 条 baseline 记录保持逐字段一致。

- [x] **Step 2：运行红灯测试**

```powershell
uv run --no-sync pytest tests/services/test_ai_evaluation_service.py tests/tools/test_evaluate_deepseek_against_manual_review.py tests/tools/test_regenerate_review_csv.py -q --basetemp=../tmp/pytest-envision-adjudication-red
```

- [x] **Step 3：实现只读 overlay**

新增：

```python
def load_final_adjudications(path: Path) -> dict[str, FinalAdjudicationRecord]: ...
def apply_final_adjudications(
    baseline: ManualReviewBaseline,
    adjudications: dict[str, FinalAdjudicationRecord],
) -> ManualReviewBaseline: ...
```

不得写回 Excel。AI evaluation CLI 将旧 `--adjudication-recommendations` 保留为兼容参数，新增 `--final-adjudications`；Envision 默认使用 v1.1 最终裁决 CSV，待裁决 ID 集合为空。

`regenerate_review_csv.py` 同样新增可选参数：

```text
--final-adjudications data/review_inputs/envision_2024/adjudication/envision_2024_result_adjudication_v1.csv
```

`write_diff_summary` 先加载原工作簿，再应用 final adjudication overlay，确保 16 条用最终裁决参与 false disclosed 和 wrong source page gate；没有传入该参数时保持旧行为。

- [x] **Step 4：运行绿灯测试并提交**

```powershell
uv run --no-sync pytest tests/services/test_ai_evaluation_service.py tests/tools/test_evaluate_deepseek_against_manual_review.py tests/tools/test_regenerate_review_csv.py -q --basetemp=../tmp/pytest-envision-adjudication-green
git add backend/src/services/ai_evaluation_service.py backend/src/tools/evaluate_deepseek_against_manual_review.py backend/src/tools/regenerate_review_csv.py backend/tests/services/test_ai_evaluation_service.py backend/tests/tools/test_evaluate_deepseek_against_manual_review.py backend/tests/tools/test_regenerate_review_csv.py
git commit -m "feat: apply final Envision product adjudications"
```

### Task 5：对齐确定性规则与最终裁决

**Files：**

- Modify: `backend/src/agents/disclosure_agent.py`
- Modify: `backend/src/standards/evidence_contracts.py`
- Test: `backend/tests/agents/test_disclosure_agent.py`

- [x] **Step 1：写目标回归测试**

使用真实页文本 fixture 或最小等价文本，断言：

- `GRI 2-22-a` 组合第 4 页声明和第 9 页 CEO 身份后为 `disclosed`；
- `GRI 303-3-d`、`303-4-e`、`303-5-d` 有数据背景但无完整方法时为 `partially_disclosed`；
- `GRI 306-3-b`、`306-4-e` 的一般数字化流程文本不能升级为 partial；
- `GRI 403-9-d` 的控制层级行动为 `disclosed`；
- `GRI 403-9-e` 只接受第 67 页百万工时方法证据；
- `GRI 414-1-a` 第 67 页 100% 社会评价筛选为 `disclosed`，rationale 不再引用第 31 页 85 家审核，missing-items 为空。

- [x] **Step 2：运行红灯测试**

```powershell
uv run --no-sync pytest tests/agents/test_disclosure_agent.py -q --basetemp=../tmp/pytest-envision-rules-red
```

- [x] **Step 3：最小规则修复**

只修改上述 requirement：

- 将 `GRI 2-22-a` 从通用 `current_150_partial_items` 移出，允许页 4、9 组合；
- 为 303 三个方法项增加“有对应数据背景但方法不完整”的 partial 分支；
- 306 两项继续要求废弃物编制方式的直接证据；
- 将 `GRI 403-9-d` 证据契约改为管理机制/控制层级语义，限定正确页；
- 保持 `GRI 403-9-e` 第 67 页方法证据；
- 更新 `GRI 414-1-a` 契约 rationale 和 missing-items。

禁止加入比例硬编码或依赖 report_id 的条件。

- [x] **Step 4：运行目标和邻近回归**

```powershell
uv run --no-sync pytest tests/agents/test_disclosure_agent.py tests/standards/test_evidence_contracts.py tests/standards/test_no_evidence_guardrails.py -q --basetemp=../tmp/pytest-envision-rules-green
```

期望：全部通过，非目标 requirement 无 verdict delta。

- [x] **Step 5：提交**

```powershell
git add backend/src/agents/disclosure_agent.py backend/src/standards/evidence_contracts.py backend/tests/agents/test_disclosure_agent.py
git commit -m "fix: align Envision rules with final adjudication"
```

### Task 6：提供真正的 577 项范围接口

**Files：**

- Create: `backend/src/services/requirement_scope_service.py`
- Create: `backend/tests/services/test_requirement_scope_service.py`
- Modify: `backend/src/api/schemas.py`
- Modify: `backend/src/api/routes/assessments.py`
- Modify: `backend/tests/api/test_assessments_api.py`

- [x] **Step 1：写服务和 API 失败测试**

DTO 结构固定为：

```python
class RequirementScopeItemResponse(BaseModel):
    requirement_id: str
    gri_topic: str
    unit_status: Literal["assessed", "context_incorporated"]
    source_requirement_text: str
    effective_requirement_text: str
    component_requirement_ids: list[str]
    incorporated_into_requirement_ids: list[str]
    assessment_id: str | None
    effective_verdict: str | None
    review_priority: str | None
    review_status: str | None
    source_pdf_pages: list[int]
```

分页响应包含 `items/page/page_size/total`。测试断言：

- total 恒为当前 run 的 `standard_unit_count=577`；
- 499 行 `unit_status=assessed` 且有 assessment；
- 78 行 `unit_status=context_incorporated` 且 verdict/risk/review 均为空；
- 上下文行通过反向 `context_requirement_ids` 列出被纳入的独立判断；
- 不生成伪 assessment；
- 自然排序和分页稳定。

- [x] **Step 2：运行红灯测试**

```powershell
uv run --no-sync pytest tests/services/test_requirement_scope_service.py tests/api/test_assessments_api.py -q --basetemp=../tmp/pytest-envision-scope-red
```

- [x] **Step 3：实现范围服务**

服务读取 v3 manifest，按 canonical requirement ID 与最新有效 run assessments 合并。没有 run 时返回结构范围但 assessment 字段为空；run 与 manifest 计数不一致时抛出明确错误，不降级为 499。

- [x] **Step 4：增加 API**

```text
GET /api/reports/{report_id}/scope-items?page=1&page_size=50
```

旧 `/assessments` 保留不变。Dashboard 增加 `standard_unit_count`，从最新 run 读取；历史 run 字段为空时使用实际 manifest 范围，不伪造旧结构细分。

- [x] **Step 5：运行绿灯测试并生成 OpenAPI**

```powershell
uv run --no-sync pytest tests/services/test_requirement_scope_service.py tests/api/test_assessments_api.py tests/api/test_openapi_contract.py -q --basetemp=../tmp/pytest-envision-scope-green
cd ../frontend
pnpm generate:api
pnpm typecheck
```

- [x] **Step 6：提交**

```powershell
git add backend/src/services/requirement_scope_service.py backend/src/api backend/tests/services/test_requirement_scope_service.py backend/tests/api frontend/lib/generated/api-types.ts
git commit -m "feat: expose complete 577-unit GRI scope"
```

### Task 7：让导出覆盖 577 项

**Files：**

- Modify: `backend/src/services/export_service.py`
- Modify: `backend/tests/api/test_exports_api.py`

- [x] **Step 1：写失败测试**

断言 assessment XLSX 和 print HTML：

- 总范围行数为 577；
- 499 行包含 verdict；
- 78 行显示“已作为上下文纳入相关判断”；
- 上下文行不显示伪风险、伪复核状态或伪证据；
- 文件顶部包含“AI 建议未经人工确认时不构成最终披露结论”；
- `review_scope.standard_unit_total=577`；
- `review_scope.human_reviewed_total` 只计算真实 assessment；
- 文案不出现“全部 577 项均已人工确认”。

- [x] **Step 2：运行红灯测试**

```powershell
cd backend
uv run --no-sync pytest tests/api/test_exports_api.py -q --basetemp=../tmp/pytest-envision-export-red
```

- [x] **Step 3：实现 scope rows**

复用 `RequirementScopeService`，不要在 export service 复制 manifest 合并逻辑。`assessment_xlsx` 和 `print_html` 使用 577 行；管理层摘要只显示“核查范围 577 项”和动态复核百分比。

- [x] **Step 4：运行绿灯测试并提交**

```powershell
uv run --no-sync pytest tests/api/test_exports_api.py -q --basetemp=../tmp/pytest-envision-export-green
git add backend/src/services/export_service.py backend/tests/api/test_exports_api.py
git commit -m "feat: export complete 577-unit GRI scope"
```

### Task 8：前端统一为 577 项产品口径

**Files：**

- Modify: `frontend/lib/api.ts`
- Modify: `frontend/lib/types.ts`
- Modify: `frontend/components/analysis/assessment-table.tsx`
- Modify: `frontend/components/analysis/assessment-table.test.tsx`
- Modify: `frontend/components/analysis/report-dashboard.tsx`
- Modify: `frontend/components/analysis/report-dashboard.test.tsx`

- [x] **Step 1：写失败测试**

页面断言：

```text
完整 GRI 核查范围
共 577 项
```

并验证：

- 独立项显示结论、优先级、复核状态和证据页，可进入复核；
- 上下文项显示“已纳入相关判断”，没有复核链接；
- 分页显示“第 1–50 项，共 577 项”；
- Dashboard 显示“核查范围 577 项”；
- 普通页面不出现 `493`、`499`、`78`、`6 个方法待确认`；
- 高优先级仍显示真实完成百分比，不使用 `/577`。

- [x] **Step 2：运行红灯测试**

```powershell
cd frontend
pnpm test -- assessment-table.test.tsx report-dashboard.test.tsx --run
```

- [x] **Step 3：实现最小前端修改**

`AssessmentTable` 改用 `listReportScopeItems`。上下文行使用禁用样式和明确状态；不得伪造 assessment link。

Dashboard 新增范围卡片或标题行：

```text
核查范围：577 项
```

风险卡片继续显示高/中/低/适用性数量，不显示多个总分母。

- [x] **Step 4：运行绿灯和前端全量**

```powershell
pnpm test -- --run
pnpm typecheck
pnpm build
```

- [x] **Step 5：提交**

```powershell
git add frontend
git diff --cached --check
git commit -m "feat: unify Envision UI around 577 GRI units"
```

### Task 9：重新生成 Envision v3 基线

**Files：**

- Runtime output: `backend/data/runtime/evaluations/envision_2024/current_499_review_regenerated.csv`
- Runtime output: matching audit/diff/scope JSON
- Modify: `backend/data/manifests/assets_manifest.json`

- [x] **Step 1：运行无外部模型 regeneration**

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

该命令不得带 LLM、OCR 或 VLM 参数。

- [x] **Step 2：验证硬门禁**

必须满足：

```text
standard_unit_count=577
independent_assessment_count=499
context_only_count=78
method_pending_count=0
unique_assessment_requirement_id_count=499
global_fallback_count=0
new_false_disclosed_count=0
new_wrong_source_page_count=0
audit.ok=true
audit.errors=[]
audit.warnings=[]
```

16 条最终裁决检查必须为 0 条 pending；规则与最终裁决的预期差异逐条有明确状态，不能通过排除 pending 来隐藏失败。

- [x] **Step 3：登记运行产物**

更新 manifest 的相对路径、SHA256、大小和用途。运行 CSV/JSON 保持现有 runtime 提交策略；若被 gitignore，只提交 manifest。

### Task 10：全量自动与产品验收

**Files：** 只产生 ignored runtime 证据。

- [x] **Step 1：后端全量**

```powershell
cd backend
uv run --no-sync pytest -q --basetemp=../tmp/pytest-envision-577-freeze-final
```

期望：不少于计划开始时的 627 项，0 failed、0 error。实际结果：651 passed。禁止使用 ACL 异常的 `tmp/pytest-current` 作为完成证据。

- [x] **Step 2：前端串行全量**

```powershell
cd frontend
pnpm test -- --run
pnpm typecheck
pnpm build
```

必须串行执行，避免 `.next/types` 与 build 并发竞争。

- [x] **Step 3：普通 Chrome 人工主流程**

不使用 Codex 内置浏览器。验证：

1. 重复上传远景报告仍提供“查看已有结果”和“重新上传并分析”；
2. metadata 企业、年度、语言正确，AI 默认关闭；
3. `confirm_llm=false` 完成八阶段，AI 阶段 skipped；
4. 分析终态 100%，没有转圈；
5. Dashboard 只显示“核查范围 577 项”；
6. 完整范围分页总数 577；
7. 上下文行没有伪 verdict；
8. 独立行进入三栏复核，PDF 不下载；
9. 规则、AI、人工三层不混用；
10. 草稿输出包含 577 行范围和 AI 免责声明。

实际结果：普通 Chrome 完成 metadata、无 AI 八阶段、Dashboard、577 项首尾分页、上下文行、三层复核、右栏页图和草稿输出验收。Chrome 扩展无法自动控制本机文件选择器；重复上传双路径由真实 API 与前端自动测试补足。该环境限制已登记。发现的右栏 PDF 空白 P1 已改为只读页图接口并重跑相关与全量门禁；首页“条/项”P2 文案同时修复。

- [x] **Step 4：记录问题**

任何问题记录：

```text
编号、严重程度、前置条件、复现步骤、实际结果、期望结果、影响范围、建议修复、状态
```

P0/P1 必须修复并重跑相关与全量门禁；P2 可在验收报告中列为非阻断限制，但不能影响 577 口径真实性。

### Task 11：更新文档并正式冻结

**Files：**

- Modify: `README.md`
- Modify: `docs/DESIGN.md`
- Modify: `docs/DEVELOPMENT.md`
- Modify: `docs/product/api-contract.md`
- Modify: `docs/product/data-model-impact.md`
- Modify: `docs/product/page-architecture.md`
- Modify: `docs/product/mvp-acceptance-report.md`
- Modify: `docs/plan/envision-577-final-adjudication-freeze-plan.md`

- [x] **Step 1：统一文案**

普通产品事实固定为：

```text
Envision 2024 中文报告完成 577 项 GRI 核查。
```

技术附录可以披露 `577/499/78/0`，必须明确这些是内部结构计数。删除“6 条方法待确认”和“16 条差异继续等待裁决”的当前状态表述，改为历史问题及其最终裁决。

- [x] **Step 2：记录冻结身份**

文档写明：

- Git commit；
- 数据库 head `0011_ai_suggestions`；
- manifest `gri-requirement-checklist-v3`；
- 产品方法版本 `envision-method-v1.1`；
- 结果裁决版本 `envision-result-v1.1`；
- risk 规则 `risk-v2.1`；
- DeepSeek Prompt/模型未改变；
- OCR/VLM 未启用；
- Goldwind 不阻塞；
- 无 GRI 专家认证；
- 企业条件适用性仍可能需要企业确认。

- [x] **Step 3：最终 diff 与 checkpoint**

```powershell
git status --short
git diff --check
git add README.md docs backend/data/manifests/assets_manifest.json
git diff --cached --check
git commit -m "docs: freeze Envision 577-unit backend baseline v1.1"
git status --short --branch
```

保持 `main`，不 push。

---

## 五、完成判定

只有同时满足以下条件，才能标记“后端已冻结”：

- 公开口径只使用 577 项；
- 577 个范围单元全部具有 `assessed` 或 `context_incorporated` 终态；
- 499 个独立判断项全部生成确定性结果或明确失败状态；
- 78 个上下文项不生成伪 verdict；
- `method_pending_count=0`；
- 6 条复合裁决可追溯到官方组成和产品方法版本；
- 16 条最终裁决资产完整、唯一、0 pending；
- Sol/Pro 原始工作簿 SHA256 不变；
- 4 条条件适用性明确进入待企业确认状态；
- 规则、AI、人工三层保持独立；
- 完整范围页面和导出均覆盖 577 行；
- 普通页面不出现互相竞争的结构总数；
- 后端全量、前端 test/typecheck/build 全部通过；
- Envision v3 gate 无新增 false disclosed 或 wrong source page；
- 普通 Chrome 主流程通过；
- 数据库仍为 `0011_ai_suggestions`；
- 没有清库、没有覆盖原始资产、没有删除旧 API、没有 push；
- 最终验收报告明确“产品方法基线，不构成 GRI 专家认证”。

## 六、冻结后的变更控制

冻结后允许：

- 不改变 API 语义的 P0/P1 修复；
- 前端布局、文案和演示体验优化；
- 测试、日志和验收材料补充；
- 性能改进，但必须证明结果不变。

以下修改需要解除冻结并重新执行 Envision gate：

- 577 清单或 6 条复合裁决；
- 证据路由、证据合同或 verdict 规则；
- risk-v2.1；
- DeepSeek 模型、Prompt、调用范围或 guardrail；
- 数据库 schema；
- API 字段语义；
- 规则、AI、人工权威关系；
- 正式输出门禁。

最终冻结名称：

```text
Envision 2024 中文报告 MVP 后端基线 v1.1
范围：577 项 GRI 核查
性质：本地产品与工程基线
限制：不构成 GRI 专家认证、外部鉴证或企业部署承诺
```
