# Ontology Contract Migration Full Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将大部分 per-ID explicit verdict 从 `evidence_contracts.py` 迁移到 ontology matrix，让同构 requirement 由 `semantic_group + facet + evidence_kind + guardrail` 判定，同时保留必要 per-ID guardrail。

**Architecture:** 以已经人工复核通过的 577 条 eligible requirement 为 baseline，每次只迁移一个语义组或一个小型语义簇。每次迁移后必须重跑 577 regression diff、review CSV audit、first-pass quality 和相关 pytest；只有 diff 为 0 或仅出现预期的 rationale / missing_items 变化时才提交。

**Tech Stack:** Python 3.11、pytest、现有 `RequirementEvidenceContract`、`backend/src/standards/evidence_ontology.py`、`DisclosureAgent`、review CSV audit、first-pass quality、577 review CSV baseline、84 条 compilation requirement guardrail mapping。

---

## 1. 当前状态

当前目标已经从 pilot 扩展为“大部分 per-ID explicit verdict 迁移完”。已完成或正在完成的基础工作：

- 577 条 eligible requirement 已作为主 assessment baseline。
- 84 条 `compilation_requirement` 已导出并复核为 guardrail / missing item / sufficiency rule 映射，不作为独立 assessment。
- `supplier_assessment` 已完成试点迁移。
- `ohs_kpi` 已完成试点迁移。
- `breakdown_dimension` 已完成试点迁移。
- `zero_event_compliance` 尚未迁移，是下一批优先任务。

本计划接续 `docs/plan/ontology-contract-migration-pilot-plan.md`，目标是从少数组试点推进到大部分 per-ID explicit verdict 的系统性迁移。

## 2. 不做范围

- 不删除所有 per-ID contract。
- 不迁移候选页、allowed pages、forbidden pages、quality flags、当前报告回归保护。
- 不把固定 PDF 页码写成跨报告通用规则。
- 不通过放宽 `disclosed` 门槛换取 recall。
- 不把 84 条 `compilation_requirement` 变成独立 assessment。
- 不启用外部模型。
- 不改数据库 schema。
- 不改前端 UI。
- 不一次性迁移全部剩余 contract。

## 3. 核心原则

### 3.1 迁移对象

本计划迁移的是 per-ID explicit verdict，包括：

- `verdict`
- `review_status`
- 可以泛化的 `rationale`
- 可以由 ontology matrix 生成的通用 `missing_items`

本计划保留 per-ID guardrail，包括：

- 当前报告候选页和证据页约束。
- 禁止页和错证据防护。
- 报告特定措辞解释。
- 最大 verdict 限制。
- 已知误升 disclosed 的防线。
- compilation requirement 产生的 sufficiency guardrail。

### 3.2 迁移分类

每个目标 requirement 必须先归入以下三类之一：

| 类别 | 处理方式 | 示例 |
| --- | --- | --- |
| 可移除 explicit verdict | verdict 可完全由 ontology matrix 复现 | KPI 直接数量、直接比例、明确零事件 leaf |
| 保留 guardrail，移除 explicit verdict | matrix 给默认 verdict，contract 只约束边界和缺口 | 缺 breakdown、缺 why、缺方法、缺范围 |
| 暂不迁移 | 依赖报告特定语义或历史误判风险高 | 政策文本容易误判为风险识别结果、复杂索引语义、低质量 OCR 页 |

### 3.3 disclosed 红线

matrix 只有在以下条件同时满足时才允许输出 `disclosed + not_required`：

1. `semantic_group` 与 requirement 语义匹配。
2. `facet` 完整表达 leaf requirement 的充分性要求。
3. `evidence_kind` 是强证据，例如 `kpi_value`、`kpi_breakdown` 或明确的 `explicit_zero_statement`。
4. evidence scope 与 requirement scope 一致。
5. 没有 contract、compilation guardrail 或 missing item 指出关键缺口。
6. 没有从 parent 或 sibling requirement 传播来的不充分证据。

出现以下任一情况，最高只能是 `partially_disclosed` 或 `unknown`：

- 只有政策或管理机制，没有具体结果。
- 只有总体值，缺少要求的性别、地区、员工类别、供应商类型或方法拆分。
- 只有零事件总声明，却要求罚款、警告、来源分类、往期事件归属。
- 只有案例或项目描述，缺少比例、覆盖范围、影响评估或边界说明。
- 只有索引页定位，缺少实质证据。

## 4. 停止条件

任一迁移批次触发以下条件，必须暂停，不能继续下一组：

- 577 unique requirement 数量变化。
- `global_fallback` 回归。
- `omission_note` 或 `not_applicable` 被升为 `partial/disclosed`。
- 非预期 `unknown/partial -> disclosed`。
- `disclosed` 数量意外增加。
- `review_status` 与 verdict 错配。
- `source_pdf_page`、`source_report_page`、`page_label` 出现非预期变化。
- `evidence_type`、`retrieval_strategy`、`quality_flags`、OCR/VLM 字段回退。
- KPI evidence 丢失 `complex_table`。
- `page_label` 出现 `?` 乱码或字面量 `\u`。
- 84 条 compilation guardrail 被当成独立 assessment。
- matrix 规则无法用 semantic group / facet / evidence kind 表达，只能靠具体报告解释。

触发停止条件时，处理方式：

1. 记录触发的 requirement、字段、diff 和对应规则。
2. 判断是计划内预期变化、实现 bug、规则过宽还是 baseline 需要人工复核。
3. 对实现 bug 先修复并重跑当前批次。
4. 对规则过宽，收窄 matrix 或退回 per-ID guardrail。
5. 对 baseline 争议，暂停并等待人工复核。

## 5. 每批固定执行流程

每批迁移都必须按以下顺序执行：

1. 选定一个 semantic group 或小型语义簇。
2. 统计该组 per-ID explicit verdict 和 contract guardrail。
3. 写 ontology matrix 失败测试。
4. 写 contract metadata 失败测试。
5. 写 agent 行为回归测试。
6. 实现最小 ontology / contract 修改。
7. 跑 focused pytest。
8. 生成 577 ontology review CSV。
9. 跑 review CSV audit。
10. 跑 577 diff。
11. 跑 first-pass quality。
12. 检查停止条件。
13. diff 通过后提交。

每批最小命令：

```powershell
uv run --no-sync pytest tests/standards/test_evidence_ontology.py tests/standards/test_evidence_contracts.py tests/agents/test_disclosure_agent.py -q
uv run --no-sync pytest tests/tools/test_review_csv_audit.py tests/tools/test_first_pass_quality.py -q
```

577 regression 复用 `docs/plan/ontology-regression-validation-plan.md` 中的脚本和输出路径：

- `tmp/review/current_577_review_after_ontology.csv`
- `tmp/review/current_577_review_after_ontology_audit.json`
- `tmp/review/current_577_review_ontology_diff.csv`
- `tmp/review/current_577_review_ontology_diff_summary.json`

## 6. 阶段路线

### Phase 1：完成 pilot 剩余组

目标：完成 `416 / 417 / 418 zero_event_compliance`。

迁移内容：

- 明确零事件 leaf 可由 `explicit_zero_statement` 给出 `disclosed`。
- 零事件总声明不能传播到罚款、警告、自愿准则、投诉来源分类、往期事件归属。
- 产品安全零事件、标签违规零事件、营销传播零事件、客户隐私零投诉分别保持 scope 隔离。

保留 guardrail：

- `416-2-a-i / a-ii / a-iii`
- `417-2-a-i / a-ii / a-iii`
- `417-3-a-i / a-ii / a-iii`
- `418-1-a-i / a-ii`
- 往期事件归属和无过错排除相关 compilation guardrail。

验收：

- 577 diff 中 verdict、review_status、页码、evidence 字段不得变化。
- 允许 `evidence_type` 后续从 `substantive` 精细化为 `explicit_zero_statement`，但本阶段若发生该变化必须单独列为预期 diff。

### Phase 2：接入 84 条 compilation guardrail

目标：将 `tmp/review/compilation_requirement_mapping_fixed.csv` 转成正式 sufficiency guardrail，不作为独立 assessment。

迁移内容：

- `requires_exclusion_scope`
- `requires_method_or_assumption`
- `requires_rate_basis`
- `requires_prior_period_attribution`
- `requires_fault_exclusion`
- `requires_water_stress_methodology`
- `requires_reporting_period_alignment`

实现要求：

- guardrail 只影响 `missing_items`、max verdict 或 disclosed gate。
- guardrail 不能单独制造 evidence。
- guardrail 不能把 unknown 升为 partial/disclosed。
- header-only compilation rows 必须继续排除。

验收：

- 577 assessment 数仍为 577。
- 84 条 compilation requirement 不出现在 review CSV 主 assessment 中。
- `missing_items` 可出现预期增加。
- `disclosed` 不得因 guardrail 接入增加。

### Phase 3：环境、能源、水、废弃物 KPI 组

目标：迁移 `302 / 303 / 305 / 306` 中可泛化的 KPI 数量、总量、方法、拆分和边界规则。

候选 semantic group：

- `energy_kpi`
- `water_kpi`
- `ghg_emissions_kpi`
- `waste_kpi`
- `methodology_guardrail`

优先迁移：

- 明确总量 KPI。
- 明确范围一、范围二、范围三排放总量。
- 明确节能量、减排量。
- 明确取水、排水、废弃物总量和主要拆分。

保留 guardrail：

- GWP rates。
- 基准年和重算。
- 水压力区域拆分。
- 排放目的地。
- 废弃物 recovery operation 拆分。
- effluent exclusion。
- 方法、假设、换算因子来源。

验收：

- 不得把总量 KPI 传播到方法 leaf。
- 不得把案例型节能或回收项目升为 disclosed。
- KPI 表必须保留 `complex_table`。

### Phase 4：合规、零事件、投诉和事件分类组

目标：迁移 `406 / 416 / 417 / 418` 以及类似零事件声明和事件分类规则。

候选 semantic group：

- `zero_event_compliance`
- `incident_classification`
- `complaint_kpi`

优先迁移：

- 明确“无歧视事件”。
- 明确“无客户隐私或数据丢失投诉”。
- 明确“无产品安全伤害事件”方向。

保留 guardrail：

- 不传播到罚款、警告、整改状态。
- 不传播到投诉来源分类。
- 不传播到往期事件归属。
- 不传播到标签违规或营销传播违规。

### Phase 5：员工、OHS、培训、多元化组扩展

目标：在已迁移的 `ohs_kpi` 和 `breakdown_dimension` 基础上，继续迁移相似条目。

候选 semantic group：

- `employee_kpi`
- `training_kpi`
- `ohs_management`
- `benefits_policy`
- `diversity_breakdown`

优先迁移：

- 员工总量、新进、离职、培训小时、绩效考核覆盖率。
- OHS 死亡、工时、TRIR、职业病数量。
- 管理层/员工性别、年龄、多元化比例的 partial 口径。

保留 guardrail：

- 管理层不自动等同治理机构。
- 总体值不满足性别和员工类别拆分。
- 外部供方不自动等同所有非雇员工作者。
- LTIR 不自动等同 high-consequence injury rate。
- 职业病病例不自动等同全部 work-related ill health。

### Phase 6：供应商、人权、社区、政策机制组

目标：迁移政策、机制、供应商筛查、人权风险、社区项目等非纯 KPI 规则。

候选 semantic group：

- `supplier_assessment`
- `human_rights_policy`
- `community_program`
- `management_mechanism`
- `risk_identification`

优先迁移：

- 已验证的 308/414 供应商评估规则扩展。
- 禁止童工、强迫劳动、供应商行为准则等 policy 只给 partial 或 unknown 的边界。
- 社区项目案例只给 partial 的边界。

保留 guardrail：

- policy 不能支撑具体风险运营点或供应商类型。
- 社区项目不能支撑运营点覆盖比例。
- 供应商退出机制不能支撑终止关系原因。
- 风险管理机制不能替代风险识别结果。

### Phase 7：税务、治理、薪酬、经济专题组

目标：迁移 `201 / 202 / 203 / 207` 等经济与治理专题中可泛化的 partial/unknown 边界。

候选 semantic group：

- `economic_kpi`
- `tax_governance`
- `governance_policy`
- `omission_confidentiality`

优先迁移：

- `omission_note` confidentiality。
- 税务治理 partial。
- 经济价值和政府补助从略披露 guardrail。
- 气候财务影响的风险/机会/行动 partial 与成本 unknown。

保留 guardrail：

- 保密从略不能升 disclosed。
- 治理架构不能支撑最高治理机构完整组成。
- 税务合规机制不能支撑税务战略公开链接或利益相关方沟通细项。

## 7. 完成标准

达到以下条件时，可认为“大部分 per-ID explicit verdict 迁移完”：

- 剩余 explicit verdict 只保留在高风险、报告特定或人工复核争议条目。
- 已迁移 semantic group 均有 ontology matrix 单元测试。
- 已迁移 contract 均有 metadata 测试。
- `DisclosureAgent` 行为测试覆盖每个主要 semantic group。
- 577 regression audit 通过。
- 577 diff 无非预期 verdict / review_status / evidence 字段变化。
- first-pass quality 指标无回退。
- 84 条 compilation guardrail 已接入，且不作为独立 assessment。
- 输出剩余 per-ID explicit verdict 清单和保留理由。

建议量化门槛：

- per-ID explicit verdict 数量较 full migration 前下降至少 60%。
- 每个已迁移 semantic group 至少有 1 个正例和 2 个反例测试。
- 所有 `disclosed` 输出都能追溯到强 evidence kind 或 explicit zero statement。

## 8. 提交策略

每个 semantic group 或小型语义簇独立提交。

提交信息格式：

```text
refactor: migrate <semantic-group> verdicts to ontology
```

示例：

```text
refactor: migrate zero event compliance verdicts to ontology
refactor: add compilation requirement guardrails to ontology
refactor: migrate water KPI verdicts to ontology
```

每次提交前必须确认：

- focused tests pass。
- 577 regression gate pass。
- diff summary 已检查。
- 工作区只包含本批次相关代码和测试。

## 9. 最终交付物

- 更新后的 `backend/src/standards/evidence_ontology.py`。
- 精简 explicit verdict 后的 `backend/src/standards/evidence_contracts.py`。
- compilation guardrail 正式代码和测试。
- 每个 semantic group 的 matrix 测试。
- `DisclosureAgent` 行为回归测试。
- `tmp/review/current_577_review_after_ontology.csv`。
- `tmp/review/current_577_review_ontology_diff_summary.json`。
- 剩余 per-ID explicit verdict 清单。
- `docs/DEVELOPMENT.md` 中记录迁移口径、回归命令和停止条件。

