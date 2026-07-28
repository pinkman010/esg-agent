# LLM 辅助建议层产品验收说明

## 1. 验收结论

当前 DeepSeek 接入只属于辅助复核建议层。外部模型默认关闭，只有分析请求显式传入 `confirm_llm=true` 时才允许调用。AI suggestion 不覆盖规则 assessment，用户采纳、修改或拒绝后均形成追加式人工 snapshot。

该能力用于辅助人工理解报告证据和缺失项，不构成 GRI 专家认证、外部鉴证或最终合规结论。当前正式 Envision v1.1 产品运行使用 `confirm_llm=false`，AI 阶段为 skipped，没有发生外部模型调用。

## 2. 权威层级

1. 规则 assessment：系统确定性基线。
2. AI suggestion：可选辅助建议。
3. 人工 snapshot：最终有效人工结论。

AI suggestion 不得设置适用性、风险优先级、人工复核状态或正式输出状态。没有人工 snapshot 时，产品使用规则结果；存在有效人工 snapshot 时，最终有效结论来自人工层。

## 3. 外部调用边界

- `confirm_llm=false`：不调用模型，只记录 run 级授权状态和 AI stage skipped。
- `confirm_llm=true`：只调用独立结构、高/中复核优先级且具有实质证据的候选。
- 测试不得真实调用外部模型。
- 每次真实模型评估均需要当次用户批准。
- 密钥只通过环境变量提供，不写入代码、文档、日志或评估产物。

## 4. 状态说明

- `succeeded`：建议通过 schema 和证据 guardrail。
- `failed`：当前后端版本同时包含技术失败和安全拦截，必须结合 `error_code` 与 `guardrail_codes` 判断。
- `skipped`：进入 AI 编排后因候选边界或调用预算未调用。
- 没有 suggestion：可能是 run 未授权、服务未配置或该项没有进入候选集合。

前端可以根据已有 guardrail 字段区分“需要人工独立判断”和“技术调用未完成”，但不得把被 guardrail 拦截的 suggestion 变成可采纳建议。

## 5. DeepSeek 工程基线

当前 225 条真实 DeepSeek 评估只作为工程质量基线。可比较样本为 224 条，一致 162 条，一致率 72.32%；applicability exception 为 1，targeted reruns 为 18。Guardrail 后 false disclosed、证据 ID 越界、可比错页、schema failure 和 model failure 均为 0。

规则与模型不一致不能直接解释为模型错误或规则错误。当前没有独立 ESG 专家 gold，因此不得用该一致率指导 Prompt、模型或候选筛选调整。

## 6. 风险清单

| 风险 | 当前控制 | 后续条件 |
| --- | --- | --- |
| `failed` 混合技术失败和安全拦截 | 结合 `error_code` 与 `guardrail_codes` 判断 | 只有明确运营需求后才解冻正式状态语义 |
| assessment 详情缺少 run 授权原因 | 前端使用概括性空态 | 精确拆分需要后端或页面 run context |
| 缺少采纳率、修改率和拒绝率 | 人工 snapshot 保留 reason code 和 suggestion ID | 可单独批准只读观测工具 |
| 缺少独立专家 gold | 不调 Prompt、模型和候选筛选 | 取得独立高质量 gold 后重新评估 |
| `assess_explicit_candidates()` 绕过默认筛选 | 仅评估工具和测试调用 | 后续可增加架构边界测试 |
| 影子 RAG 与正式 AI suggestion 混用 | Phase 1.5 与正式工作流隔离 | 只有独立批准 RAG Phase 2 后才讨论接入 |

## 7. 当前冻结决策

- 不保存 `confirm_llm=false` 的逐项 skipped suggestion。
- 不修改 DeepSeek 模型、Prompt、参数或候选筛选。
- 不修改数据库结构、API 状态语义或正式导出。
- 不改变规则、AI、人工三层优先级。
- 不把影子 RAG 接入正式 AI suggestion。
- `needs_human_review` 只作为后续可选的后端状态语义调整。
- `assess_explicit_candidates()` 只允许离线评估工具和测试使用，不进入默认产品工作流。

## 8. 当前验收门禁

- 后端 709 项测试通过。
- 前端 28 个测试文件、105 项测试、typecheck 和 production build 通过。
- Envision v3 为 `577/499/78/0`。
- Global fallback、新增 false disclosed 和新增 wrong source page 均为 0。
- Audit 为 0 error、0 warning。

这些门禁描述当前 v1.1 工程基线。后续文档或纯前端展示调整不能被表述为模型质量提升；任何后端语义变化必须解除冻结并重新执行完整门禁。
