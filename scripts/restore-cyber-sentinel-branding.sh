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

# Export OPENCTI_* so wait loops use the real published port (9080), not 8080.
# Strip Windows CRLF (\r) — sourcing a CRLF .env otherwise fails with: $'\r': command not found
ENV_UNIX="$(mktemp)"
tr -d '\r' < .env > "$ENV_UNIX"
set -a
# shellcheck disable=SC1090
source "$ENV_UNIX"
set +a
rm -f "$ENV_UNIX"

PORT="${OPENCTI_PORT:-9080}"
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
  # Health endpoint is more reliable than bare GET / while the UI is booting.
  if curl -fsS -o /dev/null \
      "http://127.0.0.1:${PORT}/health?health_access_key=${OPENCTI_HEALTHCHECK_ACCESS_KEY:-}" \
      2>/dev/null; then
    ready=1
    break
  fi
  # Fallback: GraphQL returns JSON (even AUTH_REQUIRED) when the API is up.
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
