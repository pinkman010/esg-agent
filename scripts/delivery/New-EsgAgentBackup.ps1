param(
  [ValidateSet("demo", "main", "test")][string]$Environment = "demo",
  [string]$ArchivePath = "",
  [switch]$IncludeRuntime
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "Delivery.Common.ps1")

$projectRoot = Get-EsgProjectRoot
$config = Import-EsgEnvironment -Path (Join-Path $projectRoot ".env")
Assert-EsgCommand -Name "docker" -ErrorCode "DOCKER_MISSING"

$projectName = Get-EsgComposeProjectName -Config $config
$containerId = Get-EsgPostgresContainerId -ProjectName $projectName
if (-not $containerId) {
  throw "POSTGRES_CONTAINER_MISSING: initialize PostgreSQL first"
}
$postgresUser = Get-EsgConfigValue -Config $config -Name "POSTGRES_USER" -Default "esg_agent"
$databaseName = Get-EsgDatabaseName -Environment $Environment
Assert-EsgDatabaseName -Name $databaseName
Wait-EsgPostgres -ContainerId $containerId -User $postgresUser -Database $databaseName

if (-not $ArchivePath) {
  $backupDirectory = Join-Path $projectRoot "backups"
  $ArchivePath = Join-Path $backupDirectory (
    "esg-agent-{0}-backup-{1}.zip" -f $Environment, (Get-Date -Format "yyyyMMdd-HHmmss")
  )
}
$resolvedArchive = [System.IO.Path]::GetFullPath($ArchivePath)
Assert-EsgPathWithin -Path $resolvedArchive -Root $projectRoot -ErrorCode "BACKUP_PATH_INVALID"
if (Test-Path -LiteralPath $resolvedArchive) {
  throw "BACKUP_ARCHIVE_EXISTS: refusing to overwrite an existing archive"
}
New-Item -ItemType Directory -Path (Split-Path -Parent $resolvedArchive) -Force | Out-Null

$stagingParent = Join-Path $projectRoot "tmp\backup-build"
$stagingRoot = Join-Path $stagingParent ([guid]::NewGuid().ToString("N"))
Assert-EsgPathWithin -Path $stagingRoot -Root $stagingParent -ErrorCode "BACKUP_STAGING_INVALID"
New-Item -ItemType Directory -Path $stagingRoot -Force | Out-Null
$databaseDump = Join-Path $stagingRoot "database.dump"
$containerDump = "/tmp/esg-agent-backup-$([guid]::NewGuid().ToString('N')).dump"
$backupSucceeded = $false

try {
  docker exec $containerId pg_dump -U $postgresUser -d $databaseName `
    --format=custom --no-owner --no-privileges --file=$containerDump
  if ($LASTEXITCODE -ne 0) {
    throw "DATABASE_BACKUP_FAILED: pg_dump failed"
  }
  docker cp "${containerId}:${containerDump}" $databaseDump
  if ($LASTEXITCODE -ne 0) {
    throw "DATABASE_BACKUP_FAILED: unable to copy database dump"
  }

  if ($IncludeRuntime) {
    Write-Warning "Runtime backup may contain non-public reports and derived evidence."
    $runtimeTarget = Join-Path $stagingRoot "runtime"
    New-Item -ItemType Directory -Path $runtimeTarget -Force | Out-Null
    $defaultRuntimeBase = if ($Environment -eq "demo") {
      Join-Path $projectRoot "backend\data\runtime\demo"
    } else {
      Join-Path $projectRoot "backend\data\runtime"
    }
    foreach ($name in @("uploads", "derived", "exports")) {
      $configuredName = if ($name -eq "uploads") { "UPLOAD_DIR" } elseif ($name -eq "derived") { "DERIVED_DIR" } else { "" }
      $configured = if ($configuredName) { Get-EsgConfigValue -Config $config -Name $configuredName } else { "" }
      $source = if ($configured) {
        if ([System.IO.Path]::IsPathRooted($configured)) { $configured } else { Join-Path $projectRoot $configured }
      } else {
        Join-Path $defaultRuntimeBase $name
      }
      if (Test-Path -LiteralPath $source -PathType Container) {
        Copy-Item -LiteralPath $source -Destination (Join-Path $runtimeTarget $name) -Recurse
      }
    }
  }

  $revision = docker exec $containerId psql -U $postgresUser -d $databaseName -Atc `
    "SELECT version_num FROM alembic_version;"
  if ($LASTEXITCODE -ne 0 -or -not $revision) {
    throw "BACKUP_SCHEMA_UNKNOWN: unable to read Alembic revision"
  }
  $versionMatch = Select-String -LiteralPath (Join-Path $projectRoot "backend\pyproject.toml") `
    -Pattern '^version\s*=\s*"([^"]+)"' | Select-Object -First 1
  if (-not $versionMatch) {
    throw "BACKUP_VERSION_UNKNOWN: backend version is unavailable"
  }

  $files = @()
  Get-ChildItem -LiteralPath $stagingRoot -File -Recurse | Sort-Object FullName | ForEach-Object {
    $relative = $_.FullName.Substring($stagingRoot.Length + 1).Replace("\", "/")
    $files += [ordered]@{
      path = $relative
      size_bytes = $_.Length
      sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
    }
  }
  $manifest = [ordered]@{
    schema_version = 1
    app_version = $versionMatch.Matches[0].Groups[1].Value
    database_name = $databaseName
    alembic_revision = $revision
    includes_runtime = [bool]$IncludeRuntime
    created_at_utc = (Get-Date).ToUniversalTime().ToString("o")
    files = $files
  }
  $manifestPath = Join-Path $stagingRoot "backup-manifest.json"
  [System.IO.File]::WriteAllText(
    $manifestPath,
    ($manifest | ConvertTo-Json -Depth 6),
    (New-Object System.Text.UTF8Encoding($false))
  )

  $checksumLines = @()
  Get-ChildItem -LiteralPath $stagingRoot -File -Recurse | Sort-Object FullName | ForEach-Object {
    $relative = $_.FullName.Substring($stagingRoot.Length + 1).Replace("\", "/")
    $checksumLines += "{0}  {1}" -f (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash, $relative
  }
  [System.IO.File]::WriteAllLines(
    (Join-Path $stagingRoot "SHA256SUMS.txt"),
    $checksumLines,
    (New-Object System.Text.UTF8Encoding($false))
  )

  Compress-Archive -Path (Join-Path $stagingRoot "*") -DestinationPath $resolvedArchive -CompressionLevel Optimal
  $outerHash = (Get-FileHash -LiteralPath $resolvedArchive -Algorithm SHA256).Hash
  [System.IO.File]::WriteAllText(
    "${resolvedArchive}.sha256",
    ("{0}  {1}`n" -f $outerHash, (Split-Path -Leaf $resolvedArchive)),
    (New-Object System.Text.UTF8Encoding($false))
  )
  $backupSucceeded = $true
  Write-Output "BACKUP_CREATED archive=$resolvedArchive sha256=$outerHash revision=$revision"
} finally {
  docker exec $containerId rm -f $containerDump *> $null
  if ($backupSucceeded -and (Test-Path -LiteralPath $stagingRoot)) {
    Assert-EsgPathWithin -Path $stagingRoot -Root $stagingParent -ErrorCode "BACKUP_CLEANUP_INVALID"
    Remove-Item -LiteralPath $stagingRoot -Recurse -Force
  }
}
