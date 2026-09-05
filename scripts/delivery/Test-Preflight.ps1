param(
  [switch]$StrictDelivery,
  [switch]$Quiet
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "Delivery.Common.ps1")

$projectRoot = Get-EsgProjectRoot
$errors = New-Object System.Collections.Generic.List[string]
$warnings = New-Object System.Collections.Generic.List[string]
$versions = [ordered]@{}
$checks = [ordered]@{}

function Add-PreflightError {
  param([string]$Code)
  if (-not $errors.Contains($Code)) { $errors.Add($Code) }
}

function Add-PreflightWarning {
  param([string]$Code)
  if (-not $warnings.Contains($Code)) { $warnings.Add($Code) }
}

function Test-ExcludedTcpPort {
  param([int]$Port)

  foreach ($family in @("ipv4", "ipv6")) {
    $lines = @(netsh interface $family show excludedportrange protocol=tcp 2>$null)
    foreach ($line in $lines) {
      if ($line -match "^\s*(\d+)\s+(\d+)") {
        $start = [int]$Matches[1]
        $end = [int]$Matches[2]
        if ($Port -ge $start -and $Port -le $end) {
          return $true
        }
      }
    }
  }
  return $false
}

$toolchainPath = Join-Path $projectRoot "delivery\toolchain-lock.json"
$releasePolicyPath = Join-Path $projectRoot "delivery\release-policy.json"
if (-not (Test-Path -LiteralPath $toolchainPath -PathType Leaf) -or
    -not (Test-Path -LiteralPath $releasePolicyPath -PathType Leaf)) {
  Add-PreflightError "DELIVERY_LOCK_MISSING"
  $toolchain = $null
} else {
  $toolchain = Get-Content -LiteralPath $toolchainPath -Raw | ConvertFrom-Json
  $checks["delivery_locks"] = $true
}

$configPath = Join-Path $projectRoot ".env"
$configInitialized = Test-Path -LiteralPath $configPath -PathType Leaf
if (-not $configInitialized) {
  Add-PreflightWarning "INITIALIZATION_REQUIRED:CONFIG"
  $checks["initialization_required"] = $true
  $config = @{}
} else {
  $config = Import-EsgEnvironment -Path $configPath
  $checks["config_present"] = $true
}

foreach ($command in @("uv", "node", "corepack", "docker")) {
  if ($null -eq (Get-Command $command -ErrorAction SilentlyContinue)) {
    Add-PreflightError ("COMMAND_MISSING:{0}" -f $command.ToUpperInvariant())
  }
}

$pythonEnvironment = Join-Path $projectRoot "backend\.venv\Scripts\python.exe"
$pythonEnvironmentReady = Test-Path -LiteralPath $pythonEnvironment -PathType Leaf
if (Get-Command uv -ErrorAction SilentlyContinue) {
  $versions["uv"] = ((uv --version) -split "\s+")[1]
  if ($pythonEnvironmentReady) {
    Push-Location (Join-Path $projectRoot "backend")
    try {
      $pythonVersionText = uv run --no-sync python --version 2>&1
      if ($LASTEXITCODE -eq 0) {
        $versions["python"] = (($pythonVersionText | Select-Object -First 1) -split "\s+")[1]
      } else {
        Add-PreflightError "PYTHON_ENVIRONMENT_MISSING"
      }
      $heads = @(uv run --no-sync alembic heads 2>&1)
      $checks["migration_head_file"] = ($LASTEXITCODE -eq 0 -and ($heads -join " ") -match "0012_chunk_embeddings")
      if (-not $checks["migration_head_file"]) {
        Add-PreflightError "MIGRATION_HEAD_FILE_MISMATCH"
      }
    } finally {
      Pop-Location
    }
  } else {
    if ($configInitialized) {
      Add-PreflightError "PYTHON_ENVIRONMENT_MISSING"
    } else {
      Add-PreflightWarning "INITIALIZATION_REQUIRED:PYTHON_ENVIRONMENT"
      $checks["initialization_required"] = $true
    }
    $migrationHeadFile = Join-Path $projectRoot "backend\alembic\versions\0012_chunk_embeddings.py"
    $checks["migration_head_file"] = Test-Path -LiteralPath $migrationHeadFile -PathType Leaf
    if (-not $checks["migration_head_file"]) {
      Add-PreflightError "MIGRATION_HEAD_FILE_MISMATCH"
    }
  }
}
if (Get-Command node -ErrorAction SilentlyContinue) {
  $versions["node"] = (node --version).TrimStart("v")
}
if (Get-Command corepack -ErrorAction SilentlyContinue) {
  $previousCorepackNetwork = [System.Environment]::GetEnvironmentVariable("COREPACK_ENABLE_NETWORK", "Process")
  $previousErrorAction = $ErrorActionPreference
  try {
    [System.Environment]::SetEnvironmentVariable("COREPACK_ENABLE_NETWORK", "0", "Process")
    $ErrorActionPreference = "Continue"
    $pnpmVersionText = @(corepack pnpm --version 2>$null)
    $pnpmExitCode = $LASTEXITCODE
  } finally {
    $ErrorActionPreference = $previousErrorAction
    [System.Environment]::SetEnvironmentVariable(
      "COREPACK_ENABLE_NETWORK",
      $previousCorepackNetwork,
      "Process"
    )
  }
  if ($pnpmExitCode -eq 0 -and $pnpmVersionText.Count -gt 0) {
    $versions["pnpm"] = [string]($pnpmVersionText | Select-Object -First 1)
  } elseif ($configInitialized) {
    Add-PreflightError "COREPACK_PNPM_UNAVAILABLE"
  } else {
    Add-PreflightWarning "INITIALIZATION_REQUIRED:PNPM"
    $checks["initialization_required"] = $true
  }
}

$windowsPowerShell = Join-Path $env:WINDIR "System32\WindowsPowerShell\v1.0\powershell.exe"
if (Test-Path -LiteralPath $windowsPowerShell -PathType Leaf) {
  $versions["windows_powershell"] = (& $windowsPowerShell -NoProfile -Command '$PSVersionTable.PSVersion.ToString()')
} else {
  Add-PreflightError "WINDOWS_POWERSHELL_MISSING"
}
$powershell7 = Get-Command pwsh -ErrorAction SilentlyContinue
if ($powershell7) {
  $versions["powershell_7"] = (& $powershell7.Source -NoProfile -Command '$PSVersionTable.PSVersion.ToString()')
} else {
  Add-PreflightWarning "OPTIONAL_MISSING:POWERSHELL_7"
}

$frameworkKey = "HKLM:\SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full"
if (Test-Path -LiteralPath $frameworkKey) {
  $frameworkRelease = [int](Get-ItemProperty -LiteralPath $frameworkKey).Release
  $versions["dotnet_framework_release"] = $frameworkRelease
  if ($frameworkRelease -lt 533320) {
    Add-PreflightError "DOTNET_FRAMEWORK_BELOW_MINIMUM"
  }
} else {
  Add-PreflightError "DOTNET_FRAMEWORK_MISSING"
}

$dockerAvailable = $false
if (Get-Command docker -ErrorAction SilentlyContinue) {
  $engineVersion = docker info --format "{{.ServerVersion}}" 2>$null
  if ($LASTEXITCODE -ne 0 -or -not $engineVersion) {
    Add-PreflightError "DOCKER_DAEMON_UNAVAILABLE"
  } else {
    $dockerAvailable = $true
    $versions["docker_engine"] = $engineVersion
    $versions["docker_compose"] = ((docker compose version --short) -replace "^v", "")
  }
}

$desktopVersion = ""
foreach ($key in @(
  "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Docker Desktop",
  "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Docker Desktop"
)) {
  if (Test-Path -LiteralPath $key) {
    $desktopVersion = [string](Get-ItemProperty -LiteralPath $key).DisplayVersion
    break
  }
}
if ($desktopVersion) {
  $versions["docker_desktop"] = $desktopVersion
  if ([version]$desktopVersion -lt [version]"4.89.0") {
    if ($StrictDelivery) {
      Add-PreflightError "DOCKER_DESKTOP_BELOW_RECOMMENDED"
    } else {
      Add-PreflightWarning "DOCKER_DESKTOP_BELOW_RECOMMENDED"
    }
  }
} else {
  Add-PreflightError "DOCKER_DESKTOP_VERSION_UNKNOWN"
}

$appEnvironment = Get-EsgConfigValue -Config $config -Name "APP_ENV"
$ocrEnabled = (Get-EsgConfigValue -Config $config -Name "OCR_ENABLED" -Default "false").ToLowerInvariant()
$embeddingEnabled = (Get-EsgConfigValue -Config $config -Name "EMBEDDING_ENABLED" -Default "false").ToLowerInvariant()
$llmKeyPresent = [bool](Get-EsgConfigValue -Config $config -Name "OPENAI_COMPATIBLE_API_KEY")
$embeddingKeyPresent = [bool](Get-EsgConfigValue -Config $config -Name "EMBEDDING_API_KEY")
$checks["app_env_demo"] = ($appEnvironment -eq "demo")
$checks["ocr_enabled"] = ($ocrEnabled -eq "true")
$checks["embedding_enabled"] = ($embeddingEnabled -eq "true")
$checks["api_key_present"] = [ordered]@{
  llm = $llmKeyPresent
  embedding = $embeddingKeyPresent
}
if ($appEnvironment -and $appEnvironment -ne "demo") {
  Add-PreflightError "APP_ENV_NOT_DEMO"
}
if ($ocrEnabled -notin @("true", "false") -or $embeddingEnabled -notin @("true", "false")) {
  Add-PreflightError "FEATURE_FLAG_INVALID"
}
if ($ocrEnabled -eq "true" -or $embeddingEnabled -eq "true" -or $llmKeyPresent -or $embeddingKeyPresent) {
  Add-PreflightError "EXTERNAL_FEATURE_ENABLED"
}

$ports = [ordered]@{}
try {
  $ports["postgres"] = ConvertTo-EsgPort -Value (Get-EsgConfigValue -Config $config -Name "POSTGRES_PORT" -Default "5432") -Name "POSTGRES_PORT"
  $ports["backend"] = ConvertTo-EsgPort -Value (Get-EsgConfigValue -Config $config -Name "BACKEND_PORT" -Default "8000") -Name "BACKEND_PORT"
  $ports["frontend"] = ConvertTo-EsgPort -Value (Get-EsgConfigValue -Config $config -Name "FRONTEND_PORT" -Default "3000") -Name "FRONTEND_PORT"
} catch {
  Add-PreflightError "PORT_INVALID"
}
if (($ports.Values | Select-Object -Unique).Count -ne $ports.Count) {
  Add-PreflightError "PORT_COLLISION"
}

$projectName = ""
$containerId = ""
if ($config.Count -gt 0) {
  try {
    $projectName = Get-EsgComposeProjectName -Config $config
  } catch {
    Add-PreflightError "COMPOSE_PROJECT_INVALID"
  }
}
if ($dockerAvailable -and $projectName) {
  $volumeName = "${projectName}_postgres_data"
  if (-not (Test-EsgNativeCommand -Command { docker volume inspect $volumeName })) {
    Add-PreflightError "DOCKER_VOLUME_MISSING"
  } else {
    $checks["postgres_volume_present"] = $true
  }
  $containerId = Get-EsgPostgresContainerId -ProjectName $projectName
  if ((Get-EsgConfigValue -Config $config -Name "POSTGRES_PASSWORD")) {
    Push-Location $projectRoot
    try {
      docker compose -p $projectName config --quiet
      if ($LASTEXITCODE -ne 0) {
        Add-PreflightError "COMPOSE_CONFIG_INVALID"
      } else {
        $checks["compose_config"] = $true
      }
    } finally {
      Pop-Location
    }
  } else {
    Add-PreflightError "POSTGRES_PASSWORD_MISSING"
  }
}

if ($ports.Count -eq 3) {
  foreach ($entry in $ports.GetEnumerator()) {
    $listeners = @(Get-NetTCPConnection -LocalPort $entry.Value -State Listen -ErrorAction SilentlyContinue)
    $expectedPostgres = $false
    if ($entry.Key -eq "postgres" -and $containerId) {
      $containerState = docker inspect --format "{{.State.Status}}" $containerId 2>$null
      $expectedPostgres = ($containerState -eq "running")
    }
    if ($listeners.Count -gt 0 -and -not $expectedPostgres) {
      Add-PreflightError ("PORT_IN_USE:{0}" -f $entry.Key.ToUpperInvariant())
    } elseif ($listeners.Count -eq 0 -and (Test-ExcludedTcpPort -Port $entry.Value)) {
      Add-PreflightError ("PORT_EXCLUDED:{0}" -f $entry.Key.ToUpperInvariant())
    }
  }
}

$optionalMissing = New-Object System.Collections.Generic.List[string]
$ocrmypdfAvailable = $false
if ($pythonEnvironmentReady -and (Get-Command uv -ErrorAction SilentlyContinue)) {
  Push-Location (Join-Path $projectRoot "backend")
  try {
    $previousErrorAction = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    uv run --no-sync ocrmypdf --version *> $null
    $ocrmypdfAvailable = ($LASTEXITCODE -eq 0)
    $ErrorActionPreference = $previousErrorAction
  } finally {
    $ErrorActionPreference = "Stop"
    Pop-Location
  }
}
if (-not $ocrmypdfAvailable) { $optionalMissing.Add("OCRmyPDF") }
$ghostscriptCommand = Get-EsgConfigValue -Config $config -Name "GHOSTSCRIPT_CMD"
if (-not $ghostscriptCommand) {
  $ghostscript = Get-Command gswin64c -ErrorAction SilentlyContinue
  if ($ghostscript) { $ghostscriptCommand = $ghostscript.Source }
}
if (-not $ghostscriptCommand) {
  $ghostscriptRoot = Join-Path $env:ProgramFiles "gs"
  if (Test-Path -LiteralPath $ghostscriptRoot -PathType Container) {
    $ghostscriptFile = Get-ChildItem -LiteralPath $ghostscriptRoot -Filter "gswin64c.exe" -Recurse |
      Sort-Object FullName -Descending | Select-Object -First 1
    if ($ghostscriptFile) { $ghostscriptCommand = $ghostscriptFile.FullName }
  }
}
if (-not $ghostscriptCommand -or -not (Test-Path -LiteralPath $ghostscriptCommand -PathType Leaf)) {
  $optionalMissing.Add("Ghostscript")
}
$tesseractCommand = Get-EsgConfigValue -Config $config -Name "TESSERACT_CMD"
if (-not $tesseractCommand) {
  $defaultTesseract = Join-Path $env:ProgramFiles "Tesseract-OCR\tesseract.exe"
  if (Test-Path -LiteralPath $defaultTesseract -PathType Leaf) { $tesseractCommand = $defaultTesseract }
}
if (-not $tesseractCommand -or -not (Test-Path -LiteralPath $tesseractCommand -PathType Leaf)) {
  $optionalMissing.Add("Tesseract")
} else {
  $languages = @(& $tesseractCommand --list-langs 2>$null)
  foreach ($language in @("chi_sim", "eng", "osd")) {
    if ($languages -notcontains $language) { $optionalMissing.Add("Tesseract:$language") }
  }
}
foreach ($missing in $optionalMissing) {
  if ($ocrEnabled -eq "true") {
    Add-PreflightError ("OPTIONAL_MISSING:{0}" -f $missing)
  } else {
    Add-PreflightWarning ("OPTIONAL_MISSING:{0}" -f $missing)
  }
}

if ($null -ne $toolchain) {
  if ($versions.Contains("python") -and $versions["python"] -ne $toolchain.python) { Add-PreflightError "PYTHON_VERSION_MISMATCH" }
  if ($versions.Contains("uv") -and $versions["uv"] -ne $toolchain.uv) { Add-PreflightError "UV_VERSION_MISMATCH" }
  if ($versions.Contains("node") -and $versions["node"] -ne $toolchain.node) { Add-PreflightError "NODE_VERSION_MISMATCH" }
  if ($versions.Contains("pnpm") -and $versions["pnpm"] -ne $toolchain.pnpm) { Add-PreflightError "PNPM_VERSION_MISMATCH" }
}

$result = [ordered]@{
  status = if ($errors.Count -eq 0) { "ok" } else { "failed" }
  checked_at_utc = (Get-Date).ToUniversalTime().ToString("o")
  strict_delivery = [bool]$StrictDelivery
  versions = $versions
  ports = $ports
  checks = $checks
  errors = @($errors)
  warnings = @($warnings)
}
$outputPath = Join-Path (Get-EsgLogRoot) "preflight.json"
Write-EsgJsonFile -Path $outputPath -Value $result
if (-not $Quiet) {
  $result | ConvertTo-Json -Depth 8
}
if ($errors.Count -gt 0) { exit 1 }
exit 0
