#!/usr/bin/env python3
"""Remove Filigran Experience menu/route links from OpenCTI frontend assets.

Runs inside the custom platform image build (and can be re-run after upgrades).
Hashed bundle names change between versions, so we scan all *.js under public/assets.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ASSETS = Path(sys.argv[1] if len(sys.argv) > 1 else "/opt/opencti/public/assets")
PUBLIC = ASSETS.parent
INDEX_HTML = PUBLIC / "index.html"

# Hide empty ProductSwitcher chevron so wordmark uses full rail width
NAV_CSS = """
<style id="cyber-sentinel-nav">
/* Hide empty ProductSwitcher chevron (options=[]). Do NOT target submenu toggles. */
nav.app-navbar a[aria-label="logo"] ~ button,
nav.app-navbar [aria-label="logo"] ~ button,
nav.app-navbar button[aria-label="Switch product"] {
  display: none !important;
}
/* Full-width text wordmark in sidebar header */
nav.app-navbar a[aria-label="logo"],
nav.app-navbar a[aria-label="logo"] img {
  max-width: 100% !important;
  width: auto !important;
  height: auto !important;
  object-fit: contain !important;
  object-position: left center !important;
}
</style>
"""

# Menu entry under Settings left nav
MENU_ITEM = re.compile(
    r",\{granted:[^,]+,link:`/dashboard/settings/experience`,label:[^}]*\(`Filigran Experience`\)\}"
)

# Capability-based default landing when opening Settings
SETTINGS_LANDING = re.compile(
    r":[A-Za-z_$][A-Za-z0-9_$]*\?`/dashboard/settings/experience`:`/dashboard`"
)

# Logo / sidebar deep-links to Experience
EXPERIENCE_TO = re.compile(r"\{to:`/dashboard/settings/experience`\}")
EXPERIENCE_HREF = re.compile(r"`/dashboard/settings/experience`")

# ProductSwitcher logo is hardcoded tiny (126x28) — enlarge for Cyber-Sentinel wordmark
LOGO_SIZE = re.compile(r"width:126,height:28")
LOGO_COLLAPSED_SIZE = re.compile(
    r"(logoCollapsed:\(0,[A-Za-z]\.jsx\)\(`img`,\{src:[^,]+,alt:`[^`]*`,)height:28,width:28"
)

# Remove OpenAEV + XTM Hub product switcher dropdown entries
PRODUCT_OPTIONS = re.compile(
    r"options:\[\{id:`openaev`.{0,1200}?id:`xtmhub`.{0,600}?\}\]"
)

# Sidebar rail: Filigran Navbar uses Tailwind w-45 (180px). Widen to w-64 (256px)
# so the Cyber-Sentinel wordmark + logo fit without "Cyber-S..." truncation.
NAV_RAIL_CLASS = re.compile(r"(`w-12`:`w-)45(`)")
# TopBar / content offsets must match OPEN_BAR_WIDTH (was 180, now 256)
NAV_OFFSET = re.compile(r"\?180:48")
# Idempotent: if already patched once, leave w-64 / ?256:48 alone (patterns above won't rematch)

# Community-only: stub Ask Ariane (shows EE chip when not licensed)
ASK_ARIANE_FN = re.compile(
    r"([A-Za-z_$][\w$]*)=\(\)=>\{let\{t_i18n:(\w)\}=(\w+)\(\),\{isChatbotAiEnabled:(\w)\}=(\w+)\(\),\{settings:\{filigran_chatbot_ai_cgu_status:"
)

# Community-only: stub CTEM / XTM One command-center button next to Ask Ariane
CTEM_FN = re.compile(
    r"([A-Za-z_$][\w$]*)=\(\)=>\{let\{t_i18n:(\w)\}=(\w+)\(\),\{settings:\{filigran_chatbot_ai_cgu_status:(\w)\}\}=(\w+)\(\),\{xtmOneConfigured:"
)

# Hide PIR nav item (Enterprise Edition)
PIR_NAV = re.compile(
    r",!\w&&\w&&\{id:`pir`,label:\w\(`PIR`\),icon:\(0,\w\.jsx\)\(\w+,\{}\),link:`/dashboard/pirs`\}"
)

# Hide all EE upsell chips (Community shows these next to EE-only features)
EE_CHIP_RETURN = re.compile(
    r"return!\w&&(\(0,\w\.jsxs\)\(\w\.Fragment,\{children:\[\(0,\w\.jsx\)\(\w+,\{ref:\w,label:\w\(`EE`\),severity:`ee`)"
)


def patch_text(data: str) -> tuple[str, list[str]]:
    changes: list[str] = []

    new, n = MENU_ITEM.subn("", data)
    if n:
        changes.append(f"removed Filigran Experience menu item x{n}")
        data = new

    new, n = SETTINGS_LANDING.subn(":`/dashboard/settings`", data)
    if n:
        changes.append(f"retargeted settings landing away from experience x{n}")
        data = new

    new, n = EXPERIENCE_TO.subn("{to:`/dashboard/settings`}", data)
    if n:
        changes.append(f"retargeted to=/settings/experience x{n}")
        data = new

    # Remaining backtick path literals (routes, redirects) → Parameters
    new, n = EXPERIENCE_HREF.subn("`/dashboard/settings`", data)
    if n:
        changes.append(f"rewrote /settings/experience path literals x{n}")
        data = new

    new, n = LOGO_SIZE.subn("width:200,height:52", data)
    if n:
        changes.append(f"enlarged ProductSwitcher logo slot x{n}")
        data = new

    new, n = LOGO_COLLAPSED_SIZE.subn(r"\1height:40,width:40", data)
    if n:
        changes.append(f"enlarged collapsed logo slot x{n}")
        data = new

    new, n = PRODUCT_OPTIONS.subn("options:[]", data)
    if n:
        changes.append(f"cleared OpenAEV/XTM Hub product switcher options x{n}")
        data = new

    new, n = NAV_RAIL_CLASS.subn(r"\g<1>64\2", data)
    if n:
        changes.append(f"widened sidebar rail w-45→w-64 (256px) x{n}")
        data = new

    new, n = NAV_OFFSET.subn("?256:48", data)
    if n:
        changes.append(f"aligned topbar/content left offset 180→256 x{n}")
        data = new

    new, n = ASK_ARIANE_FN.subn(
        r"\1=()=>{return null;let{t_i18n:\2}=\3(),{isChatbotAiEnabled:\4}=\5(),{settings:{filigran_chatbot_ai_cgu_status:",
        data,
    )
    if n:
        changes.append(f"disabled Ask Ariane / EE chip button x{n}")
        data = new

    new, n = CTEM_FN.subn(
        r"\1=()=>{return null;let{t_i18n:\2}=\3(),{settings:{filigran_chatbot_ai_cgu_status:\4}}=\5(),{xtmOneConfigured:",
        data,
    )
    if n:
        changes.append(f"disabled CTEM / XTM One command button x{n}")
        data = new

    new, n = PIR_NAV.subn("", data)
    if n:
        changes.append(f"removed PIR (EE) nav item x{n}")
        data = new

    new, n = EE_CHIP_RETURN.subn(r"return!1&&\1", data)
    if n:
        changes.append(f"suppressed EE upsell chips x{n}")
        data = new

    return data, changes


def patch_index_html() -> bool:
    if not INDEX_HTML.is_file():
        return False
    html = INDEX_HTML.read_text(encoding="utf-8", errors="surrogateescape")
    if 'id="cyber-sentinel-nav"' in html:
        return False
    if "</head>" not in html:
        return False
    INDEX_HTML.write_text(
        html.replace("</head>", NAV_CSS + "\n    </head>", 1),
        encoding="utf-8",
        errors="surrogateescape",
    )
    return True


def main() -> None:
    if not ASSETS.is_dir():
        raise SystemExit(f"Assets dir not found: {ASSETS}")

    total_files = 0
    for path in sorted(ASSETS.glob("*.js")):
        if path.name.endswith(".map"):
            continue
        original = path.read_text(encoding="utf-8", errors="surrogateescape")
        patched, changes = patch_text(original)
        if not changes:
            continue
        path.write_text(patched, encoding="utf-8", errors="surrogateescape")
        total_files += 1
        print(f"[ok] {path.name}")
        for c in changes:
            print(f"     - {c}")

    if patch_index_html():
        total_files += 1
        print("[ok] index.html")
        print("     - injected CSS to hide product-switcher chevron")

    if total_files == 0:
        print("[warn] No Filigran Experience patterns matched — UI may have changed.")
        print("       Re-check bundles after upgrading opencti/platform.")
        sys.exit(2)

    print(f"\nPatched {total_files} file(s).")


if __name__ == "__main__":
    main()
