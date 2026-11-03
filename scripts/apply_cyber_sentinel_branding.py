#!/usr/bin/env python3
"""Apply Cyber Sentinel favicon + logos (with title text) + theme colors."""

from __future__ import annotations

import base64
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
BRAND_DIR = ROOT / "branding"
THEME_NAME = "Cyber Sentinel"
PLATFORM_TITLE = "Cyber Sentinel"

# Preferred local source (updated when user provides a new logo)
LOGO_SRC = BRAND_DIR / "cyber-sentinel-source.png"
# Fallback: Cursor assets dump of the griffin shield logo
LOGO_SRC_FALLBACK = Path(
    r"C:\Users\shane\.cursor\projects\c-Users-shane-Desktop-docker\assets"
    r"\c__Users_shane_AppData_Roaming_Cursor_User_workspaceStorage_"
    r"fcec939602e1c74512a3c9689e5d5ad3_images_cyber-sentinel-58f5a767-2528-4d4a-a02a-1162a7ae2295.png"
)


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()
    return env


def gql(
    token: str,
    api: str,
    query: str,
    variables: dict | None = None,
    *,
    retries: int = 12,
    delay_s: float = 5.0,
) -> dict:
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(
        api,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                payload = json.load(resp)
            if payload.get("errors"):
                raise RuntimeError(json.dumps(payload["errors"], indent=2)[:4000])
            return payload["data"]
        except (urllib.error.URLError, TimeoutError, ConnectionError, json.JSONDecodeError) as exc:
            last_exc = exc
            print(f"[wait] OpenCTI API not ready ({attempt}/{retries}): {exc}")
            time.sleep(delay_s)
        except Exception as exc:  # RemoteDisconnected etc.
            if "RemoteDisconnected" in type(exc).__name__ or "Remote end closed" in str(exc):
                last_exc = exc
                print(f"[wait] OpenCTI API not ready ({attempt}/{retries}): {exc}")
                time.sleep(delay_s)
                continue
            raise
    raise RuntimeError(f"OpenCTI API unreachable after {retries} tries: {last_exc}")


def _load_font(size: int):
    from PIL import ImageFont  # type: ignore

    candidates = [
        r"C:\Windows\Fonts\segoeuib.ttf",
        r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _fit_logo(img, max_side: int = 512):
    from PIL import Image  # type: ignore

    img = img.convert("RGBA")
    w, h = img.size
    scale = min(max_side / w, max_side / h, 1.0)
    if scale < 1.0:
        img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
    return img


def _knockout_dark(img, threshold: int = 28):
    """Make near-black pixels transparent so the crest sits on the nav chrome."""
    from PIL import Image  # type: ignore

    img = img.convert("RGBA")
    pixels = img.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            if a == 0:
                continue
            if r <= threshold and g <= threshold and b <= threshold:
                pixels[x, y] = (0, 0, 0, 0)
    return img


def _trim_alpha(img, pad: int = 0):
    from PIL import Image  # type: ignore

    bbox = img.getbbox()
    if not bbox:
        return img
    l, t, r, b = bbox
    l = max(0, l - pad)
    t = max(0, t - pad)
    r = min(img.width, r + pad)
    b = min(img.height, b + pad)
    return img.crop((l, t, r, b))


def _square_pad(img, margin_ratio: float = 0.10, size: int = 320):
    """Center crest in a transparent square with margin so UI never crops it."""
    from PIL import Image  # type: ignore

    img = img.convert("RGBA")
    w, h = img.size
    inner = int(size * (1.0 - 2 * margin_ratio))
    scale = min(inner / w, inner / h)
    nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
    resized = img.resize((nw, nh), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.paste(resized, ((size - nw) // 2, (size - nh) // 2), resized)
    return canvas


def compose_logo_with_title(source: Path) -> tuple[Path, Path, Path]:
    """Build expanded crest+wordmark, square collapsed icon, and favicon.

    Collapsed nav uses a padded transparent square so object-fit never
    crops the griffin. Expanded rail uses crest + title side-by-side.
    """
    from PIL import Image, ImageDraw, ImageFilter  # type: ignore

    BRAND_DIR.mkdir(parents=True, exist_ok=True)

    crest = _knockout_dark(Image.open(source))
    crest = _trim_alpha(crest, pad=4)
    crest = _fit_logo(crest, max_side=480)

    # --- Collapsed / favicon: full crest, square, transparent ---
    icon_only = _square_pad(crest, margin_ratio=0.12, size=320)
    collapsed_path = BRAND_DIR / "cyber-sentinel-icon.png"
    icon_only.save(collapsed_path, format="PNG")

    ico_path = BRAND_DIR / "cyber-sentinel.ico"
    sizes = [(16, 16), (32, 32), (48, 48), (64, 64)]
    ico_frames = [icon_only.resize(s, Image.Resampling.LANCZOS) for s in sizes]
    ico_frames[0].save(ico_path, format="ICO", sizes=sizes, append_images=ico_frames[1:])

    # --- Expanded: crest + "Cyber Sentinel" (theme cream / amber) ---
    out_h = 208
    crest_h = out_h - 16
    cw, ch = crest.size
    cscale = crest_h / ch
    crest_sm = crest.resize((max(1, int(cw * cscale)), crest_h), Image.Resampling.LANCZOS)

    text = PLATFORM_TITLE
    font = _load_font(78)
    tmp = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
    draw = ImageDraw.Draw(tmp)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

    gap = 18
    pad_x = 6
    canvas_w = pad_x + crest_sm.width + gap + tw + pad_x
    canvas = Image.new("RGBA", (canvas_w, out_h), (0, 0, 0, 0))
    canvas.paste(crest_sm, (pad_x, (out_h - crest_sm.height) // 2), crest_sm)

    tx = pad_x + crest_sm.width + gap
    ty = (out_h - th) // 2 - 4
    glow = Image.new("RGBA", (canvas_w, out_h), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
        glow_draw.text((tx + dx, ty + dy), text, font=font, fill=(232, 163, 23, 90))
    glow = glow.filter(ImageFilter.GaussianBlur(radius=1.2))
    canvas = Image.alpha_composite(canvas, glow)
    draw = ImageDraw.Draw(canvas)
    draw.text((tx, ty), text, font=font, fill=(243, 235, 225, 255))

    full_path = BRAND_DIR / "cyber-sentinel.png"
    canvas.save(full_path, format="PNG")

    print(f"[ok]   crest+wordmark: {full_path}  ({canvas_w}x{out_h})")
    print(f"[ok]   collapsed icon: {collapsed_path}  (320x320 square)")
    print(f"[ok]   favicon:        {ico_path}")
    return full_path, collapsed_path, ico_path


def to_data_uri(path: Path, mime: str) -> str:
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


def prepare_assets() -> tuple[str, str, str]:
    src = LOGO_SRC if LOGO_SRC.exists() else LOGO_SRC_FALLBACK
    if not src.exists():
        raise SystemExit(f"Logo not found. Place it at: {LOGO_SRC}")
    if src != LOGO_SRC:
        BRAND_DIR.mkdir(parents=True, exist_ok=True)
        LOGO_SRC.write_bytes(src.read_bytes())
        print(f"[ok]   synced source -> {LOGO_SRC}")

    full, collapsed, ico = compose_logo_with_title(LOGO_SRC)
    return (
        to_data_uri(ico, "image/x-icon"),
        to_data_uri(full, "image/png"),
        to_data_uri(collapsed, "image/png"),
    )


def main() -> None:
    env = load_env()
    token = env.get("OPENCTI_ADMIN_TOKEN")
    if not token:
        sys.exit("OPENCTI_ADMIN_TOKEN missing in .env")
    public = (env.get("OPENCTI_PUBLIC_URL") or "http://localhost:8080").rstrip("/")
    api = f"{public}/graphql"

    favicon_uri, logo_full_uri, logo_icon_uri = prepare_assets()

    # Distinct from Filigran Dark/Light (cyan #42caff / teal #00f0bc / navy #070d18).
    # Gunmetal + amber copper — home widgets inherit primary/paper/accent tokens.
    theme_input = {
        "name": THEME_NAME,
        "theme_background": "#14110e",
        "theme_paper": "#1f1a16",
        "theme_nav": "#0e0c0a",
        "theme_primary": "#e8a317",
        "theme_secondary": "#5c8a6e",
        "theme_accent": "#c45c26",
        "theme_text_color": "#f3ebe1",
        "theme_logo": logo_full_uri,
        "theme_logo_collapsed": logo_icon_uri,
        "theme_logo_login": logo_full_uri,
    }

    themes = gql(
        token,
        api,
        "{ themes(first: 50) { edges { node { id name } } } }",
    )
    theme_id = None
    for edge in themes["themes"]["edges"]:
        if edge["node"]["name"] == THEME_NAME:
            theme_id = edge["node"]["id"]
            print(f"[skip] theme exists: {theme_id}")
            break

    if not theme_id:
        created = gql(
            token,
            api,
            """
            mutation ThemeAdd($input: ThemeAddInput!) {
              themeAdd(input: $input) {
                id
                name
                theme_primary
              }
            }
            """,
            {"input": theme_input},
        )
        theme_id = created["themeAdd"]["id"]
        print(f"[ok]   theme created: {theme_id}")
    else:
        patch_keys = [
            "theme_background",
            "theme_paper",
            "theme_nav",
            "theme_primary",
            "theme_secondary",
            "theme_accent",
            "theme_text_color",
            "theme_logo",
            "theme_logo_collapsed",
            "theme_logo_login",
        ]
        inputs = [{"key": k, "value": [theme_input[k]]} for k in patch_keys]
        gql(
            token,
            api,
            """
            mutation ThemePatch($id: ID!, $input: [EditInput!]!) {
              themeFieldPatch(id: $id, input: $input) {
                id
                name
                theme_primary
              }
            }
            """,
            {"id": theme_id, "input": inputs},
        )
        print(f"[ok]   theme updated: {theme_id}")

    settings = gql(token, api, "{ settings { id } }")
    settings_id = settings["settings"]["id"]

    gql(
        token,
        api,
        """
        mutation SettingsUpdateField($id: ID!, $input: [EditInput!]!) {
          settingsEdit(id: $id) {
            fieldPatch(input: $input) {
              id
              platform_title
              platform_favicon
              platform_theme { id name theme_primary theme_secondary theme_accent }
            }
          }
        }
        """,
        {
            "id": settings_id,
            "input": [
                {"key": "platform_title", "value": [PLATFORM_TITLE]},
                {"key": "platform_favicon", "value": [favicon_uri]},
                {"key": "platform_theme", "value": [theme_id]},
            ],
        },
    )

    verify = gql(
        token,
        api,
        """
        {
          settings {
            platform_title
            platform_favicon
            platform_theme {
              name
              theme_primary
              theme_secondary
              theme_accent
              theme_background
              theme_logo
              theme_logo_login
            }
          }
        }
        """,
    )
    s = verify["settings"]
    t = s["platform_theme"]
    print("\nApplied:")
    print(f"  title     = {s['platform_title']}")
    print(f"  favicon   = set ({'yes' if s['platform_favicon'] else 'no'})")
    print(f"  logo      = set ({'yes' if t.get('theme_logo') else 'no'})")
    print(f"  theme     = {t['name']}")
    print(f"  primary   = {t['theme_primary']}")
    print(f"  secondary = {t['theme_secondary']}")
    print(f"  accent    = {t['theme_accent']}")
    print("\nHard-refresh the browser (Ctrl+F5) to see the new logo + title.")


if __name__ == "__main__":
    main()
