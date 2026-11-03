# Windows → Ubuntu migration (volumes + PM2)

Move this OpenCTI Docker stack from Windows to an Ubuntu server **with data**
(Elasticsearch, MinIO, Redis, RabbitMQ, XTM One Postgres, RSA keys), then run
the Myanmar Telegram watcher under **PM2**.

## What you must copy

| Item | Required? | Notes |
|---|---|---|
| Volume backup (`*.tgz` + `env.backup`) | **Yes** | From `backup-volumes.ps1` / `.sh` |
| Project folder (`docker-compose.yml`, `scripts/`, `.env`) | **Yes** | Secrets stay offline / encrypted |
| Docker images (`docker save`) | No | Ubuntu can `docker compose pull` if online |

Images in `docker ps` are all needed for the stack, but Hub pull recreates them.
Only use `docker save` / `docker load` for offline or slow links.

## A. Backup on Windows

Prefer a quiet window (pause heavy ingest if possible):

```powershell
cd ~/Desktop/docker
powershell -ExecutionPolicy Bypass -File scripts/backup-volumes.ps1
```

Output: `~/Desktop/opencti-backups/<stamp>/` containing:

- `xtm_esdata.tgz`, `xtm_s3data.tgz`, `xtm_redisdata.tgz`, …
- `env.backup` (copy of `.env` — treat as secret)

Copy to Ubuntu (example):

```powershell
# whole project + latest backup
scp -r ~/Desktop/docker user@UBUNTU:/opt/opencti
scp -r ~/Desktop/opencti-backups/<stamp> user@UBUNTU:/opt/opencti-backups/
```

### Optional: offline images

```powershell
docker save -o opencti-images.tar `
  opencti/platform:latest opencti/worker:latest `
  opencti/connector-cve:latest opencti/connector-alienvault:latest `
  opencti/connector-cisa-known-exploited-vulnerabilities:latest `
  opencti/connector-ransomwarelive:latest opencti/connector-mitre:latest `
  opencti/connector-opencti:latest `
  docker.elastic.co/elasticsearch/elasticsearch:8.19.21 `
  redis:8.10.1 rabbitmq:4.3-management pgvector/pgvector:pg17 `
  pgsty/silo:latest alpine/openssl:latest `
  xtmone/platform:latest xtmone/worker:latest filigran/xtm-composer:latest
# scp opencti-images.tar … then on Ubuntu: docker load -i opencti-images.tar
```

## B. Prepare Ubuntu

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-v2 python3 nodejs npm
sudo npm install -g pm2
sudo usermod -aG docker "$USER"
# log out and back in so docker group applies

# Elasticsearch requirement
echo 'vm.max_map_count=262144' | sudo tee /etc/sysctl.d/99-opencti.conf
sudo sysctl --system
```

Place the project at `/opt/opencti` (or your chosen path). Ensure
`COMPOSE_PROJECT_NAME=xtm` in `.env` (same as Windows).

### Fix URLs for LAN access

Edit `.env` (from `env.backup` if needed):

```env
OPENCTI_HOST=192.168.x.x
OPENCTI_PORT=8080
OPENCTI_EXTERNAL_SCHEME=http
OPENCTI_PUBLIC_URL=http://192.168.x.x:8080
# ELASTIC_MEMORY_SIZE=4G   # raise/lower to fit server RAM
```

Keep **the same** `OPENCTI_ADMIN_TOKEN`, `OPENCTI_ENCRYPTION_KEY`, MinIO /
RabbitMQ passwords, and connector IDs as on Windows — they must match the
restored volumes.

HTTPS later: use `docker-compose.proxy.yml` + certs (see `OPERATIONS.md`).

## C. Restore volumes and start

```bash
cd /opt/opencti
chmod +x scripts/backup-volumes.sh scripts/restore-volumes.sh

# stack must be stopped
./scripts/restore-volumes.sh /opt/opencti-backups/<stamp>

docker compose --profile feeds --profile otx pull
docker compose --profile feeds --profile otx up -d
docker compose ps
```

Ransomware.live is not under a profile in this compose file — it starts with
the default services.

UI: `http://SERVER_IP:8080` — dashboard counts should roughly match Windows.

## D. PM2 — Myanmar Telegram watcher

```bash
cd /opt/opencti

# one-shot smoke test
python3 -u scripts/myanmar_news_telegram_watcher.py --test

pm2 start scripts/ecosystem.config.cjs
pm2 status
pm2 logs myanmar-news-telegram --lines 50

# survive reboot
pm2 save
pm2 startup
# run the command pm2 prints (sudo env PATH=… pm2 startup systemd -u …)
```

Config: [`scripts/ecosystem.config.cjs`](./scripts/ecosystem.config.cjs)  
Command equivalent:  
`python3 -u scripts/myanmar_news_telegram_watcher.py --interval 300 --max-per-run 10`

Keywords: edit `scripts/keywords.json` anytime (reloaded each poll).

## E. Cut over

1. Confirm Ubuntu UI + connectors + Telegram test.
2. **Stop the Windows stack** so the same connector IDs do not double-ingest:

   ```powershell
   cd ~/Desktop/docker
   docker compose --profile feeds --profile otx down
   ```

3. Point users/bookmarks at the Ubuntu LAN URL.

## Ongoing backups (Ubuntu)

```bash
cd /opt/opencti
./scripts/backup-volumes.sh
# BACKUP_ROOT=~/opencti-backups PROJECT_NAME=xtm
```

## Troubleshooting

| Symptom | Check |
|---|---|
| ES fails to start | `vm.max_map_count=262144`; `ELASTIC_MEMORY_SIZE` vs free RAM |
| Login / API broken after restore | `.env` tokens/keys ≠ Windows backup |
| Connectors missing | `docker compose --profile feeds --profile otx up -d` |
| Watcher no Telegram | `.env` `TELEGRAM_*`, `OPENCTI_ADMIN_TOKEN`; `pm2 logs` |
| Permission denied on docker | re-login after `usermod -aG docker` |

Do not commit `.env` or `env.backup` to git.
