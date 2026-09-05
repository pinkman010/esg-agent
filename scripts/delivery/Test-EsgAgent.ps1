param(
  [switch]$AllowServicesStopped,
  [switch]$Quiet
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "Delivery.Common.ps1")

$projectRoot = Get-EsgProjectRoot
$errors = New-Object System.Collections.Generic.List[string]
$serviceErrors = New-Object System.Collections.Generic.List[string]
$checks = [ordered]@{}

function Add-HealthError {
  param([string]$Code)
  if (-not $errors.Contains($Code)) { $errors.Add($Code) }
}

function Add-ServiceError {
  param([string]$Code)
  if (-not $serviceErrors.Contains($Code)) { $serviceErrors.Add($Code) }
}

$configPath = Join-Path $projectRoot ".env"
if (-not (Test-Path -LiteralPath $configPath -PathType Leaf)) {
  Add-HealthError "CONFIG_MISSING"
  $config = @{}
} else {
  $config = Import-EsgEnvironment -Path $configPath
}

$appEnvironment = Get-EsgConfigValue -Config $config -Name "APP_ENV"
$ocrEnabled = (Get-EsgConfigValue -Config $config -Name "OCR_ENABLED" -Default "false").ToLowerInvariant()
$embeddingEnabled = (Get-EsgConfigValue -Config $config -Name "EMBEDDING_ENABLED" -Default "false").ToLowerInvariant()
$llmKeyPresent = [bool](Get-EsgConfigValue -Config $config -Name "OPENAI_COMPATIBLE_API_KEY")
$embeddingKeyPresent = [bool](Get-EsgConfigValue -Config $config -Name "EMBEDDING_API_KEY")
if ($appEnvironment -ne "demo") { Add-HealthError "APP_ENV_NOT_DEMO" }
if ($ocrEnabled -ne "false" -or $embeddingEnabled -ne "false" -or $llmKeyPresent -or $embeddingKeyPresent) {
  Add-HealthError "EXTERNAL_FEATURE_ENABLED"
}
$checks["external_features_disabled"] = ($ocrEnabled -eq "false" -and $embeddingEnabled -eq "false" -and -not $llmKeyPresent -and -not $embeddingKeyPresent)

try {
  $postgresPort = ConvertTo-EsgPort -Value (Get-EsgConfigValue -Config $config -Name "POSTGRES_PORT" -Default "5432") -Name "POSTGRES_PORT"
  $backendPort = ConvertTo-EsgPort -Value (Get-EsgConfigValue -Config $config -Name "BACKEND_PORT" -Default "8000") -Name "BACKEND_PORT"
  $frontendPort = ConvertTo-EsgPort -Value (Get-EsgConfigValue -Config $config -Name "FRONTEND_PORT" -Default "3000") -Name "FRONTEND_PORT"
} catch {
  Add-HealthError "PORT_INVALID"
  $postgresPort = 0
  $backendPort = 0
  $frontendPort = 0
}

$dockerReady = $false
if (-not (Test-EsgNativeCommand -Command { docker info })) {
  Add-HealthError "DOCKER_DAEMON_UNAVAILABLE"
} else {
  $dockerReady = $true
  $checks["docker_daemon"] = $true
}

$containerId = ""
$databaseName = "esg_agent_demo"
if ($dockerReady -and $config.Count -gt 0) {
  $projectName = Get-EsgComposeProjectName -Config $config
  $volumeName = "${projectName}_postgres_data"
  if (-not (Test-EsgNativeCommand -Command { docker volume inspect $volumeName })) {
    Add-HealthError "DOCKER_VOLUME_MISSING"
  } else {
    $checks["postgres_volume"] = $true
  }
  $containerId = Get-EsgPostgresContainerId -ProjectName $projectName
  if (-not $containerId) {
    Add-HealthError "POSTGRES_UNHEALTHY"
  } else {
    $containerState = docker inspect --format "{{.State.Status}}" $containerId 2>$null
    if ($containerState -ne "running") {
      Add-HealthError "POSTGRES_UNHEALTHY"
    } else {
      $postgresUser = Get-EsgConfigValue -Config $config -Name "POSTGRES_USER" -Default "esg_agent"
      docker exec $containerId pg_isready -U $postgresUser -d $databaseName *> $null
      if ($LASTEXITCODE -ne 0) {
        Add-HealthError "POSTGRES_UNHEALTHY"
      } else {
        $checks["postgres_ready"] = $true
        $revision = docker exec $containerId psql -U $postgresUser -d $databaseName -Atc `
          "SELECT version_num FROM alembic_version;" 2>$null
        if ($revision -ne "0012_chunk_embeddings") {
          Add-HealthError "MIGRATION_NOT_AT_HEAD"
        } else {
          $checks["migration_revision"] = $revision
        }
      }
    }
  }
}

if ($backendPort -gt 0) {
  try {
    $backendResponse = Invoke-WebRequest `
      -Uri "http://localhost:$backendPort/api/health" `
      -UseBasicParsing `
      -TimeoutSec 5
    $backendHealth = $backendResponse.Content | ConvertFrom-Json
    if ($backendResponse.StatusCode -ne 200 -or $backendHealth.status -ne "ok" -or $backendHealth.app_env -ne "demo") {
      Add-ServiceError "BACKEND_HEALTH_FAILED"
    } else {
      $checks["backend_health"] = "ok"
    }
  } catch {
    Add-ServiceError "BACKEND_HEALTH_FAILED"
  }

  try {
    $openApiResponse = Invoke-WebRequest `
      -Uri "http://localhost:$backendPort/openapi.json" `
      -UseBasicParsing `
      -TimeoutSec 5
    $openApi = $openApiResponse.Content | ConvertFrom-Json
    if ($openApi.info.version -ne (Get-EsgPackageVersion)) {
      Add-ServiceError "BACKEND_VERSION_MISMATCH"
    } else {
      $checks["openapi_version"] = $openApi.info.version
    }
  } catch {
    Add-ServiceError "BACKEND_HEALTH_FAILED"
  }
}

if ($frontendPort -gt 0) {
  try {
    $frontendResponse = Invoke-WebRequest `
      -Uri "http://localhost:$frontendPort" `
      -UseBasicParsing `
      -TimeoutSec 5
    if ($frontendResponse.StatusCode -ne 200) {
      Add-ServiceError "FRONTEND_HTTP_FAILED"
    } else {
      $checks["frontend_http"] = 200
    }
  } catch {
    Add-ServiceError "FRONTEND_HTTP_FAILED"
  }
}

$servicesStopped = ($serviceErrors.Count -gt 0)
if ($servicesStopped -and -not $AllowServicesStopped) {
  foreach ($code in $serviceErrors) { Add-HealthError $code }
}
$status = if ($errors.Count -gt 0) {
  "failed"
} elseif ($servicesStopped) {
  "services_stopped"
} else {
  "ok"
}
$result = [ordered]@{
  status = $status
  checked_at_utc = (Get-Date).ToUniversalTime().ToString("o")
  app_env = $appEnvironment
  ports = [ordered]@{
    postgres = $postgresPort
    backend = $backendPort
    frontend = $frontendPort
  }
  checks = $checks
  errors = @($errors)
  service_errors = @($serviceErrors)
  state_code = if ($servicesStopped) { "SERVICES_STOPPED" } else { "SERVICES_RUNNING" }
}
if (-not $Quiet) {
  $result | ConvertTo-Json -Depth 8
}
if ($errors.Count -gt 0) { exit 1 }
exit 0
