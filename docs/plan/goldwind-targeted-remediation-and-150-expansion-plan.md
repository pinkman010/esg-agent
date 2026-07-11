# Goldwind 定向修复与 150 条扩展实施计划

> **执行要求：** 使用 `executing-plans` 在 `main` 分支按任务顺序 inline 执行；每项行为修改采用 TDD。现有 100 条 gold 未通过修复 gate 前，不得生成新增 50 条复核包。

**目标：** 基于 Goldwind 100 条人工 gold，修复 false disclosed、source promotion、KPI 行匹配和 cross-leaf missing items 四类系统问题；重跑并通过现有 100 条 gate 后，从剩余 477 条中定向增加 50 条，形成累计 150 条 holdout。

**架构：** report profile 继续只提供 candidate route；source evidence 必须经过 leaf-level anchor、evidence kind、facet 和 scope 门禁。标准 leaf 的原子缺口进入 standards metadata，Goldwind 页码和表述只存在于 report profile/holdout gold，不进入通用 contract。新增 50 条按主题确定性选择，输出独立增量复核包后暂停等待人工参与。

**技术栈：** Python 3.11、pytest、CSV/JSON、现有 report profile、evidence ontology、compilation guardrail、review CSV audit。

---

## 1. 输入与当前基线

### 1.1 权威输入

- First pass：`tmp/review/holdout_goldwind_2024_first_pass.csv`
- 100 条原始复核包：`tmp/review/holdout_goldwind_2024_stratified_100_review_pack.csv`
- 100 条人工 gold：`tmp/review/holdout_goldwind_2024_stratified_100_reviewed.csv`
- 当前质量摘要：`tmp/review/holdout_goldwind_2024_stratified_100_quality.json`
- Goldwind profile：`backend/data/reports/profiles/goldwind_2024.json`
- Envision 回归 baseline：`tmp/review/current_577_review_after_profile_routing.csv`

人工 gold CSV 是本阶段唯一逐条判断源。窗口文字用于解释，字段冲突时以 CSV 为准。

### 1.2 当前质量基线

按人工 gold CSV 计算：

- `manual_gold_available=true`
- `first_pass_recall=66.7%`
- `false_disclosed_count=12`
- `wrong_source_page_count=19`
- `unknown_leakage_count=17`
- `profile_route_valid_evidence_rate=52.8%`
- `cross_leaf_missing_items_count=9`
- `guardrail_as_evidence_count=0`

窗口复核曾给出 profile route 有效率 58.5%；CSV 的 `correct_pdf_pages` 与 source page 交集结果为 52.8%。本计划以 52.8% 为可复现 baseline，不在代码中硬编码该比例。

### 1.3 当前 100 条人工建议 verdict

- `disclosed=19`
- `partially_disclosed=32`
- `unknown=49`

任何 verdict 变化必须由人工 gold、通用 sufficiency 规则和有效 evidence 共同解释。

## 2. 硬性边界

1. 不新增 Goldwind 专用 per-ID contract。
2. 不把 Goldwind PDF 25、26、34、46、47 写入通用规则。
3. candidate page 不能直接成为 substantive source evidence。
4. 同章节相邻页只有通过 leaf anchor/evidence kind/scope 门禁后才能 promotion。
5. KPI 行必须绑定行标签、年份、单位或明确数值，页级主题命中不能支撑数值 leaf。
6. `missing_items` 只描述当前 leaf 的未满足组成部分。
7. compilation requirement 继续只进入 `guardrail_items`，不得作为 evidence 或独立 assessment。
8. 外部模型、OCR 和 VLM 保持关闭。
9. 原始 PDF、profile 原始输入和人工 gold CSV不得覆盖。
10. Envision 577 verdict、source page、evidence type、quality flag 和 OCR/VLM 字段不得出现非预期变化。

## 3. 目标问题集

### 3.1 False disclosed

人工 gold 标记的 12 条 `false_disclosed` 必须全部关闭，重点包括：

- GHG 减排：预估减排量不能等同报告期实际减排量；
- supplier assessment：审核覆盖率、A/B 评级不能替代重大影响供应商数量或改进比例；
- parental leave：总体或相邻员工数据不能替代按性别返岗和 12 个月留任人数；
- notice period：一般员工沟通不能替代最短通知周数；
- OHS KPI：死亡、培训、损失工作日不能传播到工时、rate basis 或其他 injury leaf；
- occupational ill health：职业病病例数不能直接等同工作相关健康问题死亡人数。

### 3.2 Wrong source page

人工 gold 主标签为 `wrong_source_page` 的 19 条必须按 `correct_pdf_pages` 校验。门禁必须支持：

- candidate 可保留相邻页；
- source 只保留与 leaf anchor 匹配的页面；
- source 集合中的任一无效页都应被移除；
- 无有效页时 source 清空并回到 `unknown + needs_manual_review`。

### 3.3 Unknown leakage

当前 `unknown` 且人工建议 `partial/disclosed` 的 17 条必须进入 recall 回归集。重点页为 Goldwind PDF 6、11、12、21、25、26、31、32、34、46。

修复必须依赖通用语义：

- KPI 行标签；
- 年份列；
- 单位和数值；
- section heading；
- GRI index route；
- requirement facets。

### 3.4 Cross-leaf missing items

人工 gold 主标签为 `cross_leaf_missing_items` 的 9 条，以及 review note 中指出的次要问题，统一通过 leaf metadata 修复。标准 metadata 可以按 requirement ID 定义官方 leaf 组成，但不能包含 report-specific 页码、verdict 或企业表述。

## 4. 文件职责

### 新增

- `backend/src/tools/evidence_promotion.py`
  - 纯函数判断 candidate evidence 是否允许晋升为 source evidence；
  - 输入为 requirement facets、evidence kind、匹配 anchor、KPI row metadata；
  - 不读取 Goldwind profile，不设置 verdict。
- `backend/src/standards/leaf_sufficiency.py`
  - 保存 GRI leaf 的原子化 expected components 和 missing item 模板；
  - 不保存页码、企业文本或 explicit verdict。
- `backend/tests/tools/test_evidence_promotion.py`
- `backend/tests/standards/test_leaf_sufficiency.py`

### 修改

- `backend/src/tools/kpi_row_matcher.py`
  - 增加行标签、年份、单位、scope token 和 value type 的结构化匹配。
- `backend/tests/tools/test_kpi_row_matcher.py`
- `backend/src/tools/retrieval.py`
  - 将 KPI row metadata 传给 promotion gate。
- `backend/tests/tools/test_retrieval.py`
- `backend/src/agents/disclosure_agent.py`
  - 在 source promotion 前应用通用门禁；
  - verdict 继续由 ontology + guardrail 决定。
- `backend/tests/agents/test_disclosure_agent.py`
- `backend/src/standards/evidence_ontology.py`
  - 仅在现有 facet/evidence kind 无法表达人工边界时增加最小 enum/matrix 条件。
- `backend/src/standards/evidence_contracts.py`
  - 逐步引用 `leaf_sufficiency`，不得新增 Goldwind 页码。
- `backend/src/tools/holdout_stratified_sample.py`
  - 增加定向 50 条扩展选择接口。
- `backend/tests/tools/test_holdout_stratified_sample.py`
- `backend/src/tools/holdout_review_pack.py`
  - 生成增量 50 条复核包和累计 150 条 selection manifest。
- `backend/tests/tools/test_holdout_review_pack.py`
- `backend/src/tools/first_pass_quality.py`
  - 输出 known-100 remediation metrics 和新增 50 条待复核状态。
- `backend/tests/tools/test_first_pass_quality.py`
- `docs/DEVELOPMENT.md`
  - 记录执行命令、质量 gate 和产物。

### 报告实例层

- `backend/data/reports/profiles/goldwind_2024.json`
  - 只在 profile builder 可复现地生成错误 route/metric term 时修改；
  - 允许存储 Goldwind 页码、表格页和行标签；
  - 禁止直接存储 verdict。

## 5. 执行任务

### Task 1：冻结人工 gold 与诊断 manifest

**文件：**

- 修改 `backend/src/tools/first_pass_quality.py`
- 修改 `backend/tests/tools/test_first_pass_quality.py`
- 新增产物 `tmp/review/holdout_goldwind_2024_stratified_100_remediation_manifest.csv`

- [ ] 写失败测试：100 条 reviewed CSV 必须完整、唯一并可按 `issue_type`、suggested verdict、source/correct pages 聚合。
- [ ] 写失败测试：manifest 必须保留人工 gold，不回写 reviewed CSV。
- [ ] 实现 manifest 生成纯函数，字段固定为：
  - `requirement_id`
  - `current_verdict`
  - `suggested_verdict`
  - `issue_type`
  - `current_source_pdf_pages`
  - `correct_pdf_pages`
  - `semantic_group`
  - `evidence_kinds`
  - `remediation_group`
- [ ] 生成 manifest，并核对 100 行、100 个唯一 requirement。
- [ ] 固化当前指标 JSON，确认 `manual_gold_available=true`。

**验证：**

```powershell
cd backend
uv run --no-sync pytest tests/tools/test_first_pass_quality.py -q
```

### Task 2：建立 leaf-level source promotion gate

**文件：**

- 新增 `backend/src/tools/evidence_promotion.py`
- 新增 `backend/tests/tools/test_evidence_promotion.py`
- 修改 `backend/src/agents/disclosure_agent.py`
- 修改 `backend/tests/agents/test_disclosure_agent.py`

- [ ] 先写以下 negative tests：
  1. 预估年度减排量最多支撑 partial，不能证明报告期实际减排量；
  2. supplier audit grade 不能满足重大负面影响供应商数量；
  3. OHS training hours 不能满足 employee hours worked；
  4. occupational disease cases 不能满足 work-related ill-health fatalities；
  5. general employee communication 不能满足 minimum notice weeks；
  6. general workforce data 不能满足 parental-leave return/retention by gender；
  7. section-adjacent page without leaf anchor remains candidate-only。
- [ ] 确认测试因 promotion gate 缺失而失败。
- [ ] 定义结构：

```python
@dataclass(frozen=True)
class EvidencePromotionContext:
    requirement_id: str
    semantic_group: SemanticGroup | None
    facets: tuple[RequirementFacet, ...]
    evidence_kind: EvidenceKind | None
    matched_terms: tuple[str, ...]
    kpi_row_label: str | None
    kpi_row_unit: str | None
    kpi_row_value: str | None
    source_text: str

@dataclass(frozen=True)
class EvidencePromotionDecision:
    promote: bool
    max_verdict: AssessmentVerdict
    reason: str
```

- [ ] 实现 report-agnostic promotion 规则。
- [ ] 在 `DisclosureAgent` 过滤 candidate evidence 后、分类前应用 gate。
- [ ] 保持 candidate pages 不变，仅修改 source evidence 和 max verdict。
- [ ] 跑 focused tests。

**验证：**

```powershell
cd backend
uv run --no-sync pytest tests/tools/test_evidence_promotion.py tests/agents/test_disclosure_agent.py -q
```

### Task 3：增强 KPI 行级匹配

**文件：**

- 修改 `backend/src/tools/kpi_row_matcher.py`
- 修改 `backend/tests/tools/test_kpi_row_matcher.py`
- 修改 `backend/src/tools/retrieval.py`
- 修改 `backend/tests/tools/test_retrieval.py`

- [ ] 先写 synthetic table tests，覆盖：
  - Scope 1/2/3 数值不得互相传播；
  - energy total、fuel、electricity、reduction 分开；
  - fatality count、recordable injury、hours worked、training hours 分开；
  - employee turnover 与 parental leave 分开；
  - supplier environmental/social screening、impact count、improvement rate 分开；
  - 年份列优先使用报告期列；
  - `无数据` 不得回退抓取相邻数值。
- [ ] 给 `KpiRowMatch` 增加最小 metadata：
  - `matched_term`
  - `scope_tokens`
  - `value_type`
  - `year_column`
- [ ] 行级 preview 必须从目标 row label 开始，并包含报告期表头或 year metadata。
- [ ] `retrieval.py` 将 metadata 写入 evidence metadata，供 promotion gate 使用。
- [ ] 不在 matcher 中写 requirement ID 或 Goldwind 页码。

**验证：**

```powershell
cd backend
uv run --no-sync pytest tests/tools/test_kpi_row_matcher.py tests/tools/test_retrieval.py -q
```

### Task 4：修复 report profile source promotion

**文件：**

- 修改 `backend/src/tools/evidence_routing.py`
- 修改 `backend/tests/tools/test_evidence_routing.py`
- 必要时修改 `backend/data/reports/profiles/goldwind_2024.json`
- 修改 `backend/tests/reports/test_profile_builder.py`

- [ ] 写失败测试：profile route 返回 candidate pages，不保证全部成为 source。
- [ ] 写失败测试：同一章节环境 KPI 不得支撑社会 KPI，OHS 附录页不得支撑管理体系 leaf。
- [ ] 写失败测试：Goldwind PDF 25/26 的 metric row 可由行标签选择，但通用逻辑不引用页码。
- [ ] profile route 保留候选页；source promotion 委托 Task 2 gate。
- [ ] 若 profile 缺少自动生成的 KPI table/metric terms，只修改 builder 输入可复现字段。
- [ ] 重建 profile 后抽样核对 PDF 25、26、34、46、47 route。

**验证：**

```powershell
cd backend
uv run --no-sync pytest tests/tools/test_evidence_routing.py tests/reports/test_profile_builder.py -q
```

### Task 5：建立原子化 leaf sufficiency metadata

**文件：**

- 新增 `backend/src/standards/leaf_sufficiency.py`
- 新增 `backend/tests/standards/test_leaf_sufficiency.py`
- 修改 `backend/src/standards/evidence_contracts.py`
- 修改 `backend/src/standards/no_evidence_guardrails.py`
- 修改 `backend/tests/standards/test_evidence_contracts.py`
- 修改 `backend/tests/standards/test_no_evidence_guardrails.py`

- [ ] 先为人工指出的 leaf 写失败测试：
  - `303-1-a`
  - `305-2-e`
  - `306-3-a`
  - `401-1-b`
  - `404-2-a`
  - `416-1-a`
  - `305-2-d-i`
  - `406-1-b-i`
  - `406-1-b-ii`
  - `408-1-b`
  - review note 标记的 3 条次要问题
- [ ] 定义：

```python
@dataclass(frozen=True)
class LeafSufficiencyRule:
    requirement_id: str
    expected_components: tuple[str, ...]
    missing_item_templates: tuple[str, ...]
    excluded_neighbor_components: tuple[str, ...] = ()
```

- [ ] 每条 missing item 保持单一语义，不混入相邻 leaf。
- [ ] contract 只引用标准 metadata；不复制 Goldwind rationale 或页码。
- [ ] compilation guardrail 仍由 `compilation_guardrails.py` 提供，不进入 leaf templates。
- [ ] 添加全表静态测试：同一 leaf 的 `missing_item_templates` 不得命中其 `excluded_neighbor_components`。

**验证：**

```powershell
cd backend
uv run --no-sync pytest tests/standards/test_leaf_sufficiency.py tests/standards/test_evidence_contracts.py tests/standards/test_no_evidence_guardrails.py -q
```

### Task 6：重跑 Goldwind 577 与现有 100 条 remediation gate

**文件/产物：**

- `tmp/review/holdout_goldwind_2024_after_remediation.csv`
- `tmp/review/holdout_goldwind_2024_after_remediation_audit.json`
- `tmp/review/holdout_goldwind_2024_stratified_100_after_remediation_quality.json`
- `tmp/review/holdout_goldwind_2024_stratified_100_after_remediation_diff.csv`

- [ ] 使用正式 regeneration 入口重跑 Goldwind，保持 OCR/LLM 关闭：

```powershell
cd backend
uv run --no-sync python -m src.tools.regenerate_review_csv `
  --report-id goldwind_2024 `
  --pdf "data/reports/Goldwind 2024-zh.pdf" `
  --profile data/reports/profiles/goldwind_2024.json `
  --output ../tmp/review/holdout_goldwind_2024_after_remediation.csv `
  --audit-output ../tmp/review/holdout_goldwind_2024_after_remediation_audit.json `
  --report-total-pages 52
```

- [ ] 用现有 100 条 reviewed gold 计算 remediation metrics。
- [ ] 输出逐 requirement diff：current/suggested/new verdict、current/correct/new source pages、missing items。
- [ ] 核对 5 条 seed 无回退。
- [ ] 跑 Goldwind 577 audit。

**现有 100 条放行条件：**

- `false_disclosed_count = 0`
- `wrong_source_page_count <= 2`
- `unknown_leakage_count <= 10`
- `profile_route_valid_evidence_rate >= 0.90`
- `cross_leaf_missing_items_count = 0`
- `guardrail_as_evidence_count = 0`
- 12 条 false disclosed、19 条 wrong source、17 条 leakage、9 条 cross-leaf 均有逐条 diff 解释
- 不得出现人工 gold 之外的 `unknown/partial -> disclosed`

任一条件失败时触发停止，不生成新增 50 条。

### Task 7：执行 Envision 577 回归

- [ ] 运行：

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

- [ ] 要求 577 requirement 数量不变。
- [ ] 要求 verdict/review/source/evidence/page/quality/OCR-VLM 无非预期 diff。
- [ ] 允许 `missing_items` 出现本计划明确的 leaf 原子化变化。
- [ ] 任一非预期变化触发停止。

### Task 8：从剩余 477 条定向新增 50 条

**文件：**

- 修改 `backend/src/tools/holdout_stratified_sample.py`
- 修改 `backend/tests/tools/test_holdout_stratified_sample.py`

**输出：**

- `tmp/review/holdout_goldwind_2024_targeted_50_selection.csv`
- `tmp/review/holdout_goldwind_2024_stratified_150_selection.csv`
- `tmp/review/holdout_goldwind_2024_targeted_50_summary.json`

- [ ] 先写失败测试：新增 50 条不能与原 100 条重复。
- [ ] 先写失败测试：同一输入结果确定、无随机性。
- [ ] 按剩余可用 requirement 调整五主题配额，总数保持 50：
  - `ohs_kpi`
  - `supplier_environment_social_assessment`
  - `energy_ghg_kpi`
  - `employee_turnover_parental_leave`
  - `zero_event_compliance`
- [ ] 固定配额：`ohs_kpi=12`、`supplier_environment_social_assessment=4`、`energy_ghg_kpi=12`、`employee_turnover_parental_leave=11`、`zero_event_compliance=11`。
- [ ] 每组 round-robin 覆盖实际存在的 route 状态；不要求不存在的 route 状态。
- [ ] 若任一主题无法满足调整后的固定配额，触发停止，不从无关主题补足。
- [ ] 原 100 条 selection 原样保留，累计 selection 恰好 150 条。

**验证：**

```powershell
cd backend
uv run --no-sync pytest tests/tools/test_holdout_stratified_sample.py -q
```

### Task 9：生成新增 50 条人工复核包

**文件：**

- 修改 `backend/src/tools/holdout_review_pack.py`
- 修改 `backend/tests/tools/test_holdout_review_pack.py`

**输出：**

- `tmp/review/holdout_goldwind_2024_targeted_50_review_pack.csv`

- [ ] 每个 requirement 一行，共 50 行、50 个唯一 requirement。
- [ ] 必须包含完整推理链：

```text
requirement_text
-> candidate/source evidence
-> rationale
-> missing_items
-> guardrail_items
-> verdict
```

- [ ] 必须包含 selection theme 和 selection reason。
- [ ] 人工字段保持空白：`manual_label`、`correct_pdf_pages`、`suggested_verdict`、`issue_type`、`review_note`。
- [ ] `unknown + no source evidence` 清空 stale evidence metadata。
- [ ] 最大 source/candidate PDF 页码不超过 52。
- [ ] `global_fallback=0`。

### Task 10：全量验证并到达人工停止点

- [ ] 运行 focused tests：

```powershell
cd backend
uv run --no-sync pytest `
  tests/tools/test_evidence_promotion.py `
  tests/tools/test_kpi_row_matcher.py `
  tests/tools/test_retrieval.py `
  tests/tools/test_evidence_routing.py `
  tests/agents/test_disclosure_agent.py `
  tests/standards/test_leaf_sufficiency.py `
  tests/tools/test_holdout_stratified_sample.py `
  tests/tools/test_holdout_review_pack.py `
  tests/tools/test_first_pass_quality.py -q
```

- [ ] 运行后端全量测试：

```powershell
cd backend
uv run --no-sync pytest -q
```

- [ ] 更新 `docs/DEVELOPMENT.md`，记录命令、产物、100 条 remediation gate 和新增 50 条结构。
- [ ] 执行 `git diff --check`。
- [ ] 输出新增 50 条 review pack 后暂停，等待人工复核。

## 6. 停止条件

命中任一条件必须立即暂停并汇报根因、影响和处理建议：

1. reviewed gold 不是 100 行、100 个唯一 requirement；
2. 任一人工字段为空；
3. 需要新增 Goldwind per-ID contract 或通用代码中的固定 Goldwind 页码；
4. 需要外部模型、OCR 或 VLM；
5. source/candidate PDF 页码超过 52；
6. `global_fallback` 回退；
7. guardrail 被用作 evidence 或直接推动 verdict；
8. 修复后现有 100 条任一放行门槛未通过；
9. 5 条 seed 任一 verdict/source 回退；
10. 人工 gold 之外出现新增 disclosed；
11. Envision 577 出现非预期 verdict/source/page/quality/OCR-VLM diff；
12. 定向五组任一无法满足调整后的固定配额；
13. 新增 50 条与原 100 条重复；
14. focused 或全量测试失败且三轮内无法在当前任务边界修复；
15. 原始 PDF、人工 gold 或批准 baseline 被修改。

## 7. 人工复核后的 150 条门槛

收到新增 50 条 reviewed CSV 后，合并原 100 条 gold 计算累计 150 条指标：

- `false_disclosed_count = 0`
- `wrong_source_page_count <= 3`
- `unknown_leakage_count <= 12`
- `profile_route_valid_evidence_rate >= 0.90`
- `cross_leaf_missing_items_count = 0`
- `guardrail_as_evidence_count = 0`

若通过，剩余 427 条继续作为 holdout；若未通过，仅针对失败主题继续修复，不自动扩展到全量 577 人工复核。

## 8. 非目标

本阶段不处理：

- Goldwind 全量 577 条人工复核；
- 将 Goldwind 设为正式 gold baseline；
- 新增报告专用 explicit verdict；
- 大规模重写 ontology matrix；
- 修改前端或数据库 schema；
- 启用 OCR/VLM/外部模型；
- 自动覆盖人工 reviewed CSV。
