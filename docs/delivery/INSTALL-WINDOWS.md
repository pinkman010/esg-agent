# ESG-Agent 1.5 Windows 安装与首次启动

## 1. 适用范围

本文面向只拿到 `esg-agent-1.5-windows-x64.zip` 和 `esg-agent-1.5-SHA256SUMS.txt` 的授权接收方。1.5 当前是可复现交付候选，尚未完成等价干净环境验收，也未创建正式 tag 或 Release。

交付包提供源码、锁文件、配置模板、数据库 migration、PowerShell 生命周期脚本、合成演示报告和 `ESG-Agent.exe`。启动器只负责调用已交付脚本、显示进度和打开本机网页，不安装或升级任何系统依赖。

## 2. 已验证环境

接收方环境以 `delivery/toolchain-lock.json` 为准：

| 组件 | 固定或支持基线 | 用途 |
| --- | --- | --- |
| 操作系统 | Windows 11 x64 | 当前接收方支持范围 |
| Windows PowerShell | 5.1 或更高 | 安装、启停、备份与恢复 |
| .NET Framework | 4.8.1，Release key 不低于 533320 | 运行 `ESG-Agent.exe` |
| uv | 0.9.28 | 安装 Python 3.11.14 和后端锁定依赖 |
| Python | 3.11.14 | 后端运行时，由 uv 管理 |
| Node.js | 24.15.0 | 前端构建与运行 |
| Corepack | 0.34.6 | 提供固定 pnpm 入口 |
| pnpm | 11.19.0 | 前端锁定依赖 |
| Docker Desktop | 4.89.0 或更高 | 运行 PostgreSQL/pgvector |
| PostgreSQL / pgvector | 16.14 / 0.8.4 | 由固定 digest 的 Compose 镜像提供 |
| 浏览器 | 已验证版本或更高稳定版 Chrome/Edge | 本机网页访问 |

Ghostscript、Tesseract、`chi_sim+eng+osd` 语言包和 OCRmyPDF 是可选 OCR 依赖。默认 `OCR_ENABLED=false`，缺少这些组件不阻断普通数字 PDF 演示。

交付脚本统一通过 `corepack pnpm` 调用固定版本，接收方不需要单独安装全局 pnpm，也不依赖 Corepack 是否成功生成 `pnpm.cmd` shim。首次初始化仍需联网下载或读取 Corepack 缓存中的 pnpm 11.19.0。

## 3. 网络和预计耗时

首次初始化需要访问 Python 与 Node 软件源；本机尚无固定 PostgreSQL 镜像时还要拉取镜像。耗时主要取决于网络、磁盘和前端构建性能，不能给出统一时长保证。重复启动不重新安装依赖，通常只做 preflight、启动现有容器和本地服务。

完全离线依赖缓存、Windows 安装程序和 `setup.exe` 不属于当前交付。依赖下载失败时保留日志并重试固定版本，不更新 lockfile 绕过问题。

## 4. 校验、解压、初始化

在归档与 checksum 文件所在目录执行：

```powershell
Get-FileHash ./esg-agent-1.5-windows-x64.zip -Algorithm SHA256
Get-Content ./esg-agent-1.5-SHA256SUMS.txt
Expand-Archive ./esg-agent-1.5-windows-x64.zip ./esg-agent-1.5
cd ./esg-agent-1.5
./scripts/delivery/Test-Preflight.ps1
./scripts/delivery/Initialize-Environment.ps1
./ESG-Agent.exe --no-browser
./scripts/delivery/Test-EsgAgent.ps1
```

第一条命令的哈希必须与 checksum 文件一致。解压后的 `release-manifest.json` 可逐文件核对交付内容。preflight 在尚未初始化时会报告 `INITIALIZATION_REQUIRED:*` warning；基础工具、Docker、固定版本或端口不满足时仍会失败。

`Initialize-Environment.ps1` 默认创建：

- 本地且被 Git 忽略的 `.env`，包含随机数据库密码；
- 独立的 demo Compose project 和新 PostgreSQL volume；
- `backend/.venv` 与 `frontend/node_modules`；
- 固定后端依赖、固定前端依赖和 production build；
- 空 `esg_agent_demo` 数据库，并升级至 `0012_chunk_embeddings`。

初始化不会打印数据库密码，不会填入模型密钥，并强制保持：

```text
APP_ENV=demo
OCR_ENABLED=false
EMBEDDING_ENABLED=false
OPENAI_COMPATIBLE_API_KEY=
EMBEDDING_API_KEY=
```

## 5. 日常最短启动方式

初始化成功后，双击交付根目录的 `ESG-Agent.exe`。启动器确认 PostgreSQL、后端、前端和 health 后，为本次双击打开一次本机网页。服务已健康时重复双击会重新打开网页，但不会创建第二组进程。

等价的命令行入口为：

```powershell
./ESG-Agent.exe --no-browser
./ESG-Agent.exe --status
./ESG-Agent.exe --stop

./scripts/delivery/Start-EsgAgent.ps1 -OpenBrowser
./scripts/delivery/Test-EsgAgent.ps1
./scripts/delivery/Stop-EsgAgent.ps1
```

普通停止只结束前端和后端，保留 PostgreSQL 与 volume。需要同时停止本交付目录的数据库容器时显式执行：

```powershell
./scripts/delivery/Stop-EsgAgent.ps1 -IncludeDatabase
```

## 6. 运行合成演示闭环

交付包中的 `demo/esg-agent-synthetic-report-2025.pdf` 是虚构、脱敏、固定 8 页的工程样本。它只用于验证上传到草稿下载的产品流程，不代表 GRI 认证、规则正确率样本或专业 ESG 结论。

```powershell
cd ./backend
$backendPort = if ($env:BACKEND_PORT) { [int]$env:BACKEND_PORT } else { 8000 }
uv run --no-sync python -m src.tools.verify_delivery_flow `
  --api-base "http://localhost:$backendPort" `
  --report ../demo/esg-agent-synthetic-report-2025.pdf `
  --output data/runtime/acceptance/delivery-flow.json
cd ..
```

该客户端固定发送 `confirm_llm=false` 和 `enable_ocr=false`，核对 `577/499/78/0`、AI 建议为 0、人工快照、整改任务、草稿文件 checksum 和审计事件；不会创建正式输出。

## 7. 重复初始化和边界

已有本地 `.env` 和已确认 volume 时，显式复用：

```powershell
./scripts/delivery/Initialize-Environment.ps1 `
  -Environment demo `
  -VolumeMode existing `
  -UseExistingConfig
```

不要把其他安装目录的 `.env`、volume 或 `backend/data/runtime/` 直接复制进来。数据库迁移、备份恢复和故障处理见 `docs/delivery/OPERATIONS.md`。
