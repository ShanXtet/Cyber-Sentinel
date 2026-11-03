# Ransomware.live → OpenCTI Dashboard

## Why RSS alone is not enough

The **RSS feed** (`https://www.ransomware.live/rss.xml`) only creates **Reports**
with titles like `Akira has just published a new victim : FOODMatch`.

That is useful for a news list, but it does **not** create:

- Intrusion Sets (ransomware groups: Akira, LockBit, Qilin, …)
- Victim Organizations
- `targets` relationships (group → victim)

For a real **threat / group dashboard**, use the dedicated
[Ransomware.live connector](https://hub.filigran.io/en/cybersecurity-solutions/opencti-integrations/ransomware-live)
(already added to this stack as `connector-ransomwarelive`).

Docs: [Custom dashboards](https://docs.opencti.io/latest/usage/dashboards/) ·
[Widgets](https://docs.opencti.io/latest/usage/widgets/)

---

## Immediate view (RSS Reports — works now)

1. Open **Analyses → Reports**
2. Add filter: **Creator** = `[FEED - RSS] Ransomware.live`
3. Sort by **Creation date** (newest first)

Optional: save this as a **Saved filter**, then reuse it in a dashboard widget
(perspective **Entities**, entity type **Report**).

---

## Structured intel (connector — groups + victims)

```powershell
cd ~/Desktop/docker
docker compose up -d connector-ransomwarelive
```

Check **Data → Ingestion → Connectors** → `Ransomware.live` (active / last run).

After the first run you should see new:

- **Threats → Intrusion sets** (ransomware groups)
- **Entities → Organizations** (victims)
- **Analyses → Reports** (disclosure reports with `object_refs`)

First sync can take several minutes. Default schedule: every 6 hours (`PT6H`).

---

## Build the “Ransomware Ops” dashboard (UI)

1. Go to **Dashboards** (left menu) → **+** → create **Ransomware Ops**
2. Click **+** (bottom right) → **Create a widget**

### Suggested widgets

| # | Title | Perspective | Visualization | Filters |
|---|---|---|---|---|
| 1 | New victims (7d) | Entities | Number | Entity type = Report · Creator contains `Ransomware` · Created after = relative last 7 days |
| 2 | Victims over time | Entities | Timeline / Area | Same as #1 |
| 3 | Top ransomware groups | Knowledge graph | Horizontal bar | Relation type = `targets` · Source type = Intrusion Set · Target type = Organization · Created last 30 days · Attribute = source name |
| 4 | Groups list | Entities | List | Entity type = Intrusion Set · Label/search = ransomware (or Creator = connector user after first run) |
| 5 | Latest disclosures | Entities | List | Entity type = Report · Creator = `Ransomware.live` · order by created_at |

Widget design tips: [Tips for widget creation](https://docs.opencti.io/latest/usage/tips-widget-creation/)

### Share with the team

- Dashboard menu → set **authorized members** to groups `Analysts` / `Threat Intelligence`
- Or export the dashboard JSON and import on another OpenCTI instance

---

## Optional: history backfill

In `.env` / compose, set:

```env
RANSOMWARELIVE_PULL_HISTORY=true
RANSOMWARELIVE_HISTORY_START_YEAR=2024
```

Then recreate the connector. This can import a **large** volume — use only if you have enough disk/RAM.
