# risk-v2 复核优先级、完整分页与中文展示实施计划

> **执行要求：** 实施时使用 `superpowers:executing-plans` 或 `superpowers:subagent-driven-development`，并严格采用测试驱动开发。保持在 `main` 分支，不新建分支，不自动提交或 push。所有数据库迁移、演示库重置、服务重启和其他状态变更仍需按项目授权规则执行。

**目标：** 将当前混合“披露结论、证据质量和复核优先级”的 `risk-v1` 调整为可解释的 `risk-v2`，使 `unknown` 不再天然升级为高优先级；同时修复 577 条核查表和高优先级复核队列只能访问第一页的问题，并消除产品页面及导出中的生成式英文模板。

**架构：** 保留 `assessment_risks` 的追加式历史和旧 `risk_level` 字段/API，通过新版本规则把该字段兼容解释为“复核优先级”，并新增 `review_priority` 别名、证据状态和适用性状态。先用只读模拟工具对当前 577 条结果生成新旧分布和逐条迁移明细，经用户确认后再接入分析、复核和正式输出流程。展示层在后端集中做确定性中文映射，原始引擎值和审计数据不被覆盖。列表由后端完成全量过滤、稳定排序、真实计数和分页，前端提供可访问全部记录的分页控件。

**技术栈：** FastAPI、SQLAlchemy、Alembic、Pydantic v2、PostgreSQL、pytest、Next.js App Router、TypeScript、TanStack Query、Vitest、React Testing Library。

---

## 一、问题基线与目标边界

### 1.1 已确认基线

| 项目 | 当前事实 | 影响 |
| --- | --- | --- |
| 复核优先级 | 577 条中 355 条为高风险；343 条由 `unknown_verdict` 触发，占高风险 96.6% | 高风险队列主要反映证据覆盖率，无法有效排序人工复核工作 |
| 完整 GRI 核查表 | API `total=577`，前端固定请求 `page=1&page_size=50` | 页面仅能访问 50 条，527 条不可达 |
| 高风险复核队列 | 后端先分页再按复核状态过滤，并将 `total` 覆盖为当前页数量；前端只请求第一页 | 页面最多访问 50 条，真实总数和翻页均错误 |
| 判断依据 | 577 条中 573 条为纯英文、4 条中英混合 | 中文演示页面存在大面积英文泄漏 |
| 缺失项 | 159 个 requirement 含英文缺失项，共 270 个纯英文实例 | 三栏复核和导出不符合中文产品预期 |
| 历史兼容 | `risk-v1`、旧 API、旧 `review_decisions` 仍有调用者 | 禁止删除或原地改写历史数据与兼容接口 |

以上数量用于实施前基线校验。模拟或测试读取的报告必须明确为当前远景 2024 中文报告，不能把其他 regeneration 数据混入统计。

### 1.2 四个独立业务维度

1. **披露结论：** `disclosed`、`partial`、`unknown`。
2. **证据状态：** 直接有效、缺失、仅非实质证据、质量警告、无效、冲突。
3. **适用性状态：** 适用、企业声称不适用、人工确认不适用、待判定。
4. **复核优先级：** 高、中、低，用于安排人工复核顺序。

产品界面统一使用“复核优先级”。数据库和旧 API 中的 `risk_level` 暂时保留，避免破坏现有调用者；`risk-v2` 下该字段的业务含义等同 `review_priority`。

### 1.3 risk-v2 初始规则

#### 高优先级

仅由明确异常或冲突触发：

- 分析失败或生成结果不完整；
- 证据被判无效；
- 页码、来源或证据定位冲突；
- 严重证据质量异常；
- 充分性冲突，例如结论为“已披露/部分披露”，但仅有索引、从略说明或无实质证据；
- 已被人工 reopen 或进入正式输出异常处理的项目。

#### 中优先级

- `unknown` 且无证据；
- `unknown` 且仅有索引或从略说明；
- 有有效证据但披露结论为 `partial`；
- 企业声称不适用但尚未完成人工适用性确认；
- 一般证据质量警告，尚未构成证据失效或结论冲突。

#### 低优先级

同时满足以下条件：

- 披露结论为 `disclosed`；
- 存在直接、实质性证据；
- 证据质量正常；
- 无页码、来源、充分性或适用性冲突。

#### 规则限制

- `unknown_verdict` 可以保留为解释原因，但不能单独触发高优先级；
- `non_substantive_evidence_only` 默认中优先级，只有与积极披露结论冲突时才升级为高优先级；
- “重要议题”自动升级暂不进入 `risk-v2`，直到系统拥有可信、可审计的企业重要性议题来源；
- 适用性是独立维度，不能作为第四个风险等级；
- “高优先级约 72 条”仅作为当前假设上界，不设固定数量或比例，最终分布必须由规则和数据产生。

### 1.4 正式输出门禁

- 正式输出继续只阻塞“未解决的高优先级项目”；
- 未解决的中优先级和待判定适用性项目必须写入输出范围说明和数量统计；
- “高优先级复核完成”只能表示高优先级队列已处理，禁止表述为 577 条均已人工确认；
- 历史 `risk-v1` 输出保留其原始规则版本，不回写为 `risk-v2`。

---

## 二、文件变更总览

| 文件 | 动作 | 职责 |
| --- | --- | --- |
| `backend/src/domain/enums.py` | 修改 | 新增证据状态、适用性状态枚举；保留 `RiskLevel` |
| `backend/src/domain/models.py` | 修改 | 为追加式风险快照和复核快照增加新维度 |
| `backend/src/domain/versions.py` | 新建 | 集中定义当前规则版本 `risk-v2` |
| `backend/src/services/review_priority_service.py` | 新建 | 纯函数形式实现 risk-v2 分类和原因码 |
| `backend/src/services/risk_service.py` | 修改 | 保留持久化门面和兼容入口，接入新分类器 |
| `backend/src/db/models.py` | 修改 | 为风险快照和复核快照增加可空的新维度字段 |
| `backend/src/db/repositories.py` | 修改 | 追加式写入和读取新维度；修复筛选、计数、排序、分页顺序 |
| `backend/alembic/versions/0010_risk_v2_dimensions.py` | 新建 | 迁移新增字段，不改写旧 risk-v1 历史值 |
| `backend/src/api/schemas.py` | 修改 | 新增 `review_priority`、证据状态、适用性状态及兼容别名 |
| `backend/src/api/routes/assessments.py` | 修改 | 返回真实分页总数和产品展示字段 |
| `backend/src/api/routes/review.py` | 修改 | review 后重新计算 risk-v2，并支持适用性复核字段 |
| `backend/src/services/review_service.py` | 修改 | 将高优先级完成态与全部 577 人工确认解耦 |
| `backend/src/services/export_service.py` | 修改 | 正式输出门禁、复核范围说明和中文展示 |
| `backend/src/services/presentation_localization.py` | 新建 | 对生成式判断依据和缺失项做确定性中文映射 |
| `backend/src/tools/review_csv_export.py` | 修改 | 导出中文展示值，同时保留审计所需原始值 |
| `backend/src/tools/simulate_risk_v2.py` | 新建 | 只读模拟新旧分布和逐条变化，不写数据库 |
| `backend/tests/services/test_review_priority_service.py` | 新建 | risk-v2 规则矩阵测试 |
| `backend/tests/domain/test_models.py` | 修改 | 新风险和复核快照字段测试 |
| `backend/tests/services/test_presentation_localization.py` | 新建 | 中文模板覆盖和术语白名单测试 |
| `backend/tests/tools/test_simulate_risk_v2.py` | 新建 | 只读、数量、产物和确定性测试 |
| `backend/tests/api/test_assessments_api.py` | 修改 | 完整分页、真实 total、兼容字段和中文展示测试 |
| `backend/tests/api/test_review_api.py` | 修改 | review/reopen 后优先级和适用性测试 |
| `backend/tests/api/test_exports_api.py` | 修改 | 正式输出门禁与范围说明测试 |
| `frontend/lib/types.ts` | 修改 | 增加复核优先级、证据状态、适用性状态类型 |
| `frontend/lib/api.ts` | 修改 | assessments 和 review queue 接受页码、页大小及筛选参数 |
| `frontend/lib/business-labels.ts` | 修改 | 新增四维状态中文标签，保留旧字段兼容映射 |
| `frontend/components/ui/pagination-controls.tsx` | 新建 | 统一分页控件和可访问性行为 |
| `frontend/components/analysis/assessment-table.tsx` | 修改 | 展示真实区间、总数和完整翻页 |
| `frontend/components/review/risk-queue.tsx` | 修改 | 改为“复核优先级队列”，支持完整翻页 |
| `frontend/components/review/assessment-detail.tsx` | 修改 | 分开展示结论、证据状态、适用性和优先级 |
| `frontend/components/review/review-workspace.tsx` | 修改 | 适用性复核和高优先级完成边界文案 |
| `frontend/components/analysis/report-dashboard.tsx` | 修改 | 使用复核优先级统计和准确的完成说明 |
| `frontend/components/exports/export-versions.tsx` | 修改 | 显示正式输出门禁和未解决范围 |
| `docs/DESIGN.md` | 修改 | 记录四维模型、版本化规则和分页职责 |
| `docs/DEVELOPMENT.md` | 修改 | 增加模拟、迁移、测试和人工验收路径 |
| `docs/product/risk-model.md` | 修改 | 将 risk-v2 作为当前规则并保留 risk-v1 历史说明 |
| `docs/product/api-contract.md` | 修改 | 新字段、兼容别名、分页和输出门禁契约 |
| `docs/product/data-model-impact.md` | 修改 | 新字段、迁移和历史数据策略 |
| `docs/product/state-model.md` | 修改 | 高优先级完成态与全量人工确认边界 |

实际实施前应通过 `rg` 核实上述文件名和现有类名。若当前实现的服务文件名不同，沿用现有结构并在计划执行记录中说明等价落点，不能为了匹配计划制造重复服务。

---

## 三、任务 1：冻结基线和写失败测试

**文件：**

- 修改：`backend/tests/services/test_risk_service.py`
- 新建：`backend/tests/services/test_review_priority_service.py`
- 修改：`backend/tests/api/test_assessments_api.py`
- 修改：`frontend/components/analysis/assessment-table.test.tsx`
- 修改：`frontend/components/review/review-workspace.test.tsx`
- 新建或修改：`frontend/components/review/risk-queue.test.tsx`

- [ ] **步骤 1：冻结 risk-v1 行为**

保留现有 `risk-v1` 单元测试，明确断言其历史行为不随新分类器改变。测试使用显式规则版本，避免默认版本升级后误测。

- [ ] **步骤 2：写 risk-v2 规则矩阵失败测试**

至少覆盖：

```text
unknown + no evidence → medium
unknown + index/omission only → medium
partial + valid direct evidence → medium
disclosed + valid direct evidence + no conflict → low
disclosed + no substantive evidence → high
evidence invalid → high
page/source conflict → high
analysis failed → high
claimed not applicable → medium + not_applicable_claimed
confirmed not applicable → low + not_applicable_confirmed，默认从待复核队列排除并保留可审计状态
```

- [ ] **步骤 3：写后端分页失败测试**

构造超过 50 条数据，断言：

- `total` 是过滤后的全量数量；
- 第 2 页和最后一页可访问；
- review status、priority 等筛选在分页之前执行；
- 多页之间没有重复或遗漏；
- 相同时间戳下仍保持稳定次序。

- [ ] **步骤 4：写前端分页失败测试**

断言完整核查表显示“第 1–50 条，共 577 条”，能够请求第 2 页和第 12 页；复核队列显示真实总数并能翻页，查询缓存 key 包含页码、页大小和筛选条件。

- [ ] **步骤 5：运行测试确认 RED**

```powershell
cd backend
uv run --no-sync pytest tests/services/test_review_priority_service.py tests/api/test_assessments_api.py -q --basetemp=../tmp/pytest-risk-v2-red

cd ../frontend
pnpm test -- components/analysis/assessment-table.test.tsx components/review/risk-queue.test.tsx components/review/review-workspace.test.tsx
```

预期：新分类器、真实分页或新字段尚未实现，测试失败；现有 `risk-v1` 历史测试仍应通过。

---

## 四、任务 2：实现纯函数 risk-v2 分类器

**文件：**

- 修改：`backend/src/domain/enums.py`
- 新建：`backend/src/domain/versions.py`
- 新建：`backend/src/services/review_priority_service.py`
- 修改：`backend/tests/services/test_review_priority_service.py`

- [ ] **步骤 1：定义证据状态和适用性状态**

```python
class EvidenceStatus(StrEnum):
    VALID_DIRECT = "valid_direct"
    MISSING = "missing"
    NON_SUBSTANTIVE_ONLY = "non_substantive_only"
    QUALITY_WARNING = "quality_warning"
    INVALID = "invalid"
    CONFLICT = "conflict"

class ApplicabilityStatus(StrEnum):
    APPLICABLE = "applicable"
    NOT_APPLICABLE_CLAIMED = "not_applicable_claimed"
    NOT_APPLICABLE_CONFIRMED = "not_applicable_confirmed"
    UNDETERMINED = "undetermined"
```

不重命名或删除 `RiskLevel`，避免数据库枚举、旧接口和前端调用者发生破坏性变化。

- [ ] **步骤 2：定义纯输入和输出对象**

分类输入显式包含 verdict、证据类型/质量、页码来源状态、分析状态、适用性、人工 reopen 和正式输出异常信号。输出至少包含：

```python
review_priority
evidence_status
applicability_status
reason_codes
risk_rule_version
```

- [ ] **步骤 3：按优先级顺序实现规则**

先判断分析失败、证据无效、冲突和严重质量异常；再判断适用性；随后处理 partial/unknown；最后识别低优先级。原因码必须能解释每次升级，禁止通过目标比例或 report-specific requirement ID 决定结果。

- [ ] **步骤 4：验证 unknown 不会单独升高**

增加参数化测试，组合 `unknown` 与缺失、索引、从略说明和一般质量警告，断言均为中优先级；叠加证据失效或冲突后才为高优先级。

- [ ] **步骤 5：运行分类器测试确认 GREEN**

```powershell
cd backend
uv run --no-sync pytest tests/services/test_review_priority_service.py tests/services/test_risk_service.py -q --basetemp=../tmp/pytest-risk-v2-classifier
```

---

## 五、任务 3：构建只读模拟并设置人工确认点

**文件：**

- 新建：`backend/src/tools/simulate_risk_v2.py`
- 新建：`backend/tests/tools/test_simulate_risk_v2.py`
- 输出：`tmp/risk-v2-simulation/summary.json`
- 输出：`tmp/risk-v2-simulation/transitions.csv`
- 输出：`tmp/risk-v2-simulation/high_priority.csv`

- [ ] **步骤 1：写只读性失败测试**

模拟前后分别读取 `assessment_risks` 行数、最大 `calculated_at` 和报告更新时间，断言完全一致。测试禁止调用 repository 的 create/update/commit 路径。

- [ ] **步骤 2：写基线校验失败测试**

对指定 run 校验：

```text
eligible assessment = 577
risk-v1 high = 355
unknown_verdict 触发的 high = 343
```

任一基线不符时，工具应中止并报告实际值，禁止继续输出看似有效的比较。

- [ ] **步骤 3：实现逐条模拟**

`transitions.csv` 至少包含：

```text
requirement_id
old_risk_level
old_reason_codes
new_review_priority
new_evidence_status
new_applicability_status
new_reason_codes
changed
```

`summary.json` 至少包含新旧高/中/低分布、原因码分布、适用性分布、迁移矩阵、未解决高优先级数量和正式输出门禁变化。

- [ ] **步骤 4：实现高优先级审计清单**

`high_priority.csv` 仅包含 risk-v2 高优先级项目，并附带触发证据。清单中不允许仅凭 `unknown_verdict` 成为高优先级。

- [ ] **步骤 5：运行工具测试**

```powershell
cd backend
uv run --no-sync pytest tests/tools/test_simulate_risk_v2.py -q --basetemp=../tmp/pytest-risk-v2-simulation
```

- [ ] **步骤 6：对当前远景 577 条执行只读模拟**

具体命令以工具最终 CLI 为准，至少显式传入 `report_id` 或 `run_id` 和输出目录。执行前打印数据库名、环境类型、报告 ID、run ID 和只读声明。

- [ ] **步骤 7：停止并请求用户确认**

向用户提交以下内容后暂停：

- risk-v1 与 risk-v2 的高/中/低分布；
- 高优先级原因码分布；
- 所有仍为高优先级项目的可解释清单；
- 适用性待判定数量；
- 正式输出门禁变化；
- 规则边界和异常样本。

用户确认模拟结果前，禁止执行数据库迁移、生产规则接入、历史回算或演示库重置。高优先级数量无需接近 72；只要规则正确且每条可解释即可。

---

## 六、任务 4：新增追加式数据维度和兼容 API

**前置条件：** 用户已确认 risk-v2 模拟结果。

**文件：**

- 新建：`backend/alembic/versions/0010_risk_v2_dimensions.py`
- 修改：`backend/src/domain/models.py`
- 修改：`backend/src/db/models.py`
- 修改：`backend/src/db/repositories.py`
- 修改：`backend/src/api/schemas.py`
- 修改：`backend/tests/domain/test_models.py`
- 修改：`backend/tests/db/test_repositories.py`
- 修改：`backend/tests/api/test_assessments_api.py`

- [ ] **步骤 1：写模型和 repository 失败测试**

断言新风险快照可写入并读取 `evidence_status` 与 `applicability_status`，最新快照查询仍按追加式记录选择，不覆盖旧 risk-v1 行。

- [ ] **步骤 2：新增 migration**

在 `assessment_risks` 增加：

```text
evidence_status VARCHAR(32) NOT NULL DEFAULT 'missing'
applicability_status VARCHAR(32) NOT NULL DEFAULT 'undetermined'
```

若人工复核需要独立记录适用性，在追加式 review snapshot 增加可空字段：

```text
reviewed_applicability_status VARCHAR(32) NULL
```

迁移只增加字段和索引，不删除旧列，不修改 `risk_rule_version='risk-v1'` 的历史行。

- [ ] **步骤 3：新增 API 字段并保留兼容别名**

新响应提供：

```text
review_priority
evidence_status
applicability_status
review_priority_reason_codes
```

旧 `risk_level`、`reason_codes`、`high_risk_*` 字段继续返回，并在文档中标为兼容别名。旧 review API 与 `review_decisions` 保持可用。

- [ ] **步骤 4：验证升级和降级边界**

```powershell
cd backend
uv run --no-sync alembic upgrade head
uv run --no-sync alembic current
uv run --no-sync pytest tests/db/test_repositories.py tests/api/test_assessments_api.py -q --basetemp=../tmp/pytest-risk-v2-schema
```

只对明确的测试数据库或经确认的运行环境执行 migration。不得自动清空任何库。

---

## 七、任务 5：接入分析、复核和正式输出流程

**文件：**

- 修改：`backend/src/services/risk_service.py`
- 修改：`backend/src/workflows/single_report_workflow.py`
- 修改：`backend/src/services/review_service.py`
- 修改：`backend/src/services/export_service.py`
- 修改：`backend/src/api/routes/review.py`
- 修改：对应 workflow、review、export 测试

- [ ] **步骤 1：将当前规则版本集中为 risk-v2**

新 run 和部署后的 retry 使用 `risk-v2`；父 run 的历史快照继续保留其原规则版本。每次风险计算必须把 `risk_rule_version` 写入追加式快照。

- [ ] **步骤 2：分析流程调用新分类器**

从评估结果构造明确上下文，禁止 `risk_service` 根据单一 verdict 隐式推断全部证据和适用性状态。失败项必须产生高优先级和可解释原因码。

- [ ] **步骤 3：review 后重新计算优先级**

人工调整 verdict、证据有效性或适用性后追加 review snapshot 和风险快照。reopen 项在解决前保持高优先级；不得覆盖旧决策。

- [ ] **步骤 4：修正高优先级完成态**

只有当前未解决高优先级为 0 时才能进入对应完成态。状态文案及 API 说明明确其复核范围，不声称中优先级、低优先级或全部 577 条已人工确认。

- [ ] **步骤 5：修正正式输出门禁**

正式输出只阻塞未解决高优先级。输出元数据记录：

```text
risk_rule_version
high_priority_total / unresolved
medium_priority_total / unresolved
applicability_undetermined_total
manual_review_scope
```

草稿输出仍可生成，但必须带范围提示。

- [ ] **步骤 6：运行针对性流程测试**

```powershell
cd backend
uv run --no-sync pytest tests/workflows tests/services/test_risk_service.py tests/services/test_review_service.py tests/api/test_review_api.py tests/api/test_exports_api.py -q --basetemp=../tmp/pytest-risk-v2-workflow
```

实际文件不存在时使用 `rg --files backend/tests` 定位等价测试文件，不能省略相应覆盖。

---

## 八、任务 6：修复后端完整分页和真实总数

**文件：**

- 修改：`backend/src/db/repositories.py`
- 修改：`backend/src/api/routes/assessments.py`
- 修改：`backend/tests/api/test_assessments_api.py`

- [ ] **步骤 1：统一查询顺序**

后端严格按以下顺序处理：

```text
report/run 范围
→ verdict / review priority / review status / applicability 筛选
→ 稳定排序
→ 计算过滤后 total
→ offset/limit 分页
→ 序列化
```

禁止先分页再在 Python 中过滤 review status，也禁止用当前页长度覆盖 `total`。

- [ ] **步骤 2：定义稳定排序**

完整核查表优先按标准、requirement 的业务顺序排序；复核队列优先按复核优先级、原因严重度、requirement 业务顺序排序，并用主键作为最终 tie-breaker。

- [ ] **步骤 3：验证页面边界**

对 577 条、`page_size=50` 断言前 11 页为 50 条，第 12 页为 27 条，第 13 页为空；所有页合并后正好 577 个唯一 assessment。

- [ ] **步骤 4：验证复核队列真实总数**

用超过 50 个 pending high-priority 项验证：每页 `total` 相同，翻页后能够访问全部记录；review 一条后 total 减 1，其他页不重复、不丢失。

- [ ] **步骤 5：运行 API 测试**

```powershell
cd backend
uv run --no-sync pytest tests/api/test_assessments_api.py tests/api/test_review_api.py -q --basetemp=../tmp/pytest-assessment-pagination
```

---

## 九、任务 7：实现前端完整分页

**文件：**

- 新建：`frontend/components/ui/pagination-controls.tsx`
- 修改：`frontend/lib/api.ts`
- 修改：`frontend/components/analysis/assessment-table.tsx`
- 修改：`frontend/components/review/risk-queue.tsx`
- 修改：相关测试文件

- [ ] **步骤 1：让 API 客户端接受分页参数**

`getAssessments` 和 review queue 查询显式接受 `page`、`pageSize`、priority、review status、applicability。TanStack Query key 必须包含全部查询参数。

- [ ] **步骤 2：实现共用分页控件**

至少提供上一页、下一页、当前页/总页数、当前记录区间和总数。首尾页正确禁用按钮，并提供可访问名称。

- [ ] **步骤 3：接入完整核查表**

显示：

```text
第 1–50 条，共 577 条
```

用户可连续到达第 12 页。切页保留当前筛选；筛选改变时回到第 1 页。

- [ ] **步骤 4：接入复核优先级队列**

队列标题和筛选使用“高/中/低复核优先级”。选择项复核完成导致当前页空时，自动回到最后一个有效页。

- [ ] **步骤 5：运行前端测试**

```powershell
cd frontend
pnpm test -- components/analysis/assessment-table.test.tsx components/review/risk-queue.test.tsx components/review/review-workspace.test.tsx
```

---

## 十、任务 8：集中实现中文展示映射

**文件：**

- 新建：`backend/src/services/presentation_localization.py`
- 新建：`backend/tests/services/test_presentation_localization.py`
- 修改：`backend/src/api/routes/assessments.py`
- 修改：`backend/src/services/export_service.py`
- 修改：`backend/src/tools/review_csv_export.py`
- 修改：`frontend/components/review/assessment-detail.tsx`

- [ ] **步骤 1：盘点所有生成式模板**

通过本地代码和当前 577 条数据提取判断依据、缺失项的 distinct 值，建立受版本控制的确定性映射目录。禁止调用外部翻译、模型、OCR 或 VLM。

- [ ] **步骤 2：写模板覆盖失败测试**

至少覆盖用户发现的文本：

```text
The report index contains an omission note, but no substantive disclosure evidence was found.
EVG&D source basis from audited financial/P&L statement or internally audited management accounts
applicability of EVG&D source basis
```

目标中文：

```text
报告 GRI 内容索引包含从略说明，但未找到实质性披露证据。
EVG&D 数据来源依据：经审计的财务报表或损益表，或经内部审计的管理账目
EVG&D 数据来源依据的适用性说明
```

- [ ] **步骤 3：实现集中展示函数**

公开接口至少包括：

```python
localize_rationale(value: str | None) -> str | None
localize_missing_items(values: Sequence[str]) -> list[str]
```

仅做精确模板和受控参数化模板映射；未知模板原样返回并记录可监控的未映射标识，避免错误翻译审计事实。

- [ ] **步骤 4：保留原始值**

数据库中的原始 engine/audit 值不修改。产品 API 和导出返回中文展示值；审计字段继续保留原始值。旧兼容 API 若已有原始值契约，应新增产品展示字段，避免静默改变旧调用者语义。

- [ ] **步骤 5：定义允许保留的英文术语**

中文展示中允许保留的标准缩写至少包括：

```text
GRI、ESG、EVG&D、GAAP、OHS、GHG、GWP、P&L、Scope
```

测试扫描当前 577 条展示结果，除白名单、标准编号和专有名词外，不应存在完整英文句子。

- [ ] **步骤 6：避免改写人工输入**

人工 review snapshot 的自由文本不做泛化翻译。只有与已知系统生成模板精确匹配时才应用展示映射。

- [ ] **步骤 7：运行中文展示测试**

```powershell
cd backend
uv run --no-sync pytest tests/services/test_presentation_localization.py tests/api/test_assessments_api.py tests/api/test_exports_api.py -q --basetemp=../tmp/pytest-localization
```

---

## 十一、任务 9：更新产品术语、四维详情和输出说明

**文件：**

- 修改：`frontend/lib/types.ts`
- 修改：`frontend/lib/business-labels.ts`
- 修改：`frontend/components/review/assessment-detail.tsx`
- 修改：`frontend/components/review/review-workspace.tsx`
- 修改：`frontend/components/analysis/report-dashboard.tsx`
- 修改：`frontend/components/exports/export-versions.tsx`
- 修改：相关前端测试

- [ ] **步骤 1：替换用户可见术语**

将“高风险/风险分级/高风险复核队列”等复核工作流文案改为“高复核优先级/复核优先级/高优先级复核队列”。历史规则版本说明中可以保留 `risk-v1` 名称。

- [ ] **步骤 2：三栏详情分开显示四个维度**

详情区独立展示：

```text
披露结论
证据状态
适用性状态
复核优先级及原因
```

禁止把 `unknown`、无证据和高优先级合并为一个标签。

- [ ] **步骤 3：dashboard 显示准确统计**

dashboard 显示高/中/低优先级数量、待判定适用性数量、已复核的高优先级数量。完成文案使用“高优先级项目已复核”，并附带全量核查与人工复核范围。

- [ ] **步骤 4：输出页显示门禁原因**

正式输出被阻塞时列出未解决高优先级数量；允许输出时仍展示未解决中优先级和适用性待判定数量。

- [ ] **步骤 5：运行组件测试**

```powershell
cd frontend
pnpm test -- components/review components/analysis components/exports
```

---

## 十二、任务 10：同步 OpenAPI、设计和开发文档

**文件：**

- 修改：`docs/DESIGN.md`
- 修改：`docs/DEVELOPMENT.md`
- 修改：`docs/product/risk-model.md`
- 修改：`docs/product/api-contract.md`
- 修改：`docs/product/data-model-impact.md`
- 修改：`docs/product/state-model.md`
- 修改：前端生成的 API 类型文件，以项目现有生成位置为准

- [ ] **步骤 1：更新风险模型文档**

保留 risk-v1 历史规则，新增 risk-v2 四维模型、规则优先级、原因码、版本切换和不做历史回写的约束。

- [ ] **步骤 2：更新 API 契约**

记录新字段、旧字段兼容期、分页 total 语义、稳定排序、筛选顺序、中文展示字段与原始审计字段。

- [ ] **步骤 3：更新数据模型影响**

记录 `0010_risk_v2_dimensions`、默认值、追加式风险快照、人工适用性复核和 rollback 限制。

- [ ] **步骤 4：更新状态与正式输出边界**

明确高优先级完成态只覆盖高优先级队列；输出范围必须披露中优先级和待判定适用性数量。

- [ ] **步骤 5：生成前端 API 类型**

后端服务已启动且契约测试通过后执行：

```powershell
cd frontend
pnpm generate:api
```

随后检查生成 diff，禁止手工修改生成文件掩盖后端契约错误。

---

## 十三、任务 11：自动化验证和 Envision 577 回归门禁

- [ ] **步骤 1：运行后端针对性测试**

```powershell
cd backend
uv run --no-sync pytest tests/services/test_review_priority_service.py tests/services/test_risk_service.py tests/services/test_presentation_localization.py tests/tools/test_simulate_risk_v2.py tests/api/test_assessments_api.py tests/api/test_review_api.py tests/api/test_exports_api.py -q --basetemp=../tmp/pytest-risk-v2-targeted
```

- [ ] **步骤 2：运行后端全量测试**

```powershell
cd backend
uv run --no-sync pytest -q --basetemp=../tmp/pytest-risk-v2-full
```

- [ ] **步骤 3：运行前端门禁**

```powershell
cd frontend
pnpm typecheck
pnpm test
pnpm build
```

- [ ] **步骤 4：运行 Envision 577 gate**

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

验收要求：

- 577 个唯一 eligible requirement；
- audit 通过；
- verdict、source、evidence、page、quality、OCR/VLM 字段无非预期变化；
- risk/review priority 分布变化必须与已确认的 risk-v2 模拟一致；
- 未调用外部模型、OCR 或 VLM；
- 新增分页和中文展示不会改变底层分析事实。

- [ ] **步骤 5：检查代码和文档一致性**

```powershell
rg -n "unknown_verdict|risk-v1|risk-v2|高风险|复核优先级|review_priority|evidence_status|applicability_status" backend frontend docs
git diff --check
```

逐项确认旧兼容术语只存在于历史、兼容字段或迁移说明中。

---

## 十四、任务 12：空演示库完整人工验收

**前置条件：** 自动门禁全部通过，用户再次授权演示库重置和服务重启。

- [ ] **步骤 1：确认环境边界**

打印并人工确认数据库名、环境类型、上传目录和运行目录。目标必须为演示环境；若识别为当前保留库或环境标识不明确，立即停止。

- [ ] **步骤 2：先执行 dry-run**

按 `docs/DEVELOPMENT.md` 的 demo reset 命令执行 dry-run，确认只会清理演示数据库和演示文件目录。不得删除原始报告或标准资产。

- [ ] **步骤 3：重置空演示库并重新上传分析**

使用远景 2024 中文 ESG 报告，从首次上传、metadata 确认、分析、完整核查、复核、整改任务到版本化输出完整走一遍。

- [ ] **步骤 4：使用普通浏览器或独立 Edge 验收**

不使用 Codex 内置浏览器。重点检查：

```text
完整核查表可访问全部 577 条
末页为 27 条且无重复
复核队列可访问全部高优先级项目
高优先级数量和原因与 risk-v2 模拟一致
unknown 不会单独进入高优先级
判断依据和缺失项无非白名单英文句子
三栏分别显示结论、证据、适用性和优先级
高优先级复核完成不声称 577 条均已人工确认
正式输出准确披露未解决中优先级和待判定适用性数量
```

- [ ] **步骤 5：记录验收问题**

每个问题记录复现步骤、严重程度、影响范围、根因、建议修复和验证结果。阻塞问题修复后重新执行相关针对性测试和受影响的完整流程。

---

## 十五、停止条件

遇到以下任一情况立即停止当前实施并报告：

1. 模拟数据不是 577 条，或当前 risk-v1 基线与 355/343 明显不符；
2. risk-v2 中仍存在仅由 `unknown_verdict` 触发的高优先级；
3. 需要通过硬编码数量、比例或远景专用 requirement ID 才能得到预期分布；
4. risk-v2 导致 verdict、证据文本、来源页、证据质量或 requirement 集合发生变化；
5. 迁移需要删除或重写旧 `assessment_risks`、`review_decisions` 或旧 API；
6. 数据库或文件目录无法确认属于演示环境；
7. 需要启用外部模型、OCR 或 VLM；
8. 需要使用 `git reset --hard`、`git checkout --`、自动 commit 或 push；
9. 分页修复仍使任一记录不可达、重复或 total 不稳定；
10. 中文映射需要猜测人工输入的含义，无法通过确定性模板安全处理。

---

## 十六、完成标准

全部满足后才可报告完成：

1. risk-v2 的四个业务维度已分离，规则和原因码可解释；
2. `unknown` 单独出现时为中优先级，不再天然进入高优先级；
3. risk-v1 历史数据、旧 API、旧 `risk_level` 字段和 `review_decisions` 均保持可用；
4. 只读模拟经用户确认，实际 risk-v2 分布与确认结果一致；
5. 完整核查表可访问 577 条全部记录，复核队列 total 和翻页正确；
6. 判断依据、缺失项和导出中的系统生成模板均以中文展示，仅保留允许的标准缩写和专有名词；
7. 产品界面使用“复核优先级”，并分开展示披露结论、证据状态和适用性状态；
8. 正式输出只阻塞未解决高优先级，同时披露未解决中优先级和适用性范围；
9. 任何完成态均不表达为全部 577 条已人工确认；
10. 后端针对性测试和全量测试通过；
11. 前端 typecheck、test、production build 通过；
12. Envision 577 gate 通过，除预期的 risk-v2 分布外无 verdict、source page 或证据回归；
13. 空演示库重新上传和完整人工验收通过；
14. 全程未调用外部模型、OCR 或 VLM，未自动提交或 push。

## 十七、回滚与限制

- risk-v2 通过新版本风险快照生效，回滚应用时仍可读取历史 risk-v1，不删除新快照；
- migration downgrade 只能在确认无新版本数据依赖时执行，正式验收库不得自动 downgrade；
- 中文映射只影响展示值，原始引擎和审计值保留，因此可以独立回滚展示层；
- 前端分页可以独立回滚，但后端真实 total 和筛选顺序修复应保留；
- 本计划不授权数据库重置、服务重启、commit 或 push；相应步骤执行前需要独立确认；
- 当前规则不自动判断企业重要性议题，待有可信 materiality 数据源后另行版本化设计。
