param(
  [switch]$UpdateTrackedArtifact,
  [switch]$VerifyTrackedArtifact
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "Delivery.Common.ps1")

if ($UpdateTrackedArtifact -and $VerifyTrackedArtifact) {
  throw "INVALID_BUILD_MODE: build switches are mutually exclusive"
}

$projectRoot = Get-EsgProjectRoot
$sourcePath = Join-Path $projectRoot "delivery\launcher\EsgAgentLauncher.cs"
$appManifestPath = Join-Path $projectRoot "delivery\launcher\EsgAgentLauncher.exe.manifest"
$launcherManifestPath = Join-Path $projectRoot "delivery\launcher\launcher-manifest.json"
$trackedArtifactPath = Join-Path $projectRoot "ESG-Agent.exe"
$compilerPath = Join-Path $env:WINDIR "Microsoft.NET\Framework64\v4.0.30319\csc.exe"
$expectedCompilerVersion = "4.8.9221.0"
$expectedCompilerHash = "46809206887326D2D24DB1EFF1F3064DE972C3451ABE766B49111450A5E08E00"

function Get-LauncherCompilerInfo {
  if (-not (Test-Path -LiteralPath $compilerPath -PathType Leaf)) {
    throw "LAUNCHER_COMPILER_MISSING: .NET Framework compiler is unavailable"
  }
  $compilerItem = Get-Item -LiteralPath $compilerPath
  $compilerVersion = ($compilerItem.VersionInfo.FileVersion -split "\s+")[0]
  $compilerHash = (Get-FileHash -LiteralPath $compilerPath -Algorithm SHA256).Hash
  if ($compilerVersion -ne $expectedCompilerVersion -or $compilerHash -ne $expectedCompilerHash) {
    throw "LAUNCHER_COMPILER_MISMATCH: compiler fingerprint differs from toolchain lock"
  }
  return [ordered]@{
    file_version = $compilerVersion
    sha256 = $compilerHash
    deterministic = $false
    maintainer_only = $true
  }
}

function Test-LauncherArtifact {
  param(
    [Parameter(Mandatory)][string]$ArtifactPath,
    [Parameter(Mandatory)]$Manifest
  )

  foreach ($path in @($sourcePath, $appManifestPath, $ArtifactPath)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
      throw "LAUNCHER_ARTIFACT_MISSING: required launcher input is absent"
    }
  }
  $compilerInfo = Get-LauncherCompilerInfo
  if ((Get-EsgCanonicalTextSha256 -Path $sourcePath) -ne $Manifest.source_sha256) {
    throw "LAUNCHER_SOURCE_HASH_MISMATCH: source does not match launcher manifest"
  }
  if ((Get-EsgCanonicalTextSha256 -Path $appManifestPath) -ne $Manifest.app_manifest_sha256) {
    throw "LAUNCHER_APP_MANIFEST_HASH_MISMATCH: app manifest does not match launcher manifest"
  }
  if ((Get-FileHash -LiteralPath $ArtifactPath -Algorithm SHA256).Hash -ne $Manifest.artifact.sha256) {
    throw "LAUNCHER_BINARY_HASH_MISMATCH: executable does not match launcher manifest"
  }
  if ($compilerInfo.sha256 -ne $Manifest.compiler.sha256) {
    throw "LAUNCHER_COMPILER_MISMATCH: launcher manifest compiler differs"
  }
  $assemblyVersion = [System.Reflection.AssemblyName]::GetAssemblyName($ArtifactPath).Version.ToString()
  $versionInfo = (Get-Item -LiteralPath $ArtifactPath).VersionInfo
  if ($assemblyVersion -ne "1.5.0.0" -or $versionInfo.FileVersion -ne "1.5.0.0" -or $versionInfo.ProductVersion -ne "1.5") {
    throw "LAUNCHER_VERSION_MISMATCH: executable metadata is inconsistent"
  }
  if ((Get-Item -LiteralPath $ArtifactPath).Length -ne [long]$Manifest.artifact.size_bytes) {
    throw "LAUNCHER_SIZE_MISMATCH: executable size differs"
  }
}

if ($VerifyTrackedArtifact) {
  if (-not (Test-Path -LiteralPath $launcherManifestPath -PathType Leaf)) {
    throw "LAUNCHER_MANIFEST_MISSING: launcher manifest is required"
  }
  $trackedManifest = Get-Content -LiteralPath $launcherManifestPath -Raw | ConvertFrom-Json
  Test-LauncherArtifact -ArtifactPath $trackedArtifactPath -Manifest $trackedManifest
  Write-Output "LAUNCHER_VERIFIED sha256=$($trackedManifest.artifact.sha256)"
  exit 0
}

$compiler = Get-LauncherCompilerInfo
$buildParent = Join-Path $projectRoot "tmp\launcher-build"
$buildRoot = Join-Path $buildParent "current"
Assert-EsgPathWithin -Path $buildRoot -Root $buildParent -ErrorCode "LAUNCHER_BUILD_PATH_INVALID"
if (Test-Path -LiteralPath $buildRoot) {
  Remove-Item -LiteralPath $buildRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $buildRoot -Force | Out-Null
$candidatePath = Join-Path $buildRoot "ESG-Agent.exe"
$compileArguments = @(
  "/nologo",
  "/target:winexe",
  "/platform:anycpu",
  "/optimize+",
  "/checked+",
  "/reference:System.dll",
  "/reference:System.Core.dll",
  "/reference:System.Windows.Forms.dll",
  "/win32manifest:$appManifestPath",
  "/out:$candidatePath",
  $sourcePath
)
& $compilerPath $compileArguments
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $candidatePath -PathType Leaf)) {
  throw "LAUNCHER_COMPILE_FAILED: compiler did not create the candidate executable"
}
[System.Reflection.AssemblyName]::GetAssemblyName($candidatePath) | Out-Null

$smokeRoot = Join-Path $buildRoot "smoke"
$smokeScripts = Join-Path $smokeRoot "scripts\delivery"
New-Item -ItemType Directory -Path $smokeScripts -Force | Out-Null
$smokeExecutable = Join-Path $smokeRoot "ESG-Agent.exe"
Copy-Item -LiteralPath $candidatePath -Destination $smokeExecutable
$smokeMarker = Join-Path $smokeRoot "status.marker"
$smokeScript = @(
  '[System.IO.File]::WriteAllText($env:ESG_AGENT_LAUNCHER_SMOKE_MARKER, "status")',
  'exit 0'
)
[System.IO.File]::WriteAllLines(
  (Join-Path $smokeScripts "Test-EsgAgent.ps1"),
  $smokeScript,
  (New-Object System.Text.UTF8Encoding($false))
)
$previousNonInteractive = [System.Environment]::GetEnvironmentVariable("ESG_AGENT_LAUNCHER_NONINTERACTIVE", "Process")
$previousMarker = [System.Environment]::GetEnvironmentVariable("ESG_AGENT_LAUNCHER_SMOKE_MARKER", "Process")
[System.Environment]::SetEnvironmentVariable("ESG_AGENT_LAUNCHER_NONINTERACTIVE", "1", "Process")
[System.Environment]::SetEnvironmentVariable("ESG_AGENT_LAUNCHER_SMOKE_MARKER", $smokeMarker, "Process")
try {
  $smokeProcess = Start-Process `
    -FilePath $smokeExecutable `
    -ArgumentList "--status" `
    -WindowStyle Hidden `
    -Wait `
    -PassThru
  if ($smokeProcess.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $smokeMarker -PathType Leaf)) {
    throw "LAUNCHER_SMOKE_FAILED: candidate did not call the fixed status script"
  }
} finally {
  [System.Environment]::SetEnvironmentVariable("ESG_AGENT_LAUNCHER_NONINTERACTIVE", $previousNonInteractive, "Process")
  [System.Environment]::SetEnvironmentVariable("ESG_AGENT_LAUNCHER_SMOKE_MARKER", $previousMarker, "Process")
}

$manifest = [ordered]@{
  schema_version = 1
  public_version = "1.5"
  package_version = "1.5.0"
  target_framework = ".NET Framework 4.8.1"
  assembly_version = "1.5.0.0"
  file_version = "1.5.0.0"
  product_version = "1.5"
  source_sha256 = Get-EsgCanonicalTextSha256 -Path $sourcePath
  app_manifest_sha256 = Get-EsgCanonicalTextSha256 -Path $appManifestPath
  compiler = $compiler
  compile_arguments = @(
    "/nologo",
    "/target:winexe",
    "/platform:anycpu",
    "/optimize+",
    "/checked+",
    "/reference:System.dll",
    "/reference:System.Core.dll",
    "/reference:System.Windows.Forms.dll",
    "/win32manifest:delivery/launcher/EsgAgentLauncher.exe.manifest",
    "/out:tmp/launcher-build/ESG-Agent.exe",
    "delivery/launcher/EsgAgentLauncher.cs"
  )
  actions = [ordered]@{
    double_click = [ordered]@{ script = "Start-EsgAgent.ps1"; argument = "-OpenBrowser" }
    "--no-browser" = [ordered]@{ script = "Start-EsgAgent.ps1"; argument = $null }
    "--status" = [ordered]@{ script = "Test-EsgAgent.ps1"; argument = $null }
    "--stop" = [ordered]@{ script = "Stop-EsgAgent.ps1"; argument = $null }
  }
  artifact = [ordered]@{
    path = "ESG-Agent.exe"
    size_bytes = (Get-Item -LiteralPath $candidatePath).Length
    sha256 = (Get-FileHash -LiteralPath $candidatePath -Algorithm SHA256).Hash
  }
  generated_at_utc = (Get-Date).ToUniversalTime().ToString("o")
}

if ($UpdateTrackedArtifact) {
  $temporaryTrackedPath = Join-Path $projectRoot "ESG-Agent.exe.new"
  if (Test-Path -LiteralPath $temporaryTrackedPath) {
    Remove-Item -LiteralPath $temporaryTrackedPath -Force
  }
  Copy-Item -LiteralPath $candidatePath -Destination $temporaryTrackedPath
  Move-Item -LiteralPath $temporaryTrackedPath -Destination $trackedArtifactPath -Force
  Write-EsgJsonFile -Path $launcherManifestPath -Value $manifest
  $writtenManifest = Get-Content -LiteralPath $launcherManifestPath -Raw | ConvertFrom-Json
  Test-LauncherArtifact -ArtifactPath $trackedArtifactPath -Manifest $writtenManifest
  Write-Output "LAUNCHER_UPDATED sha256=$($writtenManifest.artifact.sha256)"
} else {
  Write-Output "LAUNCHER_CANDIDATE_BUILT path=tmp/launcher-build/current/ESG-Agent.exe sha256=$($manifest.artifact.sha256)"
}
