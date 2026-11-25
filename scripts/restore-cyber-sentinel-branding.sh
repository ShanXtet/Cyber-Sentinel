#!/usr/bin/env bash
# Restore Cyber Sentinel title, amber theme, and logos after a stock OpenCTI reset.
# Run on the CyberHub VM from the cyber-sentinel repo root.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  echo "Missing .env" >&2
  exit 1
fi

# Read a single KEY from .env without `source` (PEMs / CRLF / spaces break source).
env_get() {
  local key="$1"
  tr -d '\r' < .env \
    | grep -E "^${key}=" \
    | tail -n1 \
    | sed -E "s/^${key}=//" \
    | sed -E 's/^["'\'']//; s/["'\'']$//'
}

PORT="$(env_get OPENCTI_PORT)"
PORT="${PORT:-9080}"
HEALTH_KEY="$(env_get OPENCTI_HEALTHCHECK_ACCESS_KEY)"

# Branding must hit OpenCTI, never Coturn on :8080.
export OPENCTI_BRANDING_URL="http://127.0.0.1:${PORT}"
export OPENCTI_BRANDING_USE_LOCALHOST=true

COMPOSE=(docker compose -f docker-compose.opensearch.yml)

echo "==> Rebuild custom Cyber Sentinel platform image"
git pull --ff-only || true
"${COMPOSE[@]}" build opencti
"${COMPOSE[@]}" up -d opencti

echo "==> Wait for OpenCTI on :${PORT} (GraphQL)"
ready=0
for _ in $(seq 1 90); do
  if [[ -n "${HEALTH_KEY}" ]] && curl -fsS -o /dev/null \
      "http://127.0.0.1:${PORT}/health?health_access_key=${HEALTH_KEY}" \
      2>/dev/null; then
    ready=1
    break
  fi
  body="$(curl -fsS -X POST "http://127.0.0.1:${PORT}/graphql" \
      -H 'content-type: application/json' \
      -d '{"query":"{ __typename }"}' 2>/dev/null || true)"
  if [[ "$body" == *"__typename"* || "$body" == *"errors"* ]]; then
    ready=1
    break
  fi
  sleep 5
done

if [[ "$ready" -ne 1 ]]; then
  echo "OpenCTI did not become ready on :${PORT}. Recent logs:" >&2
  "${COMPOSE[@]}" logs opencti --tail=80 >&2 || true
  exit 1
fi

echo "==> Apply Cyber Sentinel theme + platform_title via ${OPENCTI_BRANDING_URL}"
python3 scripts/apply_cyber_sentinel_branding.py

echo "Done. Hard-refresh the browser (Ctrl+F5)."
