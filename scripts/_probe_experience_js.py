#!/usr/bin/env python3
"""Probe OpenCTI frontend bundles for Filigran Experience menu/route strings."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "platform-custom" / "_probe"
OUT.mkdir(parents=True, exist_ok=True)

files = [
    "Root-CG84KerO.js",
    "Root-K9Iivr4t.js",
    "TextField-Bkp2A289.js",
    "index-D26ltj7T.js",
]

for name in files:
    dest = OUT / name
    subprocess.check_call(
        [
            "docker",
            "compose",
            "cp",
            f"opencti:/opt/opencti/public/assets/{name}",
            str(dest),
        ]
    )
    data = dest.read_text(encoding="utf-8", errors="replace")
    print(f"\n===== {name} =====")
    for pat in [
        r".{0,180}Filigran Experience.{0,120}",
        r".{0,120}/dashboard/settings/experience.{0,120}",
        r".{0,100}settings/experience.{0,100}",
    ]:
        for i, m in enumerate(re.finditer(pat, data)):
            if i > 2:
                break
            print(repr(m.group(0)))
            print("---")
