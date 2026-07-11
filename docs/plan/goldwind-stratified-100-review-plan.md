# Goldwind 100 条分层人工复核实施计划

> **执行要求：** 使用 `executing-plans` 按任务顺序 inline 执行；实现任务采用 TDD。生成复核包后必须暂停，等待人工复核，不得根据样本提前修改 ontology、contract 或 report profile。

## 1. 目标

从 Goldwind 2024 的 577 条 eligible assessment requirement 中，确定性选取 100 条进行分层人工复核，验证以下能力：

- report profile route 是否把 requirement 送入正确候选页；
- 候选页是否形成有效的 leaf-level evidence；
- KPI、管理机制、零事件声明等 evidence kind 是否识别正确；
- `disclosed / partially_disclosed / unknown` 边界是否符合 requirement 充分性；
- `rationale`、`missing_items`、`guardrail_items` 是否保持 leaf 边界；
- Goldwind holdout 的 first-pass recall 与 precision 是否达到继续泛化优化的门槛。

本计划不把 577 条全部立即交给人工逐条复核。全量 577 条继续执行自动审计，100 条用于当前阶段的人工质量估计。其余 477 条继续作为第二阶段 holdout。

## 2. 当前基线

- Goldwind eligible assessment requirement：577 条。
- GRI compilation requirement：84 条，仅作为 sufficiency guardrail，不作为独立 assessment。
- 当前已人工稳定复核的 seed requirement：
  - `GRI 205-1-a`
  - `GRI 205-1-b`
  - `GRI 414-1-a`
  - `GRI 403-9-a-i`
  - `GRI 418-1-a`
- Goldwind PDF 为双页拼版，`source_pdf_page` 为权威定位字段；`source_report_page` 仅用于展示和辅助核对。
- 禁止为本次 100 条样本新增 Goldwind per-ID contract。
- 禁止调用外部模型和 OCR。

## 3. 抽样方案

### 3.1 样本数量与互斥 bucket

100 条 requirement 按以下互斥 bucket 选择：

| bucket | 数量 | 选择目的 |
| --- | ---: | --- |
| `all_disclosed` | 15 | 全量覆盖当前 disclosed，优先检查 false disclosed |
| `partial_stratified` | 35 | 覆盖主要 semantic group、evidence kind 和 route 类型 |
| `unknown_stratified` | 40 | 优先识别 unknown leakage、candidate 缺失和 keyword miss |
| `boundary_guardrail` | 10 | 覆盖零事件、复杂表格、双页拼版、compilation guardrail 和 candidate-only 边界 |

若执行时 disclosed 数量不再是 15：

1. disclosed 少于 15 时全部纳入，空缺优先补入 `boundary_guardrail`；
2. disclosed 多于 15 时触发停止条件，不自动裁剪，先确认是否存在新的 verdict 扩张；
3. 四个 bucket 必须互斥，总数必须恰好为 100。

### 3.2 确定性选择规则

- 不使用随机数。
- 固定按 `requirement_id` 自然顺序排序。
- partial 和 unknown 使用 round-robin，分层键依次为：
  1. `semantic_group`
  2. `evidence_kind`
  3. route 状态
- route 状态至少区分：
  - `candidate_with_evidence`
  - `candidate_without_evidence`
  - `no_candidate`
- 5 条 seed requirement 必须入选，并归入其实际 verdict/boundary bucket，不重复占位。
- 同一 requirement 只能出现一次。
- 若某一 strata 数量不足，按 `semantic_group -> evidence_kind -> requirement_id` 的固定顺序从相邻 strata 补足。

### 3.3 boundary 样本

`boundary_guardrail` 从非 disclosed requirement 中选择，优先级如下：

1. `explicit_zero_statement` 与 zero-event propagation；
2. compilation guardrail 已命中但不得作为 evidence 的 requirement；
3. `complex_table` KPI 页；
4. candidate-only 页面不得提升为 source evidence；
5. Goldwind 双页拼版导致的页码与 preview 边界；
6. `unknown + no source evidence` 的 stale metadata 清理。

## 4. 字段边界

### 4.1 主 assessment CSV

不得为抽样过程新增 selection 字段。主 CSV 继续保留 assessment、证据、页码和人工判断所需字段。

### 4.2 selection manifest

抽样诊断字段只写入：

`tmp/review/holdout_goldwind_2024_stratified_100_selection.csv`

字段：

- `requirement_id`
- `selection_bucket`
- `semantic_group`
- `evidence_kinds`
- `route_status`
- `candidate_page_source`
- `selection_reason`

### 4.3 人工复核包

输出：

`tmp/review/holdout_goldwind_2024_stratified_100_review_pack.csv`

至少包含：

- `requirement_id`
- `requirement_text`
- `verdict`
- `review_status`
- `candidate_pdf_pages`
- `source_pdf_pages`
- `evidence_type`
- `evidence_kind`
- `evidence_preview`
- `rationale`
- `missing_items`
- `guardrail_items`
- `selection_bucket`
- `selection_reason`
- `manual_label`
- `correct_pdf_pages`
- `suggested_verdict`
- `issue_type`
- `review_note`

`selection_bucket` 和 `selection_reason` 通过 `requirement_id` 从 manifest 合并，仅存在于复核包，不回写主 assessment CSV。

## 5. 产物

执行阶段生成：

- `tmp/review/holdout_goldwind_2024_stratified_100_selection.csv`
- `tmp/review/holdout_goldwind_2024_stratified_100_review_pack.csv`
- `tmp/review/holdout_goldwind_2024_stratified_100_summary.json`

人工填写后生成或接收：

- `tmp/review/holdout_goldwind_2024_stratified_100_reviewed.csv`
- `tmp/review/holdout_goldwind_2024_stratified_100_quality.json`

## 6. 实施任务

### Task 1：锁定基线与失败测试

**影响文件：**

- 新增 `backend/tests/tools/test_holdout_stratified_sample.py`

**步骤：**

1. 读取 `tmp/review/holdout_goldwind_2024_first_pass.csv`，确认 577 个唯一 requirement。
2. 为以下约束先写失败测试：
   - 输出恰好 100 个唯一 requirement；
   - 5 条 seed requirement 全部存在；
   - 当前 disclosed 全部存在；
   - bucket 互斥且数量符合配置；
   - 同一输入重复运行结果完全一致；
   - 选择器不写入或修改主 CSV；
   - requirement 缺少 contract metadata 时仍可按稳定 fallback 排序。
3. 运行测试，确认因实现缺失而失败。

**验证命令：**

```powershell
cd backend
uv run --no-sync pytest tests/tools/test_holdout_stratified_sample.py -q
```

### Task 2：实现确定性分层选择器

**影响文件：**

- 新增 `backend/src/tools/holdout_stratified_sample.py`
- 修改 `backend/tests/tools/test_holdout_stratified_sample.py`

**实现要求：**

1. 将多 evidence 行聚合为一个 requirement 记录。
2. 使用现有 contract/ontology API 获取：
   - `semantic_group`
   - `evidence_kinds`
3. 从 candidate/source 状态计算 `route_status`。
4. 按本计划第 3 节执行确定性选择。
5. 支持 CLI：

```powershell
cd backend
uv run --no-sync python -m src.tools.holdout_stratified_sample `
  ../tmp/review/holdout_goldwind_2024_first_pass.csv `
  ../tmp/review/holdout_goldwind_2024_stratified_100_selection.csv `
  --summary ../tmp/review/holdout_goldwind_2024_stratified_100_summary.json
```

6. CLI 返回非零状态时不得留下半成品文件。

**验证：**

```powershell
cd backend
uv run --no-sync pytest tests/tools/test_holdout_stratified_sample.py -q
```

### Task 3：将 selection manifest 接入 review pack

**影响文件：**

- 修改 `backend/src/tools/holdout_review_pack.py`
- 修改 `backend/tests/tools/test_holdout_review_pack.py`

**步骤：**

1. 先写失败测试，验证 review pack 可接收 selection manifest。
2. 通过 `requirement_id` 内连接，只输出 selection 中的 100 条。
3. 每个 requirement 只输出一行；多 evidence 页聚合到数组字段。
4. 保留完整推理链：

```text
requirement_text
-> source evidence
-> rationale
-> missing_items
-> guardrail_items
-> verdict
```

5. `unknown + no source evidence` 必须清空 stale `evidence_kind`、source 和 preview。
6. selection metadata 不得进入主 assessment 导出。

**验证：**

```powershell
cd backend
uv run --no-sync pytest tests/tools/test_holdout_review_pack.py -q
```

### Task 4：扩展 100 条样本质量摘要

**影响文件：**

- 修改 `backend/src/tools/first_pass_quality.py`
- 修改 `backend/tests/tools/test_first_pass_quality.py`

**步骤：**

1. 先写失败测试。
2. 保留现有人工字段：
   - `manual_label`
   - `correct_pdf_pages`
   - `suggested_verdict`
   - `issue_type`
3. 增加或确认以下指标可从 reviewed 100 样本计算：
   - `first_pass_recall`
   - `false_disclosed_count`
   - `wrong_source_page_count`
   - `unknown_leakage_count`
   - `profile_route_valid_evidence_rate`
   - `cross_leaf_missing_items_count`
   - `guardrail_as_evidence_count`
4. 未完成人工字段时，指标标记为 `manual_gold_available=false`，不得输出虚假 0。
5. quality 工具只读 CSV，不回写 assessment 结果。

**验证：**

```powershell
cd backend
uv run --no-sync pytest tests/tools/test_first_pass_quality.py -q
```

### Task 5：生成 100 条 selection 与 review pack

**前置条件：** Task 1-4 测试通过。

**步骤：**

1. 运行选择器生成 manifest 与 summary。
2. 运行 review pack 工具生成 100 条复核包。
3. 自动检查：
   - 100 行、100 个唯一 requirement；
   - 5 条 seed 全部存在；
   - 当前 15 条 disclosed 全部存在；
   - `requirement_text_missing=0`；
   - source/candidate PDF 页码不超过 52；
   - `global_fallback=0`；
   - 无 `?` 乱码和字面量 `\u`；
   - review pack 必需字段全部存在；
   - 不存在重复 bucket 或重复 requirement。

### Task 6：全量自动回归

**步骤：**

1. 跑相关工具测试。
2. 跑后端全量测试。
3. 审计 Goldwind 577 first-pass。
4. 执行 Envision 577 regression gate，防止 Goldwind 工具改动影响既有基线。

**验证命令：**

```powershell
cd backend
uv run --no-sync pytest tests/tools/test_holdout_stratified_sample.py tests/tools/test_holdout_review_pack.py tests/tools/test_first_pass_quality.py -q
uv run --no-sync pytest -q
```

Goldwind 与 Envision 审计命令以 `docs/DEVELOPMENT.md` 当前记录为准，不在计划中复制可能过期的入口。

### Task 7：人工复核停止点

生成 `tmp/review/holdout_goldwind_2024_stratified_100_review_pack.csv` 后立即暂停，并向人工复核方提供：

- 100 条 review pack；
- selection summary；
- 自动审计结果；
- bucket 和 semantic group 分布；
- 已知限制与待填写字段说明。

在收到人工复核结果前，禁止：

- 修改 Goldwind per-ID contract；
- 调整 ontology matrix；
- 修改 report profile route；
- 根据这 100 条更新正式 gold baseline；
- 扩展到 150 或全量 577 人工复核。

### Task 8：人工复核后的质量决策

收到 reviewed CSV 后执行质量统计。

**放行门槛：**

- `false_disclosed_count = 0`
- `wrong_source_page_count <= 2`
- `unknown_leakage_count <= 10`
- `profile_route_valid_evidence_rate >= 0.90`
- `cross_leaf_missing_items_count = 0`
- `guardrail_as_evidence_count = 0`

**决策：**

1. 全部门槛通过：保留其余 477 条作为第二阶段 holdout，进入 report-agnostic 优化。
2. 任一门槛失败：从失败主题定向扩展到 150 条，不重新随机抽样。
3. Goldwind 将升级为正式 gold baseline 或进入多报告生产验收前：再安排全量 577 人工复核。

## 7. 停止条件

执行过程中命中任一条件必须暂停并汇报原因、影响和处理建议：

1. 输入不再是 577 个唯一 eligible requirement；
2. disclosed requirement 超过 15，且无法确认是预期变化；
3. 选择器无法生成恰好 100 个互斥样本；
4. 5 条 seed requirement 任一缺失；
5. source/candidate PDF 页码超过 Goldwind 总页数 52；
6. 发现 `global_fallback` 回退；
7. review pack 缺少 requirement、证据、推理链或人工字段；
8. Goldwind 自动审计出现新增错误；
9. Envision 577 verdict/source/page/quality flag 出现非预期 diff；
10. 后端测试失败且根因无法在当前任务边界内修复；
11. 需要新增 Goldwind per-ID contract 才能满足抽样或导出要求；
12. 需要调用 OCR、外部模型或修改原始报告资产。

## 8. 验收标准

- 选择算法确定、可重复、无随机性；
- 100 条覆盖 disclosed、partial、unknown 和高风险边界；
- 抽样字段未污染主 assessment CSV；
- review pack 可独立完成人工复核，无需依赖另一份 JSON 补齐核心字段；
- 84 条 compilation requirement 只进入 `guardrail_items`，不成为独立 assessment 或 substantive evidence；
- Goldwind 全量自动审计通过；
- Envision 577 回归无非预期变化；
- 执行在人工复核点暂停。

## 9. 非目标

本轮不处理：

- Goldwind 全量 577 条人工复核；
- 新增 Goldwind per-ID contract；
- 修改 ontology verdict matrix；
- 扩展 report profile 固定页码规则；
- 启用 OCR/VLM 或外部模型；
- 将 Goldwind 直接升级为正式 gold baseline。
