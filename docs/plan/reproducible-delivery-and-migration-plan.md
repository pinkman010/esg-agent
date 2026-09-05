# ESG-Agent 1.5 可复现交付与迁移实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**目标：** 将当前冻结的单报告 ESG 产品基线交付为可追溯、可安装、可迁移、可验证的 1.5 版本；先提供本机双击启动的 C# 轻量入口，最终仍由等价干净环境证明授权接收方能够恢复同一套产品行为。

**执行状态：** 用户已授权连续执行 Task 1–10，并授权在验证通过后 fast-forward 合并与清理隔离 worktree/已合并分支；Task 11 等价干净环境验收继续延期。本轮不得创建 tag、发布 release 或 push。Task 10 完成后必须从同一提交重建候选 ZIP、旁路证明和 checksum，候选状态不得写成最终验收通过。

**架构：** 采用两层交付。发布压缩包是接收方入口，包含源码、锁文件、配置模板、PowerShell 运维脚本、C# 轻量启动器、合法合成演示报告、文档和校验清单；Git 仓库、固定提交和 `v1.5` tag 构成审计底座。启动器只调用同一套 PowerShell 生命周期脚本并打开本机网页，Docker Compose 本阶段只管理固定版本的 PostgreSQL/pgvector，后端、前端和可选 OCR 工具继续在 Windows 本机运行。

**技术栈：** Windows 11 x64、Windows PowerShell 5.1、可选 PowerShell 7、.NET Framework 4.8.1、C#、Python 3.11、uv、Node.js、pnpm、PostgreSQL 16、pgvector、FastAPI、Alembic、Next.js、Docker Compose；OCRmyPDF、Ghostscript 和 Tesseract 保持默认关闭的可选能力。

---

## 1. 交付目标、第一性原理与交付结论

可复现交付必须同时满足四个独立契约：

1. **身份契约**：接收方能够核对源码 commit、公开版本、锁文件、交付文件和 SHA-256。
2. **恢复契约**：接收方能够从空数据库和空运行目录安装、迁移、启动、停止、备份及恢复。
3. **行为契约**：接收方能够在无真实密钥、无外部模型调用、无 OCR、无 embedding 的条件下完成最小产品闭环，并核对 `577/499/78/0`。
4. **操作契约**：完成初始化的本机或交付目录能够通过双击入口幂等启动服务，health 通过后打开网页，并能安全查询状态或停止当前目录的服务。

本阶段采用以下确定方案：

| 层级 | 形式 | 定位 | 本阶段结论 |
| --- | --- | --- | --- |
| 第一层 | Git 仓库 + 固定 commit + `v1.5` tag | 源码追溯和后续维护 | 必须提供 |
| 第二层 | `esg-agent-1.5-windows-x64.zip` + SHA-256 | 授权接收方的主要安装入口 | 主要交付物 |
| 便捷入口 | ZIP 根目录 `ESG-Agent.exe` | 已完成初始化环境的一键启动、状态和停止 | 本阶段提供 |
| 数据库依赖 | 固定镜像的 PostgreSQL/pgvector Compose | 降低 Windows 数据库安装差异 | 本阶段保留 |
| 全栈 Docker | PostgreSQL、后端、前端和 OCR 全部容器化 | 跨平台或集中部署 | 本阶段延期 |

延期全栈 Docker 的依据：当前后端、前端均按 Windows 本机工具链验收；OCRmyPDF、Ghostscript、Tesseract 中文语言包、PDF 页面渲染、Windows 挂载路径和离线镜像会显著扩大交付面。只有出现跨平台部署、统一 OCR 容器或离线镜像的明确需求时，才重新立项评估。

轻量启动器不承担依赖安装、Docker Desktop 安装或升级、数据库初始化、schema migration、自动更新和卸载。当前先完成本机一键启动验收；干净环境验收只调整执行时点，不从最终终止条件删除。若只完成本地启动器，阶段状态仍为“实施中”。

## 2. 基线、版本与支持范围

### 2.1 源码基线

- 本计划最初审计起点为 commit `77c8f61a10a734c2994ffda3997b81f51292cc10`；Docker 恢复记录完成后，本轮实施起点更新为 commit `7f788e5010e04b12cb3c2a19ecd990d95399a8b8`。
- `main`、`origin/main` 和 `origin/HEAD` 在本轮实施开始时均指向 `7f788e5010e04b12cb3c2a19ecd990d95399a8b8`。
- 工作区审计时只有未跟踪文件 `首页.png`；该文件不得修改、删除、加入索引或进入归档。
- 最终交付 commit 将由归档工具在构建时读取 `git rev-parse HEAD` 并写入版本清单，不在计划中预填尚未产生的提交号。
- 现有 `v1.3.1` tag 保留为历史记录，不移动、不覆盖、不删除。
- 完整验收通过并获得用户单独批准后，才允许创建 `v1.5` tag；本计划实施过程不自动创建 tag、release 或 push。

### 2.2 版本策略

- 对外版本只保留一位小数，本次公开版本为 **1.5**。
- Git tag、归档名、交付文档和产品发布说明统一使用 `v1.5` 或 `1.5`。
- npm 与 Python 包元数据使用 `1.5.0`，满足工具格式要求；OpenAPI `info.version` 同步为 `1.5.0`。
- 后续兼容性交付可使用 `1.6`、`1.7`；只有产品边界、数据模型或部署架构发生重大变化时才使用 `2.0`。

### 2.3 已验证工具链与接收方目标

以下本机版本来自只读核验。Docker 行同时区分 2026-09-03 故障恢复后的实测环境和接收方目标环境，不能把建议版本写成已经完成的本机验证：

| 能力 | 本机恢复验证版本 | 1.5 交付口径 |
| --- | --- | --- |
| Windows | Windows 11 x64，10.0.26200 | 1.5 首个正式支持环境；Windows 10 暂不承诺 |
| Windows PowerShell | 5.1.26100.9168 | 启动器与接收方脚本最低运行环境；随当前 Windows 提供 |
| PowerShell 7 | 7.6.4 | 维护者附加验证环境；当前来自 Codex 运行目录，不能当作系统级接收方依赖 |
| .NET Framework | 4.8.1，Release 533509 | 轻量启动器运行环境；接收方接受 Release key `>=533320` |
| C# 编译器 | 4.8.9221.0，SHA-256 `46809206887326D2D24DB1EFF1F3064DE972C3451ABE766B49111450A5E08E00` | 仅用于维护者生成本地启动器；从 `%WINDIR%` 相对解析 |
| Python | 3.11.14 | 项目只支持 Python 3.11 |
| uv | 0.9.28 | 使用 `backend/uv.lock` 冻结 Python 依赖 |
| Node.js | 24.15.0 | 使用 `.node-version` 固定 |
| Corepack | 0.34.6 | 激活固定 pnpm |
| pnpm | 11.19.0 | 使用 `frontend/pnpm-lock.yaml` 冻结前端依赖 |
| Docker Desktop | 4.80.0 | 恢复来源环境；接收方建议使用 4.89.0 或更高稳定版 |
| Docker Engine | 29.6.1 | 记录 Desktop 4.80.0 当前实际组件；接收方记录其 Desktop 实际捆绑版本 |
| Docker Compose | 5.1.4 | 恢复来源环境；Desktop 4.89.0 官方捆绑 Compose 5.5.0 |
| PostgreSQL | 16.14 | 通过固定 pgvector 镜像提供 |
| pgvector | 0.8.4 | migration `0012_chunk_embeddings` 所需扩展 |
| OCRmyPDF | 17.8.0 | 可选，默认关闭 |
| Ghostscript | 10.07.1 | 可选，默认关闭 |
| Tesseract | 5.5.0.20241111 | 可选，默认关闭；语言包为 `chi_sim`、`eng`、`osd` |
| Poppler `pdftoppm` | 26.02.0 | 辅助检查工具，不属于默认解析链路 |
| LibreOffice | 26.2.1.2 | 辅助文档检查工具，不属于服务启动依赖 |
| Chrome | 151.0.7922.170 | 已验证浏览器版本 |
| Edge | 146.0.3856.109 | 已验证浏览器版本 |

PostgreSQL 镜像先固定为审计机器已验证的 `pgvector/pgvector:pg16@sha256:ad2e18408bf447f62092a8a5259e7df10505c5a0360bd1a1853ac8b8b0763da2`。实施时必须在干净环境重新拉取并核对 PostgreSQL 16.14 与 pgvector 0.8.4；平台摘要不匹配时停止发布，不改回浮动 tag。

.NET Framework preflight 按 [Microsoft 的 Release key 判断规则](https://learn.microsoft.com/dotnet/framework/migration-guide/how-to-determine-which-versions-are-installed) 使用 `Release >= 533320` 接受 4.8.1 或更高适用版本，不把当前 Windows 的 `533509` 错写为所有接收方必须完全相同的值。

Docker Desktop 4.80.0 已实际恢复 PostgreSQL volume、demo 数据库和应用服务，但该版本曾在异常退出后受到残留 socket 影响。[Docker Desktop 4.89.0 release notes](https://docs.docker.com/desktop/release-notes/) 明确记录了 stuck socket 启动失败修复，因此将 4.89.0 作为接收方建议下限；最终支持声明仍以干净环境验收结果为准。`delivery/toolchain-lock.json` 分别保存 `recovery_source` 与 `delivery_target`，禁止继续沿用审计前的 Compose 5.3.0 记录。

Docker Desktop 升级不纳入自动化脚本。对保有业务数据的开发机升级前，必须另行取得用户批准，完成数据库逻辑备份、运行文件备份、volume 身份与报告计数记录，并保留可回退的旧版本交付目录；也可以在另一台干净机器或等价隔离环境完成最终验收，避免为交付验证扰动已恢复的本机数据。

本机 .NET Framework 编译器不支持 `/deterministic`，不能承诺相同源码每次重编得到相同 EXE 字节。当前方案把核验后的 `ESG-Agent.exe`、C# 源码、编译器指纹和 launcher manifest 成套提交；归档构建器只复制固定 commit 中的已核验 EXE，不在归档过程中重编，因此同一 commit 的 ZIP 仍可保持字节级可重复。启动器属于可选便捷层；PowerShell 脚本仍是可读、可重建、可直接运行的生命周期入口。

浏览器采用“已验证版本或更高稳定版”的支持口径。每次验收记录实际浏览器完整版本，不把浏览器安装包放入发布归档。

所有交付脚本必须同时通过 Windows PowerShell 5.1 和维护者 PowerShell 7 语法及行为测试，不使用 `ForEach-Object -Parallel`、空值合并运算符、三元运算符、`ConvertFrom-Json -AsHashtable` 等 5.1 不支持的语法或参数。启动器固定调用 Windows 目录中的系统 `powershell.exe`，不依赖 Codex 进程注入的 PATH。

## 3. 数据、密钥与运行边界

### 3.1 默认关闭项

发布包和合成演示运行固定满足：

```text
APP_ENV=demo
OCR_ENABLED=false
EMBEDDING_ENABLED=false
OPENAI_COMPATIBLE_API_KEY=
EMBEDDING_API_KEY=
confirm_llm=false
enable_ocr=false
```

- DeepSeek 只有请求显式传入 `confirm_llm=true` 才可能调用；1.5 交付验收始终传入 `false`。
- OCR 需要 `OCR_ENABLED=true` 与请求 `enable_ocr=true` 双重授权；1.5 交付验收两者均为 `false`。
- embedding 保持 `EMBEDDING_ENABLED=false`，交付脚本不执行 embedding 工具。
- VLM 尚未实现，交付文档不得暗示已具备该能力。
- 依赖安装需要访问 Python/npm/Docker 软件源；这类安装网络访问与运行时外部模型调用分开记录。

### 3.2 环境划分

| 环境 | 数据库 | 运行目录 | 用途 |
| --- | --- | --- | --- |
| demo | `esg_agent_demo` | `backend/data/runtime/demo/` | 接收方演示和干净验收，可重建 |
| main | `esg_agent` | `backend/data/runtime/` | 授权开发、回归和长期数据；不声明为生产平台 |
| test | `esg_agent_test` 或唯一临时库 | `tmp/` | 自动测试和 migration round-trip |

`main` 只是当前开发/回归环境名。1.5 不承诺公网生产部署、高可用、SSO、多租户、集中密钥管理或企业运维平台。

### 3.3 资产分类

1. **发布包内资产**：已跟踪源码、GRI 运行时 manifest、前端静态图片、合成演示报告及其来源和 SHA-256。
2. **授权维护者本地资产**：Envision、Goldwind、GRI 原始标准、人工复核工作簿和语义回归基线。继续受 `backend/data/manifests/assets_manifest.json` 管理，不进入公开发布包。
3. **运行时数据**：上传副本、派生 OCR PDF、导出、日志、数据库 dump 和测试输出。源码发布包默认排除；本地备份可在操作员明确执行后单独生成。
4. **禁止资产**：真实 `.env`、API key、数据库密码、非公开模型响应、未授权报告、当前本机数据库和 `首页.png`。

当前资产 manifest 的 49 项本机目标中，8 项由 Git 跟踪，41 项只存在于维护者本机。归档验收必须以发布资产策略为准，不能把“本机存在”等同于“允许交付”。

## 4. 计划文件结构

### 4.1 新建文件

- `.python-version`：固定 Python 3.11.14。
- `.node-version`：固定 Node.js 24.15.0。
- `delivery/toolchain-lock.json`：保存系统依赖、浏览器验收版本和 PostgreSQL 镜像摘要。
- `delivery/release-policy.json`：保存归档允许项、拒绝项、版本和命名规则。
- `delivery/launcher/EsgAgentLauncher.cs`：轻量 Windows 启动器源码，只负责固定参数映射、进度反馈和错误呈现。
- `delivery/launcher/EsgAgentLauncher.exe.manifest`：声明 `asInvoker`、Windows 兼容性和无需管理员权限。
- `delivery/launcher/launcher-manifest.json`：保存启动器源码、应用 manifest、编译器和 EXE 的 SHA-256 及编译参数。
- `delivery/demo/demo-report-source.json`：保存虚构、脱敏、可重复生成的演示报告正文和固定元数据。
- `backend/src/tools/generate_demo_report.py`：确定性生成演示 PDF。
- `backend/src/tools/build_release_archive.py`：从固定 commit 创建归档、文件 manifest 和 SHA-256。
- `backend/src/tools/verify_delivery_flow.py`：通过真实 HTTP API执行最小产品闭环。
- `backend/src/services/runtime_paths.py`：统一数据库路径序列化和恢复后的路径解析。
- `backend/src/tools/normalize_runtime_paths.py`：安全扫描并转换旧绝对运行路径。
- `backend/tests/delivery/test_delivery_contracts.py`：验证版本、环境模板、Compose 和发布策略。
- `backend/tests/delivery/test_launcher_contract.py`：验证启动器参数、相对路径、脚本映射、退出码、manifest 和二进制哈希。
- `backend/tests/tools/test_generate_demo_report.py`：验证演示 PDF 的确定性、页数和来源声明。
- `backend/tests/tools/test_build_release_archive.py`：验证归档拒绝项、排序和 checksum。
- `backend/tests/tools/test_verify_delivery_flow.py`：验证 HTTP 闭环客户端状态机和失败输出。
- `backend/tests/services/test_runtime_paths.py`：验证相对路径和旧绝对路径兼容。
- `backend/tests/tools/test_normalize_runtime_paths.py`：验证 dry-run、哈希匹配和写入门禁。
- `backend/tests/db/test_migration_roundtrip.py`：在唯一临时数据库验证空库 upgrade、`0012` downgrade/upgrade 和清理。
- `scripts/delivery/Delivery.Common.ps1`：PowerShell 公共路径、版本、日志、端口和安全函数。
- `scripts/delivery/Test-Preflight.ps1`：只读核验工具链、配置和可选 OCR 能力。
- `scripts/delivery/Initialize-Environment.ps1`：生成本地配置、安装锁定依赖并构建前端。
- `scripts/delivery/Initialize-Database.ps1`：启动 PostgreSQL、创建隔离数据库并迁移到 head。
- `scripts/delivery/Build-Launcher.ps1`：在临时目录编译、冒烟并经显式开关更新已跟踪启动器及 manifest。
- `scripts/delivery/Start-EsgAgent.ps1`：以非开发模式启动后端和前端并记录 PID/日志。
- `scripts/delivery/Stop-EsgAgent.ps1`：只停止当前交付目录记录的进程，可选停止 PostgreSQL。
- `scripts/delivery/Test-EsgAgent.ps1`：核对数据库 revision、后端 health、前端 HTTP 和默认关闭项。
- `scripts/delivery/New-EsgAgentBackup.ps1`：生成数据库与授权运行文件的本地备份及 checksum。
- `scripts/delivery/Restore-EsgAgentBackup.ps1`：在显式确认后恢复到隔离目标并核对 checksum。
- `scripts/delivery/Invoke-CleanAcceptance.ps1`：在新目录、新数据库和新 Compose project 中编排完整验收。
- `docs/delivery/INSTALL-WINDOWS.md`：接收方安装、初始化、启动和首次验收说明。
- `docs/delivery/OPERATIONS.md`：停止、日志、备份、恢复、升级、回滚和故障处理说明。
- `docs/delivery/CLEAN-ACCEPTANCE.md`：自动与人工验收清单。
- `docs/delivery/DOCKER-EVALUATION.md`：方案 A/B/C 比较及延期条件。
- `docs/product/v1.5-reproducible-delivery-acceptance.md`：最终事实记录；实施前只创建结构，最终验收后填写实际命令结果。
- `ESG-Agent.exe`：位于仓库和 ZIP 根目录的已核验启动器二进制；不含密钥、配置或业务数据。

以下文件由验收工具生成到被忽略的 `tmp/release/`，不加入 Git：

- `esg-agent-1.5-windows-x64.zip`：最终发布归档。
- `esg-agent-1.5-attestation.json`：最终 commit、归档 SHA-256、工具版本和验收结果的旁路证明。
- `esg-agent-1.5-SHA256SUMS.txt`：最终 ZIP 与旁路证明的校验清单。

### 4.2 修改文件

- `.env.example`：改为无密码的交付配置模板，默认 demo 和全部外部能力关闭。
- `backend/.env.example`：补齐 OCR、embedding、Ghostscript、timeout 和当前 Prompt 版本，但 API key 保持空。
- `backend/.env.demo.example`：与 demo 安全约束和全部默认关闭项一致。
- `frontend/.env.example`：保留本机 API 地址并记录可配置端口边界。
- `.gitignore`：明确排除本地交付归档、启动器临时构建目录、进程文件、日志、备份和生成演示 PDF，只跟踪演示源文件与已核验的根目录启动器。
- `docker-compose.yml`：固定镜像摘要、移除硬编码密码、增加端口变量和 PostgreSQL healthcheck。
- `backend/pyproject.toml`、`backend/uv.lock`：固定项目元数据为 `1.5.0`，保持依赖锁一致。
- `frontend/package.json`、`frontend/pnpm-lock.yaml`：固定项目元数据为 `1.5.0`，增加 `packageManager` 和 `engines`。
- `backend/src/main.py`：只把 OpenAPI 版本改为 `1.5.0`，不改 API 行为。
- `backend/src/services/document_store.py`、`backend/src/api/routes/reports.py`、`backend/src/services/analysis_runner.py`：改用统一的可迁移路径契约。
- `backend/tests/api/test_phase17_product_closure_e2e.py`：缺少 Goldwind 原始 PDF 时明确标记为授权资产跳过；授权维护者门禁仍要求该测试实际执行。
- `README.md`、`docs/DESIGN.md`、`docs/DEVELOPMENT.md`、`docs/ASSETS.md`：更新 1.5 交付入口、版本策略、运行命令和资产边界，不改历史验收文件中的历史事实。

### 4.3 明确不修改

- `backend/data/manifests/gri_requirement_checklist_v3.json`
- `backend/data/manifests/gri_requirement_structure_v3.json`
- GRI adapter、披露规则、证据规则、risk-v2.1、AI Prompt、候选筛选、人工快照和正式导出语义
- 现有 Alembic schema revision；预计 head 继续为 `0012_chunk_embeddings`
- Envision、Goldwind、GRI 原始标准和人工复核来源资产
- `首页.png`

## 5. C# 轻量启动器设计

### 5.1 定位与范围

启动器解决“初始化完成后如何低门槛使用”的问题，不承担“如何把干净机器变成可运行环境”。用户双击仓库或 ZIP 根目录的 `ESG-Agent.exe` 后，应看到简短启动进度；数据库、后端和前端 health 全部通过后，系统使用默认浏览器打开本机前端地址。

`ESG-Agent.exe` 是可选便捷入口。任何启动器故障都不能阻断维护者直接运行 `Start-EsgAgent.ps1`、`Stop-EsgAgent.ps1` 和 `Test-EsgAgent.ps1`，也不能把生命周期逻辑复制到不可审计的二进制中。

当前启动器明确不包含以下能力：

- `setup.exe`、依赖下载、Docker Desktop 安装或升级、WSL 配置、卸载程序；
- 数据库创建、Alembic upgrade/downgrade、volume 创建、备份恢复；
- 托盘常驻、自动更新、静默遥测、管理员提权、Windows 服务注册；
- DeepSeek、SiliconFlow、embedding、OCR、VLM 的启用或授权。

### 5.2 组件边界

| 组件 | 单一职责 | 允许依赖 |
| --- | --- | --- |
| `ESG-Agent.exe` | 校验固定参数、显示进度、调用脚本、呈现结果 | `.NET Framework 4.8.1`、Windows PowerShell 5.1、相对目录中的交付脚本 |
| `Start-EsgAgent.ps1` | 幂等启动 PostgreSQL、后端、前端，完成 health 并可打开浏览器 | 已初始化配置、Docker、uv、pnpm |
| `Stop-EsgAgent.ps1` | 核对 PID 身份后停止当前目录的应用进程 | 当前目录的进程清单 |
| `Test-EsgAgent.ps1` | 只读输出数据库、后端、前端和默认关闭项状态 | 当前目录配置和服务 |
| `Build-Launcher.ps1` | 核验编译器、在临时目录编译、验证后更新二进制与 manifest | 维护者本机编译器；接收方不需要执行 |

启动器以 `AppContext.BaseDirectory` 作为交付根目录，只接受固定动作，不接收脚本路径、数据库 URL、命令片段或任意透传参数。它从 `Environment.SpecialFolder.Windows` 推导系统 Windows PowerShell 路径，找不到时返回 `POWERSHELL_NOT_FOUND`；不读取 PATH 中可能由开发工具临时注入的 `pwsh`。

### 5.3 用户动作与脚本映射

| 用户动作 | 启动器参数 | 唯一脚本调用 | 成功结果 |
| --- | --- | --- | --- |
| 双击 | 无 | `Start-EsgAgent.ps1 -OpenBrowser` | health 通过后打开 `${FRONTEND_URL}` |
| 只启动 | `--no-browser` | `Start-EsgAgent.ps1` | 服务健康，浏览器不打开 |
| 查看状态 | `--status` | `Test-EsgAgent.ps1` | 显示结构化状态摘要，不修改服务 |
| 停止应用 | `--stop` | `Stop-EsgAgent.ps1` | 只停止当前目录记录的前后端进程，默认保留 PostgreSQL |

无参数以外只允许单独使用 `--no-browser`、`--status` 或 `--stop`。未知参数、重复动作或动作组合返回退出码 `64` 和 `INVALID_ARGUMENTS`，不启动 PowerShell。C# 端固定调用：

```text
powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File scripts/delivery/Start-EsgAgent.ps1 -OpenBrowser
```

`Bypass` 只应用于该子进程，脚本路径由启动器基目录与固定相对路径组合后执行完整路径检查；参数由枚举映射生成，不拼接用户输入。企业策略禁止执行时返回 `POWERSHELL_POLICY_BLOCKED`，不尝试修改机器策略。

### 5.4 启动状态机

默认双击流程固定为：

```text
解析 EXE 基目录
  → 校验系统 Windows PowerShell 与 scripts/delivery
  → 显示“正在检查并启动服务”窗口
  → Start-EsgAgent.ps1 检查现有 health 和启动锁
  → 已健康：直接打开浏览器
  → 启动中：等待同一目录的既有启动完成
  → 未启动：启动已有 PostgreSQL volume、后端和前端
  → 等待综合 health
  → 成功：打开一次浏览器并退出启动器
  → 失败：显示稳定错误码与相对日志位置
```

`Start-EsgAgent.ps1` 使用当前交付目录专属锁，锁中记录 PID、进程启动时间和根目录哈希。发现同目录正在启动时不创建第二组进程，而是在统一超时内轮询 health；发现陈旧锁时先验证 PID 已不存在，再以原子方式替换。启动 PostgreSQL 只允许对已初始化且可见的目标 volume 执行 `docker compose up -d postgres`；volume 缺失时返回 `DOCKER_VOLUME_MISSING`，不能静默创建同名空 volume。

启动器成功后自行退出，后端和前端由生命周期脚本管理。浏览器地址只读取健康检查确认过的 `FRONTEND_URL`，协议限定为 `http`，主机限定为 `127.0.0.1` 或 `localhost`，禁止打开配置提供的外部 URL。

### 5.5 交互、日志与失败语义

启动窗口只包含产品名、当前阶段文本和不确定进度条，不增加设置页、账号、托盘菜单或产品功能。成功时自动关闭；失败时使用对话框显示一个稳定错误码、简短中文解释和“日志位于 `backend/data/runtime/logs/`”提示，不显示密码、API key、完整 `DATABASE_URL`、用户名目录或原始异常堆栈。

启动器保留子脚本退出码，并把自身错误固定为：

| 退出码 | 错误码 | 含义 |
| --- | --- | --- |
| `0` | `OK` | 动作完成 |
| `10` | `LAUNCHER_LAYOUT_INVALID` | EXE 与脚本目录关系不合法 |
| `11` | `POWERSHELL_NOT_FOUND` | Windows 系统 PowerShell 不可用 |
| `12` | `POWERSHELL_POLICY_BLOCKED` | 系统策略拒绝执行 |
| `13` | `LAUNCHER_PROCESS_FAILED` | 无法创建或等待脚本进程 |
| `64` | `INVALID_ARGUMENTS` | 参数不在固定白名单 |

脚本已有的稳定错误码通过 stdout/stderr 摘要返回；启动器只展示最后一个已脱敏错误码。详细诊断继续由 PowerShell 脚本写入相对日志目录。

### 5.6 构建、二进制审计与归档

`Build-Launcher.ps1` 从 `%WINDIR%` 推导 .NET Framework 编译器路径，核对文件版本 `4.8.9221.0` 与 SHA-256 `46809206887326D2D24DB1EFF1F3064DE972C3451ABE766B49111450A5E08E00`，然后使用以下固定语义编译：

```text
/nologo /target:winexe /platform:anycpu /optimize+ /checked+
/reference:System.dll /reference:System.Core.dll /reference:System.Windows.Forms.dll
/win32manifest:delivery/launcher/EsgAgentLauncher.exe.manifest
/out:tmp/launcher-build/ESG-Agent.exe
delivery/launcher/EsgAgentLauncher.cs
```

构建脚本先在 `tmp/launcher-build/` 生成候选文件，验证 PE 可加载、测试夹具动作、源码哈希和 manifest 后，只有显式传入 `-UpdateTrackedArtifact` 才原子替换根目录 `ESG-Agent.exe` 并重写 `delivery/launcher/launcher-manifest.json`。manifest 至少记录：schema version、目标框架、源码和应用 manifest 的 SHA-256、编译器文件版本与 SHA-256、完整编译参数、EXE 大小与 SHA-256。

C# 源码固定程序集版本 `1.5.0.0`、文件版本 `1.5.0.0` 和产品版本 `1.5`，与对外一位小数及内部三段式元数据策略一致。launcher manifest 同时记录 `public_version=1.5` 与 `package_version=1.5.0`，版本测试读取 PE metadata 和 JSON 双重核对。

当前编译器缺少确定性输出能力，因此二进制审计采用“固定已跟踪工件”策略：源码或应用 manifest 改变时，合约测试要求重新生成 EXE 和 launcher manifest；归档构建器只接受三者哈希一致的 tracked 状态，并把根目录 EXE 作为普通 payload 写入内部 release manifest。它不在每次归档时重新编译，连续两次从同一 commit 构建的 ZIP 仍必须具有相同 SHA-256。

启动器暂不做代码签名。当前本机使用由 checksum 和 Git commit 建立信任；对外扩大分发前必须单独决定签名证书、SmartScreen 和签名后 checksum 流程，不在本阶段自动购买证书或建设签名服务。

### 5.7 本地里程碑验收

启动器里程碑只在当前已初始化本机验证以下事实：

- 双击或无参数启动时，健康服务直接打开一次网页；停止服务时完成幂等启动后再打开网页。
- 并发启动不产生第二组后端或前端进程。
- `--status` 不改变进程、数据库、volume 或配置。
- `--stop` 只停止当前目录记录的前后端，默认保留 PostgreSQL 和全部数据。
- Docker daemon、volume、端口、前端构建或 health 异常均返回稳定错误码并指向相对日志目录。
- 测试夹具证明参数不能注入命令、不能跳转到外部 URL、不能引用交付根目录外的脚本。
- 启动前后 `OCR_ENABLED=false`、`EMBEDDING_ENABLED=false`，没有 DeepSeek、SiliconFlow、OCRmyPDF 或 VLM 调用。

通过这些检查只代表“本机一键启动里程碑”完成。发布包、空库 migration、备份恢复、checksum 和等价干净环境尚未通过时，不能宣布“可复现交付与迁移阶段”完成。

## 6. Task 1：冻结交付契约与版本工具链

**文件：**

- 新建：`.python-version`
- 新建：`.node-version`
- 新建：`delivery/toolchain-lock.json`
- 新建：`delivery/release-policy.json`
- 新建：`backend/tests/delivery/test_delivery_contracts.py`
- 修改：`frontend/package.json`

- [ ] **Step 1：先写交付契约测试**

测试必须读取真实文件并断言：

```python
def test_toolchain_lock_matches_supported_delivery_baseline():
    assert toolchain["python"] == "3.11.14"
    assert toolchain["uv"] == "0.9.28"
    assert toolchain["node"] == "24.15.0"
    assert toolchain["pnpm"] == "11.19.0"
    assert toolchain["windows_powershell"] == {
        "recovery_source": "5.1.26100.9168",
        "recipient_minimum": "5.1",
    }
    assert toolchain["powershell_7"]["version"] == "7.6.4"
    assert toolchain["powershell_7"]["recipient_required"] is False
    assert toolchain["dotnet_framework"] == {
        "recovery_release": 533509,
        "recipient_minimum_release": 533320,
    }
    assert toolchain["launcher_compiler"] == {
        "file_version": "4.8.9221.0",
        "sha256": "46809206887326D2D24DB1EFF1F3064DE972C3451ABE766B49111450A5E08E00",
        "deterministic": False,
        "maintainer_only": True,
    }
    assert toolchain["postgresql"] == "16.14"
    assert toolchain["pgvector"] == "0.8.4"
    assert toolchain["docker"]["recovery_source"] == {
        "desktop": "4.80.0",
        "engine": "29.6.1",
        "compose": "5.1.4",
    }
    assert toolchain["docker"]["delivery_target"] == {
        "desktop_minimum": "4.89.0",
        "compose_bundled": "5.5.0",
    }

def test_release_policy_uses_public_version_1_5():
    assert policy["public_version"] == "1.5"
    assert policy["package_version"] == "1.5.0"
    assert policy["archive_name"] == "esg-agent-1.5-windows-x64.zip"
    assert policy["git_tag"] == "v1.5"
```

同时断言 `.python-version`、`.node-version`、`packageManager` 和 `engines.node` 与 JSON 一致。

- [ ] **Step 2：运行测试并确认缺失文件导致失败**

```powershell
cd backend
uv run --no-sync pytest tests/delivery/test_delivery_contracts.py -q
```

预期：测试因工具链与发布策略文件尚不存在而失败；不得出现数据库写入或外部网络调用。

- [ ] **Step 3：写入固定工具链与发布策略**

`release-policy.json` 至少固定以下契约：

```json
{
  "public_version": "1.5",
  "package_version": "1.5.0",
  "git_tag": "v1.5",
  "archive_name": "esg-agent-1.5-windows-x64.zip",
  "source_mode": "git_archive",
  "launcher_artifact": "ESG-Agent.exe",
  "launcher_manifest": "delivery/launcher/launcher-manifest.json",
  "generated_demo_pdf": "demo/esg-agent-synthetic-report-2025.pdf",
  "checksum_algorithm": "SHA256"
}
```

拒绝规则必须覆盖真实 `.env`、`.git/`、`node_modules/`、`.venv/`、`.next/`、`tmp/`、`backend/data/runtime/`、数据库 dump、日志、未授权 PDF、模型响应和 `首页.png`。根目录只允许精确名称 `ESG-Agent.exe` 的启动器二进制；其他 `.exe`、`.msi` 和 `setup.exe` 均拒绝进入归档。

- [ ] **Step 4：固定前端包管理器声明**

在 `frontend/package.json` 增加：

```json
"packageManager": "pnpm@11.19.0",
"engines": {
  "node": "24.15.0"
}
```

此步骤先不改产品版本，避免尚未验收时提前对外声明 1.5。

- [ ] **Step 5：运行契约测试**

```powershell
cd backend
uv run --no-sync pytest tests/delivery/test_delivery_contracts.py -q
```

预期：全部通过。

- [ ] **Step 6：提交第一批**

```powershell
git add .python-version .node-version delivery frontend/package.json backend/tests/delivery/test_delivery_contracts.py
git commit -m "chore: pin reproducible delivery toolchain"
```

提交前确认 `git status --short` 仍显示 `首页.png` 为未跟踪且未暂存。

## 7. Task 2：收敛环境模板与 PostgreSQL Compose

**文件：**

- 修改：`.env.example`
- 修改：`backend/.env.example`
- 修改：`backend/.env.demo.example`
- 修改：`frontend/.env.example`
- 修改：`docker-compose.yml`
- 修改：`backend/tests/delivery/test_delivery_contracts.py`

- [ ] **Step 1：增加环境模板失败测试**

测试按 key 解析所有 example 文件，至少断言：

```python
assert root_env["APP_ENV"] == "demo"
assert root_env["OCR_ENABLED"] == "false"
assert root_env["EMBEDDING_ENABLED"] == "false"
assert root_env["POSTGRES_PORT"] == "5432"
assert root_env["BACKEND_PORT"] == "8000"
assert root_env["FRONTEND_PORT"] == "3000"
assert root_env["STARTUP_TIMEOUT_SECONDS"] == "180"
assert root_env["OPENAI_COMPATIBLE_API_KEY"] == ""
assert root_env["EMBEDDING_API_KEY"] == ""
assert backend_env["GHOSTSCRIPT_CMD"] == ""
assert backend_env["OCR_TIMEOUT_SECONDS"] == "300"
assert backend_env["LLM_PROMPT_VERSION"] == "deepseek-gri-assist-v1.2"
assert "esg_agent:esg_agent" not in all_example_text
assert "POSTGRES_PASSWORD=esg_agent" not in all_example_text
```

测试还必须断言 Compose 使用固定 digest、`${POSTGRES_PASSWORD:?` 和 `pg_isready`，不含硬编码密码。

- [ ] **Step 2：运行测试并确认当前配置漂移导致失败**

```powershell
cd backend
uv run --no-sync pytest tests/delivery/test_delivery_contracts.py -q
```

预期：因根模板缺少 OCR/embedding、demo Prompt 版本陈旧、Compose 使用浮动 tag 和硬编码密码而失败。

- [ ] **Step 3：统一模板字段和默认关闭状态**

根模板作为交付脚本输入，数据库密码和 `DATABASE_URL` 保持空值，由初始化脚本在本机生成。`POSTGRES_PORT=5432`、`BACKEND_PORT=8000`、`FRONTEND_PORT=3000` 是默认值，均允许在本地 `.env` 显式覆盖。`STARTUP_TIMEOUT_SECONDS=180` 由生命周期脚本读取，只接受 30–600 秒；启动器不解析 `.env`。backend 两个模板完整列出 `Settings` 支持的变量；真实密钥字段一律为空。

demo 模板固定 `APP_ENV=demo`、`OCR_ENABLED=false`、`EMBEDDING_ENABLED=false`，运行目录只能位于 `backend/data/runtime/demo/`。

`frontend/.env.example` 保留 `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`。初始化脚本必须在 `pnpm build` 前按实际 `BACKEND_PORT` 设置该值；当 Windows 排除 8000 时，操作员把本地 `BACKEND_PORT` 改为 8200，前端构建和 health 检查同步使用 8200，不修改受版本控制的默认模板。

- [ ] **Step 4：收敛 Compose**

Compose 必须满足：

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16@sha256:ad2e18408bf447f62092a8a5259e7df10505c5a0360bd1a1853ac8b8b0763da2
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-esg_agent_demo}
      POSTGRES_USER: ${POSTGRES_USER:-esg_agent}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?POSTGRES_PASSWORD must be set in the local .env}
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $$POSTGRES_USER -d $$POSTGRES_DB"]
      interval: 5s
      timeout: 5s
      retries: 20
```

端口使用 `${POSTGRES_PORT:-5432}:5432`；数据卷继续持久化，不自动删除。

- [ ] **Step 5：验证 Compose 展开结果不泄露密码**

在当前 shell 临时设置非生产测试值，只检查配置，不启动或重建当前数据库：

```powershell
$env:POSTGRES_PASSWORD="delivery-contract-test"
docker compose config --quiet
Remove-Item Env:POSTGRES_PASSWORD
```

预期：退出码为 0；终端和提交文件中不得出现真实密码。

- [ ] **Step 6：运行契约测试并提交**

```powershell
cd backend
uv run --no-sync pytest tests/delivery/test_delivery_contracts.py -q
cd ..
git add .env.example backend/.env.example backend/.env.demo.example frontend/.env.example docker-compose.yml backend/tests/delivery/test_delivery_contracts.py
git commit -m "chore: harden delivery configuration defaults"
```

## 8. Task 3：实现可迁移运行路径

**文件：**

- 新建：`backend/src/services/runtime_paths.py`
- 新建：`backend/tests/services/test_runtime_paths.py`
- 新建：`backend/src/tools/normalize_runtime_paths.py`
- 新建：`backend/tests/tools/test_normalize_runtime_paths.py`
- 修改：`backend/src/services/document_store.py`
- 修改：`backend/src/api/routes/reports.py`
- 修改：`backend/src/services/analysis_runner.py`
- 修改：`backend/tests/services/test_document_store.py`

- [ ] **Step 1：先写路径契约测试**

固定公开接口为 `serialize_runtime_path(path: Path, *, project_root: Path) -> str` 和 `resolve_stored_path(stored_path: str, *, project_root: Path) -> Path`。

测试必须证明：

- 项目根目录内的新上传保存为 `backend/data/runtime/...` 相对路径。
- 相对路径解析时不得逃出项目根目录，`../` 输入明确失败。
- 旧数据库中的绝对路径仍能读取，形成兼容窗口。
- 项目根目录外的显式绝对 `UPLOAD_DIR` 保持绝对路径，但在迁移报告中标记为不可自动迁移。

- [ ] **Step 2：运行路径测试并确认失败**

```powershell
cd backend
uv run --no-sync pytest tests/services/test_runtime_paths.py tests/services/test_document_store.py -q
```

预期：新测试因路径服务不存在而失败。

- [ ] **Step 3：实现最小路径服务并接入读写入口**

`DocumentStore.save_upload()` 只负责写文件，交给 `serialize_runtime_path()` 生成数据库值。报告文件下载、PDF 页图和分析 runner 全部通过 `resolve_stored_path()` 读取；不得批量改写现有数据库记录。

- [ ] **Step 4：实现旧路径迁移工具的 dry-run 门禁**

CLI 固定为：

```powershell
cd backend
uv run --no-sync python -m src.tools.normalize_runtime_paths --dry-run
uv run --no-sync python -m src.tools.normalize_runtime_paths --apply --confirm-database esg_agent_demo
```

工具只处理 `reports.stored_path`。写入前必须同时满足：目标数据库名与确认值一致、候选文件位于允许运行目录、文件 SHA-256 与 `reports.file_hash` 一致、候选唯一。dry-run 输出计数和相对路径，不输出数据库 URL、密码或报告正文。

- [ ] **Step 5：运行路径与 API 相关测试**

```powershell
cd backend
uv run --no-sync pytest tests/services/test_runtime_paths.py tests/services/test_document_store.py tests/tools/test_normalize_runtime_paths.py tests/api/test_reports_api.py -q
uv run --no-sync ruff check src/services/runtime_paths.py src/tools/normalize_runtime_paths.py tests/services/test_runtime_paths.py tests/tools/test_normalize_runtime_paths.py
```

预期：全部通过；既有绝对路径兼容测试通过。

- [ ] **Step 6：提交路径迁移批次**

```powershell
git add backend/src/services/runtime_paths.py backend/src/tools/normalize_runtime_paths.py backend/src/services/document_store.py backend/src/api/routes/reports.py backend/src/services/analysis_runner.py backend/tests/services/test_runtime_paths.py backend/tests/tools/test_normalize_runtime_paths.py backend/tests/services/test_document_store.py
git commit -m "feat: make runtime report paths portable"
```

## 9. Task 4：建立数据库初始化、migration 与备份恢复门禁

**文件：**

- 新建：`backend/tests/db/test_migration_roundtrip.py`
- 新建：`scripts/delivery/Delivery.Common.ps1`
- 新建：`scripts/delivery/Initialize-Database.ps1`
- 新建：`scripts/delivery/New-EsgAgentBackup.ps1`
- 新建：`scripts/delivery/Restore-EsgAgentBackup.ps1`
- 修改：`.gitignore`

- [ ] **Step 1：写临时数据库 migration round-trip 测试**

测试只在设置 `MIGRATION_TEST_DATABASE_URL` 时运行，数据库名必须以 `esg_agent_migration_test_` 开头。测试流程固定为：

```text
create unique empty database
alembic upgrade head
assert current revision == 0012_chunk_embeddings
assert vector extension exists
alembic downgrade 0011_ai_suggestions
assert document_chunk_embeddings table is absent
alembic upgrade head
assert current revision == 0012_chunk_embeddings
drop only the unique test database in finally
```

测试不得对 `esg_agent`、`esg_agent_demo`、`postgres`、`template0` 或 `template1` 执行 drop/downgrade。

- [ ] **Step 2：编写数据库初始化脚本**

`Initialize-Database.ps1` 参数固定为：

```powershell
param(
  [ValidateSet("demo", "main", "test")][string]$Environment = "demo",
  [Parameter(Mandatory)]
  [ValidateSet("new", "existing")][string]$VolumeMode,
  [switch]$RunMigrationRoundTrip
)
```

`-VolumeMode new` 要求目标 Compose project 使用唯一的新 volume，发现同名 volume 时停止；`-VolumeMode existing` 要求目标 volume 已存在，缺失时返回 `DOCKER_VOLUME_MISSING`，不能创建同名空 volume 掩盖数据缺失。existing 模式先记录 volume 标识、容器状态、数据库名、Alembic revision 和报告计数，再等待 Compose health。随后脚本创建对应数据库或复用已确认数据库，执行 `uv run --frozen --no-sync alembic upgrade head`，再查询 `alembic_version`。任何一步失败立即退出，不能继续启动应用，也不得执行 `docker compose down -v`。

- [ ] **Step 3：编写完整本地备份格式**

`New-EsgAgentBackup.ps1` 生成被 `.gitignore` 排除的本地归档，包含：

```text
database.dump
runtime/                 # 仅操作员明确允许的 uploads/derived/exports
backup-manifest.json     # app version、schema revision、database name、文件大小和 SHA-256
SHA256SUMS.txt
```

默认备份 demo 数据库。`-IncludeRuntime` 才复制运行文件，并在终端明确提示归档可能包含非公开报告；日志、缓存和测试输出始终排除。备份脚本不打印连接密码。

- [ ] **Step 4：编写恢复门禁**

恢复脚本必须要求：

```powershell
./scripts/delivery/Restore-EsgAgentBackup.ps1 `
  -ArchivePath ./backups/esg-agent-demo-backup.zip `
  -TargetDatabase esg_agent_demo_restore `
  -ConfirmDatabase esg_agent_demo_restore
```

恢复前验证外层与内层 SHA-256、确认服务已停止、拒绝系统数据库名、默认恢复到新数据库、运行 `normalize_runtime_paths --dry-run`。只有追加 `-ApplyPathNormalization` 才修改路径。恢复失败时保留原数据库和解压日志，不自动覆盖原运行目录。

- [ ] **Step 5：解析并 dry-run 验证所有 PowerShell 脚本**

```powershell
$errors = $null
Get-ChildItem scripts/delivery/*.ps1 | ForEach-Object {
  [System.Management.Automation.Language.Parser]::ParseFile($_.FullName, [ref]$null, [ref]$errors) | Out-Null
}
if ($errors.Count -gt 0) { $errors; exit 1 }
```

预期：没有 PowerShell 语法错误。

- [ ] **Step 6：在唯一临时库运行 migration 验收**

由脚本生成唯一数据库名和 URL，运行：

```powershell
./scripts/delivery/Initialize-Database.ps1 -Environment test -VolumeMode existing -RunMigrationRoundTrip
```

预期：空库升级、`0012 → 0011 → 0012` 和临时库清理全部成功。真实 main/demo 库不执行 downgrade。

- [ ] **Step 7：提交数据库运维批次**

```powershell
git add .gitignore scripts/delivery backend/tests/db/test_migration_roundtrip.py
git commit -m "feat: add database migration and recovery tooling"
```

## 10. Task 5：实现 Windows preflight、安装、启动、停止和 health

**文件：**

- 新建：`scripts/delivery/Test-Preflight.ps1`
- 新建：`scripts/delivery/Initialize-Environment.ps1`
- 新建：`scripts/delivery/Start-EsgAgent.ps1`
- 新建：`scripts/delivery/Stop-EsgAgent.ps1`
- 新建：`scripts/delivery/Test-EsgAgent.ps1`
- 修改：`scripts/delivery/Delivery.Common.ps1`
- 修改：`backend/tests/delivery/test_delivery_contracts.py`

- [ ] **Step 1：增加脚本安全契约测试**

测试至少检查：

- 所有脚本从 `$PSScriptRoot` 推导项目根目录，不依赖调用者当前目录。
- 所有脚本同时兼容 Windows PowerShell 5.1 与 PowerShell 7，且启动器不依赖 PATH 中的 `pwsh`。
- 启动脚本不包含 `--reload`，前端使用 `pnpm start`。
- 安装使用 `uv sync --frozen` 和 `pnpm install --frozen-lockfile`。
- `Start-Process` 使用 `-WindowStyle Hidden`、`-PassThru` 和日志重定向。
- 停止脚本只读取当前目录的 PID 清单，不按进程名批量终止。
- preflight 和 health 输出不包含完整 `DATABASE_URL` 或任何 key。
- 后端、前端和 health 都读取同一组 `BACKEND_PORT`、`FRONTEND_PORT`，不得在脚本内部重新硬编码 8000/3000。
- preflight 分别检查监听进程与 Windows TCP 排除范围，返回不同错误码。
- 任何脚本都不得自动执行 Docker factory reset、`Clean up data`、删除 volume、删除 `docker_data.vhdx` 或改写系统端口排除规则。
- `Start-EsgAgent.ps1` 支持 `-OpenBrowser`，只允许打开 health 已确认的 localhost 前端 URL。
- 启动锁、PID 清单和停止逻辑均绑定当前交付根目录哈希，不能影响其他 checkout 或工作区。

- [ ] **Step 2：实现只读 preflight**

`Test-Preflight.ps1` 核对必需工具的完整版本、Windows PowerShell 5.1、Docker daemon、Compose 配置、volume 可见性、锁文件、migration head 和配置安全状态。PowerShell 7 只记录为可选维护者工具，缺少时不阻断启动器或接收方运行。普通模式在 Docker Desktop 4.80.0 上返回 `DOCKER_DESKTOP_BELOW_RECOMMENDED` 警告；最终 `-StrictDelivery` 模式要求 Docker Desktop 至少为 4.89.0，并记录实际 Engine 和 Compose 版本。缺少 OCRmyPDF、Ghostscript、Tesseract 或语言包时只给出 `OPTIONAL_MISSING`，前提是 `OCR_ENABLED=false`；OCR 被打开时缺少任一项必须失败。

端口检查读取 `POSTGRES_PORT`、`BACKEND_PORT` 和 `FRONTEND_PORT`：先用 `Get-NetTCPConnection` 判断监听占用，再解析 `netsh interface ipv4/ipv6 show excludedportrange protocol=tcp`。存在监听进程时返回 `PORT_IN_USE`；没有监听但端口落入排除范围时返回 `PORT_EXCLUDED`。脚本不删除排除规则、不自动杀进程、不静默选择新端口，只提示操作员在本地 `.env` 指定可用端口。

Docker daemon 无法连接时返回 `DOCKER_DAEMON_UNAVAILABLE`，并指向运维文档的残留 socket 排查章节。preflight 只采集诊断，不重命名 socket 目录、不重启 Docker Desktop、不执行 factory reset。

preflight 结果写入 `backend/data/runtime/logs/preflight.json`，只包含版本、布尔状态、错误码和时间，不包含路径中的用户名、密码或密钥。

- [ ] **Step 3：实现本地配置和依赖安装**

`Initialize-Environment.ps1` 的默认 demo 流程：

1. 从 `.env.example` 生成被忽略的根 `.env`。
2. 使用加密随机十六进制字符串生成本地 PostgreSQL 密码，不在终端回显。
3. 根据密码、端口和数据库名生成进程环境中的 `DATABASE_URL`。
4. 执行 `uv sync --frozen`。
5. 通过 Corepack 激活 pnpm 11.19.0。
6. 根据 `BACKEND_PORT` 设置进程级 `NEXT_PUBLIC_API_BASE_URL`，再执行 `pnpm install --frozen-lockfile`、`pnpm build`。
7. 首次安装调用 `Initialize-Database.ps1 -Environment demo -VolumeMode new`；迁移已有数据必须由操作员显式改为 `-VolumeMode existing`。

存在 `.env` 时默认拒绝覆盖；只有 `-UseExistingConfig` 才复用，只有 `-RegenerateLocalConfig` 且用户明确执行时才重建。

- [ ] **Step 4：实现生产模式启动和进程记录**

后端命令模板固定为：

```powershell
$backendPort = [int]$config.BACKEND_PORT
uv run --frozen --no-sync uvicorn src.main:app --host 127.0.0.1 --port $backendPort
```

前端命令模板固定为：

```powershell
$frontendPort = [int]$config.FRONTEND_PORT
pnpm start --hostname 127.0.0.1 --port $frontendPort
```

启动前必须通过 preflight、数据库 head 检查和端口检查。若综合 health 已通过，脚本不创建进程；指定 `-OpenBrowser` 时只打开一次已确认的本机前端 URL。若服务尚未启动，脚本先确认预期 PostgreSQL volume 存在，再执行 `docker compose up -d postgres` 并等待 healthy；不得因 volume 缺失而创建同名空库。

启动脚本使用当前根目录哈希对应的独占锁；同目录第二次启动等待既有启动完成，其他 checkout 使用独立锁。脚本将 `NEXT_PUBLIC_API_BASE_URL` 与已构建前端使用的 `BACKEND_PORT` 比较，不一致时返回 `FRONTEND_API_BASE_MISMATCH` 并停止。进程 PID、启动时间、工作目录、实际端口、根目录哈希和日志文件写入 `backend/data/runtime/delivery/processes.json`。stdout/stderr 分开保存在 `backend/data/runtime/logs/`。

- [ ] **Step 5：实现安全停止**

`Stop-EsgAgent.ps1` 逐项核对 PID、记录的启动时间和命令行属于当前项目目录，再执行停止。PID 已复用或命令不匹配时只报错，不终止进程。默认保留 PostgreSQL；`-IncludeDatabase` 才执行 `docker compose stop postgres`，不得执行 `down -v`。

- [ ] **Step 6：实现综合 health**

`Test-EsgAgent.ps1` 依次核对：

```text
docker info => daemon available
docker compose ps postgres => healthy
alembic current => 0012_chunk_embeddings
GET http://localhost:${BACKEND_PORT}/api/health => status=ok, app_env=demo
GET http://localhost:${BACKEND_PORT}/openapi.json => info.version matches package version
GET http://localhost:${FRONTEND_PORT} => HTTP 200
OCR_ENABLED=false
EMBEDDING_ENABLED=false
API key fields empty in delivery demo
```

失败输出必须给出稳定错误码，例如 `DOCKER_DAEMON_UNAVAILABLE`、`DOCKER_DESKTOP_BELOW_RECOMMENDED`、`DOCKER_VOLUME_MISSING`、`PORT_IN_USE`、`PORT_EXCLUDED`、`FRONTEND_API_BASE_MISMATCH`、`POSTGRES_UNHEALTHY`、`MIGRATION_NOT_AT_HEAD`、`BACKEND_HEALTH_FAILED`、`FRONTEND_HTTP_FAILED` 和 `EXTERNAL_FEATURE_ENABLED`。

- [ ] **Step 7：运行最小脚本验证**

```powershell
$windowsPowerShell = Join-Path $env:WINDIR "System32/WindowsPowerShell/v1.0/powershell.exe"
& $windowsPowerShell -NoProfile -File ./scripts/delivery/Test-Preflight.ps1
& $windowsPowerShell -NoProfile -File ./scripts/delivery/Test-EsgAgent.ps1 -AllowServicesStopped
./scripts/delivery/Test-Preflight.ps1
./scripts/delivery/Test-EsgAgent.ps1 -AllowServicesStopped
cd backend
uv run --no-sync pytest tests/delivery/test_delivery_contracts.py -q
```

预期：Windows PowerShell 5.1 与维护者 PowerShell 7 得到相同的稳定状态码；preflight 通过必需依赖，停止状态 health 返回明确的服务未启动状态且不修改系统。

- [ ] **Step 8：提交运行脚本批次**

```powershell
git add scripts/delivery backend/tests/delivery/test_delivery_contracts.py
git commit -m "feat: add Windows delivery lifecycle scripts"
```

## 11. Task 6：构建并验证 C# 轻量启动器

**文件：**

- 新建：`scripts/delivery/Build-Launcher.ps1`
- 新建：`delivery/launcher/EsgAgentLauncher.cs`
- 新建：`delivery/launcher/EsgAgentLauncher.exe.manifest`
- 新建：`delivery/launcher/launcher-manifest.json`
- 新建：`backend/tests/delivery/test_launcher_contract.py`
- 新建：`ESG-Agent.exe`
- 修改：`delivery/release-policy.json`
- 修改：`.gitignore`

- [ ] **Step 1：先写启动器失败测试**

`test_launcher_contract.py` 必须先在 `ESG-Agent.exe`、源码、应用 manifest 和 launcher manifest 尚不存在时失败，并覆盖：

```python
def test_launcher_allows_only_fixed_actions():
    assert launcher_actions == {
        (): ("Start-EsgAgent.ps1", "-OpenBrowser"),
        ("--no-browser",): ("Start-EsgAgent.ps1", None),
        ("--status",): ("Test-EsgAgent.ps1", None),
        ("--stop",): ("Stop-EsgAgent.ps1", None),
    }

def test_launcher_manifest_matches_tracked_inputs_and_binary():
    assert sha256(source) == manifest["source_sha256"]
    assert sha256(app_manifest) == manifest["app_manifest_sha256"]
    assert sha256(executable) == manifest["artifact"]["sha256"]
```

测试还要把候选 EXE 复制到临时根目录，写入只记录参数并返回固定退出码的假 `scripts/delivery/*.ps1`，设置 `ESG_AGENT_LAUNCHER_NONINTERACTIVE=1` 后分别执行四种合法动作和非法参数。断言启动器只调用预期相对脚本、保留脚本退出码、非法参数不创建 PowerShell 进程、输出不含临时根目录外路径或环境变量秘密值。

```powershell
cd backend
uv run --no-sync pytest tests/delivery/test_launcher_contract.py -q
```

预期：因启动器工件尚不存在而失败，不启动真实数据库、后端、前端或浏览器。

- [ ] **Step 2：实现并构建最小 C# 启动器**

`EsgAgentLauncher.cs` 使用 `AppContext.BaseDirectory`、固定动作枚举和 `ProcessStartInfo.ArgumentList` 等价的逐参数转义函数，不接受任意脚本或命令参数，也不读取 `.env`。子进程固定 `UseShellExecute=false`、`CreateNoWindow=true`，异步读取 stdout/stderr 并将内存摘要分别限制为 8 KiB，避免输出阻塞或无限占用；启动、health 和外部命令超时由生命周期脚本统一控制。正常交互模式显示仅含状态文本与 marquee progress bar 的 WinForms 窗口；`ESG_AGENT_LAUNCHER_NONINTERACTIVE=1` 时不显示窗口或 MessageBox，只向 stdout/stderr 输出稳定错误码，供自动测试使用。

`Build-Launcher.ps1` 提供互斥参数：

```powershell
param(
    [switch]$UpdateTrackedArtifact,
    [switch]$VerifyTrackedArtifact
)
```

默认无参数只编译到 `tmp/launcher-build/` 并运行测试夹具；`-VerifyTrackedArtifact` 只核对现有源码、应用 manifest、编译器和根目录 EXE 的哈希；`-UpdateTrackedArtifact` 在候选测试全部通过后才替换根目录 EXE 并生成 launcher manifest。两种开关同时出现时返回 `INVALID_BUILD_MODE`，任何模式都不得修改 PowerShell 策略、注册表、数据库或服务。

- [ ] **Step 3：运行启动器自动与本机验收**

```powershell
./scripts/delivery/Build-Launcher.ps1 -UpdateTrackedArtifact
./scripts/delivery/Build-Launcher.ps1 -VerifyTrackedArtifact
cd backend
uv run --no-sync pytest tests/delivery/test_launcher_contract.py tests/delivery/test_delivery_contracts.py -q
cd ..
./ESG-Agent.exe --status
```

预期：构建与 manifest 核验通过；假脚本测试证明四种动作映射和失败语义；`--status` 只读返回当前本机服务状态。随后人工双击根目录 `ESG-Agent.exe`：若服务已健康，只打开一次网页；若服务未启动，在不创建新 volume、不迁移数据库的前提下启动并通过 health 后打开网页。验收前后记录进程清单、volume 身份、数据库 revision 和外部能力关闭状态；已有服务不为测试而强制停止。

- [ ] **Step 4：提交启动器批次**

```powershell
git add .gitignore ESG-Agent.exe delivery/launcher scripts/delivery/Build-Launcher.ps1 backend/tests/delivery/test_launcher_contract.py delivery/release-policy.json
git commit -m "feat: add one-click Windows launcher"
```

提交前复核根目录 EXE 的 SHA-256 与 launcher manifest、release policy 和 Git staged 内容一致；`首页.png` 与其他用户未跟踪文件保持未暂存。

## 12. Task 7：建立合法、脱敏、确定性的演示闭环

**文件：**

- 新建：`delivery/demo/demo-report-source.json`
- 新建：`backend/src/tools/generate_demo_report.py`
- 新建：`backend/tests/tools/test_generate_demo_report.py`
- 新建：`backend/src/tools/verify_delivery_flow.py`
- 新建：`backend/tests/tools/test_verify_delivery_flow.py`
- 修改：`backend/tests/api/test_phase17_product_closure_e2e.py`

- [ ] **Step 1：定义合成报告来源**

演示报告使用虚构英文企业 `ESG-Agent Demo Manufacturing Co., Ltd.` 和固定报告年度 2025。正文覆盖治理、能源、排放、员工、健康安全、社区和产品责任，首页明确声明：

```text
This is a fictional report generated solely for ESG-Agent delivery verification.
It contains no real company, person, credential, model response, or confidential data.
```

报告不得复制 Envision、Goldwind 或 GRI 原始文本，不宣称通过 GRI 认证，也不作为规则正确率样本。

- [ ] **Step 2：先写确定性 PDF 测试**

测试必须连续生成两份 PDF，断言 SHA-256 完全一致、页数固定、可由 pypdf/pdfplumber 提取声明和企业名、文件不包含当前用户名或绝对路径。

- [ ] **Step 3：实现确定性生成器**

生成器只读取受版本控制的 JSON，使用 ReportLab 内置字体、固定页面尺寸、固定 PDF metadata 和 invariant 模式。CLI 固定为：

```powershell
cd backend
uv run --no-sync python -m src.tools.generate_demo_report `
  --source ../delivery/demo/demo-report-source.json `
  --output ../tmp/demo/esg-agent-synthetic-report-2025.pdf
```

- [ ] **Step 4：先写 HTTP 闭环客户端测试**

以 `httpx.MockTransport` 覆盖以下顺序和失败点：上传、metadata 确认、分析、轮询完成、范围核对、人工复核、整改创建/更新、草稿输出、逐文件下载与 SHA-256、审计事件核对。任何响应非 2xx 或计数不符时返回非零退出码和稳定错误码。

- [ ] **Step 5：实现真实 HTTP 验收客户端**

CLI 固定为：

```powershell
cd backend
$backendPort = if ($env:BACKEND_PORT) { [int]$env:BACKEND_PORT } else { 8000 }
uv run --no-sync python -m src.tools.verify_delivery_flow `
  --api-base "http://localhost:$backendPort" `
  --report ../tmp/demo/esg-agent-synthetic-report-2025.pdf `
  --output data/runtime/acceptance/delivery-flow.json
```

请求体固定 `confirm_llm=false`、`enable_ocr=false`。验收必须核对 `standard_unit_count=577`、`eligible_requirement_count=499`、`context_only_count=78`、`method_pending_count=0`，且 AI suggestion 为 0；不得自动生成正式输出。

- [ ] **Step 6：显式划分授权资产测试**

Goldwind PDF 缺失时，`test_phase17_product_closure_e2e.py` 使用稳定原因 `authorized Goldwind regression asset is not installed` 跳过。维护者发布门禁先执行资产 SHA-256 校验，再运行该测试，并断言没有跳过；干净发布包门禁允许这一个已登记的授权资产跳过，不允许未知跳过。

- [ ] **Step 7：运行演示工具测试和真实 demo 闭环**

```powershell
cd backend
uv run --no-sync pytest tests/tools/test_generate_demo_report.py tests/tools/test_verify_delivery_flow.py tests/api/test_phase17_product_closure_e2e.py -q
uv run --no-sync ruff check src/tools/generate_demo_report.py src/tools/verify_delivery_flow.py tests/tools/test_generate_demo_report.py tests/tools/test_verify_delivery_flow.py
```

服务启动后再运行真实 HTTP CLI。预期：完整闭环通过，报告文件和验收 JSON 只写入被忽略的 demo/runtime 目录。

- [ ] **Step 8：提交演示闭环批次**

```powershell
git add delivery/demo backend/src/tools/generate_demo_report.py backend/src/tools/verify_delivery_flow.py backend/tests/tools/test_generate_demo_report.py backend/tests/tools/test_verify_delivery_flow.py backend/tests/api/test_phase17_product_closure_e2e.py
git commit -m "test: add asset-safe delivery demo flow"
```

## 13. Task 8：构建源码归档、交付清单和 checksum

**文件：**

- 新建：`backend/src/tools/build_release_archive.py`
- 新建：`backend/tests/tools/test_build_release_archive.py`
- 修改：`delivery/release-policy.json`
- 读取：`delivery/launcher/launcher-manifest.json`
- 读取：`ESG-Agent.exe`
- 修改：`.gitignore`

- [ ] **Step 1：先写归档安全测试**

测试在临时 Git 仓库中证明：

- 只读取指定 commit 的 `git archive`，不复制工作区未跟踪文件。
- 真实 `.env`、私钥、dump、日志、runtime 文件和未授权 PDF 触发构建失败。
- 只允许根目录 `ESG-Agent.exe`；其他 EXE、MSI、安装器或 EXE 哈希与 launcher manifest 不一致时触发构建失败。
- 合成演示 PDF 是唯一允许新增到归档的 PDF。
- 文件按 POSIX 相对路径排序，ZIP timestamp 固定为 commit timestamp。
- 同一 commit 连续构建两次得到相同归档 SHA-256。
- 内部 `release-manifest.json` 列出每个 payload 的路径、大小、SHA-256 和角色。
- 外部 `esg-agent-1.5-SHA256SUMS.txt` 能验证 ZIP。

- [ ] **Step 2：实现归档构建器**

CLI 固定为：

```powershell
cd backend
uv run --no-sync python -m src.tools.build_release_archive `
  --repo-root .. `
  --commit HEAD `
  --output-dir ../tmp/release
```

构建器必须先验证 tracked worktree 无差异；未跟踪文件不进入归档。它从 commit 建立临时 staging，验证 C# 源码、应用 manifest、编译器指纹记录和根目录 `ESG-Agent.exe` 与 launcher manifest 一致；归档阶段只复制已跟踪 EXE，不重新编译。随后生成合成 PDF，加入版本与工具链 manifest，执行拒绝项和敏感模式扫描，最后创建确定性 ZIP。staging 始终位于 `tmp/`，失败时保留脱敏错误摘要，不保留已发现的秘密内容。

- [ ] **Step 3：运行归档单元测试**

```powershell
cd backend
uv run --no-sync pytest tests/tools/test_build_release_archive.py tests/delivery/test_delivery_contracts.py -q
uv run --no-sync ruff check src/tools/build_release_archive.py tests/tools/test_build_release_archive.py
```

- [ ] **Step 4：提交归档批次**

```powershell
git add .gitignore delivery/release-policy.json backend/src/tools/build_release_archive.py backend/tests/tools/test_build_release_archive.py
git commit -m "feat: build deterministic delivery archives"
```

- [ ] **Step 5：从干净 HEAD 执行构建冒烟验证**

提交后 tracked worktree 无差异，才能运行真实 `git archive` 构建。核对：

```powershell
cd backend
uv run --no-sync python -m src.tools.build_release_archive `
  --repo-root .. `
  --commit HEAD `
  --output-dir ../tmp/release
cd ..
Get-FileHash tmp/release/esg-agent-1.5-windows-x64.zip -Algorithm SHA256
Get-Content tmp/release/esg-agent-1.5-SHA256SUMS.txt
```

解压到 `tmp/release-inspection/` 后核对当前阶段已经存在的核心内容；Task 11 再核对后续新增的交付文档：

```text
present: backend/uv.lock
present: frontend/pnpm-lock.yaml
present: .env.example
present: ESG-Agent.exe
present: delivery/launcher/launcher-manifest.json
present: scripts/delivery/Test-Preflight.ps1
present: demo/esg-agent-synthetic-report-2025.pdf
absent: .git/
absent: .env
absent: backend/.env
absent: node_modules/
absent: .venv/
present: backend/data/runtime/.gitkeep only
absent: backend/data/runtime 的上传、派生、导出和日志 payload
absent: 首页.png
```

## 14. Task 9：编写接收方文档与 Docker 评估

**文件：**

- 新建：`docs/delivery/INSTALL-WINDOWS.md`
- 新建：`docs/delivery/OPERATIONS.md`
- 新建：`docs/delivery/CLEAN-ACCEPTANCE.md`
- 新建：`docs/delivery/DOCKER-EVALUATION.md`
- 修改：`README.md`
- 修改：`docs/DESIGN.md`
- 修改：`docs/DEVELOPMENT.md`
- 修改：`docs/ASSETS.md`

- [ ] **Step 1：编写接收方最短恢复路径**

`INSTALL-WINDOWS.md` 从“只拿到 ZIP 的接收方”视角编写，命令顺序固定为：

```powershell
Get-FileHash ./esg-agent-1.5-windows-x64.zip -Algorithm SHA256
Expand-Archive ./esg-agent-1.5-windows-x64.zip ./esg-agent-1.5
cd ./esg-agent-1.5
./scripts/delivery/Test-Preflight.ps1
./scripts/delivery/Initialize-Environment.ps1
./ESG-Agent.exe --no-browser
./scripts/delivery/Test-EsgAgent.ps1
```

初始化完成后，日常使用说明把“双击 `ESG-Agent.exe`”作为最短入口，并把 PowerShell 启停命令保留为可审计、可诊断的等价入口。文档明确安装过程需要软件源网络，启动器不安装任何依赖；演示运行不调用 DeepSeek、SiliconFlow、OCR 或 VLM。

- [ ] **Step 2：编写运维和故障恢复说明**

`OPERATIONS.md` 必须覆盖以下故障及明确动作：

| 故障 | 检查点 | 处理与回滚 |
| --- | --- | --- |
| 工具安装失败 | preflight 错误码、版本 | 保留日志，补齐固定版本后重跑；不降级锁文件 |
| Docker daemon 无法启动 | Desktop 版本、进程、诊断日志、残留 socket | 完全退出 Docker 后按受控步骤检查并重命名临时 socket 目录；禁止脚本自动处理 |
| Docker Desktop 升级 | 数据库备份、运行文件备份、volume 身份、报告计数、安装包来源 | 单独审批后人工升级；失败时保留数据盘与备份，恢复旧 Desktop 或转移到干净验收机，禁止 factory reset |
| Docker volume 不可见 | `docker volume ls`、`docker ps -a`、数据盘状态 | 停止创建同名新 volume，先恢复或确认原数据；禁止 factory reset 和 `Clean up data` |
| 启动器无法运行 | launcher manifest、EXE SHA-256、.NET Framework、系统 Windows PowerShell、相对目录 | 使用 `Build-Launcher.ps1 -VerifyTrackedArtifact` 核验；直接运行等价 PowerShell 脚本；不从非交付来源替换 EXE |
| 启动器重复点击 | 启动锁、PID、综合 health | 等待同目录既有启动完成；不得创建第二组服务进程 |
| 端口被进程占用 | 配置端口的监听 PID | 修改本地端口配置或停止已确认进程；脚本不代替用户杀进程 |
| Windows 排除端口 | IPv4/IPv6 excluded port ranges | 不修改系统排除规则；在本地 `.env` 改用可用端口，并重新构建前端 API 地址 |
| PostgreSQL 连接失败 | Compose health、容器日志 | 检查本地 `.env` 和端口；不输出密码 |
| migration 失败 | Alembic revision、迁移日志 | 停止服务，恢复升级前备份；真实库不直接 downgrade |
| Ghostscript/Tesseract 缺失 | OCR capability | 保持 OCR 关闭继续默认链路；需要 OCR 时另行安装并授权 |
| 前端构建失败 | Node/pnpm 版本和 build log | 以 frozen lock 重装；不得更新依赖绕过 |
| 后端启动失败 | stderr、数据库 head | 修复配置或迁移后重启，不清库 |
| 恢复上一版本 | 旧归档 checksum、旧数据库备份 | 旧代码与其兼容备份成对恢复，不共享已升级数据库 |
| 数据库恢复失败 | dump/manifest checksum | 保留原库，恢复到新目标库后再切换 |

残留 socket 恢复说明必须保持人工受控：先退出 Docker Desktop 并确认相关进程结束，再检查临时目录只含预期的零字节 reparse-point socket，随后以时间戳重命名目录留档。恢复引擎后依次核对 `docker info`、原 volume、原容器、`pg_isready`、数据库名、Alembic revision 和报告计数。任何内容或目标不符合预期时停止，不执行删除。

- [ ] **Step 3：记录 Docker A/B/C 结论**

`DOCKER-EVALUATION.md` 明确排序：

1. B：Release ZIP + 固定依赖 + PowerShell，作为主要交付。
2. A：Git clone + 固定 commit/tag，作为维护与审计入口。
3. C：全栈 Docker Compose，因 OCR、Windows 路径、镜像体积和离线成本延期。

比较矩阵必须逐项评价：OCRmyPDF、Ghostscript、Tesseract 与 `chi_sim+eng` 语言包、PDF 页面渲染、Windows 文件路径、持久化目录、数据库备份恢复、预计镜像体积、首次拉取时间和完全离线交付成本。每项给出依赖、风险、验证方法和是否阻断默认链路，不能只给总体判断。

重新评估 C 的触发条件为：明确要求 Linux/服务器部署、两个以上接收环境、OCR 容器化或离线镜像。未满足触发条件时不创建 Dockerfile。

- [ ] **Step 4：更新项目唯一源文档**

- `README.md` 先增加 1.5 交付入口并标记为待验收候选；Task 10 完成版本同步后才把当前公开基线更新到 1.5，保留 1.3.1 历史说明。
- `docs/DESIGN.md` 增加交付架构、相对运行路径和数据边界，不改产品语义章节。
- `docs/DEVELOPMENT.md` 区分开发命令与接收方脚本，记录固定版本和门禁；保留 2026-09-03 Docker Desktop 残留 socket、volume 核验和 Windows 排除端口的实际恢复记录。
- `docs/ASSETS.md` 增加发布包资产、授权本地回归资产、运行时备份三类边界。

`README.md` 和 `docs/DEVELOPMENT.md` 在本计划编写后已有用户修改。实施时必须基于当前内容小步补丁合并，不得覆盖、回退或把恢复事实改写成计划推测。`README.md` 中 Docker Desktop 4.89.0 建议与 `docs/DEVELOPMENT.md` 中 4.80.0 恢复来源事实必须同时保留并明确区分。

- [ ] **Step 5：扫描新文档中的禁止内容**

```powershell
rg -n "[A-Za-z]:\\|OPENAI_COMPATIBLE_API_KEY=.+|EMBEDDING_API_KEY=.+|POSTGRES_PASSWORD=.+" docs/delivery README.md docs/DESIGN.md docs/DEVELOPMENT.md docs/ASSETS.md
```

预期：没有本机绝对路径、真实 API key 或数据库密码。命令示例中的空值和环境变量名允许存在。

- [ ] **Step 6：提交文档批次**

```powershell
git add README.md docs/DESIGN.md docs/DEVELOPMENT.md docs/ASSETS.md docs/delivery
git commit -m "docs: add 1.5 delivery and migration runbooks"
```

## 15. Task 10：最终同步 1.5 元数据

**文件：**

- 修改：`backend/pyproject.toml`
- 修改：`backend/uv.lock`
- 修改：`backend/src/main.py`
- 修改：`frontend/package.json`
- 修改：`frontend/pnpm-lock.yaml`
- 修改：`README.md`
- 修改：`docs/DESIGN.md`
- 修改：`docs/DEVELOPMENT.md`
- 修改：`backend/tests/delivery/test_delivery_contracts.py`
- 读取：`delivery/launcher/launcher-manifest.json`
- 读取：`ESG-Agent.exe`

- [ ] **Step 1：先写版本一致性测试**

在 `test_delivery_contracts.py` 断言 backend project、frontend package、OpenAPI 常量、release policy 和 launcher manifest 的 package version 都为 `1.5.0`，公开文档、启动器 PE product version 和归档名使用 `1.5`；启动器 assembly/file version 为 `1.5.0.0`。

- [ ] **Step 2：运行测试并确认旧元数据导致失败**

```powershell
cd backend
uv run --no-sync pytest tests/delivery/test_delivery_contracts.py tests/test_health.py -q
```

预期：当前 `1.3.1` 元数据导致版本一致性测试失败。

- [ ] **Step 3：同步内部元数据并更新锁文件**

只修改版本字段：

```text
backend/pyproject.toml => 1.5.0
backend/src/main.py APP_VERSION => 1.5.0
frontend/package.json => 1.5.0
```

随后执行：

```powershell
cd backend
uv lock
uv lock --check
cd ../frontend
pnpm install --frozen-lockfile
```

不得借版本同步升级任何依赖。执行后检查 `backend/uv.lock` 和 `frontend/pnpm-lock.yaml`；除项目自身版本记录外，依赖名称、解析版本和 integrity 不得变化。

- [ ] **Step 4：运行版本相关门禁**

按顺序运行：

```powershell
cd backend
uv run --no-sync pytest tests/delivery/test_delivery_contracts.py tests/test_health.py tests/api/test_openapi_contract.py -q
uv run --no-sync ruff check src/main.py tests/delivery/test_delivery_contracts.py
cd ../frontend
pnpm typecheck
pnpm build
```

预期：backend、frontend、OpenAPI、release policy 和 launcher manifest 的内部版本均为 `1.5.0`；公开版本均为 `1.5`，启动器四段式程序集版本为 `1.5.0.0`。

- [ ] **Step 5：提交 1.5 元数据**

```powershell
git add backend/pyproject.toml backend/uv.lock backend/src/main.py frontend/package.json frontend/pnpm-lock.yaml README.md docs/DESIGN.md docs/DEVELOPMENT.md backend/tests/delivery/test_delivery_contracts.py
git commit -m "chore: prepare 1.5 delivery metadata"
```

- [ ] **Step 6：从 Task 10 最终提交重建候选交付包**

重新运行 Task 8 的归档构建与双次确定性校验，生成 `tmp/release/esg-agent-1.5-windows-x64.zip`、旁路证明和 `SHA256SUMS.txt`。校验 ZIP 内部 manifest、根目录 `ESG-Agent.exe`、launcher manifest、版本和当前 commit 一致，并将产物复制到主工作区被忽略的 `tmp/release/` 后再清理 worktree。

该候选包只证明 Task 1–10 的源码、启动器、文档和归档契约一致。由于 Task 11 尚未执行，文档与旁路证明必须明确标记“未完成等价干净环境验收”，不得创建 `v1.5` tag、托管平台 release 或形成正式发布结论。

## 16. Task 11：执行最终归档与等价干净环境验收

**文件：**

- 新建：`scripts/delivery/Invoke-CleanAcceptance.ps1`
- 新建：`docs/product/v1.5-reproducible-delivery-acceptance.md`
- 修改：`docs/delivery/CLEAN-ACCEPTANCE.md`

- [ ] **Step 1：实现隔离验收编排**

脚本只允许在 `tmp/clean-acceptance/` 下创建目录，使用独立 Compose project、独立 volume、唯一数据库名和可配置端口。运行前解析并核对目标绝对路径确实位于该目录；不得删除工作区根目录、用户目录或现有 Compose volume。

验收输入只能是刚生成的 ZIP 和 SHA 文件，不能复用当前工作区的 `.venv`、`node_modules`、`.env`、数据库或 runtime。

脚本参数必须显式支持 `-PostgresPort`、`-BackendPort` 和 `-FrontendPort`。默认分别为 5432、8000 和 3000；任一端口被占用或排除时停止，由操作员选择新端口后重新执行。2026-09-03 当前 Windows 的 8000 位于排除范围，等价隔离验收命令应显式传入 `-BackendPort 8200`，并在旁路证明中记录实际端口。最终交付验收调用 `Test-Preflight.ps1 -StrictDelivery`，Docker Desktop 低于 4.89.0 时不能形成 1.5 支持结论。

当前 4.80.0 环境恢复成功、服务健康和数据完整只作为恢复来源证据，不能替代最终干净环境验收。最终验收应优先在另一台干净机器或独立验收环境执行；若必须升级当前开发机，先完成前述备份与单独审批，再运行 `-StrictDelivery`。

- [ ] **Step 2：增加脚本契约并验证语法**

`test_delivery_contracts.py` 增加以下断言：隔离根目录固定为项目 `tmp/clean-acceptance/`、Compose project/端口/数据库名必须唯一、清理目标必须先通过 `IsPathWithin`、脚本不得使用 `docker compose down -v` 或宽泛递归删除。验收编排必须先核对 launcher manifest 与根目录 EXE，再通过 `ESG-Agent.exe --no-browser` 启动、通过 `--status` 核对、通过 `--stop` 停止；任一动作失败时保存退出码和脱敏日志。

随后解析全部 PowerShell 文件：

```powershell
$errors = $null
Get-ChildItem scripts/delivery/*.ps1 | ForEach-Object {
  [System.Management.Automation.Language.Parser]::ParseFile($_.FullName, [ref]$null, [ref]$errors) | Out-Null
}
if ($errors.Count -gt 0) { $errors; exit 1 }
```

- [ ] **Step 3：提交隔离验收编排骨架**

先创建状态为“尚未执行”的验收记录结构并提交脚本，确保后续归档从干净 commit 构建：

```powershell
git add scripts/delivery/Invoke-CleanAcceptance.ps1 docs/delivery/CLEAN-ACCEPTANCE.md docs/product/v1.5-reproducible-delivery-acceptance.md backend/tests/delivery/test_delivery_contracts.py
git commit -m "test: add clean 1.5 delivery harness"
```

- [ ] **Step 4：先执行维护者语义回归门禁**

该门禁在含授权资产的维护者环境中执行，不在发布 ZIP 中执行：

1. 按 `assets_manifest.json` 核验 Envision、Goldwind 和人工复核输入 SHA-256。
2. 运行 Goldwind Phase 1.7 产品闭环测试，确认没有 skip。
3. 运行 Envision v3 regeneration 与 audit。
4. 核对 `577/499/78/0`、0 global fallback、0 新增 false disclosed、0 新增 wrong source page。
5. 核对原始报告 SHA-256 前后不变。

任一授权资产缺失、hash 不符或门禁回归时停止发布，不能把维护者资产加入 ZIP 规避失败。

- [ ] **Step 5：运行维护者环境完整自动门禁**

按顺序运行，避免资源争用：

```powershell
cd backend
uv run --no-sync ruff check .
uv run --no-sync pytest -q
cd ../frontend
pnpm lint
pnpm typecheck
pnpm test
pnpm build
```

维护者环境的授权资产测试不得 skip。lint 允许两条已记录 warning，error 必须为 0。实际通过、跳过和 warning 数写入验收记录，不沿用旧数字冒充本轮结果。

- [ ] **Step 6：创建候选归档并从 ZIP 完整恢复**

从当前 commit 构建候选 ZIP，顺序固定为：

```text
verify outer SHA-256
extract into empty target
verify internal manifest
verify launcher manifest and ESG-Agent.exe SHA-256
run preflight
create local config with blank model keys
record Docker Desktop, Engine, Compose, ports and volume identity
uv sync --frozen
pnpm install --frozen-lockfile
create empty PostgreSQL database
alembic upgrade head
pnpm build
start backend and frontend through ESG-Agent.exe --no-browser
run Test-EsgAgent.ps1
run verify_delivery_flow.py with synthetic PDF
stop frontend/backend through ESG-Agent.exe --stop
create backup with authorized runtime files
restore backup into a new database
start against restored database
rerun health and audit read checks
stop services and retain acceptance logs
```

- [ ] **Step 7：在解压目录运行自动门禁**

```powershell
cd backend
uv run --no-sync ruff check .
uv run --no-sync pytest -q
cd ../frontend
pnpm lint
pnpm typecheck
pnpm test
pnpm build
```

干净包允许且只允许登记的授权报告 E2E 跳过；其他测试不得跳过。必须记录实际计数和 skip 标识。

- [ ] **Step 8：执行人工浏览器验收**

在实际记录的 Chrome 或 Edge 版本中验证：

- 首页与 `/reports` 可访问且无横向溢出。
- 双击 ZIP 根目录 `ESG-Agent.exe` 能幂等启动或复用健康服务，并只打开一次本机网页。
- `ESG-Agent.exe --status` 只读，`ESG-Agent.exe --stop` 只停止当前解压目录记录的前后端并保留 PostgreSQL。
- 合成报告可完成上传、metadata、分析、范围核查、人工复核、整改、草稿、下载和审计。
- 桌面端 1280×720、移动端 390×844 的核心布局可用。
- 页面显示 577 项产品口径；技术审计保持 `577/499/78/0`。
- 低质量 OCR 展示仍可审计，但本次运行没有执行 OCR。
- 浏览器没有本轮新增 console error。

- [ ] **Step 9：验证默认无外部调用**

验收证据必须同时包含：

- 本地配置中两个 API key 为空。
- `confirm_llm=false`、`enable_ocr=false`。
- run 的 AI suggestion 数为 0。
- evidence 中没有本次 OCR 来源。
- embedding 表没有本次 demo 写入。
- 服务日志中没有 DeepSeek、SiliconFlow、OCRmyPDF 或 VLM 调用记录。

- [ ] **Step 10：记录候选验收事实并提交**

`docs/product/v1.5-reproducible-delivery-acceptance.md` 记录候选 commit、工具版本、migration、门禁计数、浏览器版本、备份恢复结果、已登记 skip、两个 lint warning、资产排除证明和剩余限制。任何未执行项明确写为未通过，不能写成计划结果。

该受版本控制的文档不得写入其所在最终 ZIP 的外层 SHA-256，避免“归档包含记录自身 hash 的文档”形成不可收敛的循环。外层 hash 由下一步生成的归档旁路证明记录。

```powershell
git add docs/product/v1.5-reproducible-delivery-acceptance.md
git commit -m "docs: record 1.5 delivery acceptance"
```

- [ ] **Step 11：从最终 commit 重建并复验**

从新的最终 `HEAD` 重建 ZIP，重新运行内部 manifest、空库 migration、health、合成演示闭环和备份恢复。最终归档的完整 SHA-256、最终 commit、实际计数和时间写入归档旁的 `esg-agent-1.5-attestation.json`；该旁路证明不放回 ZIP，也不加入 Git，因此不存在自引用 hash。

`esg-agent-1.5-SHA256SUMS.txt` 至少列出最终 ZIP 与旁路证明文件。发布前再次验证：

```powershell
Get-FileHash tmp/release/esg-agent-1.5-windows-x64.zip -Algorithm SHA256
Get-Content tmp/release/esg-agent-1.5-SHA256SUMS.txt
git status --short
```

预期：tracked worktree 无差异；`首页.png` 仍为未跟踪；归档与旁路证明只存在于被忽略的 `tmp/release/`。

- [ ] **Step 12：建立发布停止点**

向用户汇报：最终 commit、所有门禁结果、归档 SHA-256、Git/工作区/远端状态、排除资产和剩余限制。此处必须停止并等待用户明确批准。

获得批准后才可分别执行：

```powershell
git tag -a v1.5 -m "ESG-Agent 1.5 reproducible delivery"
git push origin main
git push origin v1.5
```

tag、push 和托管平台 release 是三个外部状态变更，应按用户批准范围执行；没有批准时一个都不执行。

创建 tag 后重新构建一次归档，结果必须与批准前的 ZIP SHA-256 相同；随后把旁路证明的 `git_tag` 更新为 `v1.5` 并重新生成 `SHA256SUMS.txt`。tag 本身不得改变归档 payload。

## 17. 提交拆分

计划采用以下小步提交，每批先通过最相关门禁：

1. `docs: plan reproducible delivery and migration`：仅本计划，用户批准后提交。
2. `chore: pin reproducible delivery toolchain`：版本文件和发布策略。
3. `chore: harden delivery configuration defaults`：环境模板和 PostgreSQL Compose。
4. `feat: make runtime report paths portable`：路径序列化、兼容读取和迁移工具。
5. `feat: add database migration and recovery tooling`：空库迁移、备份和恢复。
6. `feat: add Windows delivery lifecycle scripts`：preflight、安装、启动、停止和 health。
7. `feat: add one-click Windows launcher`：C# 源码、应用 manifest、构建脚本、已核验 EXE 和 launcher manifest。
8. `test: add asset-safe delivery demo flow`：合成 PDF 和最小产品闭环。
9. `feat: build deterministic delivery archives`：归档、manifest 和 checksum。
10. `docs: add 1.5 delivery and migration runbooks`：安装、运维、资产和 Docker 评估。
11. `chore: prepare 1.5 delivery metadata`：最终版本同步和锁文件。
12. `test: add clean 1.5 delivery harness`：隔离验收编排与未执行记录结构。
13. `docs: record 1.5 delivery acceptance`：候选验收事实；最终归档事实写入旁路证明。

不得把计划提交、代码提交、tag 和 push 合并成一次不可审查的动作。

## 18. 回滚策略

### 18.1 代码与发布包

- 每个批次均为独立 commit；某批失败时停止后续实施，保留日志和差异供审查。
- 已发布版本回滚使用旧 ZIP、旧 checksum、旧 tag 和与其兼容的数据库备份成套恢复。
- 启动器失败时直接使用同一交付目录的 PowerShell 生命周期脚本；EXE、C# 源码和 launcher manifest 只能从同一 commit 成套恢复，不能单独替换二进制。
- 不执行 `git reset --hard` 或覆盖用户工作区；回滚通过新提交或独立旧版本目录完成。

### 18.2 数据库

- 升级真实 main 数据库前必须生成并验证备份。
- Alembic downgrade 只在唯一临时数据库验证 `0012 → 0011 → 0012`，不作为真实业务库首选回滚方式。
- 真实迁移失败时停止前后端，保留失败库，恢复到新数据库并验证后再切换连接。
- 旧版本代码不得直接连接已经升级且未验证兼容的数据库。

### 18.3 运行文件

- 源码发布包不含运行文件。
- 完整本地恢复需要数据库 dump 与经授权的 runtime 文件同时存在。
- 旧绝对路径先 dry-run、再 SHA-256 匹配、最后显式确认转换；无法唯一匹配的记录保持不变并进入人工处理清单。

## 19. 最终终止条件

只有以下条件全部满足，阶段才能完成：

1. 授权接收方仅依据 ZIP、checksum 和文档完成恢复。
2. Git commit、`v1.5` tag、内部 `1.5.0` 元数据和归档清单一致。
3. Python、Node、pnpm、uv、.NET Framework、C# 编译器指纹、Docker Desktop/Engine/Compose、PostgreSQL、pgvector 和可选 OCR 版本可核对；恢复来源与接收方目标明确分列。
4. 空 PostgreSQL 数据库升级到 `0012_chunk_embeddings`。
5. 临时库 `0012 → 0011 → 0012` 验证通过，真实库回滚使用备份恢复。
6. 配置端口不受监听冲突或 Windows 排除范围影响，后端、前端、数据库 health 全部通过；C# 启动器能够幂等启动、查询状态、停止当前目录应用并打开一次本机网页。
7. 合成演示样本完成上传、metadata、分析、核查、人工复核、整改、草稿、下载和审计。
8. 结构保持 `577/499/78/0`，维护者语义门禁保持 0 global fallback、0 新增 false disclosed、0 新增 wrong source page。
9. 演示运行没有 DeepSeek、SiliconFlow、OCRmyPDF 或 VLM 调用。
10. 发布包不含真实密钥、本机数据库、未授权资产、运行缓存、日志或 `首页.png`。
11. 内外 checksum、版本清单、launcher manifest 和文件清单全部一致；同一 commit 连续生成的 ZIP SHA-256 相同。
12. 数据库与运行文件备份恢复在新目标环境验证成功，原 volume 身份和数据计数经过核对。
13. 后端测试与 Ruff、前端 lint/typecheck/test/build 全部完成，只有已登记的资产 skip 和两条既有 lint warning。
14. 干净环境自动验收与桌面/移动浏览器人工验收均通过。
15. 文档、最终 commit、工作区和远端状态一致。
16. 用户明确确认交付形式、最终归档和发布动作。

任一条件未满足时，状态保持“实施中”或“阻塞”，不得标记交付完成。

## 20. 明确不做事项

- 不扩展 GRI checklist、577 项口径、规则判定或风险规则。
- 不调整 AI Prompt、模型、候选筛选、规则/AI/人工三层优先级或正式导出口径。
- 不自动启用 DeepSeek、embedding、OCR 或 VLM。
- 不建设通用 OCR、Docling、PaddleOCR、RAG Phase 2 或后台任务队列。
- 不建设云部署、企业 SSO、多租户、高可用、监控平台或公网生产安全体系。
- 不制作完全离线依赖仓库、`setup.exe`、Windows 安装/卸载程序或全栈 Docker 镜像；本阶段只提供无需安装的 C# 轻量启动入口。
- 不建设启动器托盘常驻、自动更新、遥测、管理员提权、Windows 服务注册或自动 migration。
- 不打包当前本机数据库、真实业务报告、GRI 原始标准、非公开模型响应或运行时缓存。
- 不覆盖、删改原始报告和标准资产。
- 不处理 `首页.png`。
- 未经用户明确批准，不创建 tag、不发布 release、不 push。

## 21. 宏观执行顺序

```text
交付契约与工具链
  → 配置与 PostgreSQL 固定
  → 运行路径可迁移
  → 空库 migration 与备份恢复
  → Windows 生命周期脚本
  → C# 本机一键启动里程碑
  → 合法合成演示闭环
  → 确定性归档与 checksum
  → 接收方文档与 Docker 结论
  → 1.5 元数据同步
  → 等价干净环境与最终门禁
  → 用户发布确认
```

该顺序先解决身份和数据安全，再把 C# 启动器建立在可审计脚本之上，避免把服务管理逻辑锁进二进制。本机一键启动里程碑通过后可以先交付本地使用体验，但阶段状态继续为“实施中”；1.5 元数据只在进入最终干净验收前同步，验收通过后仍停在用户发布确认点，可以避免提前形成“已发布”事实。
