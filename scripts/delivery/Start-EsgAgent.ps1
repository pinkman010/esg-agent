param(
  [switch]$OpenBrowser
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "Delivery.Common.ps1")

$projectRoot = Get-EsgProjectRoot
$rootHash = Get-EsgRootHash
$mutex = New-Object System.Threading.Mutex($false, "Local\ESGAgent-$rootHash")
$lockTaken = $false
$windowsPowerShell = Join-Path $env:WINDIR "System32\WindowsPowerShell\v1.0\powershell.exe"

function Open-EsgLocalFrontendOnce {
  param(
    [Parameter(Mandatory)][string]$Url,
    [Parameter(Mandatory)][string]$ManifestPath
  )

  $uri = [uri]$Url
  if ($uri.Scheme -ne "http" -or $uri.Host -notin @("localhost", "127.0.0.1")) {
    throw "BROWSER_URL_INVALID: only a local HTTP frontend URL may be opened"
  }
  if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) {
    throw "PROCESS_MANIFEST_MISSING: cannot record browser state"
  }
  $manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
  Start-Process -FilePath $Url
  $manifest.browser_opened = $true
  Write-EsgJsonFile -Path $ManifestPath -Value $manifest
}

try {
  $lockTaken = $mutex.WaitOne([TimeSpan]::FromSeconds(180))
  if (-not $lockTaken) {
    throw "START_LOCK_TIMEOUT: another start is still in progress"
  }

  $configPath = Join-Path $projectRoot ".env"
  if (-not (Test-Path -LiteralPath $configPath -PathType Leaf)) {
    throw "CONFIG_MISSING: run Initialize-Environment.ps1 first"
  }
  $config = Import-EsgEnvironment -Path $configPath
  $backendPort = ConvertTo-EsgPort `
    -Value (Get-EsgConfigValue -Config $config -Name "BACKEND_PORT") `
    -Name "BACKEND_PORT"
  $frontendPort = ConvertTo-EsgPort `
    -Value (Get-EsgConfigValue -Config $config -Name "FRONTEND_PORT") `
    -Name "FRONTEND_PORT"
  $startupTimeout = 0
  $timeoutText = Get-EsgConfigValue -Config $config -Name "STARTUP_TIMEOUT_SECONDS" -Default "180"
  if (-not [int]::TryParse($timeoutText, [ref]$startupTimeout) -or $startupTimeout -lt 30 -or $startupTimeout -gt 600) {
    throw "STARTUP_TIMEOUT_INVALID: STARTUP_TIMEOUT_SECONDS must be between 30 and 600"
  }
  $frontendUrl = "http://localhost:$frontendPort"
  $processManifestPath = Get-EsgProcessManifestPath

  & $windowsPowerShell -NoProfile -ExecutionPolicy Bypass `
    -File (Join-Path $PSScriptRoot "Test-EsgAgent.ps1") -Quiet
  if ($LASTEXITCODE -eq 0) {
    if ($OpenBrowser) {
      Open-EsgLocalFrontendOnce -Url $frontendUrl -ManifestPath $processManifestPath
    }
    Write-Output "ESG_AGENT_ALREADY_RUNNING frontend=$frontendUrl"
    exit 0
  }

  & $windowsPowerShell -NoProfile -ExecutionPolicy Bypass `
    -File (Join-Path $PSScriptRoot "Test-Preflight.ps1") -Quiet
  if ($LASTEXITCODE -ne 0) {
    throw "PREFLIGHT_FAILED: inspect backend/data/runtime/logs/preflight.json"
  }

  $buildManifestPath = Get-EsgBuildManifestPath
  if (-not (Test-Path -LiteralPath $buildManifestPath -PathType Leaf)) {
    throw "FRONTEND_BUILD_MISSING: run Initialize-Environment.ps1 first"
  }
  $buildManifest = Get-Content -LiteralPath $buildManifestPath -Raw | ConvertFrom-Json
  $expectedApiBase = "http://localhost:$backendPort"
  if ($buildManifest.root_hash -ne $rootHash -or $buildManifest.backend_api_base -ne $expectedApiBase) {
    throw "FRONTEND_API_BASE_MISMATCH: rebuild the frontend for the configured backend port"
  }

  $projectName = Get-EsgComposeProjectName -Config $config
  $volumeName = "${projectName}_postgres_data"
  if (-not (Test-EsgNativeCommand -Command { docker volume inspect $volumeName })) {
    throw "DOCKER_VOLUME_MISSING: refusing to create an unconfirmed empty volume"
  }
  $containerId = Get-EsgPostgresContainerId -ProjectName $projectName
  if (-not $containerId) {
    Push-Location $projectRoot
    try {
      docker compose -p $projectName up -d postgres
      if ($LASTEXITCODE -ne 0) {
        throw "POSTGRES_START_FAILED: unable to attach the confirmed volume"
      }
    } finally {
      Pop-Location
    }
    $containerId = Get-EsgPostgresContainerId -ProjectName $projectName
  } else {
    $containerState = docker inspect --format "{{.State.Status}}" $containerId
    if ($containerState -ne "running") {
      docker start $containerId *> $null
      if ($LASTEXITCODE -ne 0) { throw "POSTGRES_START_FAILED: container start failed" }
    }
  }
  $postgresUser = Get-EsgConfigValue -Config $config -Name "POSTGRES_USER" -Default "esg_agent"
  Wait-EsgPostgres -ContainerId $containerId -User $postgresUser -Database "esg_agent_demo"
  $revision = docker exec $containerId psql -U $postgresUser -d esg_agent_demo -Atc `
    "SELECT version_num FROM alembic_version;"
  if ($revision -ne "0012_chunk_embeddings") {
    throw "MIGRATION_NOT_AT_HEAD: run Initialize-Database.ps1"
  }

  if (Test-Path -LiteralPath $processManifestPath -PathType Leaf) {
    $previous = Get-Content -LiteralPath $processManifestPath -Raw | ConvertFrom-Json
    if ($previous.root_hash -ne $rootHash) {
      throw "PROCESS_MANIFEST_ROOT_MISMATCH: refusing to use another checkout's process record"
    }
    foreach ($entry in @($previous.backend, $previous.frontend)) {
      if ($entry -and (Get-Process -Id ([int]$entry.pid) -ErrorAction SilentlyContinue)) {
        throw "PARTIAL_SERVICE_STATE: recorded process is still running but health failed"
      }
    }
  }

  $logRoot = Get-EsgLogRoot
  $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
  $backendOut = Join-Path $logRoot "backend-$stamp.out.log"
  $backendErr = Join-Path $logRoot "backend-$stamp.err.log"
  $frontendOut = Join-Path $logRoot "frontend-$stamp.out.log"
  $frontendErr = Join-Path $logRoot "frontend-$stamp.err.log"
  $uvCommand = Get-Command uv.exe -ErrorAction Stop
  $corepackCommand = Get-Command corepack.cmd -ErrorAction Stop

  $backendProcess = Start-Process `
    -FilePath $uvCommand.Source `
    -ArgumentList @("run", "--frozen", "--no-sync", "uvicorn", "src.main:app", "--host", "127.0.0.1", "--port", $backendPort) `
    -WorkingDirectory (Join-Path $projectRoot "backend") `
    -WindowStyle Hidden `
    -PassThru `
    -RedirectStandardOutput $backendOut `
    -RedirectStandardError $backendErr
  $frontendProcess = Start-Process `
    -FilePath $corepackCommand.Source `
    -ArgumentList @("pnpm", "start", "--hostname", "127.0.0.1", "--port", $frontendPort) `
    -WorkingDirectory (Join-Path $projectRoot "frontend") `
    -WindowStyle Hidden `
    -PassThru `
    -RedirectStandardOutput $frontendOut `
    -RedirectStandardError $frontendErr

  $processManifest = [ordered]@{
    schema_version = 1
    root_hash = $rootHash
    project_root = $projectRoot
    started_at_utc = (Get-Date).ToUniversalTime().ToString("o")
    browser_opened = $false
    backend = [ordered]@{
      pid = $backendProcess.Id
      process_started_at_utc = $backendProcess.StartTime.ToUniversalTime().ToString("o")
      working_directory = (Join-Path $projectRoot "backend")
      port = $backendPort
      command_signature = "uv run --frozen --no-sync uvicorn src.main:app"
      stdout_log = $backendOut
      stderr_log = $backendErr
    }
    frontend = [ordered]@{
      pid = $frontendProcess.Id
      process_started_at_utc = $frontendProcess.StartTime.ToUniversalTime().ToString("o")
      working_directory = (Join-Path $projectRoot "frontend")
      port = $frontendPort
      command_signature = "corepack pnpm start"
      stdout_log = $frontendOut
      stderr_log = $frontendErr
    }
  }
  Write-EsgJsonFile -Path $processManifestPath -Value $processManifest

  $deadline = (Get-Date).AddSeconds($startupTimeout)
  $healthy = $false
  do {
    & $windowsPowerShell -NoProfile -ExecutionPolicy Bypass `
      -File (Join-Path $PSScriptRoot "Test-EsgAgent.ps1") -Quiet
    if ($LASTEXITCODE -eq 0) {
      $healthy = $true
      break
    }
    if ($backendProcess.HasExited -or $frontendProcess.HasExited) {
      break
    }
    Start-Sleep -Seconds 2
  } while ((Get-Date) -lt $deadline)
  if (-not $healthy) {
    & (Join-Path $PSScriptRoot "Stop-EsgAgent.ps1")
    throw "LAUNCHER_PROCESS_FAILED: services did not become healthy; inspect runtime logs"
  }

  if ($OpenBrowser) {
    Open-EsgLocalFrontendOnce -Url $frontendUrl -ManifestPath $processManifestPath
  }
  Write-Output "ESG_AGENT_STARTED frontend=$frontendUrl backend_port=$backendPort"
} finally {
  if ($lockTaken) { $mutex.ReleaseMutex() }
  $mutex.Dispose()
}
