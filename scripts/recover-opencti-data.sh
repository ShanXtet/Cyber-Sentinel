#!/usr/bin/env bash
# Inventory what can still be restored after an accidental OpenSearch wipe.
# Run on the CyberHub VM from /opt/opencti. Does NOT delete anything.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=== Docker volumes (OpenCTI-related) ==="
docker volume ls | grep -E 'xtm_|VOLUME' || true
echo

for vol in xtm_osdata xtm_esdata xtm_s3data xtm_redisdata xtm_amqpdata; do
  if docker volume inspect "$vol" >/dev/null 2>&1; then
    mount="$(docker volume inspect -f '{{.Mountpoint}}' "$vol" 2>/dev/null || true)"
    size="$(sudo du -sh "$mount" 2>/dev/null | awk '{print $1}' || echo '?')"
    echo "FOUND  $vol  size≈$size  path=$mount"
  else
    echo "MISSING $vol"
  fi
done

echo
echo "=== Local backup folders ==="
ls -lah "$HOME/opencti-backups" 2>/dev/null || echo "(no $HOME/opencti-backups)"
ls -lah /opt/opencti-backups 2>/dev/null || true
ls -lah /var/backups/opencti 2>/dev/null || true

echo
echo "=== Current OpenCTI image / version pin ==="
grep -E '^OPENCTI_VERSION=' .env 2>/dev/null || echo "(OPENCTI_VERSION not set)"
docker compose -f docker-compose.opensearch.yml ps opencti opensearch 2>/dev/null || true

cat <<'EOF'

Recovery options (pick one):

1) If you have a backup stamp under ~/opencti-backups/<stamp>:
     cd /opt/opencti
     # pin back to the version that created the backup (usually latest / 7.x)
     sed -i 's/^OPENCTI_VERSION=.*/OPENCTI_VERSION=latest/' .env
     docker compose -f docker-compose.opensearch.yml stop opencti worker opensearch
     ./scripts/restore-volumes.sh ~/opencti-backups/<stamp>
     # if backup has xtm_esdata but you run opensearch compose, also:
     #   docker volume create xtm_osdata   # only if missing
     # and copy/restore search data appropriately

2) If xtm_esdata still EXISTS and is large (old Elasticsearch data):
     That may be an older copy from before OpenSearch. Do NOT delete it.
     Tell the agent the size from this script output.

3) If only MinIO (xtm_s3data) remains:
     Graph/index data in OpenSearch is gone unless a VM snapshot / host backup exists.
     Check hypervisor snapshots for 192.168.11.56.

SSO note: restoring OpenCTI 7.x data requires staying on OpenCTI 7 + an EE license
for CyberHub OpenID. Do not wipe search volumes again for CE SSO.
EOF
