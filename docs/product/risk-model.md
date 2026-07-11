# 固定风险模型

## 1. 输出结构

每条 assessment 生成：

```text
risk_level: high | medium | low
risk_reason_codes: string[]
risk_rule_version: string
calculated_at: datetime
```

第一版风险规则固定，不提供配置 UI。规则版本首版使用 `risk-v1`。

## 2. 优先级

高风险条件优先于中、低风险；中风险条件优先于低风险。同一条可有多个原因代码。

## 3. 高风险规则

| 原因代码 | 中文名称 | 条件 |
| --- | --- | --- |
| `analysis_failed` | 分析失败 | requirement 没有成功 assessment |
| `unknown_verdict` | 结论待确认 | system verdict 为 unknown |
| `no_valid_evidence` | 无有效证据 | 没有 substantive source evidence |
| `evidence_quality_risk` | 证据质量风险 | OCR/VLM、正文未抽取、扫描、低文本或解析失败 |
| `page_conflict` | 页码或证据冲突 | source 页冲突、越界或人工标记错页 |
| `non_substantive_only` | 仅有非实质证据 | 只有 omission note、index statement 或同类说明 |
| `sufficiency_conflict` | 证据充分性冲突 | verdict 与 leaf 要求、缺失维度或 guardrail 冲突 |
| `evidence_invalidated` | 人工判定证据无效 | 最新 review snapshot 标记证据无效 |
| `batch_review_check` | 批量操作待抽查 | 批量操作按固定规则进入抽查 |
| `reopened_after_formal` | 正式输出后重开 | requirement 或报告在正式输出后重开 |

## 4. 中风险规则

| 原因代码 | 中文名称 | 条件 |
| --- | --- | --- |
| `partial_disclosure` | 部分披露 | verdict 为 partially_disclosed 且有有效证据 |
| `missing_breakdown` | 缺拆分维度 | 缺性别、地区、员工类别或其他 leaf 拆分 |
| `missing_methodology` | 缺方法或假设 | 缺方法、基准、边界、换算或假设 |
| `action_required` | 存在整改项 | recommendation 或整改任务未完成 |

## 5. 低风险规则

必须同时满足：

- verdict 为 disclosed；
- 至少一条直接 substantive evidence；
- evidence quality 无高风险 flag；
- 没有 sufficiency conflict；
- 没有失败、重开或人工证据无效状态。

低风险原因代码为 `direct_disclosure_evidence`。

## 6. 人工操作后的重算

- 快速通过：保留系统风险，增加已复核状态；满足低风险条件时可降级；
- 修改结论或证据：基于最新 snapshot 重算；
- 证据无效：强制高风险；
- 重开：强制高风险；
- 重跑：生成新 assessment risk，不覆盖旧 risk。

每次重算保存旧值、新值、规则版本和触发事件。

## 7. 批量操作抽查

第一版固定规则：批量操作涉及 10 条及以上时，所有被操作项增加 `batch_review_check`，直到用户逐条打开并确认，或在批量确认对话框中完成二次确认并填写备注。该规则用于降低误批风险，不代表系统准确率。

## 8. API 和界面要求

API 返回中文展示所需的 `risk_level` 和 `risk_reason_codes`，前端通过本地业务词典显示中文。内部规则表达式不返回普通界面。

风险队列默认按以下顺序：分析失败、无有效证据、证据质量风险、unknown、充分性冲突、其他高风险。
