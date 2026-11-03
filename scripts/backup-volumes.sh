#!/usr/bin/env bash
# Backup OpenCTI Docker named volumes (Elasticsearch, MinIO/S3, Redis, RabbitMQ, Postgres, RSA keys).
# Prefer a brief maintenance window (pause heavy writes) for a cleaner ES snapshot.
#
# Usage:
#   ./scripts/backup-volumes.sh
#   PROJECT_NAME=xtm BACKUP_ROOT=~/opencti-backups ./scripts/backup-volumes.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_NAME="${PROJECT_NAME:-xtm}"
BACKUP_ROOT="${BACKUP_ROOT:-$HOME/opencti-backups}"
STAMP="$(date +%Y%m%d-%H%M%S)"
DEST="${BACKUP_ROOT}/${STAMP}"
HELPER_IMAGE="${HELPER_IMAGE:-alpine:3.20}"

VOLUMES=(
  "${PROJECT_NAME}_esdata"
  "${PROJECT_NAME}_s3data"
  "${PROJECT_NAME}_redisdata"
  "${PROJECT_NAME}_amqpdata"
  "${PROJECT_NAME}_pgsqlxtmonedata"
  "${PROJECT_NAME}_rsakeys"
)

mkdir -p "$DEST"
echo "Backing up to $DEST"

for vol in "${VOLUMES[@]}"; do
  if ! docker volume inspect "$vol" >/dev/null 2>&1; then
    echo "[skip] volume missing: $vol"
    continue
  fi
  out="${DEST}/${vol}.tgz"
  echo "[backup] $vol -> $out"
  docker run --rm \
    --entrypoint tar \
    -v "${vol}:/data:ro" \
    -v "${DEST}:/backup" \
    "$HELPER_IMAGE" \
    czf "/backup/${vol}.tgz" -C /data .
done

if [[ -f "$ROOT/.env" ]]; then
  cp "$ROOT/.env" "$DEST/env.backup"
  echo "[backup] .env -> $DEST/env.backup"
else
  echo "[warn] .env not found at $ROOT/.env"
fi

echo
echo "Done. Keep $DEST offline and encrypted."
echo "Restore: ./scripts/restore-volumes.sh $DEST"
