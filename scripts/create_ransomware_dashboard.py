#!/usr/bin/env python3
"""Create / update the 'Ransomware Ops' custom dashboard with starter widgets."""

from __future__ import annotations

import base64
import json
import sys
import uuid
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
API = "http://localhost:8080/graphql"


def load_token() -> str:
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        if line.startswith("OPENCTI_ADMIN_TOKEN="):
            return line.split("=", 1)[1].strip()
    sys.exit("OPENCTI_ADMIN_TOKEN missing")


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
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.load(resp)
    if payload.get("errors"):
        raise RuntimeError(json.dumps(payload["errors"], indent=2)[:2000])
    return payload["data"]


def entity_filters(creator_id: str | None) -> dict:
    filters: list[dict] = [
        {
            "key": "entity_type",
            "values": ["Report"],
            "operator": "eq",
            "mode": "or",
        }
    ]
    if creator_id:
        filters.append(
            {
                "key": "creator_id",
                "values": [creator_id],
                "operator": "eq",
                "mode": "or",
            }
        )
    return {"mode": "and", "filters": filters, "filterGroups": []}


def main() -> None:
    token = load_token()
    ws = gql(
        token,
        """
        {
          workspaces(
            first: 50
            filters: {
              mode: and
              filters: [{ key: "type", values: ["dashboard"] }]
              filterGroups: []
            }
          ) {
            edges { node { id name } }
          }
        }
        """,
    )
    existing = {e["node"]["name"]: e["node"]["id"] for e in ws["workspaces"]["edges"]}
    name = "Ransomware Ops"
    if name in existing:
        dash_id = existing[name]
        print(f"[skip] dashboard exists: {dash_id}")
    else:
        created = gql(
            token,
            """
            mutation($input: WorkspaceAddInput!) {
              workspaceAdd(input: $input) { id name }
            }
            """,
            {
                "input": {
                    "type": "dashboard",
                    "name": name,
                    "description": (
                        "Track ransomware groups and daily victims "
                        "from Ransomware.live"
                    ),
                    "tags": ["ransomware", "threats"],
                }
            },
        )
        dash_id = created["workspaceAdd"]["id"]
        print(f"[ok]   created dashboard: {dash_id}")

    users = gql(
        token,
        '{ users(first: 50, search: "Ransomware") { edges { node { id name } } } }',
    )
    creator_id = None
    for edge in users["users"]["edges"]:
        if edge["node"]["name"] == "[FEED - RSS] Ransomware.live":
            creator_id = edge["node"]["id"]
            break
    print(f"[info] RSS creator_id={creator_id}")

    w1, w2, w3 = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    filters = entity_filters(creator_id)
    empty_dyn = {"mode": "and", "filters": [], "filterGroups": []}
    manifest = {
        "widgets": {
            w1: {
                "id": w1,
                "type": "number",
                "perspective": "entities",
                "dataSelection": [
                    {
                        "label": "Ransomware disclosures (RSS)",
                        "number": 1000,
                        "attribute": "entity_type",
                        "date_attribute": "created_at",
                        "filters": filters,
                        "dynamicFrom": empty_dyn,
                        "dynamicTo": empty_dyn,
                    }
                ],
                "parameters": {
                    "title": "Ransomware disclosures (count)",
                    "interval": "day",
                },
                "layout": {
                    "w": 4,
                    "h": 2,
                    "x": 0,
                    "y": 0,
                    "i": w1,
                    "moved": False,
                    "static": False,
                },
            },
            w2: {
                "id": w2,
                "type": "temporal-bar",
                "perspective": "entities",
                "dataSelection": [
                    {
                        "label": "Daily victims (RSS)",
                        "number": 1000,
                        "attribute": "entity_type",
                        "date_attribute": "created_at",
                        "filters": filters,
                        "dynamicFrom": empty_dyn,
                        "dynamicTo": empty_dyn,
                    }
                ],
                "parameters": {
                    "title": "Daily ransomware disclosures",
                    "interval": "day",
                },
                "layout": {
                    "w": 8,
                    "h": 4,
                    "x": 4,
                    "y": 0,
                    "i": w2,
                    "moved": False,
                    "static": False,
                },
            },
            w3: {
                "id": w3,
                "type": "list",
                "perspective": "entities",
                "dataSelection": [
                    {
                        "label": "Latest disclosures",
                        "number": 20,
                        "attribute": "entity_type",
                        "date_attribute": "created_at",
                        "filters": filters,
                        "dynamicFrom": empty_dyn,
                        "dynamicTo": empty_dyn,
                    }
                ],
                "parameters": {
                    "title": "Latest Ransomware.live victims (RSS)",
                    "interval": "day",
                },
                "layout": {
                    "w": 12,
                    "h": 8,
                    "x": 0,
                    "y": 4,
                    "i": w3,
                    "moved": False,
                    "static": False,
                },
            },
        },
        "config": {},
    }
    encoded = base64.b64encode(json.dumps(manifest).encode()).decode()
    gql(
        token,
        """
        mutation($id: ID!, $input: [EditInput!]!) {
          workspaceFieldPatch(id: $id, input: $input) { id name }
        }
        """,
        {"id": dash_id, "input": [{"key": "manifest", "value": [encoded]}]},
    )
    print(f"[ok]   widgets applied")
    print(
        f"Open: http://localhost:8080/dashboard/workspaces/dashboards/{dash_id}"
    )
    print(
        "After Ransomware.live connector runs, add a Knowledge Graph widget "
        "(relation targets, source=Intrusion Set) for Top Groups — see "
        "RASSOMWARE_DASHBOARD.md"
    )


if __name__ == "__main__":
    main()
