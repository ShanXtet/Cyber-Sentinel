#!/usr/bin/env bash
# Enable CyberHub OpenID on Community Edition by pinning OpenCTI 6.9.22.
# OpenCTI 7.x returns "Authentication provider is not available" for SSO without EE.
# Keeps Cyber Sentinel UI via custom image + branding script.
#
# Run on the CyberHub VM from /opt/opencti (or the cyber-sentinel repo root).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  echo "Missing .env" >&2
  exit 1
fi

# Normalize Windows CRLF once.
if grep -q $'\r' .env 2>/dev/null; then
  tr -d '\r' < .env > .env.unix && mv .env.unix .env
  echo "==> Converted .env from CRLF to LF"
fi

env_get() {
  local key="$1"
  tr -d '\r' < .env \
    | grep -E "^${key}=" \
    | tail -n1 \
    | sed -E "s/^${key}=//" \
    | sed -E 's/^["'\'']//; s/["'\'']$//'
}

env_set() {
  local key="$1"
  local value="$2"
  if grep -qE "^${key}=" .env; then
    # Use | as sed delimiter — values may contain /
    sed -i "s|^${key}=.*|${key}=${value}|" .env
  else
    printf '\n%s=%s\n' "$key" "$value" >> .env
  fi
}

is_uuid() {
  [[ "$1" =~ ^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$ ]]
}

COMPOSE=(docker compose -f docker-compose.opensearch.yml)
PORT="$(env_get OPENCTI_PORT)"
PORT="${PORT:-9080}"
export OPENCTI_BRANDING_URL="http://127.0.0.1:${PORT}"
export OPENCTI_BRANDING_USE_LOCALHOST=true

echo "==> Pin OpenCTI to 6.9.22 (Community OpenID)"
env_set OPENCTI_VERSION 6.9.22
env_set OPENCTI_PUBLIC_URL "http://192.168.11.56:${PORT}"
env_set CYBERHUB_OIDC_ISSUER "http://192.168.11.56:8180/realms/cyberhub"
env_set CYBERHUB_OIDC_CLIENT_ID "cyber-sentinel"
env_set CYBERHUB_OIDC_LABEL "Sign in with CyberHub"
env_set CYBERHUB_OIDC_REDIRECT_URIS "[\"http://192.168.11.56:${PORT}/auth/oic/callback\"]"

# OpenCTI refuses to start unless ADMIN_TOKEN is a real UUID.
TOKEN="$(env_get OPENCTI_ADMIN_TOKEN)"
if ! is_uuid "$TOKEN"; then
  NEW_TOKEN="$(cat /proc/sys/kernel/random/uuid 2>/dev/null || uuidgen)"
  echo "==> OPENCTI_ADMIN_TOKEN was not a UUID — generating ${NEW_TOKEN}"
  env_set OPENCTI_ADMIN_TOKEN "$NEW_TOKEN"
fi

if [[ -z "$(env_get CYBERHUB_OIDC_CLIENT_SECRET)" || "$(env_get CYBERHUB_OIDC_CLIENT_SECRET)" == "ChangeMeWithKeycloakClientSecret" ]]; then
  echo "WARNING: CYBERHUB_OIDC_CLIENT_SECRET is missing/placeholder." >&2
  echo "Run from cyberhub-portal: npm run auth:provision-cyber-sentinel" >&2
fi

echo "==> Stop OpenSearch + platform, then wipe search volume"
# MUST stop opensearch first — otherwise volume rm fails silently and 6.9.22
# boots against 7.x indices → container stays unhealthy.
"${COMPOSE[@]}" stop opencti worker opensearch || true
"${COMPOSE[@]}" rm -f opencti worker opensearch || true
docker rm -f xtm-opencti-1 xtm-opensearch-1 xtm-worker-1 xtm-worker-2 xtm-worker-3 >/dev/null 2>&1 || true

if docker volume inspect xtm_osdata >/dev/null 2>&1; then
  docker volume rm -f xtm_osdata
  echo "==> Removed volume xtm_osdata"
else
  echo "==> Volume xtm_osdata already absent"
fi

# Clear Redis session/cache left by OpenCTI 7 (best effort).
docker exec xtm-redis-1 redis-cli FLUSHALL >/dev/null 2>&1 || true

echo "==> Pull/build OpenCTI 6.9.22 custom image"
git pull --ff-only || true
"${COMPOSE[@]}" pull opensearch worker || true
docker pull "opencti/platform:6.9.22"
docker pull "opencti/worker:6.9.22"
if ! "${COMPOSE[@]}" build --build-arg "BASE_TAG=6.9.22" opencti; then
  echo "WARNING: custom image build failed — starting stock opencti/platform:6.9.22" >&2
  docker tag opencti/platform:6.9.22 cyber-sentinel/platform:custom
fi

echo "==> Start OpenSearch, then OpenCTI"
"${COMPOSE[@]}" up -d opensearch
for _ in $(seq 1 36); do
  status="$("${COMPOSE[@]}" ps opensearch --format '{{.Status}}' 2>/dev/null || true)"
  if echo "$status" | grep -qi healthy; then
    break
  fi
  sleep 5
done

"${COMPOSE[@]}" up -d opencti worker

echo "==> Wait for OpenCTI on :${PORT}"
HEALTH_KEY="$(env_get OPENCTI_HEALTHCHECK_ACCESS_KEY)"
ready=0
for i in $(seq 1 90); do
  # Surface crash-loops early.
  running="$("${COMPOSE[@]}" ps opencti --format '{{.Status}}' 2>/dev/null || true)"
  if echo "$running" | grep -Eqi 'Exit|exited|unhealthy'; then
    if [[ "$i" -gt 6 ]]; then
      echo "OpenCTI status: $running" >&2
      break
    fi
  fi
  if [[ -n "${HEALTH_KEY}" ]] && curl -fsS -o /dev/null \
      "http://127.0.0.1:${PORT}/health?health_access_key=${HEALTH_KEY}" 2>/dev/null; then
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
  echo "OpenCTI did not become ready. Status + logs:" >&2
  "${COMPOSE[@]}" ps opencti >&2 || true
  "${COMPOSE[@]}" logs opencti --tail=200 >&2 || true
  exit 1
fi

echo "==> Verify /auth/oic redirects to Keycloak"
loc="$(curl -sI "http://127.0.0.1:${PORT}/auth/oic" | tr -d '\r' | awk 'tolower($1)=="location:"{print $2}')"
if [[ "$loc" != *"8180"* && "$loc" != *"openid-connect"* ]]; then
  echo "WARNING: /auth/oic Location unexpected: ${loc:-<empty>}" >&2
  "${COMPOSE[@]}" logs opencti --tail=50 >&2 || true
else
  echo "OK: $loc"
fi

echo "==> Restore Cyber Sentinel title/theme"
python3 scripts/apply_cyber_sentinel_branding.py || {
  echo "Branding failed — check OPENCTI_ADMIN_TOKEN and retry:" >&2
  echo "  OPENCTI_BRANDING_URL=http://127.0.0.1:${PORT} python3 scripts/apply_cyber_sentinel_branding.py" >&2
}

cat <<EOF

Done.
1. Hard-refresh the browser (Ctrl+F5) — title should be Cyber Sentinel.
2. Keycloak users MUST have Email set (OpenCTI maps SSO users by email).
3. Portal card should open http://192.168.11.56:${PORT}/auth/oic
4. Local password login still works.

COOP / Origin-Agent-Cluster console warnings on plain HTTP LAN are harmless.
EOF
