# Backup OpenCTI Docker named volumes (Elasticsearch, MinIO/S3, Redis, RabbitMQ, Postgres).
# Run from elevated PowerShell while stack can stay up (prefer brief maintenance window).

param(
    [string]$ProjectName = "xtm",
    [string]$BackupRoot = "$env:USERPROFILE\Desktop\opencti-backups"
)

$ErrorActionPreference = "Stop"
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$dest = Join-Path $BackupRoot $stamp
New-Item -ItemType Directory -Force -Path $dest | Out-Null

$volumes = @(
    "${ProjectName}_esdata",
    "${ProjectName}_s3data",
    "${ProjectName}_redisdata",
    "${ProjectName}_amqpdata",
    "${ProjectName}_pgsqlxtmonedata",
    "${ProjectName}_rsakeys"
)

Write-Host "Backing up to $dest"
foreach ($vol in $volumes) {
    $exists = docker volume inspect $vol 2>$null
    if (-not $exists) {
        Write-Host "[skip] volume missing: $vol"
        continue
    }
    $out = Join-Path $dest "$vol.tgz"
    Write-Host "[backup] $vol -> $out"
    docker run --rm `
        -v "${vol}:/data:ro" `
        -v "${dest}:/backup" `
        alpine:3.20 `
        tar czf "/backup/$vol.tgz" -C /data .
}

# Also snapshot .env (contains secrets — store offline / encrypted)
Copy-Item (Join-Path $PSScriptRoot "..\.env") (Join-Path $dest "env.backup") -ErrorAction SilentlyContinue

Write-Host "`nDone. Keep $dest offline and encrypted."
Write-Host "Restore example:"
Write-Host "  docker run --rm -v ${ProjectName}_esdata:/data -v ${dest}:/backup alpine tar xzf /backup/${ProjectName}_esdata.tgz -C /data"
