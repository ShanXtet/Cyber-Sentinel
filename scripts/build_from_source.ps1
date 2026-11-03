# Build Cyber Sentinel platform image from cloned OpenCTI source.
# Requires Docker Desktop with plenty of RAM/disk (full frontend+backend build).
#
# Usage (from repo root):
#   powershell -ExecutionPolicy Bypass -File scripts\build_from_source.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Src = Join-Path $Root "opencti-src\opencti-platform"
$Tag = "cyber-sentinel/platform:from-source"

if (-not (Test-Path (Join-Path $Src "Dockerfile"))) {
  throw "opencti-src missing. Clone first: git clone --depth 1 https://github.com/OpenCTI-Platform/opencti.git opencti-src"
}

Write-Host "Building $Tag from $Src (this can take 20-60+ minutes)..."
docker buildx build --load -t $Tag -f (Join-Path $Src "Dockerfile") $Src
Write-Host "Done. Switch compose image to $Tag then: docker compose up -d opencti"
