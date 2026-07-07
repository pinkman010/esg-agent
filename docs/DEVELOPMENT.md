# 开发运行文档

## 1. 本地开发方式

本项目采用前后端单仓：

- 后端：`backend/`
- 前端：`frontend/`
- 文档：`docs/`

本地服务策略：

- PostgreSQL 由 Docker Compose 管理。
- OCR/Tesseract 使用本机工具。
- 后端和前端本机运行。

## 2. 包管理

已确认包管理方式：

- 后端使用 `uv`。
- 前端使用 `pnpm`。

后端依赖声明以 `backend/pyproject.toml` 为准。前端依赖声明以 `frontend/package.json` 为准。

## 3. 依赖服务

第一版需要：

- PostgreSQL。
- pgvector 预留，第一版不生成真实 embedding。
- Tesseract。
- OCRmyPDF。
- Ghostscript，供 OCRmyPDF 真实执行 OCR 时调用。
- Node.js。
- Python 3.11。

工具路径约定：

- 工具类地址优先查找：`$CODEX_TOOLS_DIR`。
- soffice：`$SOFFICE_PATH`。
- pdftoppm：`$PDFTOPPM_PATH`。

## 4. 环境变量

项目不得提交 `.env`。

应提供：

- 根目录 `.env.example`。
- `backend/.env.example`。
- `frontend/.env.example`，如前端需要。

后端配置通过 `pydantic-settings` 读取，至少应覆盖：

- PostgreSQL 连接字符串。
- 上传文件目录。
- 派生文件目录。
- OCR/Tesseract 工具路径。
- OCR 开关、语言和页数上限。
- OpenAI-compatible API base URL。
- 模型名称。
- CORS 来源。

OCR 相关环境变量：

- `OCR_ENABLED=false`：默认关闭 OCR 自动路由。
- `OCR_LANG=chi_sim+eng`：OCRmyPDF/Tesseract 语言。
- `OCR_MAX_PAGES=5`：未显式指定页码时最多处理的低文本/扫描页数。
- `TESSERACT_CMD`：Tesseract 命令或路径。
- `OCRMYPDF_CMD=ocrmypdf`：OCRmyPDF 命令。

测试默认使用独立 PostgreSQL 数据库，避免清空开发库：

- `TEST_DATABASE_URL` 未设置时默认指向测试库名 `esg_agent_test`。
- 测试 helper 会在需要时创建测试库。
- 不要把 `TEST_DATABASE_URL` 指向开发库名 `esg_agent`。

## 5. 常用命令

前后端脚手架已初始化。常用命令如下。

计划命令形态：

```powershell
# 后端
docker compose up -d postgres
cd backend
uv sync
uv run alembic upgrade head
uv run pytest
uv run uvicorn src.main:app --reload

# 前端
cd frontend
pnpm install
pnpm generate:api
pnpm typecheck
pnpm test
pnpm build
pnpm dev
```

## 6. 测试策略

后端测试使用 `pytest`，重点覆盖：

- domain models。
- PDF 页面预检测和分块。
- `GRIAdapter`。
- `DisclosureAgent`。
- `SingleReportWorkflow`。
- PostgreSQL repository。
- reports API。
- review API。
- exports API。
- audit API。
- OpenAPI 契约。
- 测试数据库隔离。

前端测试使用 Vitest 和 React Testing Library，重点覆盖：

- 上传页状态。
- 运行结果页空状态和数据状态。
- 人工复核提交。
- 图表封装组件。
- API client 基础请求状态。

验收命令以实际脚手架为准，至少包括：

- 后端 `pytest`。
- 前端 typecheck。
- 前端 Vitest。
- 前端 build。

review CSV 生成后必须执行硬门禁自查：

```powershell
cd backend
@'
from src.tools.review_csv_audit import audit_review_csv
result = audit_review_csv("../tmp/review/current_350_review_after_rules.csv", report_total_pages=78)
print("ok=", result.ok)
print("errors=", result.errors)
print("warnings=", result.warnings)
'@ | uv run --no-sync python -
```

自查覆盖 `global_fallback`、页码越界、`page_label` 乱码、`omission_note` 升格、KPI 表缺少 `complex_table`、鉴证页缺少 OCR/VLM 风险标记、GRI 305 误挂 PDF 第 3 页等硬规则。

### Requirement/Evidence Ontology

系统将 requirement 拆为语义标签，将 evidence 拆为证据类型，再通过 verdict matrix 判断 `disclosed` / `partially_disclosed` / `unknown`。

规则优先级：

1. `omission_note` / `not_applicable` 先短路为 `unknown + needs_manual_review`。
2. contract / report profile 提供候选页。
3. evidence kind 识别证据类型。
4. ontology matrix 给默认 verdict。
5. per-ID contract 作为最终 override / guardrail。

关键边界：

- KPI 数量或比例可以支撑数值类 leaf。
- 总体值不能自动传播到性别、员工类别、地区拆分 leaf。
- 政策和管理机制不能自动支撑具体风险运营点、供应商类型或安保人员人权培训比例。
- `compilation_requirement` 只转成充分性规则、`missing_items` 和 guardrail，不作为独立 assessment requirement。
- 固定 PDF 页码只用于当前报告回归样本；跨报告逻辑必须依赖 KPI 行标签、年份列、单位和 evidence type。

### Envision 固定页码清单

固定页码清单输出到 `tmp/review/envision_fixed_page_inventory.csv`，用于把 Envision 2024 的回归页码从通用 contract 迁入 report profile。

当前批次统计：

- `batch_1_kpi_pages`：66 行，PDF 第 63-68 页 KPI 表。
- `batch_2_section_pages`：154 行，章节正文页。
- `batch_3_index_omission_pages`：23 行，索引、从略和不适用说明页。
- `batch_4_empty_routes`：68 行，无有效证据的 no-evidence guardrail。

迁移顺序为 KPI 页、章节页、索引/从略页、empty routes。每批迁移必须跑 577 regression gate，硬字段不得回退；允许 `candidate_page_source` 从 contract 切换为 report profile。

first-pass 质量评估命令：

```powershell
cd backend
uv run --no-sync python -m src.tools.first_pass_quality ../tmp/review/current_550_review.csv ../tmp/review/current_550_review_after_rules.csv
```

该工具按 `requirement_id` 聚合首行，并支持人工复核字段：`manual_label`、`correct_pdf_pages`、`suggested_verdict`、`issue_type`。输出指标包括 first-pass recall、false disclosed、wrong source page、unknown leakage 和 after-rules delta。

## 7. OpenAPI 类型生成

前端 API 类型通过 FastAPI OpenAPI 自动生成。

约束：

- 后端接口变更后同步生成前端 types/client。
- 前端业务组件不手写重复接口类型。
- 生成文件放在 `frontend/lib/generated/` 或实施计划确认的等价目录。

生成命令：

```powershell
cd frontend
pnpm generate:api
```

生成前需要后端在 `http://localhost:8000` 提供 `/openapi.json`。

## 8. 开发日志

### 2026-07-05

- 接入显式 OCRmyPDF/Tesseract 路由：`enable_ocr=false` 时保持现有 `pypdf + pdfplumber` 主链路；`enable_ocr=true` 时支持 `ocr_pages` 指定页码，未指定时仅选择 `low_text_density` 或 `scanned` 页并受 `OCR_MAX_PAGES` 限制。
- OCR 派生 PDF 写入运行时派生目录；OCR chunk 使用 `source_method=ocr`，默认携带 `needs_manual_review`，不覆盖原始 PDF。
- 新增 OCR 配置项：`OCR_ENABLED`、`OCR_LANG`、`OCR_MAX_PAGES`、`TESSERACT_CMD`、`OCRMYPDF_CMD`；后端依赖加入 `ocrmypdf` 并更新锁文件。
- 验证：`uv run pytest -q --basetemp=../tmp/pytest-ocr-main-final` 通过，结果为 179 passed；`uv run ocrmypdf --version` 返回 17.8.0；Tesseract 可见 `chi_sim`、`eng`、`osd` 语言包。
- 限制：Ghostscript 当前仍是本机外部前置条件；若 `gs`/`gswin64c` 不可用，真实 OCRmyPDF 执行会失败，单元测试只覆盖 mock 路径和默认关闭行为。
- 生成 `tmp/review/current_600_review.csv` 时确认：当前 `GRIAdapter` 的独立核查过滤口径为 `assessment_mode=current_gap`、`requirement_type=requirement`、`is_mandatory=True`、`scoring_role=hard_score`，因此实际进入首轮证据核查的是 577 条 requirement，不是 checklist 总数 661 条。
- checklist 剩余 84 条均为 `requirement_type=compilation_requirement`。这些条目不应作为独立 `disclosed` / `partially_disclosed` / `unknown` 任务处理，应映射到对应 leaf requirement 的充分性规则、`missing_items`、guardrail 或口径校验中。
- `tmp/review/current_600_review.csv` 当前包含 773 行、577 个唯一 requirement；按唯一 requirement 聚合后为 37 条 `disclosed`、189 条 `partially_disclosed`、351 条 `unknown`，37 条 `not_required`、540 条 `needs_manual_review`。本轮未调用外部模型。
- 新增第 551-577 条 requirement 均为 `unknown + needs_manual_review`，主题集中在 `GRI 416-2`、`GRI 417`、`GRI 418-1`。后续人工复核应重点判断是否存在产品责任、营销沟通、客户隐私相关的明确零事件声明、KPI 或从略说明。
- `review_csv_audit` 对 `tmp/review/current_600_review.csv` 通过，未发现 `global_fallback`、页码越界、`page_label` 乱码、`omission_note` 升格、KPI 表缺少 `complex_table` 或鉴证页 OCR/VLM 标记回退。
- 当前合理执行顺序：先完成 577 条独立 requirement 的首轮人工复核；再导出 84 条 `compilation_requirement` 映射表；复核映射后更新 ontology 计划；随后执行 requirement/evidence ontology refactor；改造后重新跑 577 条，并只对差异项做人工复核。
- 84 条 `compilation_requirement` 映射表建议先作为阶段性审查产物输出到 `tmp/review/`，字段至少包括 `compilation_requirement_id`、`canonical_disclosure_id`、`target_requirement_ids`、`facet`、`missing_item_template`、`guardrail_effect`、`source_requirement_text`。确认稳定后再决定是否产品化为 manifest 或规则文件。
- requirement/evidence ontology migration 已完成到 evidence-backed verdict 边界：`zero_event_compliance`、`compilation guardrail`、`GHG/energy/water/waste KPI`、`OHS management`、`OHS KPI parent`、`employee KPI / benefits`、`human_rights_policy` 以及 residual evidence-backed groups 均已迁入 ontology matrix 或 metadata。每批均执行 577 regression gate，结果均为 577 requirement 不变、`global_fallback=0`、无新增 `disclosed`、无 verdict/review/evidence/page/quality/OCR 字段变化，仅 `missing_items` 出现预期变化。
- no-evidence guardrail migration 已完成：原剩余 68 条 `unknown + needs_manual_review` per-ID explicit verdict 已迁移到 `no_evidence_guardrails.py`，用于结构化阻断零事件分类、风险地点、方法范围、拆分维度和安保人员培训等无效 evidence 传播；`remaining_explicit_verdicts.csv` 重新导出后为 0 条。
- ontology 后 577 回归产物：`tmp/review/current_577_review_after_ontology.csv`、`tmp/review/current_577_review_after_ontology_audit.json`、`tmp/review/current_577_review_ontology_diff.csv`、`tmp/review/current_577_review_ontology_diff_summary.json`。最新 gate 结论为 audit 通过，`compilation_overlap=0`，无新增或删除 requirement，无 verdict / review_status / source page / evidence_type / quality_flags / OCR-VLM 字段变化，`first_pass_quality` 的 disclosed/partial/unknown delta 均为 0；当前 diff 仅剩 ontology matrix 补充的 `missing_items` 差异。
- Report profile 与 evidence routing 第一阶段已完成：新增 `backend/data/reports/profiles/envision_2024.json` 作为 Envision 2024 报告实例画像；PDF 和 manifests 仍沿用后端现有数据目录，profile 只保存报告级候选页、KPI 页、页码偏移和行级 KPI term。
- Evidence routing 优先级为 GRI 索引、report profile、contract metadata、ontology metadata、KPI row matcher、ontology matrix、contract guardrail。固定 PDF 页码只作为当前报告 profile candidate，不作为跨报告通用规则。
- 首批 KPI 行级匹配只覆盖 PDF 第 63-68 页，支持 `kpi_row_label`、`kpi_row_value`、`kpi_row_unit`、`kpi_year_column` metadata，并优先用 KPI 行片段生成 `evidence_preview`。
- 577 profile routing 回归产物：`tmp/review/current_577_review_after_profile_routing.csv`、`tmp/review/current_577_review_after_profile_routing_audit.json`、`tmp/review/current_577_review_profile_routing_diff.csv`、`tmp/review/current_577_review_profile_routing_diff_summary.json`。本次 gate 结论为 audit 通过，577 requirement 不变，无新增 `disclosed`，无 verdict / review_status / source page / evidence_type / quality_flags / OCR-VLM 字段变化；仅 6 条 `candidate_page_source` 从 contract 切换为 profile。
- Holdout 当前只实现接口和指标字段，不执行跨报告 holdout。正式 holdout 需要先确定新报告资产、人工复核样本和禁止新增 per-ID contract 的验收边界。
- Goldwind 2024 holdout 已执行首轮 remediation：生成 `backend/data/reports/profiles/goldwind_2024.json`、`tmp/review/holdout_goldwind_2024_first_pass.csv`、`tmp/review/holdout_goldwind_2024_reviewed.csv`、`tmp/review/holdout_goldwind_2024_quality_summary.json` 和 `tmp/review/holdout_goldwind_2024_audit.json`。本次不启用 OCR；profile 已识别双页拼版 GRI 索引并生成 337 条 requirement route，`profile_route_hit_count=40`、`global_fallback_count=0`、`false_disclosed_count=0`，first-pass 与 reviewed CSV 均通过 `review_csv_audit`。本轮同时将 `global_no_index` 后备证据降为 `unknown + needs_manual_review`，避免无候选页全局命中直接支撑 `disclosed`；Envision 577 回归 audit 通过，577 requirement 数量和 verdict/review 分布不变。
- Goldwind holdout recall 改造完成：新增 recall 诊断表 `tmp/review/holdout_goldwind_2024_recall_diagnosis.csv`；profile builder 从 Goldwind GRI 索引抽取 requirement route，并增加双页拼版页码换算、章节 route 和 KPI 行级 preview。当前 `profile_route_hit_count` 从 40 提升到 53，`global_no_index_count` 从 53 降到 23，`false_disclosed_count=0`，`wrong_source_page_count=0`，`global_fallback_count=0`；`tmp/review/holdout_goldwind_2024_first_pass.csv`、`tmp/review/holdout_goldwind_2024_reviewed.csv`、`tmp/review/holdout_goldwind_2024_audit.json` 均通过 gate。Envision 577 regression 产物 `tmp/review/current_577_review_after_profile_routing_regression.csv` audit 通过，577 requirement 数量不变，verdict/review/source/evidence/page/quality/OCR-VLM 字段无回退。
- Goldwind route review pack 已生成：新增 `tmp/review/holdout_goldwind_2024_route_improvement.csv`、`tmp/review/holdout_goldwind_2024_review_pack.csv`、`tmp/review/holdout_goldwind_2024_route_improvement_summary.json`。本轮接入 `report_profile_section` 到 workflow，并给 Goldwind profile 增加“产品服务与研发创新”章节；`global_no_index_count` 从 23 降到 4，`global_fallback_count=0`，Goldwind 最大 source/candidate PDF 页码均为 52，first-pass/reviewed audit 均通过。route improvement 共 5 行，其中 4 行为 `candidate_without_evidence`，1 行为 `missing_candidate`；当前停止点为人工复核 `tmp/review/holdout_goldwind_2024_review_pack.csv`。focused tests 通过；现有 Envision 577 profile routing regression diff 为 0。本轮未找到可复用的 Envision 577 重新生成脚本，因此只验证历史 regression 产物，后续应沉淀正式 regression 生成入口。
- Goldwind recall 诊断扩充完成：新增 `backend/data/holdout/goldwind_2024_recall_gold.json`，当前保存 5 条已人工复核的 gold case，并生成 `tmp/review/holdout_goldwind_2024_recall_diagnosis.csv`。新增 `preview_sample_audit` 工具并生成 `tmp/review/holdout_goldwind_2024_preview_sample.csv`，本轮 4 条抽样均为 `missing_anchor`，对应当前仍缺有效 source 或 source 错页的诊断样本，不改变 verdict。最终 `profile_route_hit_count=53`、`global_no_index_count=23`、`false_disclosed_count=0`、`wrong_source_page_count=0`、`global_fallback_count=0`；Goldwind first-pass/reviewed audit 通过，Envision 577 regression 无 requirement 数量变化，无 verdict/review/source/evidence/page/quality/OCR-VLM 回退。

### 2026-07-04

- 增加 `review_csv_audit` 工具，将人工复核硬规则固化为可重复运行的 review CSV gate；新增首批 leaf-level evidence contract，先覆盖 GRI 305 的候选页、禁用页、verdict 和 review status；PDF 第 63、65、68 页 KPI evidence 统一使用行级 preview helper，并修复 `GRI 205-3-b` PDF 第 68 页缺少 `complex_table` 的质量标记问题。
- 扩展 `omission_note` 识别：支持“因商业保密限制从略披露”“因不适用而从略披露”“不适用从略披露”“confidentiality constraints”“not applicable”。从略说明只作为缺口解释保留，固定进入 `unknown + needs_manual_review`。
- 当前 `review_csv_audit.py`、`evidence_contracts.py`、`DisclosureAgent` 中的部分页码规则、`SingleReportWorkflow._candidate_page_overrides()` 和 `GRIAdapter` 的部分关键词服务于远景能源样本的 661 条核查。核查完成后，应将通用 GRI 充分性规则、报告实例页码 profile、报告实例关键词扩展拆分，避免样本页码和公司特定表达长期留在产品运行链路。
- 根据 `current_150_review.csv` 人工复核结论，增加 `GRI 2-20-a-iii`、`GRI 2-20-b`、`GRI 2-21`、`GRI 2-30` 的 `omission_note` 继承规则；GRI 索引中的“因商业保密限制从略披露”只作为缺口解释保留，不提升 `disclosed`。
- 增加 `GRI 2-22`、`GRI 2-23`、`GRI 2-24`、`GRI 2-25`、`GRI 2-26`、`GRI 2-27`、`GRI 2-28`、`GRI 2-29`、`GRI 3-1` 的中文关键词、候选页收窄和子项级充分性规则；章节封面页不能单独作为 evidence，候选页超过报告页数时过滤。
- 生成 `tmp/review/current_150_review_after_rules.csv`：150 个 requirement、227 行、169 条 evidence；按 requirement 聚合后为 11 条 `disclosed`、58 条 `partially_disclosed`、81 条 `unknown`，11 条 `not_required`、139 条 `needs_manual_review`；169 条 evidence 均为 `index_page_bounded`，0 条 `global_fallback`；其中 23 条为 `omission_note`、7 条为 `index_statement`，未调用外部模型。
- 根据 `current_200_review.csv` 人工复核结论，增加 `GRI 201`、`GRI 202`、`GRI 203` topic-specific 规则：`201-1`、`201-4`、`202-2` 继承 `omission_note`；`201-3` 严格要求退休计划/养老金/缴费比例等强证据，普通员工福利和薪酬福利不能支撑；`201-2` 使用 PDF 第 17-19 页气候风险与机遇内容，子项按 disclosed/partial/unknown 区分；`203` 从章节封面扩展到 PDF 第 42-44 页社区项目正文，并保留 partial + 人工复核。
- 生成 `tmp/review/current_200_review_after_rules.csv`：200 个 requirement、299 行、221 条 evidence；按 requirement 聚合后为 14 条 `disclosed`、65 条 `partially_disclosed`、121 条 `unknown`，14 条 `not_required`、186 条 `needs_manual_review`；221 条 evidence 均为 `index_page_bounded`，0 条 `global_fallback`；其中 43 条为 `omission_note`、7 条为 `index_statement`，未调用外部模型。
- 根据 `current_250_review.csv` 人工复核结论，增加 `GRI 204`、`GRI 205`、`GRI 206` topic-specific 规则：`204-1` 继承 `omission_note`；`205` 从治理章节封面扩展到 PDF 第 57-59 页和 KPI 第 68 页，并按反腐败风险评估、培训传达、供应商阳光协议、腐败事件 KPI 做子项级判断；`205-3-b` 可由 KPI 直接支撑 `disclosed`，`205-2-a`、`205-2-d`、`205-3-c`、`205-3-d` 保持 `unknown`；`206-1-a` 使用反竞争行为 KPI 作为 partial evidence，`206-1-b` 保持 `unknown`。
- 根据 `current_250_review_after_rules.csv` 人工复核结论，补充 `GRI 207` 与 `GRI 302-1` 规则：`207-4` 全组继承 `omission_note`；`207-1-a`、`207-1-a-iii`、`207-2-a` 及其部分子项、`207-3-a` 使用 PDF 第 57 页税务治理内容作为 partial evidence；`207-3` 子项税务机关沟通、公共政策倡导、外部意见收集保持 `unknown`；`302-1-a` 和 `302-1-c` 使用 PDF 第 63 页能源 KPI 作为 partial evidence，并标记 `complex_table`；`302-1-b` 和 `302-1-d` 保持 `unknown`。
- 重新生成 `tmp/review/current_250_review_after_rules.csv`：250 个 requirement、354 行、260 条 evidence；按 requirement 聚合后为 15 条 `disclosed`、82 条 `partially_disclosed`、153 条 `unknown`，15 条 `not_required`、235 条 `needs_manual_review`；260 条 evidence 均为 `index_page_bounded`，0 条 `global_fallback`；其中 59 条为 `omission_note`、7 条为 `index_statement`，未调用外部模型。
- 根据 `current_300_review.csv` 人工复核结论，补充 `GRI 302` 与 `GRI 303` 规则：`302-1-e` 使用 PDF 第 63 页能源使用总量 KPI 判定为 `disclosed`；`302-4-a` 和 `302-4-b` 使用 PDF 第 23 页节能改造与 PDF 第 63 页节电量 KPI 作为 partial evidence；`302-1-f/g`、`302-2`、`302-3`、`302-4-c/d`、`302-5` 保持 `unknown`；`303-1`、`303-2-a/a-ii`、`303-3` 部分取水拆分、`303-4` 部分排水拆分使用 PDF 第 16、22、25、63 页作为 partial evidence，水源、排放目的地、高水风险区域拆分和数据编制方法不足的子项保持 `unknown`。
- 生成 `tmp/review/current_300_review_after_rules.csv`：300 个 requirement、413 行、290 条 evidence；按 requirement 聚合后为 16 条 `disclosed`、102 条 `partially_disclosed`、182 条 `unknown`，16 条 `not_required`、284 条 `needs_manual_review`；290 条 evidence 均为 `index_page_bounded`，0 条 `global_fallback`；其中 59 条为 `omission_note`、7 条为 `index_statement`，未调用外部模型。新增第 251-300 条中为 1 条 `disclosed`、20 条 `partially_disclosed`、29 条 `unknown`；PDF 第 63 页 KPI evidence 标记 `complex_table`。

### 2026-07-03

- 完成 evidence retrieval 质量改造：从 GRI 指标索引页提取 disclosure 候选页，检索优先限定在候选页，fallback 和低质量页进入人工复核。
- 增加 `backend/src/standards/gri_report_index.py`，按 `report_index_pdf_page - report_index_report_page` 将报告页码换算为 PDF 页码。
- 修复 GRI 索引页双列表格解析污染问题：同一行中右侧 disclosure 的页码不再并入左侧 disclosure 候选页。
- 真实 PDF `confirm_llm=false` 验收通过：10 个 assessment、5 条 evidence、7 条 recommendation、1 条 `index_page_bounded` evidence、4 条 `global_fallback` evidence、9 条待复核 assessment，四个导出接口均返回 `200`。
- 本次未调用外部模型；fallback evidence 和低质量页 evidence 只能作为人工复核入口，不能作为最终合规结论。
- 根据 `tmp/fallback_review.csv` 人工复核结论，调整披露判定门禁：`global_fallback` evidence 只能作为可疑线索，不再支撑 `disclosed`。
- 为 `GRI 2-2-a` 增加中文检索词：报告边界、实际运营场所、统计口径、合并范围、纳入报告；命中候选页但只披露报告边界时，判为 `partially_disclosed` 并记录缺失项。
- 为 `GRI 2-2-c-ii` 增加合并口径、并购、收购、实体处置等中文检索词；无候选页正确证据时保持 `unknown + needs_manual_review`。
- 重新跑真实 PDF `confirm_llm=false` 验收：10 个 assessment、3 条 evidence、9 条 recommendation、2 条 `index_page_bounded` evidence、1 条 `global_fallback` evidence、9 条待复核 assessment，四个导出接口均返回 `200`，未调用外部模型。
- 根据 bounded evidence 人工复核结论，增加 `GRI 2-2-c-iii` 充分性规则：候选页只说明报告期、资料来源、编制流程或报告边界时，不能支撑 `disclosed`，改为 `unknown + needs_manual_review` 并记录缺失的合并方法与差异说明。
- 再次跑真实 PDF `confirm_llm=false` 验收：10 个 assessment、3 条 evidence、10 条 recommendation、2 条 `index_page_bounded` evidence、1 条 `global_fallback` evidence、10 条待复核 assessment，四个导出接口均返回 `200`，未调用外部模型。
- 根据前 10 条 requirement 人工复核结论，增加 `GRI 2-1` 与 `GRI 2-2-c` 的中文关键词、候选页补充和充分性规则：`2-1-a` 可使用封面/报告说明页公司全称，`2-1-c` 可补充总部页，`2-1-d` 与 `2-2-c` 只支持部分披露，`2-2-c-ii` 无效 fallback evidence 被过滤。
- 重新跑真实 PDF `confirm_llm=false` 验收：10 个 assessment、7 条 evidence、9 条 recommendation、7 条 `index_page_bounded` evidence、0 条 `global_fallback` evidence；结果为 1 条 `disclosed`、4 条 `partially_disclosed`、5 条 `unknown`，四个导出接口均返回 `200`，未调用外部模型。
- 根据 `current_10_review_after_rules.csv` 人工复核结论，保留前 10 条 verdict/review_status 分布，并将 `GRI 2-2-c-iii` 的第 3 页 insufficient evidence 过滤出有效 evidence；再次跑真实 PDF `confirm_llm=false` 验收：10 个 assessment、6 条 evidence、9 条 recommendation、6 条 `index_page_bounded` evidence、0 条 `global_fallback` evidence，四个导出接口均返回 `200`，未调用外部模型。
- 后续 GRI 结构化字段引用以实际存在字段为准：`report_index_pdf_page`、`report_index_report_page`、`evidence_expectation`、`official_pdf_page_candidates`；不得引用不存在的 `report_index_target_pages` 或 `expected_evidence_type`。
- 根据 `current_20_review.csv` 人工复核结论，增加 `GRI 2-3`、`GRI 2-4`、`GRI 2-5` 的中文关键词、索引备注和充分性规则：`2-3-a` 报告期只能支撑部分披露，`2-3-d` 联系邮箱可支撑披露，`2-4` 使用 GRI 索引页“无信息重述”，`2-5` 使用鉴证报告页，`source_page=23/60/64` 的 `global_fallback` 误命中被过滤。
- 生成 `tmp/review/current_20_review_after_rules.csv`：20 个 requirement、21 行、14 条 evidence，结果为 7 条 `disclosed`、6 条 `partially_disclosed`、7 条 `unknown`；7 条 `not_required`、13 条 `needs_manual_review`；14 条 evidence 均为 `index_page_bounded`，0 条 `global_fallback`，未调用外部模型。
- 增加 evidence 页码双轨字段：`source_pdf_page` 用于程序定位，`source_report_page` 用于人工阅读和 GRI 索引展示；保留 `source_page` 兼容旧 API，并在 CSV/JSON 导出中增加 `page_label`。
- 对低文本鉴证页增加 `needs_ocr_or_vlm` 和 `ocr_or_vlm_reason` 标记；本阶段只做路由预留，不调用 OCR/VLM。
- 生成 `tmp/review/current_20_review_after_page_fields.csv`：20 个 requirement、21 行、14 条 evidence，结果分布保持 7 条 `disclosed`、6 条 `partially_disclosed`、7 条 `unknown`；`GRI 2-5` evidence 展示为 `PDF 第 77 页 / 报告页 76`，并标记 `assurance_page_text_too_short`，未调用外部模型。
- 补齐字段契约：新增 `candidate_pdf_pages`、`candidate_report_pages`、`requires_ocr`、`requires_vlm`、`evidence_preview`；低文本鉴证页追加 `short_text` 和 `image_body_not_extracted` 质量标记，同时保留旧字段兼容。
- 生成 `tmp/review/current_20_review_after_contract_fields.csv`：20 个 requirement、21 行、14 条 evidence，结果分布保持不变；`GRI 2-5` 三条 evidence 均为 `requires_ocr=true`、`requires_vlm=false`，未调用外部模型。
- 修复 `evidence_preview` 页首截断问题：preview 改为基于 requirement 关键词的命中窗口，并优先选择包含邮箱、日期和更多关键词的候选片段；`GRI 2-4` preview 稳定显示 `2-4 信息重述 无信息重述 /`。
- 生成 `tmp/review/current_20_review_final_contract.csv`：20 个 requirement、21 行、14 条 evidence，结果分布保持不变；无 evidence 的 unknown 行导出布尔字段统一为 `false`，未调用外部模型。
- 根据 `current_50_review.csv` 人工复核结论，增加 `GRI 2-6`、`GRI 2-7`、`GRI 2-8`、`GRI 2-9-b` 的中文关键词、候选页补充和子项级充分性规则：`2-6` 使用业务概况、ESG 合作网络和责任采购页作为部分披露证据，`2-7-c` 使用人员结构和 KPI 页，`2-7-c-ii` 的“截至报告期末”可支撑披露，`2-8` 严格保持非雇员工作者口径，普通员工、供应商和承包商安全内容不能替代，`2-9-b` 使用 ESG 治理架构页作为部分披露证据。
- 生成 `tmp/review/current_50_review_after_rules.csv`：50 个 requirement、63 行、35 条 evidence；按 requirement 聚合后为 10 条 `disclosed`、12 条 `partially_disclosed`、28 条 `unknown`，10 条 `not_required`、40 条 `needs_manual_review`；35 条 evidence 均为 `index_page_bounded`，0 条 `global_fallback`；修复 `page_label` 中文乱码，`GRI 2-6` 子项 evidence 页码收窄，`GRI 2-7-e` 清空无效 evidence，`GRI 2-5-b-ii` 使用 PDF 第 77 页并标记 `requires_ocr=true`，未调用外部模型。
- 根据 `current_100_review.csv` 人工复核结论，增加治理类 disclosure 规则：`global_fallback` 在 agent 层全部清空；GRI 索引中的“从略披露”行作为 `omission_note` evidence 保留但不提升 `disclosed`；`GRI 2-9-a/b`、`GRI 2-12`、`GRI 2-13` 白名单子项可使用 PDF 第 13 页 ESG 治理架构作为 partial evidence；`GRI 2-9-c`、`GRI 2-11`、`GRI 2-10`、`GRI 2-19`、`GRI 2-20` 不使用 PDF 第 13 页支撑。
- 生成 `tmp/review/current_100_review_after_rules.csv`：100 个 requirement、113 行、61 条 evidence；按 requirement 聚合后为 10 条 `disclosed`、22 条 `partially_disclosed`、68 条 `unknown`，10 条 `not_required`、90 条 `needs_manual_review`；61 条 evidence 均为 `index_page_bounded`，0 条 `global_fallback`；其中 16 条为 `omission_note`，覆盖 `GRI 2-10`、`GRI 2-19`、`GRI 2-20`，未调用外部模型。

### 2026-07-02

- 确认从端到端纵切开始构建项目。
- 确认 PostgreSQL + pgvector 预留，替代早期 SQLite 设想。
- 确认 PDF 混合多路由管线。
- 确认前端使用 Next.js App Router。
- 初始化前端 Next.js App Router、Tailwind、TanStack Query、Vitest 骨架。
- 实现前端上传、结果、复核、审计页面和 Recharts 图表封装。
- 增加 FastAPI `response_model` 契约，前端类型由 OpenAPI 生成到 `frontend/lib/generated/`。
- 将后端 pytest 隔离到测试库 `esg_agent_test`，避免测试清空开发库。
- 完成本地端到端 HTTP 验收：上传、`confirm_llm=false` 分析、人工复核、JSON/CSV 导出和 audit 事件。
- 从 `../envision` 受控复制首批真实验收资产：远景能源 2024 中文 ESG 报告、GRI 官方合并标准 PDF、4 个 GRI/source manifest；记录到 `backend/data/manifests/assets_manifest.json`。
- 简化本项目数据目录：报告放在 `backend/data/reports/`，标准放在 `backend/data/standards/`，manifest 放在 `backend/data/manifests/`，运行时文件仍放在 `backend/data/runtime/`。
- 用 `backend/data/reports/Envision Energy 2024-zh.pdf` 跑通 `confirm_llm=false` 真实 PDF 验收：上传、解析、分块、assessment、review、JSON/CSV 导出、audit 均通过；未调用外部模型。
- 本次真实 PDF 解析质量：78 页，77 页可抽取文本，77 个 chunk，总抽取文本 73,824 字符；第 78 页标记为 `low_text_density` 和 `scanned`；23 页检测到表格，6 页标记为 `complex_table`。
- 修复真实 PDF 验收暴露的长 evidence/recommendation ID 入库问题：超过数据库主键长度时使用 deterministic hash，原始 `task_id` 和 `chunk_id` 保留在 evidence metadata。
- 将运行入口从 `backend/data/standards/gri_requirements.sample.json` 切换为 `backend/data/manifests/gri_requirement_checklist.json` 的前 10 条 `current_gap`、mandatory、`hard_score` requirement。
- 当前真实 checklist 来源项仍标记为 `pending_review`，第一版关键词检索得到的 evidence 只能用于流程验收和人工复核入口，不能作为最终合规结论。
- 本次未复制旧 agent 代码、旧 Streamlit 页面、旧运行结果、旧 prompt、旧 SQLite 数据或 `../esg-dashboard` 内容。
- 将技术设计保存到 `docs/DESIGN.md`。
- 精简文档体系为 `AGENTS.md`、`README.md`、`docs/DESIGN.md`、`docs/DEVELOPMENT.md`、`docs/ASSETS.md`。

