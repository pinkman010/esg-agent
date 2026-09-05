# ESG-Agent 1.5 本地运维与恢复

## 1. 运行边界

本交付面向单机 Windows demo 运行。PowerShell 脚本是可审计的唯一生命周期实现，`ESG-Agent.exe` 只映射固定动作。数据库由 Docker Compose 管理，后端和前端作为隐藏的本机进程运行。

关键相对位置：

| 内容 | 位置 |
| --- | --- |
| 本地配置 | `.env`，不提交、不打包 |
| preflight 与服务日志 | `backend/data/runtime/logs/` |
| 进程与构建状态 | `backend/data/runtime/delivery/` |
| demo 上传和派生文件 | `backend/data/runtime/demo/` |
| 默认备份 | `backups/` |
| 临时验收输出 | `tmp/` |

## 2. 启动、检查与停止

```powershell
./ESG-Agent.exe --no-browser
./ESG-Agent.exe --status
./ESG-Agent.exe --stop
```

详细诊断使用：

```powershell
./scripts/delivery/Test-Preflight.ps1
./scripts/delivery/Test-EsgAgent.ps1
Get-Content ./backend/data/runtime/logs/preflight.json
```

`Test-EsgAgent.ps1` 必须同时返回 `APP_ENV=demo`、migration `0012_chunk_embeddings`、后端 health、匹配的 OpenAPI 版本、前端 HTTP 200 和外部能力关闭状态。

## 3. 数据库分类、升级和回滚

- `esg_agent`：维护者正式/历史运行库，不进入发布包。
- `esg_agent_demo`：接收方 demo 库，用于本地演示。
- `esg_agent_test`：临时 migration 或自动测试库，不承载正式数据。

空库初始化：

```powershell
./scripts/delivery/Initialize-Database.ps1 -Environment demo -VolumeMode new
```

已确认 volume 初始化或补 migration：

```powershell
./scripts/delivery/Initialize-Database.ps1 -Environment demo -VolumeMode existing
```

真实库不直接执行 Alembic downgrade。迁移前先停前后端、生成备份；失败时保留失败库与日志，在新目标库恢复升级前备份，再切换配置。迁移 round-trip 只允许 `Environment=test` 的隔离库。

## 4. 备份与恢复

只备份数据库：

```powershell
./scripts/delivery/New-EsgAgentBackup.ps1 -Environment demo
```

包含上传、派生和导出运行文件的备份可能含非公开报告，必须单独授权：

```powershell
./scripts/delivery/New-EsgAgentBackup.ps1 -Environment demo -IncludeRuntime
```

每个备份 ZIP 都有外部 `.sha256`，内部包含 `backup-manifest.json` 和 `SHA256SUMS.txt`。恢复只允许写入尚不存在的新数据库，目标名必须双重确认：

```powershell
./scripts/delivery/Stop-EsgAgent.ps1
./scripts/delivery/Restore-EsgAgentBackup.ps1 `
  -ArchivePath ./backups/<approved-backup>.zip `
  -TargetDatabase esg_agent_demo_restore `
  -ConfirmDatabase esg_agent_demo_restore
```

路径规范化默认只做 dry-run。确认旧绝对路径能够按文件哈希唯一匹配当前 runtime 后，才增加 `-ApplyPathNormalization`。恢复成功并完成 health 与报告计数核对前，不删除原库或原备份。

## 5. 故障矩阵

| 故障 | 检查点 | 处理与回滚 |
| --- | --- | --- |
| 工具安装失败 | preflight 错误码、实际版本、安装日志 | 补齐 `delivery/toolchain-lock.json` 固定版本后重跑；不修改 lockfile 绕过 |
| Docker daemon 无法启动 | Desktop 版本、进程、诊断日志、残留 socket | 完全退出 Docker 后按第 6 节人工检查并重命名临时 socket 目录；脚本不自动处理 |
| Docker Desktop 升级 | 数据库与运行文件备份、volume 身份、报告计数、安装包来源 | 单独审批后人工升级；失败时保留数据盘与备份，恢复旧 Desktop 或转移到独立验收机；禁止 factory reset |
| Docker volume 不可见 | `docker volume ls`、`docker ps -a`、数据盘状态 | 停止创建同名新 volume，先恢复或确认原数据；禁止 `Clean up data` |
| 启动器无法运行 | launcher manifest、EXE SHA-256、.NET Framework、系统 Windows PowerShell、相对目录 | 运行 `Build-Launcher.ps1 -VerifyTrackedArtifact`；直接使用等价 PowerShell 脚本；不从非交付来源替换 EXE |
| 启动器重复点击 | 启动锁、process manifest、综合 health | 等待同目录已有启动完成；不得创建第二组服务进程 |
| 端口被进程占用 | `.env` 中端口、监听 PID | 修改本地端口或停止已确认进程；交付脚本不代替用户杀未知进程 |
| Windows 排除端口 | IPv4/IPv6 excluded port ranges | 不修改系统排除规则；在 `.env` 选择可用端口并重新执行初始化以重建前端 API 地址 |
| PostgreSQL 连接失败 | Compose 状态、`pg_isready`、容器日志、数据库名 | 检查 `.env` 和端口，不输出密码；保留 volume |
| migration 失败 | Alembic revision、升级日志、备份 checksum | 停止服务，恢复升级前备份到新库；真实库不直接 downgrade |
| Ghostscript/Tesseract 缺失 | OCR capability 与语言包 | 保持 OCR 关闭继续默认链路；确需 OCR 时另行安装并取得请求授权 |
| 前端构建失败 | Node/pnpm 版本、frozen lock、build log | 删除范围只限已确认的本地依赖缓存，按 frozen lock 重装；不得升级依赖绕过 |
| 后端启动失败 | stderr、Python 版本、数据库 head | 修复配置或 migration 后重启，不清库 |
| 恢复上一版本 | 旧归档 checksum、旧数据库备份、兼容 revision | 旧代码与对应备份成对恢复，不让旧代码共享已升级数据库 |
| 数据库恢复失败 | ZIP 与内外 checksum、目标库是否为空 | 保留原库，删除或隔离失败的新目标库需单独确认，再换新目标重试 |

## 6. Docker 残留 socket 的人工恢复

该流程只处理 Docker Desktop 临时 socket，不接触 Docker 数据盘、volume、镜像或业务文件。

1. 在错误窗口选择退出 Docker Desktop，确认 Docker Desktop、backend 和相关辅助进程已经结束。
2. 检查 `$env:LOCALAPPDATA\Docker\run` 与 `$env:LOCALAPPDATA\docker-secrets-engine`。只有目录内全部是预期、零字节、`ReparsePoint` socket 时才继续。
3. `Docker\run` 的已知项包括 `dockerInference`、`dockerEthernetVfkit`、`userAnalyticsOtlpHttp.sock`；一次失败启动还可能留下同批次的 `sailor-ingest.sock`。secrets 目录只允许 `engine.sock`。
4. 将整个临时目录重命名为带时间戳的 `.stale-*` 备份；不删除目录。存在其他文件、子目录或非零内容时立即停止。
5. 启动 Docker Desktop，依次核对 `docker info`、原 volume、原容器、`pg_isready`、数据库名、Alembic revision 和报告计数。

不要选择 `Reset to factory defaults` 或 `Clean up data`。不要删除或移动 Docker 数据盘。完整、经实际执行的恢复记录保留在 `docs/DEVELOPMENT.md` 的 2026-09-03 开发日志。

## 7. Docker Desktop 升级边界

升级属于独立高风险动作，不由交付脚本执行。升级前保存：

- demo 与正式库 custom dump 及 checksum；
- 授权范围内的 runtime 备份；
- Docker 数据盘备份；
- Desktop/Engine/Compose 版本、容器 ID、镜像 ID、volume 名、挂载点、Alembic revision 和报告计数。

升级后逐项复核。容器被重建时先停应用验收，确认仍挂载原 volume。缺少原 volume 时禁止创建同名空 volume。

## 8. 密钥、日志与问题移交

日志和验收输出不得复制真实 `.env` 内容。问题移交只提供错误码、工具版本、相对日志路径、非敏感 health、commit、archive checksum、migration revision 和经授权的计数。

DeepSeek、SiliconFlow、embedding、OCR 和 VLM 在 demo 交付中保持关闭。任何启用行为都需要独立授权，且不能覆盖规则结果或人工快照。
