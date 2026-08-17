# AI 候选路由与证据类型治理验收报告

## 1. 验收范围

本轮只验证 AI 候选路由、已授权零候选记录、前端原因表达、只读观测和调用边界。规则 verdict、适用性、风险、人工 snapshot、GRI `577/499/78/0`、数据库结构、Prompt、OCR/VLM、RAG 和正式导出均属于保护区。

## 2. 实施前基线

基线提交为 `542a49c`，工作分支为 `main`，开始时本地相对 `origin/main` ahead 2。

最新已授权 Envision 运行共有 499 个独立判断项：

| 结果 | 数量 |
|---|---:|
| `low_review_priority` | 436 |
| `no_substantive_evidence` | 59 |
| succeeded / 实际调用 | 4 |
| failed | 0 |

4 个实际调用项为 `GRI 2-5-a`、`GRI 2-5-b-i`、`GRI 2-5-b-ii`、`GRI 2-5-b-iii`。它们共同引用 PDF 第 77 页，质量标记包含 `short_text` 和 `image_body_not_extracted`，metadata 缺少显式 `evidence_type`。返回 verdict 均为 `unknown`，confidence 为 0%、0%、10%、20%。

基线 focused tests：

```text
42 passed in 10.76s
```

命令覆盖 `test_ai_assessment_service.py`、`test_single_report_workflow.py` 和 `test_evaluate_deepseek_against_manual_review.py`。

## 3. 缺陷根因

`AIAssessmentService` 将缺少 `evidence_type` 的 evidence 默认视为 `substantive_report_evidence`，没有结合 `image_body_not_extracted`。因此正文未提取的第 77 页通过 `should_call()`，产生 4 次无效外部模型调用。模型返回低置信度 `unknown`，没有覆盖规则结论，说明 response guardrail 有效，但候选资格仍需收紧。

## 4. 实施边界

- `image_body_not_extracted` 仅在 AI 本地分类中视为不合格证据，不回写 evidence。
- `index_page_bounded` 和 `candidate_page_source` 只用于诊断，不能单独决定 evidence 是否实质。
- `confirm_llm=false` 继续保持零调用、run 级 skipped、无逐项 suggestion。
- `confirm_llm=true` 且零合格候选时保存逐项 skipped 原因，但不调用模型。
- 真实 DeepSeek 前后对比需要独立授权，本轮默认不执行。

## 5. 实施与验证结果

### 5.1 代码差异

本轮形成两个代码提交：

| 提交 | 内容 |
|---|---|
| `424093b` | AI evidence eligibility、默认候选筛选、已授权零候选记录和后端回归测试 |
| `17e780b` | 前端中文跳过原因、只读 AI 观测 CLI、脱敏输出和显式候选调用边界 |

没有 Alembic、数据库 schema、OpenAPI、Prompt、模型参数、requirement manifest、evidence contract、risk rule 或 export 文件变更。

### 5.2 TDD 证据

- evidence eligibility RED：3 项失败，证明 `image_body_not_extracted` 仍被识别为实质证据并触发 4 次 fake 调用；GREEN：20 项通过。
- workflow RED：已授权零候选得到 0 条 suggestion，预期 2 条；GREEN：47 项 service/workflow 测试通过。
- 前端 RED：3 项中文映射断言失败，其余 146 项通过；GREEN：2 个 focused 文件 14 项通过。
- 观测工具先后因模块和 I/O 入口不存在进入 RED；GREEN：7 项指标、只读事务和脱敏输出测试通过。
- 显式候选边界 RED：方法缺少边界 docstring；GREEN：AST 检查确认唯一生产代码调用方为离线评估工具。

### 5.3 真实只读基线观测

只读 CLI 在 demo PostgreSQL 上读取历史 Envision run，得到：

```text
suggestion_count = 499
called_count = 4
succeeded_count = 4
skipped_count = 495
technical_failed_count = 0
guardrail_blocked_count = 0
skip reasons = 436 low_review_priority + 59 no_substantive_evidence
confidence buckets = 3 in 0-19% + 1 in 20-39%
```

输出保存在 `tmp/ai/`，未提交。该工具只读数据库，没有调用 DeepSeek，也没有输出 raw response、input hash、usage、证据正文、密钥或数据库 URL。

### 5.4 完整门禁

| 门禁 | 结果 |
|---|---|
| 后端 AI 纵向 | 87 passed |
| 后端全量 | 792 passed |
| Ruff | 0 error |
| 前端 lint | 0 error、2 条既有 warning |
| 前端测试 | 39 个文件、149 passed |
| 前端 typecheck | 通过 |
| production build | 通过 |
| Envision scope | `577/499/78/0` |
| global fallback | 0 |
| 新增 false disclosed | 0 |
| 新增 wrong source page | 0 |
| review CSV audit | 0 error、0 warning |
| 最终裁决 pending | 0 |

### 5.5 外部调用与结论边界

本轮执行产生的真实 DeepSeek、SiliconFlow、OCR 和 VLM 调用均为 0。4 个 GRI 2-5 缺陷样本已经通过默认 `assess_candidates()` 回归测试固定为 `no_substantive_evidence`，fake client 调用为 0。没有执行 Task 9 的新真实 DeepSeek 产品 run，因此不宣称模型 confidence 已提高。

规则 verdict、适用性、风险、人工 snapshot、正式导出和 `577/499/78/0` 均未改变。新分类器只提高 AI 候选资格精度，不改善缺失正文的 evidence recall。

## 6. 剩余风险与后续判断

1. PDF 第 77 页的鉴证正文仍带 `image_body_not_extracted`，本轮选择跳过 AI；要分析正文仍需独立 OCR/VLM 阶段和真实样本门禁。
2. 缺少 `evidence_type` 且没有 `image_body_not_extracted` 的 evidence 继续按兼容口径视为 substantive，避免破坏现有数字文本召回。后续只有出现新的误调用证据时才扩展分类，不采用公司名、固定页码或中文关键词硬编码。
3. confidence 是模型自报分数，当前没有独立 ESG 专家 gold，不能做可靠校准或准确率结论。
4. Task 9 保持未执行。当前自动回归和零调用安全门禁已足以验收路由代码；只有需要验证真实产品运行的调用数量、成本或供应商行为时，再单独授权该任务。

## 7. 验收结论

Task 1–8 达到计划完成条件：弱证据被默认 AI 路由拦截、已授权零候选可解释、未授权语义保持、观测可复现、显式评估未进入产品路径，前后端和 Envision 完整 gates 均通过。后端基线可在本轮文档提交后重新冻结；Task 9 和 OCR/VLM 不属于本次完成条件。
