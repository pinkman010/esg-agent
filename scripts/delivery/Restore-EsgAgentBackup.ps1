param(
  [Parameter(Mandatory)][string]$ArchivePath,
  [Parameter(Mandatory)][string]$TargetDatabase,
  [Parameter(Mandatory)][string]$ConfirmDatabase,
  [switch]$ApplyPathNormalization
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "Delivery.Common.ps1")

$projectRoot = Get-EsgProjectRoot
$config = Import-EsgEnvironment -Path (Join-Path $projectRoot ".env")
Assert-EsgCommand -Name "docker" -ErrorCode "DOCKER_MISSING"
Assert-EsgCommand -Name "uv" -ErrorCode "UV_MISSING"
Assert-EsgDatabaseName -Name $TargetDatabase
if ($TargetDatabase -ne $ConfirmDatabase) {
  throw "DATABASE_CONFIRMATION_MISMATCH: target database was not confirmed"
}

$stateRoot = Join-Path $projectRoot "tmp\run"
foreach ($pidName in @("backend.pid", "frontend.pid")) {
  $pidPath = Join-Path $stateRoot $pidName
  if (Test-Path -LiteralPath $pidPath -PathType Leaf) {
    $processId = 0
    if ([int]::TryParse((Get-Content -LiteralPath $pidPath -Raw).Trim(), [ref]$processId)) {
      if (Get-Process -Id $processId -ErrorAction SilentlyContinue) {
        throw "APPLICATION_STILL_RUNNING: stop frontend and backend before restore"
      }
    }
  }
}

$resolvedArchive = [System.IO.Path]::GetFullPath($ArchivePath)
if (-not (Test-Path -LiteralPath $resolvedArchive -PathType Leaf)) {
  throw "BACKUP_ARCHIVE_MISSING: archive does not exist"
}
$outerChecksumPath = "${resolvedArchive}.sha256"
if (-not (Test-Path -LiteralPath $outerChecksumPath -PathType Leaf)) {
  throw "BACKUP_OUTER_CHECKSUM_MISSING: sidecar checksum is required"
}
$outerLine = (Get-Content -LiteralPath $outerChecksumPath | Select-Object -First 1)
$expectedOuterHash = ($outerLine -split "\s+", 2)[0]
$actualOuterHash = (Get-FileHash -LiteralPath $resolvedArchive -Algorithm SHA256).Hash
if ($expectedOuterHash -ne $actualOuterHash) {
  throw "BACKUP_OUTER_CHECKSUM_MISMATCH: archive hash mismatch"
}

$restoreParent = Join-Path $projectRoot "tmp\restore"
$restoreRoot = Join-Path $restoreParent ([guid]::NewGuid().ToString("N"))
Assert-EsgPathWithin -Path $restoreRoot -Root $restoreParent -ErrorCode "RESTORE_STAGING_INVALID"
New-Item -ItemType Directory -Path $restoreRoot -Force | Out-Null
Expand-Archive -LiteralPath $resolvedArchive -DestinationPath $restoreRoot

$internalChecksums = Join-Path $restoreRoot "SHA256SUMS.txt"
if (-not (Test-Path -LiteralPath $internalChecksums -PathType Leaf)) {
  throw "BACKUP_INTERNAL_CHECKSUM_MISSING: SHA256SUMS.txt is required"
}
foreach ($line in Get-Content -LiteralPath $internalChecksums) {
  if ($line -notmatch "^([A-Fa-f0-9]{64})\s{2}(.+)$") {
    throw "BACKUP_INTERNAL_CHECKSUM_INVALID: malformed checksum entry"
  }
  $expected = $Matches[1]
  $relative = $Matches[2].Replace("/", "\")
  $target = [System.IO.Path]::GetFullPath((Join-Path $restoreRoot $relative))
  Assert-EsgPathWithin -Path $target -Root $restoreRoot -ErrorCode "BACKUP_ENTRY_INVALID"
  if (-not (Test-Path -LiteralPath $target -PathType Leaf)) {
    throw "BACKUP_ENTRY_MISSING: checksum target is absent"
  }
  if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -ne $expected) {
    throw "BACKUP_INTERNAL_CHECKSUM_MISMATCH: extracted file hash mismatch"
  }
}

$manifestPath = Join-Path $restoreRoot "backup-manifest.json"
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$databaseDump = Join-Path $restoreRoot "database.dump"
if (-not (Test-Path -LiteralPath $databaseDump -PathType Leaf)) {
  throw "BACKUP_DATABASE_DUMP_MISSING: database.dump is required"
}

$projectName = Get-EsgComposeProjectName -Config $config
$containerId = Get-EsgPostgresContainerId -ProjectName $projectName
if (-not $containerId) {
  throw "POSTGRES_CONTAINER_MISSING: initialize PostgreSQL first"
}
$postgresUser = Get-EsgConfigValue -Config $config -Name "POSTGRES_USER" -Default "esg_agent"
$postgresPassword = Get-EsgConfigValue -Config $config -Name "POSTGRES_PASSWORD"
$postgresPortText = Get-EsgConfigValue -Config $config -Name "POSTGRES_PORT" -Default "5432"
if (-not $postgresPassword) {
  throw "POSTGRES_PASSWORD_MISSING: local .env is incomplete"
}
$postgresPort = 0
if (-not [int]::TryParse($postgresPortText, [ref]$postgresPort)) {
  throw "POSTGRES_PORT_INVALID: POSTGRES_PORT must be numeric"
}
Wait-EsgPostgres -ContainerId $containerId -User $postgresUser -Database "postgres"

$databaseExists = docker exec $containerId psql -U $postgresUser -d postgres -Atc `
  "SELECT 1 FROM pg_database WHERE datname='$TargetDatabase';"
if ($databaseExists -eq "1") {
  throw "RESTORE_DATABASE_EXISTS: restore target must be a new database"
}
docker exec $containerId createdb -U $postgresUser $TargetDatabase
if ($LASTEXITCODE -ne 0) {
  throw "RESTORE_DATABASE_CREATE_FAILED: target database could not be created"
}

$containerDump = "/tmp/esg-agent-restore-$([guid]::NewGuid().ToString('N')).dump"
try {
  docker cp $databaseDump "${containerId}:${containerDump}"
  if ($LASTEXITCODE -ne 0) {
    throw "RESTORE_COPY_FAILED: database dump could not be staged"
  }
  docker exec $containerId pg_restore -U $postgresUser -d $TargetDatabase `
    --exit-on-error --no-owner --no-privileges $containerDump
  if ($LASTEXITCODE -ne 0) {
    throw "RESTORE_DATABASE_FAILED: pg_restore failed"
  }
} finally {
  docker exec $containerId rm -f $containerDump *> $null
}

$restoredRuntimeRoot = ""
$runtimeSource = Join-Path $restoreRoot "runtime"
if (Test-Path -LiteralPath $runtimeSource -PathType Container) {
  $runtimeRestoreParent = Join-Path $projectRoot "backend\data\runtime\restores"
  $restoredRuntimeRoot = Join-Path $runtimeRestoreParent $TargetDatabase
  Assert-EsgPathWithin -Path $restoredRuntimeRoot -Root $runtimeRestoreParent -ErrorCode "RESTORE_RUNTIME_PATH_INVALID"
  if (Test-Path -LiteralPath $restoredRuntimeRoot) {
    throw "RESTORE_RUNTIME_EXISTS: refusing to overwrite restored runtime files"
  }
  New-Item -ItemType Directory -Path $runtimeRestoreParent -Force | Out-Null
  Copy-Item -LiteralPath $runtimeSource -Destination $restoredRuntimeRoot -Recurse
}

$databaseUrl = Get-EsgDatabaseUrl `
  -User $postgresUser `
  -Password $postgresPassword `
  -Port $postgresPort `
  -Database $TargetDatabase
$previousDatabaseUrl = [System.Environment]::GetEnvironmentVariable("DATABASE_URL", "Process")
$previousAppEnv = [System.Environment]::GetEnvironmentVariable("APP_ENV", "Process")
$previousUploadDir = [System.Environment]::GetEnvironmentVariable("UPLOAD_DIR", "Process")
$previousDerivedDir = [System.Environment]::GetEnvironmentVariable("DERIVED_DIR", "Process")
[System.Environment]::SetEnvironmentVariable("DATABASE_URL", $databaseUrl, "Process")
[System.Environment]::SetEnvironmentVariable("APP_ENV", "test", "Process")
if ($restoredRuntimeRoot) {
  [System.Environment]::SetEnvironmentVariable("UPLOAD_DIR", (Join-Path $restoredRuntimeRoot "uploads"), "Process")
  [System.Environment]::SetEnvironmentVariable("DERIVED_DIR", (Join-Path $restoredRuntimeRoot "derived"), "Process")
}
Push-Location (Join-Path $projectRoot "backend")
try {
  uv run --frozen --no-sync python -m src.tools.normalize_runtime_paths --dry-run
  if ($LASTEXITCODE -ne 0) {
    throw "RESTORE_PATH_SCAN_FAILED: runtime path dry-run failed"
  }
  if ($ApplyPathNormalization) {
    uv run --frozen --no-sync python -m src.tools.normalize_runtime_paths `
      --apply --confirm-database $TargetDatabase
    if ($LASTEXITCODE -ne 0) {
      throw "RESTORE_PATH_NORMALIZATION_FAILED: path normalization failed"
    }
  }
} finally {
  Pop-Location
  [System.Environment]::SetEnvironmentVariable("DATABASE_URL", $previousDatabaseUrl, "Process")
  [System.Environment]::SetEnvironmentVariable("APP_ENV", $previousAppEnv, "Process")
  [System.Environment]::SetEnvironmentVariable("UPLOAD_DIR", $previousUploadDir, "Process")
  [System.Environment]::SetEnvironmentVariable("DERIVED_DIR", $previousDerivedDir, "Process")
}

$revision = docker exec $containerId psql -U $postgresUser -d $TargetDatabase -Atc `
  "SELECT version_num FROM alembic_version;"
if ($revision -ne $manifest.alembic_revision) {
  throw "RESTORE_SCHEMA_MISMATCH: restored revision does not match backup manifest"
}
Write-Output "BACKUP_RESTORED database=$TargetDatabase revision=$revision staging=$restoreRoot"
