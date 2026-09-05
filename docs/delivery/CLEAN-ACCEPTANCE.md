# ESG-Agent 1.5 等价干净环境验收

## 1. 当前状态

Task 1–10 只形成源码与发布 ZIP 候选。等价干净环境验收属于 Task 11，当前明确延期；在本清单完整执行并留存旁路证据前，不得把 1.5 标记为正式发布，不创建 `v1.5` tag，不发布托管平台 Release。

本机已有依赖、数据库、`.venv`、`node_modules` 和 runtime 的验证只能证明本地可用，不能代替本清单。

## 2. 隔离要求

- 输入只允许最终 ZIP 和配套 SHA256SUMS 文件。
- 使用独立解压目录、Compose project、PostgreSQL volume、数据库名和未占用端口。
- 不复制开发工作区 `.env`、依赖目录、数据库或 runtime。
- 验收前记录 Docker Desktop、Engine、Compose、Windows PowerShell、.NET Framework、uv、Node 和浏览器版本。
- 端口已监听或位于 Windows excluded range 时停止，由验收人选新端口。
- 清理验收环境不得使用 `docker compose down -v`，不得触碰现有 volume。

## 3. 验收步骤

1. 核对 ZIP 外部 SHA-256。
2. 解压后核对 `release-manifest.json` 的 commit、版本与每个 payload checksum。
3. 确认 `.git/`、真实 `.env`、密钥、数据库 dump、非授权 PDF、runtime payload、`首页.png`、额外 EXE/MSI/setup 均不存在。
4. 运行 `Test-Preflight.ps1 -StrictDelivery`；未初始化提示可以存在，基础工具、版本、Docker 和端口错误不能存在。
5. 运行 `Initialize-Environment.ps1`，确认只创建新的 demo 配置、volume 和数据库。
6. 核对空库 migration 从 base 到 `0012_chunk_embeddings`。
7. 用 `ESG-Agent.exe --no-browser` 启动，再运行 `Test-EsgAgent.ps1`。
8. 访问前端并执行合成演示报告的真实 HTTP 闭环。
9. 核对上传、metadata、分析、577 项范围、499 个独立判断、78 个上下文项、0 method pending、人工复核、整改、草稿、逐文件下载和审计时间线。
10. 确认 AI 建议为 0、未创建正式输出、未调用外部模型、embedding、OCR 或 VLM。
11. 运行后端全量测试、Ruff、前端 test、lint、typecheck、production build 和必要的资产门禁。
12. 生成数据库备份，在新的目标数据库执行恢复并核对 revision、报告计数和 checksum。
13. 停止前后端，确认端口释放；停止数据库时确认 volume 保留。

## 4. 自动门禁期望

| 门禁 | 期望 |
| --- | --- |
| migration | 空库 upgrade 至 `0012_chunk_embeddings`；test 库 round-trip 可恢复至 head |
| 产品结构 | `577/499/78/0` |
| 外部能力 | LLM、embedding、OCR、VLM 全部关闭且零调用 |
| 合成演示 | 上传到草稿下载和审计全链路通过；不生成正式输出 |
| 授权资产 | 发布包环境允许 Goldwind 单项以固定原因跳过；维护者门禁必须安装并核对 SHA-256，且不允许跳过 |
| 前端 | test、lint、typecheck、production build 通过；只接受已登记既有 warning |
| 后端 | 全量 pytest 与 Ruff 通过 |
| 归档 | 连续两次构建 ZIP SHA-256 相同；内外 manifest 一致 |
| 备份恢复 | 新目标库恢复成功，原库和原 volume 未改变 |

## 5. 必须留存的旁路证明

- 最终 commit 与候选 ZIP SHA-256；
- `release-manifest.json` 核验结果；
- 版本与 preflight JSON；
- Compose project、volume、容器、数据库名和实际端口；
- migration、health、演示闭环、自动门禁和恢复结果；
- 外部能力关闭证据；
- 未授权资产与密钥扫描结果；
- 清理后端口和 volume 状态；
- 失败、重试与人工决策记录。

## 6. 通过与终止条件

只有全部步骤通过、文档与最终 commit/归档一致，并由用户确认交付形式后，才能形成正式验收结论。任一校验不一致、volume 身份不明、密钥或非公开数据出现、默认外部调用发生时立即终止，不创建 tag 或 Release。
