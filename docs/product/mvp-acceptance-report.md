# Envision 2024 中文报告 MVP 产品验收报告

## 1. 验收结论

截至 2026-07-20，Envision 2024 中文 ESG 报告主线通过本地 MVP 产品验收。产品可以完成：重复上传选择、metadata 确认、577 个标准核查单元编译、493 个独立判断项分析、显式授权 DeepSeek、规则/AI/人工三层复核、PDF 证据定位、AI 建议采纳/修改/拒绝、整改入口和版本化草稿输出。

本结论属于产品与工程验收，不构成 GRI 专家认证、外部鉴证或最终合规结论。16 条 Sol/Pro 方法差异和 6 个方法待确认项继续保留；高优先级队列完成也不代表 577 个标准核查单元均已人工确认。

## 2. 范围与环境

| 项目 | 验收事实 |
| --- | --- |
| 分支 | `main` |
| P1 修复提交 | `4abdac9` |
| 数据库 | `esg_agent_demo` |
| Alembic head | `0011_ai_suggestions` |
| 前端 | `http://localhost:3000` |
| 后端 | `http://localhost:8000` |
| 报告 | Envision Energy 2024 中文 PDF，78 页 |
| 外部模型 | DeepSeek `deepseek-v4-flash`，显式授权后调用 |
| OCR / VLM | 均关闭 |
| Goldwind | 保留历史 100 条 gate，优先级低于 Envision，不作为本轮阻塞门禁 |

运行时证据保存在 `backend/data/runtime/acceptance/frontend-ai/`，不提交截图二进制；路径、SHA256、大小、用途和日期已登记到 `backend/data/manifests/assets_manifest.json`。

## 3. 自动门禁

| 门禁 | 结果 |
| --- | --- |
| 后端全量测试 | 627 passed |
| 前端测试 | 22 个测试文件，80 passed |
| 前端 typecheck | 通过 |
| 前端 production build | 通过 |
| Envision 结构范围 | 577 / 493 / 78 / 6 |
| Envision 唯一独立判断项 | 493 |
| Envision `global_fallback` | 0 |
| Envision 新增 false disclosed | 0 |
| Envision 新增 wrong source page | 0 |
| Envision audit | `ok=true`，0 error，0 warning |

## 4. 真实 AI 产品 run

本轮通过 metadata 页面显式勾选 AI 后启动：

- report：`report-2b0c98b72f3c47beb285f712379e573b`；
- run：`run-021eeb43338f4381910218628b64554b`；
- 规则结果：493 成功、0 失败；
- AI：4 条符合调用条件，成功 4、失败 0、跳过 489；
- 八阶段全部完成，终态 100%，没有继续转圈；
- 页面提供“查看分析结果”和“进入高优先级复核”。

产品 run 只调用“结构独立 + 高/中复核优先级 + 有实质证据”的条目，因此本次调用 4 条。225 条是固定人工基线的工程评估集，不等于每次新报告都调用 225 条。固定基线 run 为 `run-526bd97aef5d4b9baa14618b719081c9`；其追加式历史包含 230 条成功和 13 条失败记录，数量高于 225 的原因是定向重试与补跑。

## 5. 普通 Chrome 主流程结果

| 验收点 | 结果 |
| --- | --- |
| 重复上传 | 同时提供“查看已有结果”和“重新上传并分析” |
| 新报告 | 重新上传创建新 `report_id`，历史数据保留 |
| metadata | 企业、年度、语言可修改；企业识别为“远景能源有限公司” |
| AI 授权 | 默认关闭；勾选后显示发送范围与不覆盖规则/人工的边界 |
| 分析进度 | 八阶段顺序正确；终态显示 AI 4/0/489 汇总 |
| 完整核查表 | 显示 493 个独立判断项并解释 577/493/78/6 |
| 直接定位 | 点击 requirement 后进入带 `assessmentId` 的三栏工作台 |
| 三层复核 | 规则、AI、人工标题和字段独立 |
| PDF | 证据在右栏 iframe 定位，未触发下载或新窗口 |
| 高优先级口径 | 明确说明不代表全部 requirement 均已人工确认 |
| 草稿输出 | 生成 3 个文件并包含 AI 辅助免责声明 |

## 6. 三类人工决策审计

| 操作 | Requirement | Suggestion | Snapshot | Reason code | 结果 |
| --- | --- | --- | --- | --- | --- |
| 采纳 | `GRI 201-1-b` | `ai-suggestion-77e1243946d840ab811a3241fd581266` | `snapshot-c4f56fc7ff8f40f485710c7c8b70191c` | `ai_suggestion_accepted` | 通过 |
| 载入并修改 | `GRI 203-1-c` | `ai-suggestion-4c0acb6fc9bb4a3eb99dcd7284060eb2` | `snapshot-c09733610a6b4d64a32f5c2bfc25203d` | `ai_suggestion_modified` | 通过 |
| 拒绝并保留规则 | `GRI 203-2-b` | `ai-suggestion-1850d5e3dd0045518a20ab39ffb42f3d` | `snapshot-7ed3af55697c4f3d834e76f8fa375d53` | `ai_suggestion_rejected` | 通过 |

三条 snapshot 均记录 `Codex产品验收`、时间、reason code、suggestion id 和完整结果字段。三条 AI suggestion 仍保留原内容；`assessments` 的规则结论、依据和缺失项未被更新或删除。

## 7. 问题记录

| 编号 | 严重程度 | 页面/接口 | 前置条件 | 复现步骤 | 实际结果 | 期望结果 | 影响范围 | 建议修复 | 状态 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MVP-AI-001 | P1 | assessment detail | 已存在 AI 建议 | 采纳 AI 后刷新详情 | 规则区一度显示人工 snapshot 的 AI 依据和缺失项 | 规则区始终显示不可变规则字段 | 三层权威边界和拒绝 AI 行为 | API 增加 `system_rationale` / `system_missing_items` 及展示字段，前端规则区和拒绝操作只读这些字段 | 已修复，提交 `4abdac9`；相关与全量门禁通过 |
| ENV-001 | 环境限制 | Chrome 本地文件选择器 | Chrome 扩展控制本机页面 | 自动把本地 PDF 赋给原生文件选择器 | Chrome 返回 `Not allowed` | 自动选择文件 | 只影响验收自动化，不影响产品上传能力 | 人工选择文件后继续自动验收 | 已绕过；不列为产品缺陷 |

当前无未解决 P0/P1 产品问题。

## 8. 证据索引

| 文件 | 用途 |
| --- | --- |
| `01-duplicate-report-options.png` | 重复上传双路径 |
| `02-metadata-ai-default-off.png` | AI 默认关闭 |
| `03-metadata-ai-enabled.png` | 显式授权与数据边界 |
| `05-analysis-completed-ai4.png` | 八阶段终态与 AI 4/0/489 |
| `06-assessment-table-493.png` | 493 项及 577/493/78/6 解释 |
| `07-three-layer-review-pdf.png` | 三层详情与右栏 PDF |
| `08-dashboard-review-scope.png` | 高优先级范围文案 |
| `09-rule-ai-human-separated-after-accept.png` | 采纳后规则层仍独立 |
| `10-ai-modified-gri-203-1-c.png` | AI 建议载入并人工修改 |
| `11-ai-rejected-gri-203-2-b.png` | 拒绝 AI 并保留规则结论 |
| `12-draft-output.png` | 版本化草稿输出 |
| `acceptance-summary.json` | 运行、决策、问题和限制的机器可读摘要 |

草稿 export 为 `export-110b3cdea933420bb676e7593437af50`，包含 assessment XLSX、管理层摘要 PDF 和打印 HTML。打印 HTML 明确写入：“AI建议未经人工确认时不构成最终披露结论。”

## 9. 已知限制与下一步

- `actions_xlsx` 尚未生成完整整改任务清单；
- 通用 verdict 批量复核、独立 reopen、report 级审计和单 export 下载仍为规划接口；
- 旧 `review_decisions`、旧 API 和旧页面仍有调用者，继续保留；
- 16 条 Sol/Pro 差异和 6 个方法待确认项需要未来 GRI 方法负责人裁决；
- 225 条 AI 基线属于工程验证，不等同 ESG 专家复核；
- 当前验收主线只承诺 Envision 2024 中文报告，Goldwind 仅保留为次级泛化证据。

下一阶段可以冻结 Envision 后端事实与接口，集中做前端演示优化、交互收敛和简历/演示材料整理。任何规则、Prompt、GRI 结构或 risk-v2.1 变化都应重新运行 627 项后端测试、Envision gate 和相关前端门禁。
