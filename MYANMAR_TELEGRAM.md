# Cybersecurity news + Myanmar → Telegram alerts

## What you already have

RSS / connectors already **store** cyber news and intel in OpenCTI
(Reports, Intrusion Sets, etc.):

- The Hacker News, BleepingComputer, Krebs, Dark Reading, SOCRadar, Ransomware.live, CISA, …
- UI: **Analyses → Reports** / Home **Latest reports**

## What we add now

1. **OpenCTI Telegram notifier** (webhook → Bot API) for structured events  
2. **Myanmar keyword watcher** (polls new Reports mentioning Myanmar/Burma and pushes Telegram)

Org email is **not** required.

---

## Step 1 — Create a Telegram bot (2 minutes)

1. In Telegram, open [@BotFather](https://t.me/BotFather)
2. Send `/newbot` → follow prompts → copy the **bot token**
3. Start a chat with your bot (press **Start**)
4. Get your **chat id**:
   - Open [@userinfobot](https://t.me/userinfobot) and read your Id, **or**
   - Message your bot, then open in browser:  
     `https://api.telegram.org/bot<TOKEN>/getUpdates`  
     and copy `"chat":{"id": 123456789}`

---

## Step 2 — Put secrets in `.env`

```env
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
TELEGRAM_CHAT_ID=123456789
OPENCTI_PUBLIC_URL=http://localhost:8080
```

Never commit these values to git.

---

## Step 3 — Register notifier + trigger in OpenCTI

```powershell
cd ~/Desktop/docker
python scripts/setup_telegram_notifier.py
```

Creates:

- Notifier **Telegram (Myanmar alerts)** under Settings → Customization → Notifiers  
- Live trigger **Myanmar targeting / reports** under Profile → Triggers  
  Docs: [Notifications](https://docs.opencti.io/latest/usage/notifications/) · [Custom notifiers](https://docs.opencti.io/latest/administration/notifiers/)

---

## Step 4 — Run the news keyword watcher (RSS-friendly)

RSS titles often say “Myanmar” without a STIX Country link. The watcher catches those:

```powershell
cd ~/Desktop/docker
python scripts/myanmar_news_telegram_watcher.py
```

Leave the window open, or run every 5 minutes with Task Scheduler:

```powershell
python scripts/myanmar_news_telegram_watcher.py --once
```

### Ubuntu — run with PM2 (recommended)

```bash
cd /opt/opencti   # or your compose project root
python3 -u scripts/myanmar_news_telegram_watcher.py --test
pm2 start scripts/ecosystem.config.cjs
pm2 save && pm2 startup
pm2 logs myanmar-news-telegram
```

Runs: `python3 -u scripts/myanmar_news_telegram_watcher.py --interval 300 --max-per-run 10`  
Config: [`scripts/ecosystem.config.cjs`](./scripts/ecosystem.config.cjs)  
Server move: [`MIGRATE-UBUNTU.md`](./MIGRATE-UBUNTU.md)

### Notification message format

Edited in `scripts/myanmar_news_telegram_watcher.py` → function `format_alert()`.

Includes: Title, Source, Created, **Content** (report content/description),
**Link** = first external reference URL(s) when available (not localhost).

OpenCTI built-in trigger notifier template (all Reports) is in
`scripts/setup_telegram_notifier.py` (EJS webhook body) — that path has less
entity detail than the watcher.

### Keywords (editable)

Edit `scripts/keywords.json` — the watcher reloads it every poll (no restart needed):

```json
{
  "keywords": ["myanmar", "burma", "yangon", "မြန်မာ"],
  "regex_keywords": []
}
```

Add/remove strings under `keywords`. Use `regex_keywords` only for advanced patterns.

---

## How alerts fire

| Source | How Telegram is notified |
|---|---|
| Report / threat **targets Country Myanmar** (structured STIX) | OpenCTI live trigger + webhook notifier |
| News title/description contains Myanmar keywords (RSS) | `myanmar_news_telegram_watcher.py` |

---

## Test

```powershell
python scripts/myanmar_news_telegram_watcher.py --test
```

You should receive a test message in Telegram.

---

## Optional UI-only path (no script)

1. Settings → Customization → **Notifiers** → create Webhook  
   - Verb: `POST`  
   - URL: `https://api.telegram.org/bot<TOKEN>/sendMessage`  
   - Template: see `scripts/setup_telegram_notifier.py`  
2. Profile → **Triggers** → Live trigger  
   - Events: create (and update if desired)  
   - Filter: regardingOf / targets → Country **Myanmar**  
   - Notifier: your Telegram notifier  
