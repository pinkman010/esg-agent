# 混合影子 RAG Phase 1.5 工程验收报告

## 1. 验收结论

冻结名称：`混合影子 RAG Phase 1.5 工程基线`。

自动工程验收通过。Envision 2024 中文报告的 499 个独立判断项已完成规则、向量和混合三路 Top 5 对比；混合召回的 Hit@5、Recall@5 和 MRR 均高于规则召回，11 条 requirement 获得命中增益，0 条出现命中损失。499 个混合 context 的结构、唯一性和两次重建确定性均通过。

本次工具在 PostgreSQL `REPEATABLE READ READ ONLY` 事务内运行，18 张非影子表的前后行数完全一致。正式 API、service、workflow 和前端没有接入 Phase 1.5 字段。

### 1.1 发布状态

Phase 1.5 实现基线已于 2026-07-27 以提交 `0b294f9` 推送至 `origin/main`。自动验收运行发生在该提交创建之前，因此下文继续保留运行时父提交、未提交工作区摘要和关键实现文件 SHA256；发布提交与运行时溯源属于两个独立层次。

## 2. 基线与参数

| 项目 | 值 |
| --- | --- |
| 执行日期 | 2026-07-27 |
| 运行时 Git HEAD | `0cf3cbcc048d1ade2565fa458c2e377bcfc83896` |
| 工作区未提交变更 | 是 |
| Git status SHA256 | `3342084e32f042d538f6f17cb698450082a28dd666e1969492a7b8bdc8d666c8` |
| Migration head | `0012_chunk_embeddings` |
| 报告 ID | `report-15401bb4334e40d4a0885730f2635b22` |
| Provider | `siliconflow` |
| Model | `BAAI/bge-m3` |
| 检索模式 | `hybrid_rrf` |
| 向量候选池 | Top 10 |
| 最终 context | Top 5 |
| RRF 规则权重 | 2 |
| RRF 向量权重 | 1 |
| RRF 常数 | 60 |
| 外部调用 | 未发生，`EMBEDDING_ENABLED=false` |

## 3. 输入指纹

| 输入 | 相对路径 | SHA256 |
| --- | --- | --- |
| Retrieval cases | `tmp/embedding/envision_demo_bge_m3_shadow_retrieval_cases.csv` | `ab912e8070ac49520e32cac0520026f4341427d154fb7919dd1daf56b6cc02ea` |
| GRI requirements | `backend/data/manifests/gri_requirement_checklist_v3.json` | `c097cd627d87b369f5defe8bffd2a7120c4f61d1b2b36460901d9dbdb708d45c` |
| Regeneration baseline | `backend/data/review_inputs/envision_2024/baselines/current_577_review_regenerated.csv` | `20ca95e8a60a4f93999ce7b13bacf529570783284d51573f1d0d650fadcfe299` |
| Manual review workbook | `backend/data/review_inputs/envision_2024/manual/envision_2024_577_manual_review_second_review_Pro_20260719.xlsx` | `f1eeb37444de1eeda86b8ae0813dbfd6e88c94719781b98a8de659d9fbd7ddea` |
| Final adjudications | `backend/data/review_inputs/envision_2024/adjudication/envision_2024_result_adjudication_v1.csv` | `f9093feb3ba419a41fe5ee4df4636f033593a6bee11b78dbd5416497374c5d58` |
| Report PDF | `backend/data/reports/Envision Energy 2024-zh.pdf` | `57360dcda8e6256726be5d2a49f8921e13187b40ae44661549903f702df38068` |
| Phase 1.5 contexts | `tmp/embedding/envision_phase1_5_contexts.jsonl` | `e11ae0b6fc2666171c9e54d2d2e8ebdf1ca77073de74512ebb1cd1b675b0419e` |

人工工作簿、baseline、最终裁决文件和原始 PDF 的 SHA256 已在封版后独立复算，与 manifest 一致。

关键实现文件也进入 manifest，避免未提交代码只留下旧 HEAD：

| 实现文件 | SHA256 |
| --- | --- |
| `backend/src/tools/finalize_shadow_rag_phase1.py` | `a3f8a54605c81c90d7ecfde3a39bcd0a58f0fb2a7a7ccd90befa84ab4e586814` |
| `backend/src/tools/shadow_context_acceptance.py` | `30f2ad4fba9da1770712ebf1da32186f45e0b25a88e2bdb1958c6d0c2c4232a1` |
| `backend/src/tools/build_shadow_rag_contexts.py` | `a85c3a6d13a824ab1256c5be129b53009ca868585605fef1f01b8329debe3017` |
| `backend/src/tools/evaluate_shadow_retrieval.py` | `b5cbad5d21ced8951cc04741acfedcec78640f87eaf23d4a1ba832d0a8977143` |

本报告的原始自动验收运行对应未提交工作区。运行时 Git HEAD 只表示父提交；复现该次运行时还必须核对工作区状态摘要和上述实现文件指纹。发布状态以第 1.1 节记录的 Phase 1.5 实现基线提交为准。

## 4. 三路召回结果

499 条 requirement 全部进入结构审计。其中 119 条具有历史 `correct_pdf_pages`，进入召回指标分母；其余 380 条保留在逐项明细中，但不进入 Hit、Recall 和 MRR 分母。

| 方法 | Hit@1 | Hit@3 | Hit@5 | Recall@1 | Recall@3 | Recall@5 | MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 规则 | 0.697479 | 0.789916 | 0.789916 | 0.450000 | 0.694398 | 0.714146 | 0.742297 |
| 向量 | 0.394958 | 0.504202 | 0.579832 | 0.295518 | 0.384034 | 0.457563 | 0.457003 |
| 混合 | 0.773109 | 0.848739 | 0.882353 | 0.512045 | 0.745238 | 0.793277 | 0.816667 |

混合相对规则的结果：

- Hit@5 提升 0.092437。
- Recall@5 提升 0.079131。
- MRR 提升 0.074370。
- `hybrid_gain=11`，`hybrid_loss=0`。

单独的向量召回低于规则召回，说明当前 BGE-M3 候选适合作为规则召回的补充信号，不能单独替代规则路由。

## 5. Context 与确定性门禁

| 门禁 | 结果 |
| --- | ---: |
| Case 数量 | 499 |
| 进入指标分母的 gold 样本 | 119 |
| Context 数量 | 499 |
| 唯一 requirement | 499 |
| 唯一 context hash | 499 |
| 非 Top 5 context | 0 |
| 同一 context 重复页 | 0 |
| 未解析规则页 context | 0 |
| 越界页 | 0 |
| 非法 shadow evidence ID | 0 |
| 非法 RRF evidence 字段或融合分数 | 0 |
| 两次重建 hash 不一致 | 0 |

Context 固定使用 `shadow-chunk:<chunk_id>`，没有转换成正式 `evidence_id`。Provider、model、检索模式和 RRF 参数也作为结构审计条件；每条 evidence 的来源组合、rule/vector rank 和融合分数会按固定 2：1/60 公式重算，字段或参数漂移会使封版失败。

## 6. 正式表零变化

封版工具在同一个只读快照内读取 before 和 after。以下 18 张非影子表均保持不变：

| 表 | Before | After |
| --- | ---: | ---: |
| `reports` | 5 | 5 |
| `analysis_runs` | 5 | 5 |
| `analysis_stage_events` | 2781 | 2781 |
| `document_pages` | 390 | 390 |
| `document_chunks` | 385 | 385 |
| `standard_requirements` | 0 | 0 |
| `disclosure_tasks` | 2723 | 2723 |
| `assessments` | 2723 | 2723 |
| `ai_assessment_suggestions` | 736 | 736 |
| `assessment_risks` | 2727 | 2727 |
| `evidence_items` | 2391 | 2391 |
| `recommendations` | 2535 | 2535 |
| `review_decisions` | 0 | 0 |
| `review_snapshots` | 4 | 4 |
| `review_change_events` | 11 | 11 |
| `improvement_actions` | 2 | 2 |
| `export_versions` | 5 | 5 |
| `audit_events` | 28 | 28 |

`document_chunk_embeddings` 是既有可重建影子派生表，不属于正式表计数集合；本次封版也未写该表。

## 7. 回归门禁

- 后端全量测试：709 项通过，0 failure。
- Phase 1.5 focused tests：57 项通过，0 failure。
- Ruff：通过。
- Envision 结构：`577/499/78/0`。
- Global fallback：0。
- 新增 false disclosed：0。
- 新增 wrong source page：0。
- 最终裁决 pending：0。
- Audit：0 error、0 warning。
- 正式 API、service、workflow 和前端中的 Phase 1.5 字段消费者：0。

## 8. 限制与冻结边界

- 历史 `correct_pdf_pages` 只作为现有工程 gold，不代表本轮新增了 ESG 专家判断。
- 无 gold requirement 不进入召回指标分母，因此指标只描述 119 条可评价样本。
- 页码命中、向量相似度和 RRF 分数不等于披露充分。
- 本报告不构成 GRI 专家认证、外部鉴证或最终合规结论。
- Phase 1.5 继续作为离线影子能力；正式产品仍使用冻结的规则 assessment、追加式 AI suggestion 和人工 snapshot 分层。
- Phase 2 为可选增强，当前未启动，也不是 Phase 1.5 完成条件。
- Phase 3 保持关闭。只有取得独立高质量 gold 或专家条件，并重新设计正式证据准入和审计链后，才能重新决策。

## 9. 证据文件

以下诊断产物位于 `tmp/embedding/`，不进入 Git：

- `envision_phase1_5_contexts.jsonl`
- `envision_phase1_5_acceptance_cases.csv`
- `envision_phase1_5_acceptance_summary.json`
- `envision_phase1_5_input_manifest.json`
- `envision_phase1_5_formal_state.json`
- `envision_phase1_5_acceptance_report.md`

可提交的长期记录为本报告；自动产物仍可由封版命令重新生成。
