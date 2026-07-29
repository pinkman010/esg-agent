# Phase 1.7 最终闭环与发布就绪验收报告

## 1. 结论

截至 2026-07-29，Phase 1.7 的代码、契约、双报告工程验证、干净环境验证和 Chrome 自动验收均已完成。当前分支达到以下发布候选范围：

> esg-agent 已形成可本地运行的单报告 ESG 披露分析闭环，支持数字文本型 PDF 的 GRI 577 项结构化核查、证据定位、规则结果、AI 辅助建议、人工复核快照、整改跟踪、草稿/正式输出、审计追踪和失败恢复。

建议发布基线为 `v1.2`。本报告只证明本地产品闭环和工程质量，不构成 GRI 认证、ESG 专家结论、法律意见、外部鉴证或企业级生产部署承诺。

## 2. 支持范围

### 2.1 已支持

- 单份报告上传、metadata 识别与人工确认。
- GRI 577 项完整范围，其中 499 个独立判断项、78 个上下文项、0 个 method pending。
- 数字文本型 PDF 的页级文本、表格、图片和证据定位。
- 数字文本与少量扫描页混合报告的受限处理；低质量或扫描页保留人工复核提示。
- 八阶段分析进度、部分失败、失败项定向重跑和服务重启恢复。
- 运行谱系上的 577 项有效视图。
- 规则结果、AI 辅助建议、人工快照三层展示与留痕。
- 人工复核、适用性确认、整改任务创建与更新。
- 草稿与正式输出、四类文件下载、正式版本替代关系。
- 报告级审计时间线。

### 2.2 未支持

- 完全扫描 PDF 的正式无感处理。
- 生产 OCR 环境、Ghostscript preflight、Docling、PaddleOCR 和 VLM。
- RAG Phase 2 或跨报告知识检索。
- 批量报告分析、跨报告对比和企业知识库。
- 多租户、身份认证、权限矩阵、后台队列、横向扩容和灾备。
- GRI 认证、ESG 专家 gold、法律意见或外部鉴证。

完全扫描且未启用实验 OCR 的文档会在规则执行前返回稳定的 `unsupported_scanned_pdf` 错误，不生成虚假 assessment。

## 3. 结论权威关系

三层数据保持独立：

1. 规则层保存确定性 assessment 和原始证据，创建后不可覆盖。
2. AI 层只追加 `ai_assessment_suggestions`；默认 `confirm_llm=false`，未获用户明确授权时不会调用外部模型。
3. 人工层每次采纳、修改、拒绝或重开均追加 review snapshot。

当前有效复核结论来自最新有效人工快照；没有人工快照时显示规则结果。AI 建议不能修改适用性、复核优先级、规则字段、人工状态或正式输出结论。

## 4. 部分失败与重跑

产品从最新 run 沿 `parent_run_id` 向上读取同一报告的运行谱系：

- 同一 requirement 使用谱系中最近的有效 assessment。
- 明确失败且没有 assessment 的独立项显示 `analysis_status=failed`。
- 从未生成 assessment 的独立项显示 `analysis_status=not_generated`。
- 失败和未生成行不返回伪造的 verdict、evidence、risk 或人工结论。
- 上下文项继续显示 `context_incorporated`，不生成独立 assessment。
- 每条有效 assessment 返回 `source_run_id`，历史 run 不复制、不覆盖。

因此，部分失败或重跑后的范围接口仍返回完整 577 项。正式输出 gate 使用同一有效视图，499 个独立判断项存在未解决失败或未生成项时拒绝正式输出。

## 5. 正式输出后的纠正

纠正复用 assessment 的 `operation_type=reopen`：

1. 新增 reopen 快照后，报告进入 `reopened`。
2. 历史规则结果、人工快照和正式文件保持不可变。
3. 完成新的解决型人工复核后，可再次申请正式输出。
4. 新正式版本编号递增，`supersedes_export_id` 指向上一正式版本。
5. 旧正式版本变为 `superseded`，历史文件仍可下载和审计。

本阶段没有新增独立 report reopen API，也没有启用 `voided` 输出操作。

## 6. 双报告工程验证

### 6.1 Envision

Envision 继续作为权威主线回归样本。最终 regeneration 结果：

| 指标 | 结果 |
| --- | ---: |
| 标准单元 / 独立判断 / 上下文 / method pending | `577/499/78/0` |
| unique assessment requirement | 499 |
| global fallback | 0 |
| 新增 false disclosed | 0 |
| 新增 wrong source page | 0 |
| 最终裁决 / pending | `16/0` |
| audit error / warning | `0/0` |

Envision 用于证明主线规则、证据页和既有裁决未回归。

本轮重新生成产物保留在本地 runtime，不提交 Git；SHA-256 为：

| 产物 | SHA-256 |
| --- | --- |
| `current_499_review_regenerated.csv` | `16f9ca3e15cf4e75502176fbae8ae76d3c7a2ca7e0272203e7d9be7fcd8bdc3e` |
| `current_499_review_regenerated_audit.json` | `42bcde6af5a675e135e77c9fda8ee137a12b3d6d5866de78f2d1eb3f0883c83b` |
| `current_499_review_regeneration_diff_summary.json` | `1a18fc4469960d65e0edb9953a522c102c8170fcd2578e9da01b6ca99c935c3e` |
| `current_499_review_scope_summary.json` | `7123241741c01844476bb425b86fca5795dac6e4c1ca606d70220de5e22f6330` |

### 6.2 Goldwind

Goldwind 2024 报告共 52 个 PDF 页，用于验证不同企业、不同页数和双页拼版报告能够走通同一产品流程。真实 PDF API E2E 验证：

- 上传文件 hash 和页数正确。
- 生成 499 个独立 assessment 和完整 577 项范围。
- `confirm_llm=false`，AI suggestion 为 0。
- 证据页全部在 1–52 范围内。
- `global_fallback=0`。
- 人工快照、整改任务、草稿、四类文件下载和审计事件均成功。

Goldwind 是独立产品泛化和工程闭环样本，不是 ESG 专家 gold，也不替代 Envision 主线回归。

## 7. 自动门禁

验收实现提交范围为 `d638f01` 至 `549c6b2`；最终文档提交以 Git 历史为准。

| 门禁 | 命令 | 结果 |
| --- | --- | --- |
| 后端全量 | `uv run pytest -q --basetemp=../tmp/pytest-phase17-p2-final` | 774 passed |
| 后端静态检查 | `uv run ruff check .` | 通过 |
| 前端全量 | `pnpm test -- --run` | 30 个文件，119 passed |
| 前端类型 | `pnpm typecheck` | 通过 |
| 前端构建 | `pnpm build` | 通过 |
| Envision regeneration | Phase 1.7 计划中的正式 regeneration 命令 | 通过，0 error、0 warning |
| 空数据库 migration | `uv run alembic upgrade head` | `0012_chunk_embeddings (head)` |
| 启动与恢复冒烟 | health、OpenAPI、重启恢复目标测试 | 通过 |

独立代码复核后追加三批修复：

| 提交 | 关闭问题 |
| --- | --- |
| `3c707aa` | active/recovered retry run 选择、`not_generated` 仪表盘计数、旧审计接口与 POSIX 路径脱敏 |
| `038238e` | 人工复核与版本化输出事务原子性、导出失败目录清理 |
| `c116034` | report profile 源 PDF SHA-256 身份校验、打印版失败/未生成状态 |
| `549c6b2` | dashboard 失败/未生成/聚合计数拆分、通用 POSIX 路径脱敏、渲染失败目录清理和 OpenAPI 类型同步 |

故障注入测试确认复核或导出任一步失败时，数据库不会保留半套 snapshot、risk、export、supersede、report status 或 audit 状态。画像解析要求文件名、页数和 SHA-256 同时匹配。

最终独立复审对 `549c6b2` 及此前全部修复做只读核验，结论为 P0、P1、P2 均为 0；聚焦验证覆盖 39 项后端 API、4 项 OpenAPI contract、2 个前端文件的 10 项组件测试和 typecheck。

OpenAPI 由工作树后端实例生成。由于默认 8000 端口已有用户服务，本轮使用独立端口执行等价的 `openapi-typescript` 生成命令；生成结果、前端类型和后端 schema 一致。

## 8. Chrome 自动验收

验收环境使用独立 demo 后端和前端端口，不重置 demo 数据库，也没有停止用户现有服务。验收报告为 Goldwind 2024，`confirm_llm=false`，OCR/VLM 关闭。

| 验收项 | 结果 |
| --- | --- |
| 报告列表与上传入口 | 通过 |
| metadata | 自动识别公司、2024 年、中文、52 页；人工确认成功 |
| 分析进度 | 5% → 54% → 8/8 完成；AI 阶段明确显示未启用 |
| 结构范围 | 页面显示 577 项；独立判断和上下文项分层正确 |
| PDF 证据 | GRI 2-1-a 的 PDF 第 6 页图片成功加载 |
| 人工复核 | 工程验收快照追加成功，规则字段保持不可变 |
| 整改任务 | 创建成功，并从待处理更新为进行中 |
| 草稿 | 生成四个文件，披露中优先级未复核 37、适用性待判定 92 |
| 下载 | 管理层摘要 PDF 触发下载，审计记录文件大小与 SHA256 |
| 正式输出 | 预检和后端门禁通过，生成正式版本 v1 |
| 审计 | 12 条事件覆盖上传、确认、画像、分析、复核、整改、输出和下载 |
| 窄屏 | 移动导航、三栏切换和 PDF 证据栏可用，无横向溢出 |
| 键盘 | 从“证据”页签按 Tab 正确进入“缩小 PDF”，控件名称可辨识 |
| 状态表达 | 文本同时表达状态，不只依赖颜色 |
| 浏览器日志 | console error/warning 为 0 |
| 关键请求 | 最终验收路径均成功，无用户可见 4xx/5xx |

Chrome 扩展没有启用本机文件 URL 权限，原生文件选择器不能自动赋值。Computer Use 未发现可控制的 Chrome 文件选择窗口，因此上传步骤通过同一 demo 后端的正式上传 API 写入 Goldwind 原始文件只读副本，再回到 Chrome 完成 metadata 之后的全部用户流程。真实 multipart 上传、重复上传两分支和完整 Goldwind API E2E 均有自动测试覆盖。该限制属于浏览器扩展环境，不是产品上传缺陷。

验收中发现新审计事件缺少中文名称，页面显示为“系统事件”。提交 `8f79a58` 已补齐报告画像、分析启动、人工快照、草稿和正式输出等事件及关键字段标签，并增加前端回归测试。

## 9. 安全与资产检查

- 没有新增 migration 或表结构。
- 没有覆盖 Envision、Goldwind、GRI 标准或来源仓库。
- 原始 PDF 只读，上传副本和派生文件写入 demo runtime。
- 没有真实 DeepSeek、SiliconFlow、OCR 或 VLM 调用。
- docs、代码和前端没有本机绝对路径。
- token 扫描只命中测试 fixture 的占位授权头、脱敏输出 `[redacted]` 和计划中的扫描正则；没有真实密钥。
- 报告审计 payload 递归脱敏、截断，不返回本机路径、连接串、密钥、完整 stderr、Prompt 或模型原始响应。

## 10. 剩余限制与条件化路线图

独立复核发现的 6 个 P1 和 4 个 P2 已全部关闭；当前无未解决 P0/P1/P2。以下产品边界或范围外事项不阻塞 Phase 1.7：

- Chrome 文件选择器自动化依赖扩展的文件 URL 权限。
- Goldwind 工程结果未经过独立 ESG 专家复核。
- 实验 OCR 缺少正式 preflight 和真实扫描样本发布门禁。
- 批量 verdict 复核、跨报告分析和企业级运行能力未实现。

后续只在出现明确触发条件时立项：

1. 真实用户使用暴露可复现闭环缺陷。
2. 独立 ESG 专家 gold 证明规则或证据存在明确偏差。
3. 扫描报告造成关键证据缺失，并形成可复核样本与 OCR 验收指标。
4. RAG Phase 2 具备独立质量指标、受控候选边界和完整回归预算。
5. 企业化需求具备身份、权限、容量、备份、恢复和运维验收标准。

Phase 1.7 完成后不自动创建 Phase 1.8。下一发布动作仅包括独立复核、用户批准后的分支集成、`v1.2` 标签和推送。
