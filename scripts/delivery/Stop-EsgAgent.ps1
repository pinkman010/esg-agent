param(
  [switch]$IncludeDatabase
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "Delivery.Common.ps1")

$projectRoot = Get-EsgProjectRoot
$rootHash = Get-EsgRootHash
$manifestPath = Get-EsgProcessManifestPath

if (Test-Path -LiteralPath $manifestPath -PathType Leaf) {
  $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
  if ($manifest.root_hash -ne $rootHash) {
    throw "PROCESS_MANIFEST_ROOT_MISMATCH: refusing to stop another checkout's processes"
  }

  foreach ($serviceName in @("frontend", "backend")) {
    $record = $manifest.$serviceName
    if (-not $record) { continue }
    $recordedPid = [int]$record.pid
    $process = Get-Process -Id $recordedPid -ErrorAction SilentlyContinue
    if (-not $process) { continue }

    $expectedStart = [datetime]::Parse(
      [string]$record.process_started_at_utc,
      [System.Globalization.CultureInfo]::InvariantCulture,
      [System.Globalization.DateTimeStyles]::RoundtripKind
    )
    $actualStart = $process.StartTime.ToUniversalTime()
    if ([math]::Abs(($actualStart - $expectedStart.ToUniversalTime()).TotalSeconds) -gt 2) {
      throw "PROCESS_ID_REUSED: recorded $serviceName PID has a different start time"
    }

    $cimProcess = Get-CimInstance Win32_Process -Filter "ProcessId=$recordedPid"
    $commandLine = [string]$cimProcess.CommandLine
    $expectedToken = if ($serviceName -eq "backend") { "src.main:app" } else { "start" }
    if (-not $commandLine.Contains($expectedToken) -or
        -not $commandLine.Contains([string]$record.port)) {
      throw "PROCESS_COMMAND_MISMATCH: refusing to stop unverified $serviceName process"
    }

    & taskkill.exe /PID $recordedPid /T /F *> $null
    if ($LASTEXITCODE -ne 0 -and (Get-Process -Id $recordedPid -ErrorAction SilentlyContinue)) {
      throw "PROCESS_STOP_FAILED: unable to stop $serviceName process tree"
    }
  }
  Remove-Item -LiteralPath $manifestPath -Force
  Write-Output "ESG_AGENT_STOPPED application=true database=false"
} else {
  Write-Output "ESG_AGENT_ALREADY_STOPPED"
}

# -IncludeDatabase stops only this Compose project's PostgreSQL service and preserves its volume.
if ($IncludeDatabase) {
  $config = Import-EsgEnvironment -Path (Join-Path $projectRoot ".env")
  $projectName = Get-EsgComposeProjectName -Config $config
  Push-Location $projectRoot
  try {
    docker compose -p $projectName stop postgres
    if ($LASTEXITCODE -ne 0) {
      throw "POSTGRES_STOP_FAILED: docker compose stop postgres failed"
    }
  } finally {
    Pop-Location
  }
  Write-Output "ESG_AGENT_DATABASE_STOPPED volume_preserved=true"
}
