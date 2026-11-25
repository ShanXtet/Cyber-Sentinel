#!/usr/bin/env bash
# Repair xtm-opensearch-1 so OpenCTI dependencies can become healthy.
# Run on the CyberHub VM from the cyber-sentinel repo root.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  echo "Missing .env in $ROOT" >&2
  exit 1
fi

COMPOSE=(docker compose -f docker-compose.opensearch.yml)

echo "==> Raising vm.max_map_count (required by OpenSearch)"
if [[ "$(sysctl -n vm.max_map_count 2>/dev/null || echo 0)" -lt 262144 ]]; then
  sudo sysctl -w vm.max_map_count=262144
  echo 'vm.max_map_count=262144' | sudo tee /etc/sysctl.d/99-opencti.conf >/dev/null
fi

ensure_env() {
  local key="$1"
  local value="$2"
  if grep -q "^${key}=" .env; then
    sed -i "s|^${key}=.*|${key}=${value}|" .env
  else
    printf '\n%s=%s\n' "$key" "$value" >> .env
  fi
}

# Weak sample passwords (e.g. changeme) make OpenSearch 3.x exit immediately.
current_pw="$(grep -E '^OPENSEARCH_ADMIN_PASSWORD=' .env | head -n1 | cut -d= -f2- || true)"
if [[ -z "$current_pw" || "$current_pw" == "changeme" || ${#current_pw} -lt 8 ]]; then
  echo "==> Setting a strong OPENSEARCH_ADMIN_PASSWORD in .env"
  ensure_env OPENSEARCH_ADMIN_PASSWORD 'ChangeMe_OpenSearch1!'
fi

# Prefer a heap the VM can actually allocate.
ensure_env ELASTIC_MEMORY_SIZE "${ELASTIC_MEMORY_SIZE_OVERRIDE:-2G}"

echo "==> Pulling compose updates and restarting OpenSearch"
git pull --ff-only || true
"${COMPOSE[@]}" pull opensearch || true
"${COMPOSE[@]}" up -d opensearch

echo "==> Waiting for OpenSearch health"
for i in $(seq 1 60); do
  status="$("${COMPOSE[@]}" ps opensearch --format '{{.Status}}' 2>/dev/null || true)"
  if echo "$status" | grep -qi healthy; then
    echo "OpenSearch is healthy: $status"
    "${COMPOSE[@]}" up -d opencti worker
    exit 0
  fi
  if echo "$status" | grep -qi 'Exit\|exited'; then
    echo "OpenSearch exited. Recent logs:" >&2
    "${COMPOSE[@]}" logs opensearch --tail=80 >&2 || true
    break
  fi
  sleep 5
done

echo "==> OpenSearch still unhealthy. Last logs:" >&2
"${COMPOSE[@]}" logs opensearch --tail=120 || true
echo >&2
echo "If logs mention corrupt index / incompatible Lucene version, reset ONLY the search volume (wipes OpenCTI search index, not MinIO files):" >&2
echo "  ${COMPOSE[*]} stop opencti worker opensearch" >&2
echo "  docker volume rm xtm_esdata" >&2
echo "  ${COMPOSE[*]} up -d opensearch && ${COMPOSE[*]} up -d opencti worker" >&2
exit 1
