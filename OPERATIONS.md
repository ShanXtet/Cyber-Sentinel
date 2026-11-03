# OpenCTI operations guide (this stack)

Platform UI: http://localhost:8080  
XTM One: http://localhost:8090

## Connectors already in this compose file

| Connector | Purpose | How it runs |
|---|---|---|
| MITRE ATT&CK | Import ATT&CK / CAPEC datasets | Always on (`connector-mitre`) |
| OpenCTI Datasets | Markings, identities, locations | Always on |
| Import/Export STIX, CSV, TXT, YARA, Document | Manual file import/export in UI | Always on |
| CVE (NVD) | Vulnerability feed | Profile `feeds` — needs `CVE_API_KEY` |
| MISP | Sync events from your MISP | Profile `misp` — needs `MISP_URL` + `MISP_KEY` |

### Enable CVE (free NVD API key)

1. Request a key: https://nvd.nist.gov/developers/request-an-api-key  
2. Put it in `.env` as `CVE_API_KEY=...`  
3. Run:

```powershell
docker compose --profile feeds up -d
```

### Enable MISP

1. In MISP, create an API key for a sync user.  
2. Set in `.env`:

```env
MISP_URL=https://your-misp.example
MISP_KEY=xxxxxxxx
MISP_SSL_VERIFY=true
```

3. Run:

```powershell
docker compose --profile misp up -d
```

More connectors: https://hub.filigran.io/cybersecurity-solutions/open-cti-integrations  
Docs: https://docs.opencti.io/latest/deployment/connectors/

## Targeted countries map is empty?

Home widget counts **`targets` → Country** relationships (last 3 months), not the
country list itself. You already have ~250 countries from OpenCTI Datasets, but
**0 country-targeting relations** until a geo/threat feed is connected.

Enable **AlienVault OTX** (free, personal email OK):

1. Create key at https://otx.alienvault.com → Settings → API Integration  
2. Put it in `.env` as `ALIENVAULT_API_KEY=...`  
3. `docker compose --profile otx up -d`

Then wait for pulses to ingest and refresh the home dashboard.

## Myanmar cyber news → Telegram

News is already stored via RSS. For Telegram alerts when Myanmar is involved:

1. Create a bot with [@BotFather](https://t.me/BotFather), put token + chat id in `.env`
2. `python scripts/setup_telegram_notifier.py`
3. `python scripts/myanmar_news_telegram_watcher.py` (or `--once` / Task Scheduler)

Full guide: [`MYANMAR_TELEGRAM.md`](./MYANMAR_TELEGRAM.md)

## Ransomware.live dashboard

RSS alone creates **Reports** only. For ransomware **groups** (Intrusion Sets) + victims,
the dedicated `connector-ransomwarelive` is enabled.

- Dashboard: **Dashboards → Ransomware Ops**
- Guide: [`RASSOMWARE_DASHBOARD.md`](./RASSOMWARE_DASHBOARD.md)
- Hub: https://hub.filigran.io/en/cybersecurity-solutions/opencti-integrations/ransomware-live

```powershell
docker compose up -d connector-ransomwarelive
python scripts/create_ransomware_dashboard.py
```

## Import STIX / MISP data (UI)

1. **STIX 2.x bundle**: Data → Import → upload `.json` (ImportFileStix).  
2. **PDF / HTML report**: Data → Import → document (ImportDocument / Analysis).  
3. **YARA rules**: Import with YARA connector scope.  
4. **RSS / public feeds**: Data → Ingestion → RSS (seeded by `scripts/setup_team_and_feeds.py`).  
5. **MISP**: use the MISP connector above (live sync), or export STIX from MISP and import as a file.

## Team users & groups

```powershell
cd ~/Desktop/docker
python scripts/setup_team_and_feeds.py
```

Creates groups **Analysts**, **Threat Intelligence**, **Readers**, sample users, and sample RSS feeds.  
**Change the temporary passwords** under Settings → Security → Users.

Fine-tune capabilities: Settings → Security → Roles / Groups.

## Production hardening

### HTTPS reverse proxy

```powershell
# Place certs:
#   production/certs/fullchain.pem
#   production/certs/privkey.pem

# Point public URL in .env:
#   OPENCTI_HOST=opencti.example.com
#   OPENCTI_PORT=443
#   OPENCTI_EXTERNAL_SCHEME=https

docker compose -f docker-compose.yml -f docker-compose.proxy.yml up -d
```

### Backups

**Windows:**

```powershell
powershell -ExecutionPolicy Bypass -File scripts/backup-volumes.ps1
```

**Ubuntu / Linux:**

```bash
./scripts/backup-volumes.sh
./scripts/restore-volumes.sh /path/to/opencti-backups/<stamp>
```

Backs up Elasticsearch, MinIO, Redis, RabbitMQ, XTM One Postgres, and RSA keys.

### Move Windows → Ubuntu

Full runbook (volume restore + LAN URL + PM2 watcher): [`MIGRATE-UBUNTU.md`](./MIGRATE-UBUNTU.md)

### Beyond Docker Desktop

For real production, prefer:

- **Kubernetes Helm**: https://docs.opencti.io/latest/deployment/installation/#helm-charts  
- **Terraform (AWS/Azure/GCP)**: https://docs.opencti.io/latest/deployment/installation/#terraform  
- Separate managed Elasticsearch/OpenSearch, Redis, S3, RabbitMQ  
- Secrets in a vault (not plain `.env`)  
- Rotate `OPENCTI_ADMIN_*`, MinIO, RabbitMQ, and connector tokens
