# Phase 1.5 收尾报告

## 1. 收尾结论

截至 2026-07-28，Phase 1.5 已完成工程收尾，可以继续保持 Envision v1.1 后端基线冻结。

本阶段完成两项增量：

1. 混合影子 RAG 工程验收；
2. 不改变 API 语义的 LLM 辅助建议前端展示收口。

本阶段没有把影子 RAG 接入正式 evidence、assessment、risk、AI suggestion、review snapshot、export、API 或前端，没有修改 DeepSeek 模型、Prompt、候选筛选、数据库 schema、规则、GRI checklist 或导出口径。

## 2. 固化版本

- 收尾复验基线：`570a996d42143e8ffde1bfc6b2693f4c3c3ad2d0`。
- RAG Phase 1.5 实施提交：`0cf3cbc`、`0b294f9`。
- LLM 冻结边界与展示提交：`8df78cd`、`2f0b8ac`、`570a996`。
- migration head：`0012_chunk_embeddings`。

## 3. RAG 工程结果

收尾复验使用 `EMBEDDING_ENABLED=false`，未调用 SiliconFlow 或 DeepSeek。封版工具在 PostgreSQL `REPEATABLE READ READ ONLY` 事务中完成。

| 指标 | 规则基线 | 混合 RAG |
| --- | ---: | ---: |
| Hit@5 | 0.789916 | 0.882353 |
| Recall@5 | 0.714146 | 0.793277 |
| MRR | 0.742297 | 0.816667 |

其他门禁：

- 499 个 context；
- 499 个唯一 requirement；
- 499 个唯一 context hash；
- 119 条具有历史工程 gold 的样本进入指标分母；
- 0 个重复页 context；
- 0 个未解析规则页 context；
- 0 个越界页；
- 0 个无效 shadow evidence ID；
- 0 个确定性 hash 差异；
- hybrid gain 11、loss 0；
- 18 张非影子正式表计数前后一致。

历史 `correct_pdf_pages` 只作为工程 gold。页码命中不代表披露充分，也不构成新增 ESG 专家判断。

## 4. LLM 辅助建议层结果

前端继续从既有 `status` 和 `guardrail_codes` 派生展示状态：

- 未启用或未进入候选；
- 建议生成成功；
- 安全护栏拦截，需人工独立判断；
- 未调用 AI；
- 技术调用未完成。

只有 `status=succeeded` 且存在建议结论时才显示采纳、载入修改和拒绝操作。`low_review_priority` 明确显示为低复核优先级跳过，不再误写为安全校验。

该变化只影响展示层。后端 `failed`、`skipped` 和 `succeeded` 状态语义、API 类型、追加式 suggestion、人工 snapshot 和 effective verdict 规则均未改变。

## 5. 收尾门禁

2026-07-28 在收尾基线上重新执行：

- 后端：709 项测试通过；
- Ruff：`src` 和 `tests` 全部通过；
- 前端：28 个测试文件、105 项测试通过；
- frontend typecheck 通过；
- frontend production build 通过；
- Envision v3：`577/499/78/0`；
- global fallback：0；
- 新增 false disclosed：0；
- 新增 wrong source page：0；
- final adjudication pending：0；
- audit：0 error、0 warning；
- 真实外部模型调用：0。

## 6. 冻结与延期范围

继续冻结：

- DeepSeek 模型、Prompt、参数和默认候选筛选；
- `ai_assessment_suggestions` 表结构；
- 正式 AI 状态枚举和 API 语义；
- 规则、证据、risk-v2.1、GRI checklist 和导出口径；
- RAG Phase 2 正式接入；
- RAG Phase 3。

明确延期：

- 只读离线 AI 观测工具；
- 正式 `needs_human_review` 后端状态；
- `assess_explicit_candidates()` 架构边界测试。

上述延期项不会因 Phase 1.5 收尾自动获得授权。

## 7. 后续进入条件

当前不建议仅为“进入下一阶段”而解冻后端。满足以下任一条件后，再单独评估 Phase 2 或后端 AI 语义调整：

1. 出现可复现的正式 evidence 召回缺口，且影子 RAG 能明确降低该缺口；
2. 积累足够的 AI 采纳、修改和拒绝数据，需要只读观测；
3. `failed` 混合技术失败和护栏拦截已经影响运营判断；
4. 获得独立 ESG 专家 gold，可支持模型、Prompt 或候选筛选调整；
5. 产品明确要求把 RAG context 接入 AI suggestion，并接受完整后端门禁重跑。

在进入条件出现前，Phase 1.5 作为工程基线保留，不构成 GRI 认证、外部鉴证或最终合规结论。

实际产品巡检、问题优先级和后续证据采集格式见 `docs/product/phase1.5-product-observation-backlog.md`。
