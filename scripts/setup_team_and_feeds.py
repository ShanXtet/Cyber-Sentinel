#!/usr/bin/env python3
"""Bootstrap OpenCTI team groups/users and sample RSS threat-intel feeds.

Reads OPENCTI_ADMIN_TOKEN from ../.env (same folder layout as the docker stack).
Idempotent: skips entities that already exist by name/email/uri.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
API = os.environ.get("OPENCTI_URL", "http://localhost:8080") + "/graphql"

# Temporary passwords — change on first login in Settings > Security > Users
TEAM_USERS = [
    {
        "name": "CTI Analyst",
        "user_email": "analyst@example.com",
        "password": "ChangeMe_Analyst1!",
        "firstname": "CTI",
        "lastname": "Analyst",
        "group": "Analysts",
    },
    {
        "name": "Threat Intel Lead",
        "user_email": "ti-lead@example.com",
        "password": "ChangeMe_Lead1!",
        "firstname": "Threat",
        "lastname": "Lead",
        "group": "Threat Intelligence",
    },
    {
        "name": "SOC Reader",
        "user_email": "reader@example.com",
        "password": "ChangeMe_Reader1!",
        "firstname": "SOC",
        "lastname": "Reader",
        "group": "Readers",
    },
]

GROUPS = [
    {
        "name": "Analysts",
        "description": "Day-to-day CTI analysts — create/update knowledge",
        "max_confidence": 80,
        "role": "Default",
    },
    {
        "name": "Threat Intelligence",
        "description": "TI leads — broader confidence for curated intel",
        "max_confidence": 90,
        "role": "Default",
    },
    {
        "name": "Readers",
        "description": "Read-focused SOC / consumers (Default role; tighten via UI if needed)",
        "max_confidence": 50,
        "role": "Default",
    },
]

# Built-in RSS ingestion (Data > Ingestion > RSS) — no extra connector container
RSS_FEEDS = [
    {
        "name": "US-CERT / CISA Alerts",
        "uri": "https://www.cisa.gov/cybersecurity-advisories/all.xml",
        "description": "CISA cybersecurity advisories",
        "scheduling_period": "PT1H",
    },
    {
        "name": "The Hacker News",
        "uri": "https://feeds.feedburner.com/TheHackersNews",
        "description": "Public cybersecurity news (OSINT)",
        "scheduling_period": "PT2H",
    },
    {
        "name": "BleepingComputer",
        "uri": "https://www.bleepingcomputer.com/feed/",
        "description": "BleepingComputer security news",
        "scheduling_period": "PT1H",
    },
    {
        "name": "Krebs on Security",
        "uri": "https://krebsonsecurity.com/feed/",
        "description": "Investigative security journalism",
        "scheduling_period": "PT6H",
    },
    {
        "name": "Dark Reading",
        "uri": "https://www.darkreading.com/rss.xml",
        "description": "Dark Reading cybersecurity news",
        "scheduling_period": "PT2H",
    },
    {
        "name": "SOCRadar",
        "uri": "https://socradar.io/feed/",
        "description": "SOCRadar threat intelligence blog",
        "scheduling_period": "PT2H",
    },
    {
        "name": "Ransomware.live",
        "uri": "https://www.ransomware.live/rss.xml",
        "description": "Ransomware victim / group tracking feed",
        "scheduling_period": "PT1H",
    },
]


def load_token() -> str:
    if not ENV_PATH.exists():
        sys.exit(f"Missing {ENV_PATH}")
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        if line.startswith("OPENCTI_ADMIN_TOKEN="):
            return line.split("=", 1)[1].strip()
    sys.exit("OPENCTI_ADMIN_TOKEN not found in .env")


def gql(token: str, query: str, variables: dict | None = None) -> dict:
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(
        API,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.load(resp)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        sys.exit(f"HTTP {exc.code}: {detail}")
    if payload.get("errors"):
        raise RuntimeError(json.dumps(payload["errors"], indent=2))
    return payload["data"]


def existing_groups(token: str) -> dict[str, str]:
    data = gql(token, "{ groups(first:100) { edges { node { id name } } } }")
    return {e["node"]["name"]: e["node"]["id"] for e in data["groups"]["edges"]}


def existing_roles(token: str) -> dict[str, str]:
    data = gql(token, "{ roles(first:100) { edges { node { id name } } } }")
    return {e["node"]["name"]: e["node"]["id"] for e in data["roles"]["edges"]}


def existing_users(token: str) -> dict[str, str]:
    data = gql(
        token,
        "{ users(first:100) { edges { node { id name user_email } } } }",
    )
    return {
        (e["node"]["user_email"] or "").lower(): e["node"]["id"]
        for e in data["users"]["edges"]
    }


def existing_rss(token: str) -> dict[str, str]:
    data = gql(
        token,
        "{ ingestionRsss(first:100) { edges { node { id name uri } } } }",
    )
    by_uri = {}
    for e in data["ingestionRsss"]["edges"]:
        by_uri[e["node"]["uri"]] = e["node"]["id"]
    return by_uri


def ensure_groups(token: str) -> dict[str, str]:
    groups = existing_groups(token)
    roles = existing_roles(token)
    for spec in GROUPS:
        if spec["name"] in groups:
            print(f"[skip] group {spec['name']}")
            continue
        data = gql(
            token,
            """
            mutation($input: GroupAddInput!) {
              groupAdd(input: $input) { id name }
            }
            """,
            {
                "input": {
                    "name": spec["name"],
                    "description": spec["description"],
                    "group_confidence_level": {
                        "max_confidence": spec["max_confidence"],
                        "overrides": [],
                    },
                }
            },
        )
        gid = data["groupAdd"]["id"]
        groups[spec["name"]] = gid
        print(f"[ok]   group {spec['name']} -> {gid}")
        role_id = roles.get(spec["role"])
        if role_id:
            gql(
                token,
                """
                mutation($id: ID!, $input: InternalRelationshipAddInput!) {
                  groupEdit(id: $id) {
                    relationAdd(input: $input) { id }
                  }
                }
                """,
                {
                    "id": gid,
                    "input": {
                        "toId": role_id,
                        "relationship_type": "has-role",
                    },
                },
            )
            print(f"      + role {spec['role']}")
    return groups


def ensure_users(token: str, groups: dict[str, str]) -> None:
    users = existing_users(token)
    for spec in TEAM_USERS:
        email = spec["user_email"].lower()
        if email in users:
            print(f"[skip] user {spec['user_email']}")
            continue
        gid = groups.get(spec["group"])
        data = gql(
            token,
            """
            mutation($input: UserAddInput!) {
              userAdd(input: $input) { id name user_email }
            }
            """,
            {
                "input": {
                    "name": spec["name"],
                    "user_email": spec["user_email"],
                    "password": spec["password"],
                    "firstname": spec["firstname"],
                    "lastname": spec["lastname"],
                    "groups": [gid] if gid else [],
                    "prevent_default_groups": False,
                }
            },
        )
        print(
            f"[ok]   user {data['userAdd']['user_email']} "
            f"(group={spec['group']}) temp password in script"
        )


def ensure_rss(token: str) -> None:
    # With automatic_user=True, user_id is the *service account name* (must be unique).
    feeds = existing_rss(token)
    for spec in RSS_FEEDS:
        if spec["uri"] in feeds:
            print(f"[skip] rss {spec['name']}")
            continue
        service_account_name = f"[FEED - RSS] {spec['name']}"
        data = gql(
            token,
            """
            mutation($input: IngestionRssAddInput!) {
              ingestionRssAdd(input: $input) { id name uri }
            }
            """,
            {
                "input": {
                    "name": spec["name"],
                    "description": spec["description"],
                    "uri": spec["uri"],
                    "scheduling_period": spec["scheduling_period"],
                    "user_id": service_account_name,
                    "automatic_user": True,
                    "confidence_level": 50,
                    "ssl_verify": True,
                    "ingestion_running": True,
                    "report_types": ["threat-report"],
                }
            },
        )
        rid = data["ingestionRssAdd"]["id"]
        # Explicitly start in case create left it stopped
        gql(
            token,
            """
            mutation($id: ID!, $input: [EditInput!]!) {
              ingestionRssFieldPatch(id: $id, input: $input) { id ingestion_running }
            }
            """,
            {"id": rid, "input": [{"key": "ingestion_running", "value": ["true"]}]},
        )
        print(f"[ok]   rss {spec['name']} -> {rid} (running)")


def main() -> None:
    token = load_token()
    about = gql(token, "{ about { version } me { name user_email } }")
    print(
        f"Connected to OpenCTI {about['about']['version']} "
        f"as {about['me']['user_email']}\n"
    )
    groups = ensure_groups(token)
    print()
    ensure_users(token, groups)
    print()
    ensure_rss(token)
    print(
        "\nDone.\n"
        "- Change temporary user passwords in Settings > Security > Users\n"
        "- MITRE/OpenCTI dataset connectors run in Docker (check Data > Connectors)\n"
        "- STIX file import: Data > Import (uses ImportFileStix connector)\n"
        "- Enable CVE: set CVE_API_KEY in .env then: docker compose --profile feeds up -d\n"
        "- Enable MISP: set MISP_URL/MISP_KEY then: docker compose --profile misp up -d\n"
    )


if __name__ == "__main__":
    main()
