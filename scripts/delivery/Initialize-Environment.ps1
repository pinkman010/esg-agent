param(
  [ValidateSet("demo", "main", "test")][string]$Environment = "demo",
  [ValidateSet("new", "existing")][string]$VolumeMode = "new",
  [switch]$UseExistingConfig,
  [switch]$RegenerateLocalConfig
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "Delivery.Common.ps1")

if ($UseExistingConfig -and $RegenerateLocalConfig) {
  throw "CONFIG_MODE_INVALID: choose one local configuration mode"
}

$projectRoot = Get-EsgProjectRoot
$templatePath = Join-Path $projectRoot ".env.example"
$configPath = Join-Path $projectRoot ".env"
if (-not (Test-Path -LiteralPath $templatePath -PathType Leaf)) {
  throw "CONFIG_TEMPLATE_MISSING: .env.example is required"
}

$configExists = Test-Path -LiteralPath $configPath -PathType Leaf
if ($configExists -and -not $UseExistingConfig -and -not $RegenerateLocalConfig) {
  throw "CONFIG_EXISTS: use -UseExistingConfig or explicitly regenerate it"
}
if (-not $configExists -or $RegenerateLocalConfig) {
  Copy-Item -LiteralPath $templatePath -Destination $configPath -Force
  $databaseName = Get-EsgDatabaseName -Environment $Environment
  $runtimeBase = if ($Environment -eq "demo") {
    "backend/data/runtime/demo"
  } else {
    "backend/data/runtime"
  }
  $composeProject = if ($VolumeMode -eq "new") {
    "esg-agent-{0}-{1}" -f $Environment, ([guid]::NewGuid().ToString("N").Substring(0, 8))
  } else {
    "esg-agent"
  }
  Set-EsgLocalEnvValue -Path $configPath -Name "APP_ENV" -Value $Environment
  Set-EsgLocalEnvValue -Path $configPath -Name "COMPOSE_PROJECT_NAME" -Value $composeProject
  Set-EsgLocalEnvValue -Path $configPath -Name "POSTGRES_DB" -Value $databaseName
  Set-EsgLocalEnvValue -Path $configPath -Name "POSTGRES_PASSWORD" -Value (New-EsgRandomSecret)
  Set-EsgLocalEnvValue -Path $configPath -Name "UPLOAD_DIR" -Value "${runtimeBase}/uploads"
  Set-EsgLocalEnvValue -Path $configPath -Name "DERIVED_DIR" -Value "${runtimeBase}/derived"
}

$config = Import-EsgEnvironment -Path $configPath
$postgresPassword = Get-EsgConfigValue -Config $config -Name "POSTGRES_PASSWORD"
if (-not $postgresPassword) {
  throw "POSTGRES_PASSWORD_MISSING: existing configuration is incomplete"
}
$postgresUser = Get-EsgConfigValue -Config $config -Name "POSTGRES_USER" -Default "esg_agent"
$postgresPort = ConvertTo-EsgPort `
  -Value (Get-EsgConfigValue -Config $config -Name "POSTGRES_PORT" -Default "5432") `
  -Name "POSTGRES_PORT"
$backendPort = ConvertTo-EsgPort `
  -Value (Get-EsgConfigValue -Config $config -Name "BACKEND_PORT" -Default "8000") `
  -Name "BACKEND_PORT"
$frontendPort = ConvertTo-EsgPort `
  -Value (Get-EsgConfigValue -Config $config -Name "FRONTEND_PORT" -Default "3000") `
  -Name "FRONTEND_PORT"
$databaseName = Get-EsgDatabaseName -Environment $Environment
$databaseUrl = Get-EsgDatabaseUrl `
  -User $postgresUser `
  -Password $postgresPassword `
  -Port $postgresPort `
  -Database $databaseName
$apiBase = "http://localhost:$backendPort"

Set-EsgLocalEnvValue -Path $configPath -Name "APP_ENV" -Value $Environment
Set-EsgLocalEnvValue -Path $configPath -Name "POSTGRES_DB" -Value $databaseName
Set-EsgLocalEnvValue -Path $configPath -Name "DATABASE_URL" -Value $databaseUrl
Set-EsgLocalEnvValue -Path $configPath -Name "BACKEND_CORS_ORIGINS" -Value ('["http://localhost:{0}"]' -f $frontendPort)
Set-EsgLocalEnvValue -Path $configPath -Name "OCR_ENABLED" -Value "false"
Set-EsgLocalEnvValue -Path $configPath -Name "EMBEDDING_ENABLED" -Value "false"
Set-EsgLocalEnvValue -Path $configPath -Name "OPENAI_COMPATIBLE_API_KEY" -Value ""
Set-EsgLocalEnvValue -Path $configPath -Name "EMBEDDING_API_KEY" -Value ""
$config = Import-EsgEnvironment -Path $configPath

Assert-EsgCommand -Name "uv" -ErrorCode "UV_MISSING"
Assert-EsgCommand -Name "node" -ErrorCode "NODE_MISSING"
Assert-EsgCommand -Name "corepack" -ErrorCode "COREPACK_MISSING"

Push-Location (Join-Path $projectRoot "backend")
try {
  uv sync --frozen
  if ($LASTEXITCODE -ne 0) {
    throw "PYTHON_INSTALL_FAILED: uv sync --frozen failed"
  }
} finally {
  Pop-Location
}

corepack prepare pnpm@11.19.0 --activate
if ($LASTEXITCODE -ne 0) {
  throw "PNPM_ACTIVATION_FAILED: Corepack could not activate pnpm 11.19.0"
}
[System.Environment]::SetEnvironmentVariable("NEXT_PUBLIC_API_BASE_URL", $apiBase, "Process")
Push-Location (Join-Path $projectRoot "frontend")
try {
  pnpm install --frozen-lockfile
  if ($LASTEXITCODE -ne 0) {
    throw "FRONTEND_INSTALL_FAILED: pnpm install --frozen-lockfile failed"
  }
  pnpm build
  if ($LASTEXITCODE -ne 0) {
    throw "FRONTEND_BUILD_FAILED: pnpm build failed"
  }
} finally {
  Pop-Location
}

$buildManifest = [ordered]@{
  root_hash = Get-EsgRootHash
  backend_api_base = $apiBase
  backend_port = $backendPort
  frontend_port = $frontendPort
  built_at_utc = (Get-Date).ToUniversalTime().ToString("o")
}
Write-EsgJsonFile -Path (Get-EsgBuildManifestPath) -Value $buildManifest

& (Join-Path $PSScriptRoot "Initialize-Database.ps1") `
  -Environment $Environment `
  -VolumeMode $VolumeMode
if ($LASTEXITCODE -ne 0) {
  throw "DATABASE_INITIALIZATION_FAILED: database initialization failed"
}

Write-Output "ENVIRONMENT_INITIALIZED environment=$Environment backend_port=$backendPort frontend_port=$frontendPort"
