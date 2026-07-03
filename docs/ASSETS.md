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

可用 PowerShell 校验单个文件：

```powershell
Get-FileHash "backend/data/reports/Envision Energy 2024-zh.pdf" -Algorithm SHA256
```

校验结果必须与 `backend/data/manifests/assets_manifest.json` 中对应条目的 `sha256` 一致。

恢复资产时只复制原始文件，不覆盖、删改来源目录。派生文件、上传文件、OCR 文件和导出文件仍写入 `backend/data/runtime/`。

