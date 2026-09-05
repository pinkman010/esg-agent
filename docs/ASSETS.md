# 资产与证据边界

## 1. 资产来源

允许作为来源或参考的外部目录：

- 后端来源仓库：`../envision`。
- 前端参考仓库：`../esg-dashboard`。

这些目录不得删除、覆盖或回退。

## 2. 允许复制

从 `envision` 可复制：

- 远景能源 2024 中文 ESG 报告。
- GRI 标准资料。
- 必要 manifest。
- 必要 prompt。

从 `esg-dashboard` 可参考：

- UI 信息架构。
- 表格布局经验。
- 工作台视觉经验。
- 交互组织方式。

前端参考仓库不得整体复制，也不得复制无真实后端来源的静态假数据。

## 3. 本项目资产目录

本项目内的资产按用途放在浅层目录：

- 原始 ESG 报告：`backend/data/reports/`。
- 标准文件：`backend/data/standards/`。
- GRI checklist 和资产 manifest：`backend/data/manifests/`。
- 资产迁移和标准结构 manifest：`backend/data/manifests/`。
- 上传、OCR、导出等运行时文件：`backend/data/runtime/`。

## 4. 禁止复制

禁止从旧仓库复制：

- 旧 agent 代码。
- 旧 Streamlit 页面。
- 历史运行目录。
- 归档脚本。
- 旧 SQLite 数据。
- 旧分阶段测试。
- 旧日志。
- 静态假数据。
- 无真实后端来源的指标展示。

## 5. 原始材料保护

原始报告和标准文件视为证据材料：

- 不得覆盖。
- 不得删改。
- 不得用处理后文本替代原始文件。
- 派生文件必须单独保存，并记录来源文件 hash。

派生文件包括：

- OCR 后 PDF。
- 页面文本。
- 页面图片。
- 表格抽取结果。
- 文档 chunk。
- VLM 辅助识别结果。

## 6. 证据追溯字段

每条披露判断必须能追溯到：

- `run_id`
- `report_id`
- `standard_id`
- `standard_version`
- `disclosure_id`
- `requirement_id`
- `evidence_id`
- `source_text`
- `source_page`
- `source_file_hash`
- `source_method`
- `model_called`
- `review_status`

PDF/OCR/VLM 相关证据还应尽量保留：

- `bbox`
- `ocr_status`
- `vlm_used`
- `quality_flags`
- `needs_manual_review`

## 7. AI 输出边界

- AI 输出只能作为分析辅助。
- AI 输出不得写成最终合规结论。
- 没有报告证据时，不得补造企业披露事实。
- 证据质量不足时，结论必须进入人工复核。
- OCR/VLM 来源的关键 KPI 默认进入人工复核或低置信度状态。

## 8. 模型调用边界

- 默认不调用外部模型。
- 只有 `confirm_llm=true` 时允许调用外部模型。
- 所有模型输出必须经过 Pydantic 校验。
- 校验失败必须进入人工复核。
- 测试中不得真实调用外部模型，必须 mock。
- 不提交密钥、`.env` 或外部服务响应中的非公开数据。

## 9. 迁移记录要求

每次迁移资产时，应记录：

- 来源路径。
- 目标路径。
- 文件 hash。
- 迁移原因。
- 是否为原始材料或派生材料。

迁移记录可写入 `docs/DEVELOPMENT.md` 的开发日志，或后续实施计划指定的 manifest 文件。

## 10. 本地资产恢复

仓库不提交 PDF、Word、Excel 等二进制文档资产。

首次克隆或重新搭建环境后，应按 `backend/data/manifests/assets_manifest.json` 中的 `target_path` 恢复本地资产，并用 `sha256` 字段校验文件内容。

当前必需恢复的原始资产包括：

- `backend/data/reports/Envision Energy 2024-zh.pdf`
- `backend/data/standards/gri/GRI_Standards_Official_Consolidated_Set_en.pdf`

Phase 1.7 独立产品闭环验收还使用以下本地只读资产：

- `backend/data/reports/Goldwind 2024-zh.pdf`
- `backend/data/reports/profiles/goldwind_2024.json`

Envision 是权威主线回归样本；Goldwind 是不同企业、52 页双页拼版报告的产品泛化工程样本。两者都不得覆盖或改写。Goldwind 验收结果不能当作 ESG 专家 gold，也不能替代 Envision 零回归门禁。原始 Goldwind PDF 不提交 Git；缺少该本地资产时，相关真实 PDF E2E 应明确跳过或失败，不能用处理后文本、空白 PDF 或伪造页数替代。

内置 Envision/Goldwind report profile 保存对应原始 PDF 的 SHA-256。运行时只有文件名、页数和 SHA-256 全部一致时才允许应用报告专属候选页路由；哈希缺失或不一致必须明确失败。更新原始 PDF 或 profile 身份字段属于资产基线变更，需要重新审批并重跑双报告门禁。

可用 PowerShell 校验单个文件：

```powershell
Get-FileHash "backend/data/reports/Envision Energy 2024-zh.pdf" -Algorithm SHA256
```

校验结果必须与 `backend/data/manifests/assets_manifest.json` 中对应条目的 `sha256` 一致。

恢复资产时只复制原始文件，不覆盖、删改来源目录。Phase 1.7 Chrome 验收对 Goldwind 的上传只创建 runtime 副本，不修改 `backend/data/reports/` 中的源文件。派生文件、上传文件、OCR 文件和导出文件仍写入 `backend/data/runtime/`。

### 10.1 人工复核与模型评估资产

人工复核工作簿、复核建议和确定性回归基线本地保存到：

- `backend/data/review_inputs/envision_2024/manual/`
- `backend/data/review_inputs/envision_2024/baselines/`

真实模型评估、冻结验收摘要和迁移前数据库备份本地保存到：

- `backend/data/runtime/evaluations/`
- `backend/data/runtime/backups/`

这些目录中的内容不提交 Git。每项持久化资产必须在 `backend/data/manifests/assets_manifest.json` 登记项目相对目标路径、SHA256、大小、来源标识、用途和保护方式。外部来源只记录环境变量名，不记录本机绝对路径。

模型评估资产不得包含 API Key、数据库连接信息、完整 Prompt 或未经筛选的外部模型原始响应。桌面和 `tmp/` 来源在目标文件存在且哈希一致前不得清理；清理由用户人工执行。

## 11. 前端品牌与视觉资产迁移记录

前端视觉迁移（`docs/plan/frontend-visual-migration-plan.md`）阶段 3 从 `../esg-dashboard/public/` 复制以下品牌与视觉资产到 `frontend/public/`，来源仓库保持只读。资产已获用户授权搬运，仅用于界面装饰，不属于证据材料。

| 目标路径 | SHA-256 | 用途 |
|---|---|---|
| `frontend/public/brand/envision-wordmark.png` | `080b4b70eba72e04ccec0d322a8a7a9ea6682dccb0a0915540582bf80454ef1d` | 品牌 wordmark |
| `frontend/public/brand/envision-favicon.png` | `b0fd3ce4ff0a2e7880116b0133f1ba2db9f96c334019f15b02db6a450873718c` | 品牌 favicon 备用 |
| `frontend/public/visuals/overview-dashboard-hero.webp` | `2f3047f4778b792f5dfcfa00846e2f41c5266dd4f24bf5972bcd5c37296af060` | 首页 hero 背景 |
| `frontend/public/visuals/module-policy-disclosure.webp` | `e08462e062810943f2bfbbb4df16f1824e51524e0fce6cf5ae045e561c1683d5` | 报告 dashboard 头部 hero |
| `frontend/public/visuals/sidebar-renewable-energy.webp` | `4f4d9b4d36e2200f31914154f6e1a6f3ef88a2986edf86fce903c68bb522a908` | 桌面端侧边栏背景 |
| `frontend/public/visuals/module-materiality-benchmark.webp` | `1524ccf1fe7da03c233f917edc57debdd570d53ea0ff847805871ae3473f4682` | 备用视觉图 |
| `frontend/public/visuals/module-claw-monitor.webp` | `928659018577a2d8e9d543caf6a634c87193de13da87eae4174d1da10ac9f9d8` | 备用视觉图 |

## 12. 1.5 发布包与迁移资产边界

### 12.1 可进入发布包

- Git 指定 commit 中已跟踪的源码、migration、锁文件、配置模板和文档；
- `delivery/toolchain-lock.json`、`delivery/release-policy.json` 与 launcher manifest；
- 根目录已核验的 `ESG-Agent.exe` 及其 C# 源码和应用 manifest；
- `frontend/public/` 中已登记的静态视觉资产；
- GRI 结构、规则、来源与编译 manifest，以及不含原始报告内容的 report profile；
- `delivery/demo/demo-report-source.json` 及由它确定性生成的唯一演示 PDF。

演示 PDF 使用虚构企业和合成数据，只验证交付流程。它不复制 Envision、Goldwind 或 GRI 原始文本，不宣称认证，也不作为规则准确率或专家判断样本。

### 12.2 只允许授权本地恢复

Envision、Goldwind、GRI 官方 PDF、人工复核工作簿、工程 gold、真实模型评估和非公开验收截图继续按 `backend/data/manifests/assets_manifest.json` 管理。它们可以用于维护者门禁，但不进入 Release ZIP。缺少 Goldwind 时发布包测试只允许以 `authorized Goldwind regression asset is not installed` 明确跳过；维护者正式门禁必须先核对资产 SHA-256，并断言没有跳过。

### 12.3 运行时与备份

真实 `.env`、数据库密码、API key、PostgreSQL volume、数据库 dump、上传报告、派生 PDF/OCR、导出、日志和测试输出属于运行或备份数据，默认全部排除。`backend/data/runtime/` 在源码包内只保留目录 `.gitkeep`。

数据库与 runtime 迁移通过 `New-EsgAgentBackup.ps1` 和 `Restore-EsgAgentBackup.ps1` 完成。`-IncludeRuntime` 可能包含非公开报告，必须取得资产授权；备份 ZIP、sidecar checksum 和恢复目标库不进入源码归档。恢复始终写入新目标库，不覆盖原库。

发布构建器对 commit payload 执行路径拒绝、配置模板敏感值检查、launcher 哈希校验和 PDF 白名单。未跟踪文件不会被 `git archive` 读取；`首页.png` 被显式拒绝并保持用户本地文件状态。

