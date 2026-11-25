#!/usr/bin/env bash
# Bring OpenCTI back on http://192.168.11.56:9080 after a bad version pin / crash.
# Run on the CyberHub VM from the cyber-sentinel repo root.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  echo "Missing .env in $ROOT" >&2
  exit 1
fi

# Stay on the image line that matches the existing database (OpenCTI 7.x = latest).
# Pinning 6.9.x onto a 7.x volume makes the container exit and :9080 refuse connections.
if grep -q '^OPENCTI_VERSION=' .env; then
  sed -i 's/^OPENCTI_VERSION=.*/OPENCTI_VERSION=latest/' .env
else
  printf '\nOPENCTI_VERSION=latest\n' >> .env
fi

COMPOSE=(docker compose)
if [[ -f docker-compose.opensearch.yml ]] && docker compose -f docker-compose.opensearch.yml config >/dev/null 2>&1; then
  if docker ps -a --format '{{.Names}}' | grep -qi opensearch; then
    COMPOSE=(docker compose -f docker-compose.opensearch.yml)
  fi
fi

echo "Using: ${COMPOSE[*]}"
"${COMPOSE[@]}" pull opencti worker || true
if "${COMPOSE[@]}" config 2>/dev/null | grep -q 'cyber-sentinel/platform:custom'; then
  "${COMPOSE[@]}" build opencti
fi
"${COMPOSE[@]}" up -d opencti worker

echo "Waiting for :${OPENCTI_PORT:-9080} ..."
for _ in $(seq 1 60); do
  if curl -fsS -o /dev/null "http://127.0.0.1:${OPENCTI_PORT:-9080}/" || \
     curl -fsS -o /dev/null "http://192.168.11.56:${OPENCTI_PORT:-9080}/"; then
    echo "OpenCTI is responding on port ${OPENCTI_PORT:-9080}."
    curl -sI "http://127.0.0.1:${OPENCTI_PORT:-9080}/auth/oic" | head -n 5 || true
    exit 0
  fi
  sleep 5
done

echo "OpenCTI still not listening. Container status / logs:" >&2
"${COMPOSE[@]}" ps opencti || true
"${COMPOSE[@]}" logs opencti --tail=80 || true
exit 1
