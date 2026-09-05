param(
  [ValidateSet("demo", "main", "test")][string]$Environment = "demo",
  [Parameter(Mandatory)]
  [ValidateSet("new", "existing")][string]$VolumeMode,
  [switch]$RunMigrationRoundTrip
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "Delivery.Common.ps1")

$projectRoot = Get-EsgProjectRoot
$envPath = Join-Path $projectRoot ".env"
$config = Import-EsgEnvironment -Path $envPath

Assert-EsgCommand -Name "docker" -ErrorCode "DOCKER_MISSING"
Assert-EsgCommand -Name "uv" -ErrorCode "UV_MISSING"
docker info *> $null
if ($LASTEXITCODE -ne 0) {
  throw "DOCKER_DAEMON_UNAVAILABLE: Docker Desktop is not running"
}

$postgresUser = Get-EsgConfigValue -Config $config -Name "POSTGRES_USER" -Default "esg_agent"
$postgresPassword = Get-EsgConfigValue -Config $config -Name "POSTGRES_PASSWORD"
$postgresPortText = Get-EsgConfigValue -Config $config -Name "POSTGRES_PORT" -Default "5432"
if (-not $postgresPassword) {
  throw "POSTGRES_PASSWORD_MISSING: initialize local .env first"
}
$postgresPort = 0
if (-not [int]::TryParse($postgresPortText, [ref]$postgresPort) -or $postgresPort -lt 1 -or $postgresPort -gt 65535) {
  throw "POSTGRES_PORT_INVALID: POSTGRES_PORT must be between 1 and 65535"
}

$projectName = Get-EsgComposeProjectName -Config $config
$volumeName = "${projectName}_postgres_data"
$volumeExists = $true
docker volume inspect $volumeName *> $null
if ($LASTEXITCODE -ne 0) {
  $volumeExists = $false
}

if ($VolumeMode -eq "new" -and $volumeExists) {
  throw "DOCKER_VOLUME_ALREADY_EXISTS: refusing to reuse $volumeName"
}
if ($VolumeMode -eq "existing" -and -not $volumeExists) {
  throw "DOCKER_VOLUME_MISSING: required volume does not exist"
}

$containerId = Get-EsgPostgresContainerId -ProjectName $projectName
if ($VolumeMode -eq "new") {
  Push-Location $projectRoot
  try {
    docker compose -p $projectName up -d postgres
    if ($LASTEXITCODE -ne 0) {
      throw "POSTGRES_START_FAILED: docker compose failed"
    }
  } finally {
    Pop-Location
  }
  $containerId = Get-EsgPostgresContainerId -ProjectName $projectName
} elseif (-not $containerId) {
  Write-Output "Existing volume: $volumeName"
  Push-Location $projectRoot
  try {
    docker compose -p $projectName up -d postgres
    if ($LASTEXITCODE -ne 0) {
      throw "POSTGRES_START_FAILED: unable to attach the existing volume"
    }
  } finally {
    Pop-Location
  }
  $containerId = Get-EsgPostgresContainerId -ProjectName $projectName
} else {
  $containerState = docker inspect --format "{{.State.Status}}" $containerId
  Write-Output "Existing volume: $volumeName"
  Write-Output "Existing container: $containerId ($containerState)"
  if ($containerState -ne "running") {
    docker start $containerId *> $null
    if ($LASTEXITCODE -ne 0) {
      throw "POSTGRES_START_FAILED: unable to start existing container"
    }
  }
}

if (-not $containerId) {
  throw "POSTGRES_CONTAINER_MISSING: PostgreSQL container was not created"
}
Wait-EsgPostgres -ContainerId $containerId -User $postgresUser -Database "postgres"

if ($RunMigrationRoundTrip) {
  if ($Environment -ne "test") {
    throw "MIGRATION_ROUNDTRIP_FORBIDDEN: round-trip is allowed only for test"
  }
  $roundTripDatabase = "esg_agent_migration_test_$([guid]::NewGuid().ToString('N'))"
  $roundTripUrl = Get-EsgDatabaseUrl `
    -User $postgresUser `
    -Password $postgresPassword `
    -Port $postgresPort `
    -Database $roundTripDatabase
  $previousMigrationUrl = [System.Environment]::GetEnvironmentVariable("MIGRATION_TEST_DATABASE_URL", "Process")
  [System.Environment]::SetEnvironmentVariable("MIGRATION_TEST_DATABASE_URL", $roundTripUrl, "Process")
  Push-Location (Join-Path $projectRoot "backend")
  try {
    uv run --frozen --no-sync pytest tests/db/test_migration_roundtrip.py -q
    if ($LASTEXITCODE -ne 0) {
      throw "MIGRATION_ROUNDTRIP_FAILED: isolated migration test failed"
    }
  } finally {
    Pop-Location
    [System.Environment]::SetEnvironmentVariable("MIGRATION_TEST_DATABASE_URL", $previousMigrationUrl, "Process")
  }
  Write-Output "MIGRATION_ROUNDTRIP_OK volume=$volumeName"
  exit 0
}

$databaseName = Get-EsgDatabaseName -Environment $Environment
Assert-EsgDatabaseName -Name $databaseName
$databaseExists = docker exec $containerId psql -U $postgresUser -d postgres -Atc `
  "SELECT 1 FROM pg_database WHERE datname='$databaseName';"
if ($LASTEXITCODE -ne 0) {
  throw "DATABASE_QUERY_FAILED: unable to query target database"
}
if ($databaseExists -ne "1") {
  docker exec $containerId createdb -U $postgresUser $databaseName
  if ($LASTEXITCODE -ne 0) {
    throw "DATABASE_CREATE_FAILED: unable to create target database"
  }
}

$databaseUrl = Get-EsgDatabaseUrl `
  -User $postgresUser `
  -Password $postgresPassword `
  -Port $postgresPort `
  -Database $databaseName
$previousDatabaseUrl = [System.Environment]::GetEnvironmentVariable("DATABASE_URL", "Process")
[System.Environment]::SetEnvironmentVariable("DATABASE_URL", $databaseUrl, "Process")
Push-Location (Join-Path $projectRoot "backend")
try {
  uv run --frozen --no-sync alembic upgrade head
  if ($LASTEXITCODE -ne 0) {
    throw "MIGRATION_FAILED: alembic upgrade head failed"
  }
} finally {
  Pop-Location
  [System.Environment]::SetEnvironmentVariable("DATABASE_URL", $previousDatabaseUrl, "Process")
}

$revision = docker exec $containerId psql -U $postgresUser -d $databaseName -Atc `
  "SELECT version_num FROM alembic_version;"
if ($revision -ne "0012_chunk_embeddings") {
  throw "MIGRATION_HEAD_MISMATCH: expected 0012_chunk_embeddings"
}
$reportCount = docker exec $containerId psql -U $postgresUser -d $databaseName -Atc `
  "SELECT count(*) FROM reports;"

Write-Output "DATABASE_INITIALIZED environment=$Environment database=$databaseName revision=$revision reports=$reportCount volume=$volumeName"
