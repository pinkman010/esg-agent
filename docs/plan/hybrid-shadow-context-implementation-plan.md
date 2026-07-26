# 混合影子上下文实施计划

## 目标

在不改变正式 ESG 分析基线的前提下，实现规则召回与 BGE-M3 向量召回的离线 RRF 融合，使用向量 Top 10 候选池生成最终 Top 5 影子 RAG 上下文。

## Task 1：锁定纯函数契约

**影响文件**

- 修改：`backend/tests/tools/test_shadow_rag.py`
- 修改：`backend/src/tools/build_shadow_rag_contexts.py`

**执行**

1. 先添加失败测试，覆盖 RRF 2：1 计算、页级去重和稳定排序。
2. 添加失败测试，覆盖 Top 10 输入池、Top 5 最终上下文。
3. 添加失败测试，覆盖规则页无法解析、报告 chunk 集为空和同页多个 chunk。
4. 实现独立的混合候选构造纯函数。

**验证**

```powershell
cd backend
uv run --no-sync pytest tests/tools/test_shadow_rag.py -q
```

## Task 2：新增报告 chunk 只读查询

**影响文件**

- 修改：`backend/src/db/repositories.py`
- 修改：`backend/tests/db/test_repositories.py`

**执行**

1. 添加 Repository 失败测试，验证只返回指定报告的 chunk，并按页码和 chunk ID 排序。
2. 实现 `list_document_chunks(report_id=...)`。
3. 确认查询不写数据库。

**验证**

```powershell
cd backend
uv run --no-sync pytest tests/db/test_repositories.py -q
```

## Task 3：接入影子上下文命令

**影响文件**

- 修改：`backend/src/tools/build_shadow_rag_contexts.py`
- 修改：`backend/tests/tools/test_shadow_rag.py`

**执行**

1. 保留默认 `vector` 模式。
2. 新增 `hybrid_rrf` 模式和参数：
   - `--vector-pool-k 10`
   - `--context-k 5`
   - `--rrf-rule-weight 2`
   - `--rrf-vector-weight 1`
   - `--rrf-constant 60`
3. 混合模式通过 Repository 只读加载报告 chunk。
4. 输出融合来源、排名、分数和未解析规则页。
5. 不调用 SiliconFlow 或 DeepSeek。

**验证**

```powershell
cd backend
uv run --no-sync pytest tests/tools/test_shadow_rag.py -q
```

## Task 4：更新开发文档

**影响文件**

- 修改：`docs/DEVELOPMENT.md`
- 修改：`docs/plan/siliconflow-bge-m3-shadow-embedding-plan.md`

**执行**

1. 记录纯向量模式与混合 RRF 模式的命令。
2. 记录 Top 10 是内部召回池、Top 5 是实际上下文。
3. 明确混合模式只读数据库、不调用外部服务、不进入正式分析。
4. 更新原计划 Phase 2 状态，避免文档仍将该能力描述为未实施。

## Task 5：最小回归与全量验证

**验证顺序**

```powershell
cd backend
uv run --no-sync pytest tests/tools/test_shadow_rag.py tests/tools/test_shadow_retrieval.py tests/db/test_repositories.py -q
uv run --no-sync ruff check src/tools/build_shadow_rag_contexts.py src/db/repositories.py tests/tools/test_shadow_rag.py tests/db/test_repositories.py
uv run --no-sync pytest -q
```

随后按 `docs/DEVELOPMENT.md` 中现有命令运行 Envision 577 gate。

## 停止条件

- 数据库中缺少目标报告的 `document_chunks`；
- Repository 查询需要修改数据库结构；
- focused tests 暴露正式分析链路依赖；
- Envision gate 出现 verdict delta；
- 发现执行会触发外部 API。

触发停止条件时，不继续扩大修改范围，记录原因、影响和下一步选项。

## 执行结果（2026-07-26）

- focused tests：33 项通过；
- 后端全量测试：686 项通过；
- Ruff 和 `git diff --check`：通过；
- Envision gate：`577/499/78/0`、global fallback 0、新增 false disclosed 0、新增 wrong source page 0、audit 0 error/0 warning；
- demo 混合上下文：499 条、499 个唯一 context hash、每条 5 个候选、同页重复 0、未解析规则页 0；
- 执行时强制 `EMBEDDING_ENABLED=false`，未调用 SiliconFlow 或 DeepSeek，未写正式 evidence、assessment、risk、AI suggestion、review snapshot 或 export。
