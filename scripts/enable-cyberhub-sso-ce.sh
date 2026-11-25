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
    sed -i "s|^${key}=.*|${key}=${value}|" .env
  else
    printf '\n%s=%s\n' "$key" "$value" >> .env
  fi
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

if [[ -z "$(env_get CYBERHUB_OIDC_CLIENT_SECRET)" || "$(env_get CYBERHUB_OIDC_CLIENT_SECRET)" == "ChangeMeWithKeycloakClientSecret" ]]; then
  echo "WARNING: CYBERHUB_OIDC_CLIENT_SECRET is missing/placeholder." >&2
  echo "Run from cyberhub-portal: npm run auth:provision-cyber-sentinel" >&2
fi

echo "==> Stop platform and reset search volume (7.x index is incompatible with 6.9.22)"
"${COMPOSE[@]}" stop opencti worker || true
"${COMPOSE[@]}" rm -f opencti worker || true
docker volume rm xtm_osdata 2>/dev/null || true

echo "==> Pull/build OpenCTI 6.9.22 custom image"
git pull --ff-only || true
"${COMPOSE[@]}" pull opensearch worker || true
docker pull "opencti/platform:6.9.22"
docker pull "opencti/worker:6.9.22"
"${COMPOSE[@]}" build --build-arg "BASE_TAG=6.9.22" opencti
"${COMPOSE[@]}" up -d opensearch
"${COMPOSE[@]}" up -d opencti worker

echo "==> Wait for OpenCTI on :${PORT}"
HEALTH_KEY="$(env_get OPENCTI_HEALTHCHECK_ACCESS_KEY)"
ready=0
for _ in $(seq 1 90); do
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
  echo "OpenCTI did not become ready. Logs:" >&2
  "${COMPOSE[@]}" logs opencti --tail=100 >&2 || true
  exit 1
fi

echo "==> Verify /auth/oic redirects to Keycloak"
loc="$(curl -sI "http://127.0.0.1:${PORT}/auth/oic" | tr -d '\r' | awk 'tolower($1)==\"location:\"{print $2}')"
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
