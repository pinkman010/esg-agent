# Phase 1.6 产品闭环补全验收报告

> 历史快照：本文记录 Phase 1.6 完成时的能力与限制。部分失败 577 项投影、报告审计、扫描 PDF 能力边界、独立报告闭环和正式输出后纠正已由 Phase 1.7 补齐；现行结论见 `docs/product/phase1.7-final-closure-acceptance.md`。

## 1. 结论

Phase 1.6 已完成并达到重新冻结条件。OBS-001、OBS-002、OBS-004、OBS-007 已关闭，`actions_xlsx` 已进入版本化输出。`577/499/78/0`、规则 assessment、risk-v2.1、AI suggestion、人工 snapshot、正式输出门禁和三层结论权威关系均未改变。

本次验收属于产品操作闭环和工程质量验证，不构成 GRI 认证、外部鉴证或新增 ESG 专家判断。

## 2. 范围与实现提交

解冻起点：

```text
5e4848b42efc5ed2dfd41baf9235c101b28cdedb
```

实现提交：

```text
9bc8576 feat: add secure export file delivery
95f168d feat: export improvement actions as xlsx
4b34935 feat: add complete scope search and filters
585d3cf feat: allow action due date updates
acfaf48 feat: expose export file downloads
22c8d2c feat: add complete scope search controls
4a1c787 feat: add action due date editing
dc3a77a test: cover phase 1.6 product closure
d729abb fix: harden phase 1.6 contracts
```

没有新增 Alembic migration、数据库表、OCR、RAG Phase 2、AI 状态、模型、Prompt、候选筛选或正式结论字段。

## 3. 能力验收

### 3.1 安全 export 文件交付

- 新增 `GET /api/exports/{export_id}/files/{file_id}`；
- 对外 manifest 固定为 `file_id`、`filename`、`format`、`size`、`sha256`；
- 内部 `relative_path` 只保存在 JSONB，不进入 API；
- 下载校验 export/manifest 归属、目录边界、文件存在、大小和 SHA256；
- 历史 `path` manifest 使用稳定 legacy `file_id` 兼容；
- OpenAPI、生成类型和前端静态产物精确扫描没有发现 `relative_path` 或项目本机路径；
- XLSX 用户文本以 `= + - @` 开头时增加文本前缀，避免公式注入；
- 前端按中文业务名称、格式和大小展示下载入口。

### 3.2 `actions_xlsx`

- 草稿和正式输出均支持 `actions_xlsx`，正式输出继续服从原门禁；
- 固定免责声明和列顺序已通过工作簿测试；
- 有整改任务时输出 requirement、负责人、截止日期和状态；
- 无整改任务时仍生成包含免责声明和表头的有效工作簿。

### 3.3 577 项搜索和筛选

- 搜索覆盖 requirement ID、GRI 主题、原始/有效条款文本和结构关联 ID；
- 筛选覆盖单元类型、有效结论、复核优先级、复核状态和适用性；
- 所有筛选在分页前执行，返回过滤后的 `total`；
- 499 个独立判断项和 78 个上下文项保持同一稳定自然排序；
- 上下文项不生成伪 verdict、priority、review 或 applicability；
- 空结果、清空恢复、回车搜索和分页均已通过 Chrome 验收。

当前限制：范围投影要求最新 run 已生成完整 499 条 assessment。缺少 assessment 的部分失败 run 返回 409；失败数量继续由 run/dashboard 和正式输出门禁披露，尚未投影为 577 项表格内的缺失行。

### 3.4 整改截止日期

- PATCH 支持新增、修改和显式清空 `due_date`；
- 未提供 `due_date` 时保持原值；
- 旧客户端显式发送 `status=null` 时保持原状态；
- 前端只提交实际变化字段；
- 只有实际状态变化才应用状态说明约束；
- 审计记录变化字段和日期前后值，不记录内部路径。

当前数据库没有可复用整改任务样本。Chrome 验收没有为了测试日期而制造业务任务；浏览器空态正确，日期写路径由组件测试、API 测试和产品闭环端到端测试覆盖。

## 4. 自动门禁

| 门禁 | 结果 |
| --- | --- |
| 后端全量 | 727 passed |
| 后端 Ruff | All checks passed |
| 后端核心纵向 | 37 passed |
| 前端测试 | 28 files / 114 tests passed |
| 前端 typecheck | passed |
| 前端 production build | passed |
| Envision 标准结构 | 577 / 499 / 78 / 0 |
| Envision global fallback | 0 |
| Envision new false disclosed | 0 |
| Envision new wrong source page | 0 |
| Envision audit | 0 error / 0 warning |
| 外部模型、OCR、VLM | 0 calls |

Envision regeneration 的结构审计文件为：

```text
backend/data/runtime/evaluations/envision_2024/current_499_review_scope_summary.json
backend/data/runtime/evaluations/envision_2024/current_499_review_regeneration_diff_summary.json
backend/data/runtime/evaluations/envision_2024/current_499_review_regenerated_audit.json
```

最终 regeneration 对象：

```text
report_id: envision_2024_v3-regeneration-5378a72a6aec
run_id: run-4617696b8b8440f19c3bb56a800250a8
confirm_llm: false
status: completed
```

## 5. Chrome 产品验收

验收对象：

```text
report_id: envision_2024_v3-regeneration-6ab6aa7a0d2e
run_id: run-833d93f9af594a69ad3c0cf7ee8b6909
confirm_llm: false
```

结果：

- 完整核查恢复状态为 577 项、每页 50 项、12 页；
- `GRI 2-1-a` 通过按钮和 Enter 均可搜索到唯一结果；
- `unit_status=context_incorporated` 返回 78 项，行内结论显示“已纳入相关判断”，其余判断字段为空；
- 五类组合筛选可同时生效，0 结果时显示明确空态，清空后恢复 577 项；
- 下一页显示第 51–100 项和第 2/12 页；
- 正式输出因 9 条高优先级未完成保持禁用，草稿可生成；
- 草稿展示 4 个文件：GRI 核查表、整改任务清单、管理层摘要、可打印核查表；
- 四个下载入口均触发浏览器 download 事件；
- 输出页当前视口没有明显遮挡、溢出或不可读文本；
- 整改任务无数据时显示明确空态和复核入口；
- Chrome console error/warning 为 0。

Chrome 层验证页面可操作性、下载入口和下载事件。文件名、字节数、SHA256、XLSX 可打开性及 PDF/HTML 类型由 API 端到端测试完成；本轮没有在 Chrome 下载后重复落盘解析四个文件。

受控写入：

- Envision regeneration gate 在审查前和修复后各创建一个新的本地报告和 run；
- Chrome 为第一次 regeneration 的报告生成一个草稿 export；
- 未保存人工 snapshot，未创建或修改整改任务，未生成正式 export；
- 没有调用 DeepSeek、SiliconFlow、OCR 或 VLM。

## 6. 重新冻结边界

Phase 1.6 完成后，v1.1 后端基线重新冻结。以下事项仍需单独计划和再次解冻：

- OCR 生产就绪与真实扫描样本验收；
- RAG Phase 2 正式接入；
- AI 后端状态语义和运行观测；
- 通用 verdict 批量复核；
- 独立 reopen；
- report 级审计页面；
- GRI checklist、`577/499/78/0`、evidence、risk-v2.1、模型/Prompt、数据库 schema 或正式导出口径变化。

下一阶段优先进行用户操作体验确认和真实产品问题采集。没有可复现召回缺口、真实 OCR 样本、AI 运行处置数据或独立 ESG 专家 gold 时，不继续扩大后端能力。
