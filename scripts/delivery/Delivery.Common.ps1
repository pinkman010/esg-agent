Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

$script:EsgDeliveryProjectRoot = [System.IO.Path]::GetFullPath(
  (Join-Path $PSScriptRoot "..\..")
)

function Get-EsgProjectRoot {
  return $script:EsgDeliveryProjectRoot
}

function Test-EsgPathWithin {
  param(
    [Parameter(Mandatory)][string]$Path,
    [Parameter(Mandatory)][string]$Root
  )

  $candidate = [System.IO.Path]::GetFullPath($Path).TrimEnd("\")
  $boundary = [System.IO.Path]::GetFullPath($Root).TrimEnd("\")
  return $candidate.Equals($boundary, [System.StringComparison]::OrdinalIgnoreCase) -or
    $candidate.StartsWith($boundary + "\", [System.StringComparison]::OrdinalIgnoreCase)
}

function Assert-EsgPathWithin {
  param(
    [Parameter(Mandatory)][string]$Path,
    [Parameter(Mandatory)][string]$Root,
    [string]$ErrorCode = "UNSAFE_PATH"
  )

  if (-not (Test-EsgPathWithin -Path $Path -Root $Root)) {
    throw "${ErrorCode}: target path is outside the approved root"
  }
}

function Get-EsgEnvMap {
  param([string]$Path = (Join-Path (Get-EsgProjectRoot) ".env"))

  $values = @{}
  if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
    return $values
  }
  foreach ($rawLine in Get-Content -LiteralPath $Path) {
    $line = $rawLine.Trim()
    if (-not $line -or $line.StartsWith("#")) {
      continue
    }
    $separator = $line.IndexOf("=")
    if ($separator -lt 1) {
      throw "CONFIG_INVALID: invalid line in .env"
    }
    $key = $line.Substring(0, $separator).Trim()
    $value = $line.Substring($separator + 1).Trim()
    if ($value.Length -ge 2) {
      $first = $value.Substring(0, 1)
      $last = $value.Substring($value.Length - 1, 1)
      if (($first -eq "'" -and $last -eq "'") -or ($first -eq '"' -and $last -eq '"')) {
        $value = $value.Substring(1, $value.Length - 2)
      }
    }
    $values[$key] = $value
  }
  return $values
}

function Import-EsgEnvironment {
  param([string]$Path = (Join-Path (Get-EsgProjectRoot) ".env"))

  $values = Get-EsgEnvMap -Path $Path
  foreach ($key in $values.Keys) {
    [System.Environment]::SetEnvironmentVariable($key, [string]$values[$key], "Process")
  }
  return $values
}

function Get-EsgConfigValue {
  param(
    [hashtable]$Config,
    [Parameter(Mandatory)][string]$Name,
    [string]$Default = ""
  )

  if ($null -ne $Config -and $Config.ContainsKey($Name)) {
    return [string]$Config[$Name]
  }
  $environmentValue = [System.Environment]::GetEnvironmentVariable($Name, "Process")
  if ($null -ne $environmentValue) {
    return $environmentValue
  }
  return $Default
}

function Set-EsgLocalEnvValue {
  param(
    [Parameter(Mandatory)][string]$Path,
    [Parameter(Mandatory)][string]$Name,
    [AllowEmptyString()][Parameter(Mandatory)][string]$Value
  )

  $lines = @()
  if (Test-Path -LiteralPath $Path -PathType Leaf) {
    $lines = @(Get-Content -LiteralPath $Path)
  }
  $found = $false
  $updated = @()
  foreach ($line in $lines) {
    if ($line -match ("^" + [regex]::Escape($Name) + "=")) {
      $updated += "${Name}=${Value}"
      $found = $true
    } else {
      $updated += $line
    }
  }
  if (-not $found) {
    $updated += "${Name}=${Value}"
  }
  [System.IO.File]::WriteAllLines($Path, $updated, [System.Text.UTF8Encoding]::new($false))
}

function New-EsgRandomSecret {
  param([int]$ByteCount = 24)

  $bytes = New-Object byte[] $ByteCount
  $provider = New-Object System.Security.Cryptography.RNGCryptoServiceProvider
  try {
    $provider.GetBytes($bytes)
  } finally {
    $provider.Dispose()
  }
  return -join ($bytes | ForEach-Object { $_.ToString("x2") })
}

function Assert-EsgCommand {
  param(
    [Parameter(Mandatory)][string]$Name,
    [string]$ErrorCode = "COMMAND_MISSING"
  )

  if ($null -eq (Get-Command $Name -ErrorAction SilentlyContinue)) {
    throw "${ErrorCode}: required command is unavailable: $Name"
  }
}

function Assert-EsgDatabaseName {
  param([Parameter(Mandatory)][string]$Name)

  $forbidden = @("postgres", "template0", "template1")
  if ($Name -notmatch "^[a-z][a-z0-9_]{0,62}$" -or $forbidden -contains $Name) {
    throw "DATABASE_NAME_INVALID: unsafe database name"
  }
}

function Get-EsgDatabaseName {
  param([Parameter(Mandatory)][ValidateSet("demo", "main", "test")][string]$Environment)

  switch ($Environment) {
    "demo" { return "esg_agent_demo" }
    "main" { return "esg_agent" }
    "test" { return "esg_agent_test" }
  }
}

function Get-EsgDatabaseUrl {
  param(
    [Parameter(Mandatory)][string]$User,
    [Parameter(Mandatory)][string]$Password,
    [Parameter(Mandatory)][int]$Port,
    [Parameter(Mandatory)][string]$Database
  )

  $escapedUser = [System.Uri]::EscapeDataString($User)
  $escapedPassword = [System.Uri]::EscapeDataString($Password)
  return "postgresql+psycopg://${escapedUser}:${escapedPassword}@127.0.0.1:${Port}/${Database}"
}

function Get-EsgComposeProjectName {
  param([hashtable]$Config)

  $name = Get-EsgConfigValue -Config $Config -Name "COMPOSE_PROJECT_NAME" -Default "esg-agent"
  if ($name -notmatch "^[a-z0-9][a-z0-9_-]*$") {
    throw "COMPOSE_PROJECT_INVALID: invalid Compose project name"
  }
  return $name
}

function Get-EsgPostgresContainerId {
  param([Parameter(Mandatory)][string]$ProjectName)

  $id = docker ps -aq `
    --filter "label=com.docker.compose.project=$ProjectName" `
    --filter "label=com.docker.compose.service=postgres"
  if ($LASTEXITCODE -ne 0) {
    throw "DOCKER_QUERY_FAILED: unable to query PostgreSQL container"
  }
  return ($id | Select-Object -First 1)
}

function Wait-EsgPostgres {
  param(
    [Parameter(Mandatory)][string]$ContainerId,
    [Parameter(Mandatory)][string]$User,
    [Parameter(Mandatory)][string]$Database,
    [int]$TimeoutSeconds = 120
  )

  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  do {
    docker exec $ContainerId pg_isready -U $User -d $Database *> $null
    if ($LASTEXITCODE -eq 0) {
      return
    }
    Start-Sleep -Seconds 2
  } while ((Get-Date) -lt $deadline)
  throw "POSTGRES_NOT_READY: PostgreSQL did not become ready"
}

function Get-EsgRuntimeStateRoot {
  $root = Join-Path (Get-EsgProjectRoot) "tmp\run"
  New-Item -ItemType Directory -Path $root -Force | Out-Null
  return [System.IO.Path]::GetFullPath($root)
}

function Get-EsgLogRoot {
  $root = Join-Path (Get-EsgProjectRoot) "backend\data\runtime\logs"
  New-Item -ItemType Directory -Path $root -Force | Out-Null
  return [System.IO.Path]::GetFullPath($root)
}

function Get-EsgDeliveryStateRoot {
  $root = Join-Path (Get-EsgProjectRoot) "backend\data\runtime\delivery"
  New-Item -ItemType Directory -Path $root -Force | Out-Null
  return [System.IO.Path]::GetFullPath($root)
}

function Get-EsgProcessManifestPath {
  return (Join-Path (Get-EsgDeliveryStateRoot) "processes.json")
}

function Get-EsgBuildManifestPath {
  return (Join-Path (Get-EsgDeliveryStateRoot) "frontend-build.json")
}

function Get-EsgRootHash {
  $normalized = (Get-EsgProjectRoot).TrimEnd("\").ToLowerInvariant()
  $bytes = [System.Text.Encoding]::UTF8.GetBytes($normalized)
  $sha = [System.Security.Cryptography.SHA256]::Create()
  try {
    return -join ($sha.ComputeHash($bytes) | ForEach-Object { $_.ToString("x2") })
  } finally {
    $sha.Dispose()
  }
}

function Write-EsgJsonFile {
  param(
    [Parameter(Mandatory)][string]$Path,
    [Parameter(Mandatory)]$Value,
    [int]$Depth = 8
  )

  New-Item -ItemType Directory -Path (Split-Path -Parent $Path) -Force | Out-Null
  [System.IO.File]::WriteAllText(
    $Path,
    ($Value | ConvertTo-Json -Depth $Depth),
    (New-Object System.Text.UTF8Encoding($false))
  )
}

function ConvertTo-EsgUtcDateTime {
  param([Parameter(Mandatory)]$Value)

  if ($Value -is [datetime]) {
    $dateTime = [datetime]$Value
    if ($dateTime.Kind -eq [System.DateTimeKind]::Unspecified) {
      return [datetime]::SpecifyKind($dateTime, [System.DateTimeKind]::Utc)
    }
    return $dateTime.ToUniversalTime()
  }
  if ($Value -is [datetimeoffset]) {
    return ([datetimeoffset]$Value).UtcDateTime
  }

  $text = [string]$Value
  if ($text -notmatch '(Z|[+-][0-9]{2}:[0-9]{2})$') {
    throw "TIMESTAMP_INVALID: UTC offset is required"
  }
  try {
    return [datetimeoffset]::Parse(
      $text,
      [System.Globalization.CultureInfo]::InvariantCulture,
      [System.Globalization.DateTimeStyles]::None
    ).UtcDateTime
  } catch {
    throw "TIMESTAMP_INVALID: process start time is invalid"
  }
}

function Get-EsgPackageVersion {
  $projectFile = Join-Path (Get-EsgProjectRoot) "backend\pyproject.toml"
  $match = Select-String -LiteralPath $projectFile -Pattern '^version\s*=\s*"([^"]+)"' |
    Select-Object -First 1
  if (-not $match) {
    throw "VERSION_UNKNOWN: backend package version is unavailable"
  }
  return $match.Matches[0].Groups[1].Value
}

function ConvertTo-EsgPort {
  param(
    [Parameter(Mandatory)][string]$Value,
    [Parameter(Mandatory)][string]$Name
  )

  $port = 0
  if (-not [int]::TryParse($Value, [ref]$port) -or $port -lt 1 -or $port -gt 65535) {
    throw "PORT_INVALID: $Name must be between 1 and 65535"
  }
  return $port
}
