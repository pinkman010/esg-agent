# Envision 2024 中文报告 MVP 产品验收报告

## 1. 验收结论

截至 2026-07-26，Envision 2024 中文报告已完成 577 项 GRI 核查，达到本地 MVP 后端冻结条件，并完成报告中心前端演示体验验收。冻结名称：

```text
Envision 2024 中文报告 MVP 后端基线 v1.1
范围：577 项 GRI 核查
性质：本地产品与工程基线
```

产品已形成上传、metadata 确认、八阶段分析、完整范围查看、优先级复核、整改入口和版本化输出闭环。规则 assessment、AI suggestion 和人工 snapshot 分层保存。高优先级队列完成只表示该队列已处理，不表示 577 项均已人工确认。

该结论不构成 GRI 专家认证、外部鉴证、最终合规结论或企业部署承诺。企业条件适用性仍可能需要企业确认。

## 2. 冻结身份

| 项目 | 冻结事实 |
| --- | --- |
| 分支 | `main` |
| 后端冻结记录 | `f99adde` |
| 前端验收实现 | `e047e8b` |
| 数据库 migration | `0011_ai_suggestions` |
| 结构 manifest | `gri-requirement-checklist-v3` |
| 产品方法版本 | `envision-method-v1.1` |
| 结果裁决版本 | `envision-result-v1.1` |
| 复核优先级规则 | `risk-v2.1` |
| DeepSeek | 模型、Prompt、调用范围和 guardrail 本轮未改变 |
| OCR / VLM | 均未启用 |
| Goldwind | 保留历史 100 条 gate，不阻塞 Envision 冻结 |

## 3. 范围口径

普通产品页面和演示材料统一使用：

```text
Envision 2024 中文报告完成 577 项 GRI 核查。
```

技术审计结构为：

| 内部计数 | 数量 | 含义 |
| --- | ---: | --- |
| 标准单元 | 577 | 完整产品核查范围 |
| 独立判断项 | 499 | 生成确定性 assessment 的单元 |
| 上下文项 | 78 | 纳入相关独立判断，不生成伪 verdict |
| 方法待确认项 | 0 | 当前无公开未决方法项 |
| 已裁决复合结构 | 6 | 历史合并/拆分问题，已按 v1.1 方法固化 |

16 条历史 Sol/Pro 结果差异已写入独立最终裁决资产：13 条规则结果与最终裁决一致，3 条保留明确的最终人工覆盖，0 条 pending。原始人工工作簿未覆盖，SHA256 保持：

```text
f1eeb37444de1eeda86b8ae0813dbfd6e88c94719781b98a8de659d9fbd7ddea
```

## 4. 验收环境

| 项目 | 验收事实 |
| --- | --- |
| 应用环境 | `APP_ENV=demo` |
| 当前业务数据库 | `esg_agent_demo` |
| 主库对照 | `esg_agent`，未清空、未重建 |
| 前端 | `http://localhost:3000` |
| 后端 OpenAPI | `http://localhost:8000/docs` |
| 报告 | Envision Energy 2024 中文 PDF，78 页 |
| 本轮 report | `report-15401bb4334e40d4a0885730f2635b22` |
| 本轮 run | `run-92bf75b11eb042dab6cb689311634fe1` |
| 本轮 AI | `confirm_llm=false`，AI 阶段 skipped |
| OCR / VLM | 均关闭 |

验收时直接查询数据库确认：`esg_agent_demo` 有 5 份报告，`esg_agent` 有 61 份报告，两库 migration 均为 `0011_ai_suggestions`。这些数量只用于证明环境隔离，不属于长期产品断言。

### 正式库与 demo 冻结基线一致性审计

2026-07-25 对两库执行只读逐项审计：

| 项目 | 正式库 | Demo 库 |
| --- | --- | --- |
| 对比 run | `run-48c73aa456f04a198f0fc4729e539a01` | `run-92bf75b11eb042dab6cb689311634fe1` |
| run 来源 | Envision v3 regeneration | 实际产品上传与分析 |
| 内部范围 | `577/499/78/0` | `577/499/78/0` |
| 成功 / 失败 | `499/0` | `499/0` |
| 引擎 / 风险规则 | `rules-v1 / risk-v2.1` | `rules-v1 / risk-v2.1` |

两边 499 个 `requirement_id` 完全一致。逐项规范化比较 task 结构、规则 verdict、判断依据、缺失项、证据页、证据片段、证据质量、OCR/VLM 标志和最新 risk-v2.1 维度，差异数为 0；规范化 SHA256 相同：

```text
66a7edc337d44cebc662a5e5c3cf60a7ce6a3426da8efb5dfc5ea7ad8561b29a
```

该结论证明正式库 regeneration 基线与 demo 产品 run 的确定性计算结果一致。两库的报告数量、历史 run、人工复核和输出记录继续隔离；历史 v1/v2 结果不会自动改写。

## 5. 自动门禁

| 门禁 | 结果 |
| --- | --- |
| 后端全量测试 | 651 passed |
| 前端测试 | 28 个测试文件，103 passed |
| 前端 typecheck | 通过 |
| 前端 production build | 通过 |
| Envision v3 范围 | `577/499/78/0` |
| 唯一独立 requirement | 499 |
| `global_fallback` | 0 |
| 新增 false disclosed | 0 |
| 新增 wrong source page | 0 |
| 最终裁决 pending | 0 |
| Envision audit | `ok=true`，0 error，0 warning |

v3 gate 在未启用 LLM、OCR 或 VLM 的条件下运行。运行产物位于 `backend/data/runtime/evaluations/envision_2024/`，相对路径、SHA256、大小和用途登记在 `backend/data/manifests/assets_manifest.json`。

## 6. 产品主流程验收

| 验收点 | 结果 |
| --- | --- |
| 重复上传 | 后端 `reject` 返回 `409 duplicate_report` 和最新报告；`create_new` 创建新 report 并保留历史 |
| metadata | 企业识别为“远景能源有限公司”；年度 2024、语言 zh-CN、页数 78 |
| AI 授权 | 默认关闭；本轮没有外部模型调用 |
| 分析进度 | 八阶段按真实工作量完成；终态 100%，无持续转圈 |
| Dashboard | 对外统一显示“核查范围 577 项”，并展示披露结论、复核优先级和适用性分布 |
| 优先级 | 本轮独立判断项为高 9、中 54、低 436；数量由规则动态产生 |
| 适用性 | 本轮待企业确认 309 项 |
| 完整核查表 | 首尾分页均通过，范围为 577 项 |
| 上下文项 | 显示“已纳入相关判断”，无伪 verdict、优先级、复核状态或证据 |
| 三栏复核 | 点击独立项不触发 PDF 下载；规则、AI、人工三层分离；实测保存 1 条追加式人工 snapshot，高优先级进度由 0/9 更新为 1/9 |
| PDF 证据 | 右栏按页显示 PNG 预览，已验证第 77 页，原始 PDF 保持不变 |
| 整改任务 | 实测为 `GRI 2-5-a` 创建 1 条高优先级整改任务，列表显示 requirement、负责人和可更新状态 |
| 草稿输出 | `export-cbe69421eda24bb4b67ca7fa2b9df3b9` 生成 3 个文件，记录高优先级复核 1/9、剩余 8 条 |
| 输出范围 | XLSX 577 行；HTML 显示“共 577 项” |
| 输出声明 | 包含 AI 辅助免责声明和实际人工复核范围，没有“577 项均已人工确认”表述 |

Chrome 扩展无法自动向本机原生文件选择器赋值，返回 `Not allowed`；Computer Use 也因无法可靠识别本地页面 URL 而停止。用户已在普通 Chrome 手动选择并提交相同 PDF，真实请求进入重复报告分支。`409 duplicate_report`、查看已有报告和重新上传并分析两条逻辑继续由后端真实 API 与前端自动测试覆盖。该限制影响浏览器自动化，不影响产品上传能力。

## 7. AI 辅助基线边界

此前 225 条真实 DeepSeek 评估继续保留为工程基线：可比项一致 162/224（72.32%），适用性例外 1；guardrail 后 false disclosed、证据 ID 越界、可比错页、schema 失败和模型失败均为 0。

该基线用于证明产品能够受控调用模型、保存可追溯建议并阻止越界建议直接成为最终结论。它不等同于 225 条 ESG 专家认证，也不代表本轮 577 项分析调用了外部模型。本轮产品 run 明确关闭 AI。

## 8. 问题记录

| 编号 | 严重程度 | 复现与影响 | 修复 | 状态 |
| --- | --- | --- | --- | --- |
| MVP-AI-001 | P1 | 采纳 AI 后，规则区一度读取人工 snapshot 字段，破坏三层权威边界 | API 提供不可变 `system_*` 字段，前端规则区只读规则结果 | 已修复，提交 `4abdac9` |
| MVP-PDF-001 | P1 | 三栏工作台的 PDF iframe 在受控浏览器中持续空白，证据无法内联查看 | 新增只读页图接口，前端以 `<img>` 按页加载，保留加载和错误状态 | 已修复，提交 `3541b14`；第 77 页实测通过 |
| MVP-COPY-001 | P2 | 首页曾使用“577 条 GRI 要求”，与统一“577 项”口径不一致 | 首页改为“577 项 GRI 要求” | 已修复，提交 `3541b14` |
| ENV-001 | 环境限制 | Chrome 扩展不能自动控制本机文件选择器，Computer Use 无法可靠识别本地页面 URL | 用户在普通 Chrome 完成真实重复上传；使用真实 API 与前端自动测试补足双路径验证 | 已记录，不列为产品缺陷 |

当前无未解决 P0/P1 产品问题。

## 9. 已知限制

- `actions_xlsx` 尚未按整改任务字段生成完整任务清单；
- 通用 verdict 批量复核、独立 reopen、report 级审计和单 export 下载仍为规划接口；
- 旧 `review_decisions`、旧 API 和旧页面仍有调用者，继续保留；
- 225 条 AI 基线属于工程验证；
- 企业条件适用性可能需要企业确认；
- 当前冻结主线只承诺 Envision 2024 中文报告；
- Goldwind 作为次级泛化证据，当前不阻塞；
- 项目只承诺本地 MVP 验证，不承诺企业部署能力。

## 10. 冻结后的变更控制

前端布局、中文文案、演示引导和不改变接口语义的 P0/P1 修复可在冻结状态下继续。以下变化必须解除冻结并重跑后端全量、前端 test/typecheck/build 和 Envision v3 gate：

- 577 清单或 6 条复合结构裁决；
- 证据路由、证据合同或 verdict 规则；
- `risk-v2.1`；
- DeepSeek 模型、Prompt、调用范围或 guardrail；
- 数据库 schema 或 API 字段语义；
- 规则、AI、人工的权威关系；
- 正式输出门禁。
