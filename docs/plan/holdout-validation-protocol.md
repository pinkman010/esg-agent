# Holdout 验证协议

## 目标

验证 ontology、report profile 和 evidence routing 是否具备跨样本泛化能力。该协议只定义接口、指标和停止条件，当前阶段不执行 holdout。

## 样本选择

- 优先选择另一份企业 ESG 报告。
- 若暂时没有第二份报告，使用 Envision 2024 中未参与迁移决策的保留样本。
- holdout 样本不得新增 per-ID explicit verdict。
- holdout 样本不得新增报告特定页码规则；允许通过自动生成的 report profile 给出候选页。

## 输入文件

- first-pass 输出：`tmp/review/holdout_first_pass.csv`
- 人工复核输出：`tmp/review/holdout_reviewed.csv`
- 质量报告：`tmp/review/holdout_quality_summary.json`

## 人工复核字段

holdout 人工复核 CSV 至少包含：

- `requirement_id`
- `manual_label`
- `correct_pdf_pages`
- `suggested_verdict`
- `issue_type`
- `review_note`

`issue_type` 可用值：

- `missed_evidence`
- `false_disclosed`
- `wrong_source_page`
- `over_strict_unknown`
- `acceptable`

## 质量指标

必须输出：

- first-pass recall
- false disclosed count
- wrong source page count
- unknown leakage count
- disclosed precision
- partial precision
- global fallback count
- profile route hit count
- ontology matrix hit count

## 硬性停止条件

出现任一情况不得进入下一阶段：

- `global_fallback > 0`
- `false_disclosed_count > 0`
- `wrong_source_page_count > 0`
- omission note 被判为 `disclosed` 或 `partially_disclosed`
- KPI 表证据缺少 `complex_table`
- report profile 页码超过报告总页数

## 通过标准

首轮建议门槛：

- `global_fallback = 0`
- `false_disclosed_count = 0`
- `wrong_source_page_count = 0`
- first-pass recall 高于当前 Envision 逐批修复前平均水平
- unknown leakage 明显下降

## 执行顺序

1. 使用 profile builder 生成 holdout 初始 profile。
2. 跑 first-pass assessment。
3. 人工复核 `holdout_first_pass.csv`。
4. 使用 `first_pass_quality` 输出质量报告。
5. 只允许通过 semantic group、facet、evidence kind、profile routing 修复问题。
6. 禁止通过 holdout per-ID explicit verdict 修复问题。
