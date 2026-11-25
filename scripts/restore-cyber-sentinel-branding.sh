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

COMPOSE=(docker compose -f docker-compose.opensearch.yml)

echo "==> Rebuild custom Cyber Sentinel platform image"
git pull --ff-only || true
"${COMPOSE[@]}" build opencti
"${COMPOSE[@]}" up -d opencti

echo "==> Wait for GraphQL"
for _ in $(seq 1 60); do
  if curl -fsS -o /dev/null "http://127.0.0.1:${OPENCTI_PORT:-9080}/"; then
    break
  fi
  sleep 5
done

echo "==> Apply Cyber Sentinel theme + platform_title"
python3 scripts/apply_cyber_sentinel_branding.py

echo "Done. Hard-refresh the browser (Ctrl+F5)."
