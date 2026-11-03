#!/usr/bin/env python3
"""Poll OpenCTI Reports for Myanmar-related cyber news and notify Telegram.

Usage:
  python myanmar_news_telegram_watcher.py          # loop every 5 min
  python myanmar_news_telegram_watcher.py --once   # single pass
  python myanmar_news_telegram_watcher.py --test   # send test message
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
STATE_PATH = ROOT / "scripts" / ".myanmar_watcher_state.json"
KEYWORDS_PATH = ROOT / "scripts" / "keywords.json"

_DEFAULT_KEYWORDS = [
    "myanmar",
    "burma",
    "burmese",
    "yangon",
    "rangoon",
    "naypyidaw",
    "naypyitaw",
    "မြန်မာ",
]


def load_keywords_config() -> dict:
    """Load keywords.json; fall back to built-in list if missing/invalid."""
    if not KEYWORDS_PATH.exists():
        print(f"[warn] {KEYWORDS_PATH} missing — using defaults")
        return {
            "case_insensitive": True,
            "match_fields": ["name", "description"],
            "keywords": list(_DEFAULT_KEYWORDS),
            "regex_keywords": [],
        }
    try:
        data = json.loads(KEYWORDS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"[warn] keywords.json invalid ({exc}) — using defaults")
        return {
            "case_insensitive": True,
            "match_fields": ["name", "description"],
            "keywords": list(_DEFAULT_KEYWORDS),
            "regex_keywords": [],
        }
    keywords = [str(k).strip() for k in data.get("keywords", []) if str(k).strip()]
    regex_keywords = [
        str(k).strip() for k in data.get("regex_keywords", []) if str(k).strip()
    ]
    if not keywords and not regex_keywords:
        keywords = list(_DEFAULT_KEYWORDS)
    return {
        "case_insensitive": bool(data.get("case_insensitive", True)),
        "match_fields": data.get("match_fields") or ["name", "description"],
        "keywords": keywords,
        "regex_keywords": regex_keywords,
    }


def build_pattern(cfg: dict) -> re.Pattern[str]:
    parts: list[str] = []
    for kw in cfg["keywords"]:
        parts.append(re.escape(kw))
    for rx in cfg["regex_keywords"]:
        parts.append(rx)
    flags = re.IGNORECASE if cfg.get("case_insensitive", True) else 0
    return re.compile("|".join(parts), flags)


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()
    return env


def gql(token: str, api: str, query: str, variables: dict | None = None) -> dict:
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(
        api,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.load(resp)
    if payload.get("errors"):
        raise RuntimeError(json.dumps(payload["errors"], indent=2)[:1500])
    return payload["data"]


def telegram_send(bot: str, chat: str, text: str) -> None:
    url = f"https://api.telegram.org/bot{bot}/sendMessage"
    payload = json.dumps(
        {
            "chat_id": chat,
            "text": text[:4000],
            "disable_web_page_preview": True,
        }
    ).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.load(resp)
    if not result.get("ok"):
        raise RuntimeError(f"Telegram API error: {result}")


def load_state() -> set[str]:
    if not STATE_PATH.exists():
        return set()
    try:
        return set(json.loads(STATE_PATH.read_text(encoding="utf-8")).get("seen", []))
    except json.JSONDecodeError:
        return set()


def save_state(seen: set[str]) -> None:
    # Keep last 2000 ids
    trimmed = list(seen)[-2000:]
    STATE_PATH.write_text(
        json.dumps({"seen": trimmed}, indent=2),
        encoding="utf-8",
    )


_REPORT_NODE = """
  id
  name
  description
  content
  created_at
  creators { name }
  createdBy { ... on Identity { name } }
  objectLabel { value }
  externalReferences(first: 10) {
    edges {
      node {
        source_name
        url
        description
        external_id
      }
    }
  }
"""


def fetch_recent_reports(token: str, api: str, search: str | None = None) -> list[dict]:
    # Optional search uses OpenCTI full-text (helps catch keyword hits beyond latest 50)
    if search:
        data = gql(
            token,
            api,
            f"""
            query($search: String) {{
              reports(first: 50, orderBy: created_at, orderMode: desc, search: $search) {{
                edges {{
                  node {{
                    {_REPORT_NODE}
                  }}
                }}
              }}
            }}
            """,
            {"search": search},
        )
    else:
        data = gql(
            token,
            api,
            f"""
            {{
              reports(first: 50, orderBy: created_at, orderMode: desc) {{
                edges {{
                  node {{
                    {_REPORT_NODE}
                  }}
                }}
              }}
            }}
            """,
        )
    return [e["node"] for e in data["reports"]["edges"]]


def report_blob(report: dict, fields: list[str]) -> str:
    parts: list[str] = []
    for f in fields:
        if f == "creators":
            parts.extend(c.get("name") or "" for c in (report.get("creators") or []))
            created_by = report.get("createdBy") or {}
            if isinstance(created_by, dict):
                parts.append(created_by.get("name") or "")
        elif f == "labels":
            parts.extend(l.get("value") or "" for l in (report.get("objectLabel") or []))
        else:
            parts.append(str(report.get(f) or ""))
    return " ".join(parts)


def matches(report: dict, pattern: re.Pattern[str], fields: list[str]) -> bool:
    return bool(pattern.search(report_blob(report, fields)))


def _external_links(report: dict) -> list[str]:
    edges = ((report.get("externalReferences") or {}).get("edges")) or []
    links: list[str] = []
    for edge in edges:
        node = edge.get("node") or {}
        url = (node.get("url") or "").strip()
        if url:
            links.append(url)
    # Preserve order, drop duplicates
    seen: set[str] = set()
    unique: list[str] = []
    for url in links:
        if url not in seen:
            seen.add(url)
            unique.append(url)
    return unique


def _plain_content(report: dict, limit: int = 800) -> str:
    raw = (report.get("content") or report.get("description") or "").strip()
    if not raw:
        return ""
    # Strip simple HTML tags if present
    text = re.sub(r"<[^>]+>", " ", raw)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > limit:
        return text[: limit - 1] + "…"
    return text


def format_alert(report: dict, public: str) -> str:
    """Notification body — edit this function to change Telegram message layout."""
    creators = ", ".join(c["name"] for c in (report.get("creators") or []))
    author = (report.get("createdBy") or {}).get("name") or creators or "unknown"
    title = (report.get("name") or "").strip().replace("\n", " ")[:300]
    content = _plain_content(report)
    ext_links = _external_links(report)
    if ext_links:
        link_block = "\n".join(f"Link: {u}" for u in ext_links)
    else:
        # Fallback only when no external reference exists
        link_block = f"Link: {public}/dashboard/id/{report['id']}"

    lines = [
        "🇲🇲 Myanmar-related cyber news (OpenCTI)",
        f"Title: {title}",
        f"Source: {author}",
        f"Created: {report.get('created_at')}",
    ]
    if content:
        lines.append(f"Content: {content}")
    lines.append(link_block)
    return "\n".join(lines)


def run_once(
    env: dict[str, str], *, notify: bool = True, max_per_run: int = 10
) -> int:
    token = env["OPENCTI_ADMIN_TOKEN"]
    bot = env["TELEGRAM_BOT_TOKEN"]
    chat = env["TELEGRAM_CHAT_ID"]
    public = env.get("OPENCTI_PUBLIC_URL", "http://localhost:8080").rstrip("/")
    api = f"{public}/graphql"

    # Reload keywords.json every cycle so edits apply without restart
    cfg = load_keywords_config()
    pattern = build_pattern(cfg)
    fields = list(cfg["match_fields"])

    # "seen" = already notified only. Non-matching reports are NOT stored,
    # so editing keywords.json can still alert on older unread matches.
    seen = load_state()
    # Fetch latest + one search pass per plain keyword (dedupe by id)
    by_id: dict[str, dict] = {}
    for report in fetch_recent_reports(token, api):
        by_id[report["id"]] = report
    for kw in cfg["keywords"][:15]:
        try:
            for report in fetch_recent_reports(token, api, search=kw):
                by_id[report["id"]] = report
        except RuntimeError as exc:
            print(f"[warn] search failed for {kw!r}: {exc}")
    reports = list(by_id.values())
    sent = 0
    for report in reports:
        rid = report["id"]
        if rid in seen:
            continue
        if not matches(report, pattern, fields):
            continue
        if notify:
            if sent >= max_per_run:
                print(f"[info] reached --max-per-run={max_per_run}; rest next cycle")
                break
            try:
                telegram_send(bot, chat, format_alert(report, public))
                print(f"[sent] {report.get('name', '')[:80]}")
                sent += 1
                seen.add(rid)
            except Exception as exc:  # noqa: BLE001
                print(f"[error] telegram send failed: {exc}")
                break
        else:
            seen.add(rid)
    save_state(seen)
    return sent


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--test", action="store_true")
    parser.add_argument("--interval", type=int, default=300, help="seconds")
    parser.add_argument(
        "--max-per-run",
        type=int,
        default=10,
        help="max Telegram messages per poll (default 10)",
    )
    args = parser.parse_args()

    env = load_env()
    for key in ("OPENCTI_ADMIN_TOKEN", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
        if not env.get(key) or env.get(key, "").startswith("ChangeMe"):
            sys.exit(f"Missing {key} in .env — see MYANMAR_TELEGRAM.md")

    if args.test:
        telegram_send(
            env["TELEGRAM_BOT_TOKEN"],
            env["TELEGRAM_CHAT_ID"],
            "✅ OpenCTI Myanmar watcher test — Telegram OK",
        )
        print("[ok] test message sent")
        return

    cfg = load_keywords_config()
    print(
        f"[keywords] {KEYWORDS_PATH.name}: "
        f"{len(cfg['keywords'])} plain, {len(cfg['regex_keywords'])} regex"
    )

    if args.once:
        n = run_once(env, max_per_run=args.max_per_run)
        print(f"[done] sent={n}")
        return

    print(f"[loop] interval={args.interval}s — Ctrl+C to stop")
    print(f"[loop] edit {KEYWORDS_PATH} anytime to update match terms")
    while True:
        try:
            n = run_once(env, max_per_run=args.max_per_run)
            if n:
                print(f"[tick] sent={n}")
        except (urllib.error.URLError, RuntimeError, TimeoutError) as exc:
            print(f"[error] {exc}")
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
