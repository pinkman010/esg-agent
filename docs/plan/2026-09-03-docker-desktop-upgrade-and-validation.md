# Docker Desktop 4.89.0 升级与自检实施计划

> **供自动化执行者使用：** 必须使用 `executing-plans` 逐项执行并记录结果。所有步骤使用复选框跟踪；任何停止条件触发后立即停止，不得继续升级或清理数据。

**目标：** 在保留 PostgreSQL 数据、Docker volume 和项目运行文件的前提下，将本机 Docker Desktop 从 4.80.0 升级到 4.89.0，并恢复、验证 ESG Agent 全部本地服务。

**执行架构：** 先采集可比较的业务与容器基线，再停止应用并生成逻辑备份；Docker 完全停止后复制数据盘，随后通过 winget 原位升级。升级后按照 Docker、volume、PostgreSQL、数据库、后端、前端的依赖顺序恢复，并逐层比对升级前基线。

**技术栈：** Windows PowerShell、winget、Docker Desktop、Docker Compose、PostgreSQL 16、Alembic、FastAPI/Uvicorn、Next.js/pnpm。

---

## 1. 影响范围与安全边界

- 预计服务中断 20–60 分钟；Windows 安装器可能弹出一次 UAC 确认。
- 允许停止和启动本项目的前端、后端、PostgreSQL 容器及 Docker Desktop。
- 允许在 `tmp/docker-desktop-upgrade-<timestamp>/` 创建数据库 dump、运行文件归档、Docker 数据盘副本、配置副本、校验值和检查日志。
- 禁止执行 `Reset to factory defaults`、`Clean up data`、`docker compose down -v`、`docker volume rm`、数据库 downgrade 或递归删除。
- 禁止删除或覆盖升级前备份；禁止把备份、密钥、`.env` 或本机路径提交到 Git。
- 外部模型、OCR、embedding 和 VLM 在整个流程中保持关闭。
- Git worktree 不能隔离 Docker Desktop 的主机级状态。本次根据用户明确授权在当前工作区执行，只新增和更新本计划文件。

## 2. 已确认的升级前基线

| 检查项 | 基线 |
| --- | --- |
| Docker Desktop | 4.80.0 |
| Docker Engine | 29.6.1 |
| Docker Compose | 5.1.4 |
| 目标 Docker Desktop | 4.89.0，winget 官方源 |
| PostgreSQL 容器 | `esg-agent-postgres-1`，运行中 |
| PostgreSQL volume | `esg-agent_postgres_data` |
| `esg_agent` | 77 份报告，`0012_chunk_embeddings` |
| `esg_agent_demo` | 9 份报告，`0012_chunk_embeddings` |
| 后端 | `http://127.0.0.1:8200` |
| 前端 | `http://localhost:3000` |
| Docker 数据盘 | `$env:LOCALAPPDATA\Docker\wsl\disk\docker_data.vhdx`，约 4.09 GiB |
| 系统盘可用空间 | 约 338 GiB |
| 运行中的 WSL 发行版 | 仅 `docker-desktop` |

## 3. 停止条件

以下任一条件出现时立即停止，并保留当前状态和日志：

1. 两个数据库任一不存在，或报告数、Alembic revision 与基线不一致。
2. 数据库 dump 无法通过 `pg_restore --list` 验证，或校验值生成失败。
3. Docker volume 名称、数据盘路径或容器挂载与基线不一致。
4. 停止 Docker 后数据盘仍被占用，无法生成一致副本。
5. 下载的安装包不是 Docker 官方发布者、版本不是 4.89.0，或 SHA-256 与 winget 官方源清单不符。
6. 安装器失败、要求重启 Windows，或升级后 Docker daemon 无法在限定时间内恢复。
7. 升级后原 volume、数据库、报告数或 migration revision 发生变化。

## 4. 执行步骤

### Task 1：建立审计目录并固化基线

- [x] **Step 1：创建唯一备份目录**

```powershell
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backupDir = Join-Path 'tmp' "docker-desktop-upgrade-$stamp"
New-Item -ItemType Directory -Path $backupDir | Out-Null
```

预期：目录位于项目 `tmp/` 下，且不覆盖任何已有备份。

- [x] **Step 2：保存版本、容器、volume、端口和数据库基线**

```powershell
docker version | Out-File "$backupDir/docker-version-before.txt" -Encoding utf8
docker compose version | Out-File "$backupDir/compose-version-before.txt" -Encoding utf8
docker compose ps --format json | Out-File "$backupDir/compose-ps-before.jsonl" -Encoding utf8
docker volume inspect esg-agent_postgres_data |
  Out-File "$backupDir/volume-before.json" -Encoding utf8
Get-NetTCPConnection -State Listen -LocalPort 3000,5432,8200 |
  Select-Object LocalAddress,LocalPort,OwningProcess |
  ConvertTo-Json | Out-File "$backupDir/ports-before.json" -Encoding utf8
```

预期：Docker daemon 可用，volume 存在，三个服务端口均处于监听状态。

### Task 2：停止应用并生成可恢复备份

- [x] **Step 1：停止本项目后端和前端**

仅停止命令行包含当前项目目录，且分别监听 8200、3000 的进程：

```powershell
$projectRoot = (Resolve-Path '.').Path
foreach ($port in 8200,3000) {
  $listeners = @(Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue)
  foreach ($listener in $listeners) {
    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)"
    if (-not $process.CommandLine.Contains($projectRoot)) {
      throw "端口 $port 的进程不属于当前项目，停止执行"
    }
    Stop-Process -Id $listener.OwningProcess
  }
}
```

停止后再次检查端口；5432 必须继续监听以完成数据库备份。

- [x] **Step 2：在 PostgreSQL 容器内生成两个自包含 dump**

```powershell
docker exec esg-agent-postgres-1 sh -lc 'pg_dump -U "$POSTGRES_USER" -d esg_agent -Fc -f /tmp/esg_agent.dump'
docker exec esg-agent-postgres-1 sh -lc 'pg_dump -U "$POSTGRES_USER" -d esg_agent_demo -Fc -f /tmp/esg_agent_demo.dump'
docker exec esg-agent-postgres-1 sh -lc 'pg_restore --list /tmp/esg_agent.dump >/dev/null && pg_restore --list /tmp/esg_agent_demo.dump >/dev/null'
docker cp esg-agent-postgres-1:/tmp/esg_agent.dump "$backupDir/esg_agent.dump"
docker cp esg-agent-postgres-1:/tmp/esg_agent_demo.dump "$backupDir/esg_agent_demo.dump"
```

预期：两个 dump 均非空，`pg_restore --list` 返回 0。

- [x] **Step 3：备份运行文件、Docker 设置和升级前清单**

```powershell
tar.exe -czf "$backupDir/backend-runtime.tar.gz" -C backend/data runtime
tar.exe -tf "$backupDir/backend-runtime.tar.gz" | Select-Object -First 1
Copy-Item "$env:APPDATA\Docker\settings-store.json" $backupDir -ErrorAction SilentlyContinue
Get-FileHash -Algorithm SHA256 "$backupDir/esg_agent.dump",
  "$backupDir/esg_agent_demo.dump","$backupDir/backend-runtime.tar.gz" |
  Export-Csv "$backupDir/checksums-before.csv" -NoTypeInformation -Encoding utf8
```

预期：运行文件归档可列出内容，三个备份文件均有 SHA-256。

### Task 3：停止数据库与 Docker，并复制数据盘

- [x] **Step 1：停止 PostgreSQL 容器**

```powershell
docker compose stop postgres
docker compose ps --format json |
  Out-File "$backupDir/compose-ps-stopped.jsonl" -Encoding utf8
```

预期：容器状态为 exited/stopped，5432 不再监听。

- [x] **Step 2：完全停止 Docker Desktop**

```powershell
docker desktop stop
```

等待 Docker Desktop 后端进程结束。由于升级前已确认只有 `docker-desktop` 在运行，残留时只允许执行：

```powershell
wsl.exe --terminate docker-desktop
```

不得使用 `wsl --unregister`。

- [x] **Step 3：复制 Docker 数据盘并生成校验值**

```powershell
$dockerDisk = "$env:LOCALAPPDATA\Docker\wsl\disk\docker_data.vhdx"
Copy-Item -LiteralPath $dockerDisk -Destination "$backupDir/docker_data.vhdx"
Get-FileHash -Algorithm SHA256 "$backupDir/docker_data.vhdx" |
  Export-Csv "$backupDir/docker-data-checksum.csv" -NoTypeInformation -Encoding utf8
```

预期：副本约 4.09 GiB，SHA-256 成功生成。复制失败时不升级。

### Task 4：保持 per-user 模式升级 Docker Desktop

- [x] **Step 1：从 winget 官方源下载并校验安装器**

```powershell
$installerDir = Join-Path $backupDir 'installer'
New-Item -ItemType Directory -Path $installerDir | Out-Null
winget download --id Docker.DockerDesktop --exact --source winget --version 4.89.0 --scope machine --architecture x64 --download-directory $installerDir --accept-source-agreements --accept-package-agreements
$installer = @(Get-ChildItem -LiteralPath $installerDir -Recurse -File -Filter '*.exe')
if ($installer.Count -ne 1) { throw '安装器数量不符合预期' }
$expectedHash = '854626704AF28A160D5AF68B96B3E32EACF08AB397CE6C12EB02A04788D73681'
$actualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $installer[0].FullName).Hash
if ($actualHash -ne $expectedHash) { throw '安装器 SHA-256 与官方清单不一致' }
```

预期：安装器来自 `desktop.docker.com`，SHA-256 与 winget 4.89.0 清单一致。

- [x] **Step 2：按原 per-user 范围执行原位升级**

当前版本登记在 HKCU，安装位置是 `$env:LOCALAPPDATA\Programs\DockerDesktop`。winget 清单仅暴露 machine 范围，直接执行 `winget upgrade` 会返回 `0x8a150010`；根据 Docker 官方 Windows 安装说明，下载同一安装器后使用 `install --user` 保持 per-user 模式：

```powershell
$installProcess = Start-Process -FilePath $installer[0].FullName -Wait -PassThru -WindowStyle Hidden -ArgumentList 'install','--user','--quiet'
if ($installProcess.ExitCode -ne 0) { throw "Docker Desktop 安装器失败：$($installProcess.ExitCode)" }
```

预期：安装器退出码为 0，不要求切换到 all-users，不卸载现有 Docker Desktop。

- [x] **Step 3：确认安装登记版本和范围**

```powershell
winget list --id Docker.DockerDesktop --exact --accept-source-agreements
$installed = Get-ItemProperty 'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Docker Desktop'
$installed | Select-Object DisplayVersion,Publisher,InstallLocation
```

预期：已安装版本为 4.89.0，发布者为 Docker Inc.，安装位置仍为 `$env:LOCALAPPDATA\Programs\DockerDesktop`。

### Task 5：恢复 Docker 与 PostgreSQL

- [x] **Step 0：处理 4.80.0 遗留的不可访问 socket**

4.89.0 首次启动实际失败：新版后端尝试把旧 `dockerInference` 重命名为 `.stale`，Windows 仍返回无法访问。日志与时间戳确认 `dockerInference`、`dockerEthernetVfkit`、`userAnalyticsOtlpHttp.sock` 和 `engine.sock` 均由 4.80.0 在升级前创建；`sailor-ingest.sock` 由 4.89.0 本次启动创建。确认 Docker Desktop 进程已完全退出后，只允许在所有条目均为零字节 `ReparsePoint`、没有子目录且名称严格符合清单时，把两个临时目录整体重命名留档：

```powershell
$socketStamp = Get-Date -Format 'yyyyMMdd-HHmmss'
Move-Item -LiteralPath "$env:LOCALAPPDATA\Docker\run" -Destination "$env:LOCALAPPDATA\Docker\run.stale-$socketStamp"
Move-Item -LiteralPath "$env:LOCALAPPDATA\docker-secrets-engine" -Destination "$env:LOCALAPPDATA\docker-secrets-engine.stale-$socketStamp"
```

允许的 `Docker\run` 条目只有 `dockerInference`、`dockerEthernetVfkit`、`userAnalyticsOtlpHttp.sock`、`sailor-ingest.sock`；`docker-secrets-engine` 条目只有 `engine.sock`。任何其他内容出现时立即停止。该步骤不触碰 `docker_data.vhdx`、volume、容器或数据库备份。

- [x] **Step 1：启动 Docker Desktop 并等待 daemon**

```powershell
docker desktop start
```

每 5 秒执行一次 `docker info`，最长等待 180 秒。超时后停止，不执行 reset。

- [x] **Step 2：核验原 volume 和容器后启动 PostgreSQL**

```powershell
docker volume inspect esg-agent_postgres_data
docker compose ps -a --format json
docker compose up -d postgres
```

预期：原 volume 可见，`esg-agent-postgres-1` 使用原 volume，`pg_isready` 通过。

执行记录：Compose 5.5.0 因升级前后容器元数据差异重建了 PostgreSQL 容器，容器 ID 从 `8c158cacc396` 变为 `34a60391f029`。暂停后核验确认 Compose config hash、实际镜像 ID、环境配置哈希、原 volume 名称、创建时间和挂载路径均一致；数据库业务基线也完全一致，因此继续执行。该异常及完整 inspect 对比已保存到本次审计目录。

- [x] **Step 3：比对数据库业务基线**

对 `esg_agent` 和 `esg_agent_demo` 分别查询 `reports` 数量和 `alembic_version`。预期严格等于 77/9 和 `0012_chunk_embeddings`。

### Task 6：恢复应用并完成端到端自检

- [x] **Step 1：启动后端 8200**

在 `backend/` 中以现有虚拟环境启动：

```powershell
$env:APP_ENV="demo"
$env:DATABASE_URL="postgresql+psycopg://esg_agent:esg_agent@localhost:5432/esg_agent_demo"
$env:UPLOAD_DIR="backend/data/runtime/demo/uploads"
$env:DERIVED_DIR="backend/data/runtime/demo/derived"
$env:OCR_ENABLED="false"
./.venv/Scripts/uvicorn.exe src.main:app --reload --host 127.0.0.1 --port 8200
```

预期：`http://127.0.0.1:8200/api/health` 返回 `status=ok`、`app_env=demo`。

- [x] **Step 2：启动前端 3000**

在 `frontend/` 中设置 `NEXT_PUBLIC_API_BASE_URL=http://localhost:8200` 后执行 `pnpm dev`。

预期：`http://localhost:3000` 返回 HTTP 200。

- [x] **Step 3：完成服务和数据自检**

验证 Docker Desktop/Engine/Compose 版本、PostgreSQL readiness、两个数据库、报告数、Alembic revision、后端 health、OpenAPI 路径数量、前端 HTTP 状态以及 3000/5432/8200 监听状态。输出写入备份目录，不记录密钥。

### Task 7：记录结果并保护备份

- [x] **Step 1：把实际结果追加到本计划**

记录执行时间、升级版本、备份目录的相对路径、备份校验结论、服务状态、数据比对结果、异常和遗留风险。

- [x] **Step 2：检查 Git 工作区**

```powershell
git -c core.quotepath=false status --short --branch --untracked-files=all
```

预期：除本计划与原有 `首页.png` 外，不出现新项目文件；`tmp/` 备份不得进入 Git。

## 5. 回退策略

1. 升级前失败：保持 Docker 4.80.0，不修改数据，修复备份问题后重新计划。
2. 安装失败但 Docker 可启动：重新启动 4.80.0，核对原 volume 和数据库；保留所有备份。
3. 4.89.0 启动失败：收集诊断日志，不执行 factory reset；根据安装器能力恢复旧版本，或在干净环境使用 dump 恢复。
4. volume 不可见或数据不一致：立即停止应用，不创建同名 volume；优先检查数据盘挂载，必要时使用完整 VHDX 副本恢复。
5. 数据库可见但业务基线不一致：停止写入，保留现场，使用逻辑 dump 恢复到新数据库后比对，禁止覆盖原数据库。

## 6. 实际执行结果

- 执行完成时间：2026-09-03T20:59:18+08:00。
- 审计与备份目录：`tmp/docker-desktop-upgrade-20260903-202834/`；该目录受 Git 忽略，不进入版本库。
- Docker Desktop 已从 4.80.0 升级到 4.89.0，保持 per-user 模式和原用户安装位置；Docker Engine 为 29.7.2，Docker Compose 为 5.5.0。
- winget 能发现 4.89.0，但官方清单只暴露 machine 范围安装器，直接升级返回 `0x8a150010`。随后通过 winget 下载同一官方安装器，SHA-256 为 `854626704AF28A160D5AF68B96B3E32EACF08AB397CE6C12EB02A04788D73681`，再使用官方 `install --user --quiet` 完成原位升级。
- 升级前生成 `esg_agent.dump`、`esg_agent_demo.dump`、运行文件归档和 4.11 GB Docker 数据盘副本；逻辑备份回传 PostgreSQL 后通过 `pg_restore --list`，全部文件及 VHDX 的 SHA-256 在最终自检中保持一致。
- 4.89.0 首次启动仍遇到 4.80.0 已存在的 `dockerInference` reparse-point socket。新版已尝试重命名旧 socket，但 Windows 拒绝访问。确认所有 Docker 进程退出并严格核对目录内容后，将两个临时 socket 目录重命名留档；第二次启动成功，之后日志中没有新的 stuck-socket 启动错误。
- Compose 5.5.0 恢复 PostgreSQL 时重建了容器，容器 ID 从 `8c158cacc396` 变为 `34a60391f029`。核验确认实际镜像 ID、Compose config hash、环境配置哈希、原 volume 名称、创建时间和挂载路径均未变化。
- `esg_agent` 保持 77 份报告，`esg_agent_demo` 保持 9 份报告；两个数据库的 Alembic revision 均为 `0012_chunk_embeddings`。
- 后端首次恢复时因未加载 demo 会话变量而显示 `app_env=main`，自检立即发现后停止该进程；重新加载显式 demo 环境后恢复为 `status=ok`、`app_env=demo`。期间未执行写操作或外部模型调用。
- 最终状态：Docker Desktop `running`，PostgreSQL readiness 通过，后端 `http://127.0.0.1:8200/api/health` 返回 `ok/demo`，OpenAPI 为 40 条路径，前端 `http://localhost:3000` 返回 HTTP 200，3000/5432/8200 均处于监听状态。
- 全程未执行 factory reset、数据清理、volume 删除、数据库 downgrade 或原始资产修改。
- Git 最终检查确认 `tmp/docker-desktop-upgrade-20260903-202834/` 受 `.gitignore` 保护。本次操作新增本计划；原有 `首页.png` 继续保持未跟踪。检查时另有并发任务修改 `docs/plan/reproducible-delivery-and-migration-plan.md`，该改动与 Docker 升级无关，本次未覆盖、暂存或提交。
