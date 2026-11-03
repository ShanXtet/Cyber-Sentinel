#!/usr/bin/env python3
"""Create OpenCTI webhook notifier + live trigger for Myanmar-related knowledge.

Requires in ../.env:
  OPENCTI_ADMIN_TOKEN
  TELEGRAM_BOT_TOKEN
  TELEGRAM_CHAT_ID
Optional:
  OPENCTI_PUBLIC_URL (default http://localhost:8080)
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
WEBHOOK_CONNECTOR_ID = "08f9f00f-4e52-4466-ae27-be9fa9813a88"


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
        raise RuntimeError(json.dumps(payload["errors"], indent=2)[:2500])
    return payload["data"]


def find_myanmar_id(token: str, api: str) -> str | None:
    data = gql(
        token,
        api,
        '{ countries(first: 20, search: "Myanmar") { edges { node { id name } } } }',
    )
    for edge in data["countries"]["edges"]:
        name = (edge["node"]["name"] or "").lower()
        if name in ("myanmar", "burma") or "myanmar" in name:
            return edge["node"]["id"]
    data = gql(
        token,
        api,
        '{ countries(first: 20, search: "Burma") { edges { node { id name } } } }',
    )
    for edge in data["countries"]["edges"]:
        return edge["node"]["id"]
    return None


def main() -> None:
    env = load_env()
    token = env.get("OPENCTI_ADMIN_TOKEN")
    bot = env.get("TELEGRAM_BOT_TOKEN", "")
    chat = env.get("TELEGRAM_CHAT_ID", "")
    public = env.get("OPENCTI_PUBLIC_URL", "http://localhost:8080").rstrip("/")
    api = f"{public}/graphql"

    if not token:
        sys.exit("OPENCTI_ADMIN_TOKEN missing in .env")
    if not bot or bot.startswith("ChangeMe") or not chat:
        sys.exit(
            "Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env first.\n"
            "See MYANMAR_TELEGRAM.md"
        )

    myanmar_id = find_myanmar_id(token, api)
    print(f"[info] Myanmar country id: {myanmar_id}")

    # EJS template → Telegram sendMessage JSON body
    # escape chat id as string (works for user and group ids)
    template = (
        "{\n"
        f'  "chat_id": "{chat}",\n'
        '  "text": "🚨 *OpenCTI — Myanmar-related event*\\n'
        "<%= (content[0] && content[0].events[0] && content[0].events[0].message) "
        '? content[0].events[0].message : (notification.name || \\\"event\\\") %>'
        "\\n"
        f"🔗 {public}/dashboard/id/"
        "<%= (content[0] && content[0].events[0] && content[0].events[0].instance_id) "
        '? content[0].events[0].instance_id : \\\"\\\" %>",\n'
        '  "parse_mode": "Markdown",\n'
        '  "disable_web_page_preview": true\n'
        "}"
    )

    configuration = {
        "verb": "POST",
        "url": f"https://api.telegram.org/bot{bot}/sendMessage",
        "template": template,
        "params": [],
        "headers": [
            {"attribute": "Content-Type", "value": "application/json"},
        ],
    }

    existing = gql(
        token,
        api,
        '{ notifiers(first: 50) { edges { node { id name } } } }',
    )
    notifier_id = None
    for edge in existing["notifiers"]["edges"]:
        if edge["node"]["name"] == "Telegram (Myanmar alerts)":
            notifier_id = edge["node"]["id"]
            print(f"[skip] notifier exists: {notifier_id}")
            break

    if not notifier_id:
        created = gql(
            token,
            api,
            """
            mutation($input: NotifierAddInput!) {
              notifierAdd(input: $input) { id name }
            }
            """,
            {
                "input": {
                    "name": "Telegram (Myanmar alerts)",
                    "description": "Webhook to Telegram Bot API for Myanmar CTI alerts",
                    "notifier_connector_id": WEBHOOK_CONNECTOR_ID,
                    "notifier_configuration": json.dumps(configuration),
                }
            },
        )
        notifier_id = created["notifierAdd"]["id"]
        print(f"[ok]   notifier: {notifier_id}")

    # Live trigger filters:
    # - Reports / Incidents / Intrusion Sets / Campaigns created
    # - Prefer regardingOf targets → Myanmar when country id known
    # - Also match name containing Myanmar/Burma as fallback
    # Live stream triggers support a limited filter set (entity_type works;
    # name / regardingOf do NOT). Send all new Reports to Telegram; use the
    # keyword watcher for Myanmar-only filtering.
    _ = myanmar_id
    filters_obj = {
        "mode": "and",
        "filters": [
            {
                "key": ["entity_type"],
                "values": ["Report"],
                "operator": "eq",
                "mode": "or",
            },
        ],
        "filterGroups": [],
    }

    trigger_name = "All new Reports -> Telegram"
    already = False
    try:
        triggers = gql(
            token,
            api,
            '{ triggersKnowledge(first: 50) { edges { node { id name } } } }',
        )
        for edge in triggers["triggersKnowledge"]["edges"]:
            if edge["node"]["name"] == trigger_name:
                print(f"[skip] trigger exists: {edge['node']['id']}")
                already = True
                break
    except RuntimeError as exc:
        print(f"[warn] could not list triggers: {str(exc)[:200]}")

    if not already:
        try:
            t = gql(
                token,
                api,
                """
                mutation($input: TriggerLiveAddInput!) {
                  triggerKnowledgeLiveAdd(input: $input) { id name }
                }
                """,
                {
                    "input": {
                        "name": trigger_name,
                        "description": "Notify Telegram when Myanmar-related knowledge is created",
                        "event_types": ["create"],
                        "notifiers": [notifier_id],
                        "instance_trigger": False,
                        "filters": json.dumps(filters_obj),
                    }
                },
            )
            print(f"[ok]   trigger: {t['triggerKnowledgeLiveAdd']['id']}")
        except RuntimeError as exc:
            print("[warn] Could not auto-create trigger (create it in UI):")
            print(str(exc)[:500])
            print(
                "Profile > Triggers > Live > attach notifier "
                "'Telegram (Myanmar alerts)' with Myanmar filters."
            )

    print(
        "\nDone.\n"
        "- Notifier: Settings > Customization > Notifiers\n"
        "- Also run: python scripts/myanmar_news_telegram_watcher.py\n"
        "- Guide: MYANMAR_TELEGRAM.md\n"
    )


if __name__ == "__main__":
    main()
