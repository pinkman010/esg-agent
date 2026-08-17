# OCR 单页受控试点验收报告

## 1. 验收结论

OCR 单页受控试点通过，后端基线可以重新冻结。

本试点代码、系统依赖记录与验收结论已纳入 `v1.3` 发布基线。

OCR 已通过单页受控试点，默认关闭，仅在全局和请求双重启用后按目标页运行；当前不构成通用扫描 PDF 生产能力。

本轮只验证 Envision 2024 报告第 77 个 PDF 页。OCR evidence 继续带 `needs_manual_review`，规则结论、风险、适用性、人工快照和正式输出优先级均未改变。DeepSeek、embedding 和 VLM 实际调用均为 0。

## 2. 实施范围与提交

| 类型 | 提交 | 内容 |
| --- | --- | --- |
| 设计 | `3383163` | 受控 OCR 设计 |
| 依赖检查 | `bd54c41` | OCR capability 与依赖 preflight |
| 安全执行 | `421e7b4` | 超时、错误脱敏、清理与派生哈希 |
| API 门禁 | `bba64b4` | 全局/请求双重开关与 capability API |
| 工作流 | `aa808fd` | 目标页选择、OCR 解析、审计与持久化 |

本轮没有修改数据库 schema、Alembic、GRI checklist、规则、ontology、风险规则、AI 模型、Prompt、人工快照、前端产品流程或正式导出 schema。

## 3. 依赖与能力检查

| 项目 | 验收值 |
| --- | --- |
| OCRmyPDF | 17.8.0 |
| Ghostscript CLI | 10.07.1 |
| Ghostscript 安装包 | Chocolatey `Ghostscript 10.7.1` |
| Tesseract | 5.5.0.20241111 |
| Tesseract 语言 | `chi_sim`、`eng`、`osd` |
| capability | `enabled=true`、`available=true`、`dependency_codes=[]` |
| OCR 语言与页数上限 | `chi_sim+eng`、5 页 |

`GET /api/capabilities/ocr` 使用与 workflow 相同的 preflight 口径。依赖缺失只影响显式 OCR 请求，不改变 `/api/health` 的服务存活语义。

## 4. 真实单页试点

试点在隔离 demo 数据库和独立 runtime 中通过正式上传、metadata 确认与 analyze API 创建，没有覆盖历史报告。

| 项目 | 结果 |
| --- | --- |
| 新报告 | `report-c500a26acd844eb19041446ef79a3daa` |
| 新运行 | `run-5220d8feef2f4159b705da9403e541ae` |
| LLM 授权 | `confirm_llm=false` |
| OCR 请求 | `enable_ocr=true`、`ocr_pages=[77]` |
| run | completed，499 succeeded，0 failed |
| OCR 选择 | 显式第 77 页，1 页 |
| OCR 耗时 | 29,427 ms |
| OCR chunk | 1 个，来源页 77，文字长度 2,324 |
| 人工复核标记 | `needs_manual_review` |
| 派生 PDF SHA-256 | `ab6898e9d8f34dabb30575e28c8e52d14b021df46540ee2b564c673f18a549b7` |

锚点检查只在进程内执行，没有保存或输出完整 OCR 正文：

- “德勤”：命中；
- “独立有限鉴证报告”：未命中；
- “鉴证结论”：命中。

结果为 2/3 个锚点命中，满足至少两个锚点的验收条件。审计只记录页码、文字长度、耗时和派生哈希，不包含本机路径、命令行、原始 stderr、环境变量或证据正文。

## 5. 499 项逐项差异

基线 run 为 `run-debd7c6af0ed494bbb6c8b5f73d99188`，对应 499 个独立 assessment、0 个规则失败和 0 次实际外部模型调用。新旧 run 按 `requirement_id` 对齐。

| Requirement | 结论 | Evidence 数量 | 来源页 | 来源方式 | 风险/人工复核 |
| --- | --- | --- | --- | --- | --- |
| GRI 2-5-a | `partially_disclosed`，不变 | 1 → 2 | 77，不变 | `pdfplumber` → `pdfplumber + ocr` | high、quality warning、pending review |
| GRI 2-5-b-i | `disclosed`，不变 | 1 → 2 | 77，不变 | `pdfplumber` → `pdfplumber + ocr` | high、quality warning、pending review |
| GRI 2-5-b-ii | `disclosed`，不变 | 1 → 2 | 77，不变 | `pdfplumber` → `pdfplumber + ocr` | high、quality warning、pending review |
| GRI 2-5-b-iii | `disclosed`，不变 | 1 → 2 | 77，不变 | `pdfplumber` → `pdfplumber + ocr` | high、quality warning、pending review |

四项只有 evidence 数量和来源方式发生预期变化；rationale、missing items、risk level、evidence status、applicability status 和 risk reason codes 均未变化。其余 495 项的 system verdict、rationale、missing items、evidence count、source PDF pages、source method、risk、evidence status、applicability 和 risk reason codes 差异均为 0。

因此本轮新增 false disclosed 为 0、新增 wrong source page 为 0、global fallback 为 0。OCR evidence 没有越过规则或人工复核边界。

## 6. 资产与调用审计

| 项目 | 数量/结果 |
| --- | --- |
| 原始 PDF 试点前 SHA-256 | `57360dcda8e6256726be5d2a49f8921e13187b40ae44661549903f702df38068` |
| 原始 PDF 试点后 SHA-256 | 相同 |
| 派生 PDF | 1 个，只位于 demo 派生目录 |
| OCRmyPDF 实际任务 | 1 次 |
| OCR 实际页数 | 1 页 |
| DeepSeek 实际请求 | 0 |
| embedding 实际请求 | 0 |
| VLM 实际请求 | 0 |

原始 PDF 未覆盖、未移动、未改写。工作区在真实试点后保持无源代码差异。

## 7. 完整门禁

| Gate | 结果 |
| --- | --- |
| 后端 | 822 passed |
| Ruff | passed |
| 前端单测 | 39 个测试文件、149 项测试通过 |
| 前端 lint | 0 error、2 条既有 warning |
| 前端 typecheck | passed |
| 前端 production build | passed |
| Envision v3 | `577/499/78/0`，499 个唯一 assessment |
| Envision audit | 0 error、0 warning |
| Envision 差异 | global fallback 0、新增 false disclosed 0、新增 wrong source page 0 |
| 最终裁决 | 16 条，0 pending |

两条既有前端 warning 分别来自 TanStack Table 的 React Compiler 兼容提示和 PDF 页图使用 `<img>` 的性能提示，与 OCR 修改无关。

## 8. 限制、回滚与后续判断

当前证据只覆盖一个中文混合文本/图片报告的一页，不能证明对完全扫描报告、不同扫描质量、旋转页、复杂表格、多语言或大批量任务的通用能力。同步执行的单页 OCR 约 29 秒，也不足以决定是否需要后台队列。

运行回滚优先将 `OCR_ENABLED=false`，请求保持 `enable_ocr=false`；这会恢复纯 `pypdf + pdfplumber` 默认链路。系统依赖需要回滚时，可在停止 OCR 任务后使用包管理器卸载固定 Ghostscript 包；卸载不会删除原始报告，demo 派生文件仍按运行时数据策略处理。

后端在本报告对应提交完成后重新冻结。只有新增至少两类真实扫描报告、形成页级 gold，并记录关键证据召回、错页率、耗时、失败率和人工复核负担后，才评估通用 OCR、VLM 或后台队列。RAG Phase 2 与 OCR 继续独立决策。
