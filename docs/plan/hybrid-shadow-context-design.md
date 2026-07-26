# 混合影子上下文设计

## 目标

在现有 SiliconFlow `BAAI/bge-m3` 影子向量召回基础上，引入规则召回与向量召回的离线融合，为后续影子 RAG 评估生成更聚焦的上下文。

本轮固定采用：

- 向量初始候选池：Top 10；
- 融合算法：Reciprocal Rank Fusion（RRF）；
- 规则召回权重：2；
- 向量召回权重：1；
- RRF 常数：60；
- 最终上下文：Top 5。

该能力只用于 `tmp/embedding/` 下的离线评估，不进入正式分析、证据、风险、人工复核快照、输出门禁或前端页面。

## 设计依据

Envision 2024 中文报告的 Pro 调整后人工页码基线显示：

| 方法 | Top 10 命中率 | Top 10 召回率 | MRR |
| --- | ---: | ---: | ---: |
| 规则召回 | 79.83% | 71.97% | 75.07% |
| BGE-M3 向量召回 | 68.91% | 58.73% | 47.64% |
| RRF 规则 2：向量 1 | 90.76% | 82.23% | 82.79% |

RRF 2：1 从 Top 5 扩大到 Top 10 后，命中率仅增加 1.68 个百分点、召回率增加 2.48 个百分点、MRR 增加 0.28 个百分点，但传入上下文的候选数量翻倍。因此，Top 10 适合作为内部召回池，Top 5 更适合作为影子 RAG 的实际上下文。

## 方案比较

### 方案 A：离线 RRF 融合并回查 `document_chunks`（采用）

影子上下文工具读取现有检索评估 CSV：

- `rule_pages` 提供规则候选的页码和顺序；
- `vector_*` 字段提供向量 Top 10 的 chunk、页码、分数和正文；
- 对规则候选页，从数据库只读加载该报告的 `document_chunks`，补齐 chunk ID 和正文；
- 按 RRF 2：1 融合、去重并截取 Top 5。

优点：

- 规则候选能够携带真实报告正文进入上下文；
- 不需要修改检索评估文件格式；
- 不需要重新调用 SiliconFlow；
- 不接触正式检索与分析链路。

代价：

- 混合模式执行时需要连接包含该报告 `document_chunks` 的数据库；
- 需要新增一个只读 Repository 查询。

### 方案 B：在检索评估阶段写入完整规则 chunk

评估 CSV 同时保存规则候选的 chunk ID 和正文，后续上下文工具完全离线。

未采用原因：

- 需要重新运行 499 条真实向量查询才能得到新格式文件；
- CSV 会重复保存大量报告正文；
- 评估产物与上下文产物耦合更强。

### 方案 C：只融合页码，不补充规则正文

仅重新排序已有向量候选，把规则页码作为分数特征。

未采用原因：

- 规则命中但向量 Top 10 未命中的页面没有正文，无法进入 LLM 上下文；
- 会高估“混合召回已经覆盖规则证据”的实际能力。

## 数据流

1. 读取单个 requirement 的 `rule_pages` 和向量 Top 10。
2. 只读加载目标报告全部 `document_chunks`，按 PDF 页码建立索引。
3. 规则排序以 `rule_pages` 顺序为准。
4. 向量排序以 CSV 中的 Top 10 顺序为准，同一页只保留排名最高的向量 chunk。
5. 按 PDF 页去重，每页只进入一个代表 chunk：
   - 规则页同时存在向量命中时，使用该页排名最高的向量 chunk；
   - 规则独占页使用正文最长的数据库 chunk，长度相同时按 `chunk_id` 稳定选择；
   - 该约束避免同一页的多个解析 chunk 占满 Top 5，并保持与人工 gold page 和召回指标相同的页级口径。
6. 按页计算：

   `RRF = 2 / (60 + rule_rank) + 1 / (60 + vector_rank)`

   未被某一路召回时，该路贡献为 0。
7. 依次按融合分数、规则排名、向量排名、页码、chunk ID 排序。
8. 截取 Top 5，写入影子上下文 JSONL。

## 输出契约

现有证据字段保持兼容：

- `shadow_evidence_id`
- `chunk_id`
- `source_page`
- `score`
- `text`

混合模式新增诊断字段：

- `retrieval_sources`
- `rule_rank`
- `vector_rank`
- `fusion_score`

上下文新增：

- `retrieval_mode`
- `vector_pool_k`
- `context_k`
- `rrf_rule_weight`
- `rrf_vector_weight`
- `rrf_constant`
- `unresolved_rule_pages`

`score` 继续表示原始向量相似度；规则独占候选的 `score` 为 0。融合排序使用 `fusion_score`，避免混淆两种分数的含义。

## 兼容性与失败处理

- 默认模式保持 `vector`，现有命令和测试不受影响；
- `hybrid_rrf` 模式才连接数据库；
- 指定报告没有任何 `document_chunks` 时立即失败，避免把错误数据库或错误报告伪装成混合结果；
- 报告 ID 不匹配继续立即失败；
- 向量数组长度不一致继续立即失败；
- 数据库中找不到的规则页记录到 `unresolved_rule_pages`，不伪造正文；
- 候选不足 5 条时输出实际可用数量；
- 不调用外部 embedding 或 LLM；
- 不写数据库。

## 边界

本轮不修改：

- `retrieve_evidence()`；
- `SingleReportWorkflow`；
- assessment、verdict、risk；
- AI suggestion 正式记录；
- review snapshot；
- export；
- API 与前端；
- Envision v1.1 冻结基线。

## 验证标准

- 单元测试覆盖 RRF 计算、页级去重、稳定排序、Top 10 候选池和 Top 5 截断；
- 单元测试覆盖规则独占、向量独占、双路命中和规则页缺失；
- 单元测试覆盖同页多个 chunk 和报告 chunk 集为空；
- 现有纯向量上下文测试保持通过；
- `ruff` 通过；
- embedding/影子 RAG focused tests 通过；
- 后端全量 `pytest -q` 通过；
- Envision 577 gate 通过；
- 验证过程中不产生真实外部调用。
