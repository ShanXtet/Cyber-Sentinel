#!/usr/bin/env bash
# Restore OpenCTI Docker named volumes from a backup directory created by
# backup-volumes.sh or backup-volumes.ps1.
#
# Usage:
#   ./scripts/restore-volumes.sh /path/to/opencti-backups/20261015-153000
#
# Prerequisites:
#   - Docker installed; stack STOPPED (no containers using these volumes)
#   - COMPOSE_PROJECT_NAME / PROJECT_NAME matches backup (default: xtm)
#   - Place .env in the compose project root before starting the stack

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_NAME="${PROJECT_NAME:-xtm}"
# Image used only to untar into volumes. Override if Docker Hub is unreachable, e.g.:
#   HELPER_IMAGE=redis:8.10.1 ./scripts/restore-volumes.sh /path/to/backup
HELPER_IMAGE="${HELPER_IMAGE:-alpine:3.20}"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 /path/to/backup/<stamp>" >&2
  exit 1
fi

SRC="$(cd "$1" && pwd)"

pick_helper_image() {
  if docker image inspect "$HELPER_IMAGE" >/dev/null 2>&1; then
    echo "$HELPER_IMAGE"
    return
  fi
  # Prefer a local image that includes tar (common on OpenCTI hosts)
  local candidate
  for candidate in alpine:3.20 alpine:latest busybox:1.36 busybox:latest; do
    if docker image inspect "$candidate" >/dev/null 2>&1; then
      echo "$candidate"
      return
    fi
  done
  echo "$HELPER_IMAGE"
}

HELPER_IMAGE="$(pick_helper_image)"
echo "Helper image: $HELPER_IMAGE"
if ! docker image inspect "$HELPER_IMAGE" >/dev/null 2>&1; then
  echo "[warn] $HELPER_IMAGE not local — will try to pull (needs Docker Hub access)"
fi

VOLUMES=(
  "${PROJECT_NAME}_esdata"
  "${PROJECT_NAME}_s3data"
  "${PROJECT_NAME}_redisdata"
  "${PROJECT_NAME}_amqpdata"
  "${PROJECT_NAME}_pgsqlxtmonedata"
  "${PROJECT_NAME}_rsakeys"
)

echo "Restoring from $SRC"
echo "Project volumes prefix: ${PROJECT_NAME}_*"

# Refuse if core containers are still running
if docker ps --format '{{.Names}}' 2>/dev/null | grep -qE "^${PROJECT_NAME}-(opencti|elasticsearch|redis|rabbitmq|minio|pgsql)"; then
  echo "[error] Stack appears to be running. Stop it first:" >&2
  echo "  cd $ROOT && docker compose --profile feeds --profile otx down" >&2
  exit 1
fi

for vol in "${VOLUMES[@]}"; do
  archive="${SRC}/${vol}.tgz"
  if [[ ! -f "$archive" ]]; then
    echo "[skip] archive missing: $archive"
    continue
  fi
  if ! docker volume inspect "$vol" >/dev/null 2>&1; then
    echo "[create] volume $vol"
    docker volume create "$vol" >/dev/null
  else
    echo "[warn] volume $vol already exists — extracting into it (existing files may remain)"
  fi
  echo "[restore] $archive -> $vol"
  docker run --rm \
    --entrypoint sh \
    -v "${vol}:/data" \
    -v "${SRC}:/backup:ro" \
    "$HELPER_IMAGE" \
    -c "cd /data && tar xzf /backup/${vol}.tgz"
done

if [[ -f "$SRC/env.backup" && ! -f "$ROOT/.env" ]]; then
  cp "$SRC/env.backup" "$ROOT/.env"
  echo "[restore] env.backup -> $ROOT/.env"
  echo "         Edit OPENCTI_HOST / OPENCTI_PUBLIC_URL for this server before starting."
elif [[ -f "$SRC/env.backup" ]]; then
  echo "[info] $ROOT/.env already exists — left unchanged (compare with $SRC/env.backup if needed)"
fi

echo
echo "Restore complete. Next:"
echo "  1. Edit $ROOT/.env (OPENCTI_HOST, OPENCTI_PUBLIC_URL, ELASTIC_MEMORY_SIZE)"
echo "  2. cd $ROOT && docker compose --profile feeds --profile otx pull"
echo "  3. docker compose --profile feeds --profile otx up -d"
echo "  4. pm2 start scripts/ecosystem.config.cjs"
