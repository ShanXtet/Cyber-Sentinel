# Custom OpenCTI platform image (Cyber Sentinel)

Two ways to remove **Settings → Filigran Experience**:

| Method | Folder | Speed | When to use |
|---|---|---|---|
| **A. Asset patch** (default in compose) | `platform-custom/` | Seconds–minutes | Daily upgrades |
| **B. Source clone** | `opencti-src/` | 20–60+ min build | Deeper React edits |

See also: [`opencti-src/CYBER_SENTINEL.md`](./opencti-src/CYBER_SENTINEL.md)

---

## A) Asset patch (compose default)

Hides **Settings → Filigran Experience** from the UI by patching the official
`opencti/platform` frontend assets at image build time.

## What it does

- Removes the **Filigran Experience** left-nav item under Settings
- Redirects Experience deep-links to **Settings → Parameters**
- Does **not** unlock Enterprise Edition features (license still required for EE)
- Backend / connectors / data stay on the stock OpenCTI platform

## Build & run

```powershell
cd C:\Users\shane\Desktop\docker
docker compose build opencti
docker compose up -d opencti
```

Hard-refresh the browser (**Ctrl+F5**).  
Settings menu should no longer show Filigran Experience.

## Upgrade OpenCTI later

Upstream hashed JS filenames change every release — rebuild from the new base:

```powershell
docker pull opencti/platform:latest
docker compose build --no-cache opencti
docker compose up -d opencti
```

If the patch prints `[warn] No Filigran Experience patterns matched`, the UI
structure changed — update regexes in `platform-custom/patch_frontend.py`.

## Files

| Path | Role |
|---|---|
| `platform-custom/Dockerfile` | `FROM opencti/platform` + run patch |
| `platform-custom/patch_frontend.py` | Remove Experience menu/routes |
| `docker-compose.yml` → `opencti` | `build:` + `image: cyber-sentinel/platform:custom` |

Optional: set `XTM__XTMHUB_URL=` on the `opencti` service to drop Hub UI hooks.
