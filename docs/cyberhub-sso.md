# CyberHub SSO — server verification

SSO was not configured and the stack was not restarted. The confirmed browser address is not the OpenCTI or XTM One service in this repository.

```text
CYBER_SENTINEL_PUBLIC_URL=http://192.168.11.56:3002
```

## What that address serves

Checked on 13 November 2026:

- `GET /` returns HTTP 200 from Express. The HTML title is `Cyber Sentinel`. The page loads `/assets/index-D3zkd9AE.js` and `/assets/index-BOOfJx_Y.css`. `Last-Modified` on those files is Wed, 14 Oct 2026 05:17:14 GMT.
- `/login` and `/graphql` return that same HTML shell. This is a single-page fallback, not an OpenCTI GraphQL endpoint and not a login route.
- `/api/messages`, `/api/config/keywords`, and `/api/bot` return HTTP 200 JSON. The response allows any origin and does not ask for credentials.
- The bundle's pages are `/`, `/messages`, `/web`, `/sources`, `/correlations`, `/notifications`, and `/management`. It calls `/api/bot`, `/api/config/channels`, `/api/config/keywords`, `/api/config/websites`, `/api/correlations/brief`, `/api/correlations/rebuild`, `/api/crawler/run`, `/api/crawler/schedule`, `/api/messages`, `/api/web`, and notification routes. It also uses Socket.IO.
- The bundle does not contain OpenCTI, XTM One, Keycloak, or an OIDC authorization redirect.

This repository does not contain that application. Compose publishes OpenCTI on `${OPENCTI_PORT}` mapped to container port 8080, and XTM One on `${XTM_ONE_PORT}` mapped to container port 4000. The sample values are `8080` and `8090`. On `192.168.11.56`, port 8080 answered as Coturn and port 8090 refused the connection. Port 3002 is not that port mapping.

## OpenCTI and XTM One, separately

OpenCTI in this Compose file uses `PROVIDERS__LOCAL__STRATEGY=LocalStrategy` only. The platform image is built from `opencti/platform:latest` (`cyber-sentinel/platform:custom`). `latest` is not a deployed version, and this check did not find that image running on the confirmed address. Current OpenCTI documentation says that defining and using authentication strategies requires Enterprise Edition from version `7.260224.0`. The running edition was not readable because OpenCTI is not the process on port 3002.

The same documentation shows an OpenID Connect example whose callback is `{OpenCTI base URL}/auth/oic/callback` for provider identifier `oic`. That example belongs to OpenCTI. It was not observed as an authentication endpoint on `http://192.168.11.56:3002/`. Do not copy it onto that origin, and do not set `APP__BASE_URL` for this stack to `http://192.168.11.56:3002`.

XTM One is a second product. Its sample public URL is `${XTM_ONE_EXTERNAL_SCHEME}://${XTM_ONE_HOST}:${XTM_ONE_PORT}`. Nothing on port 3002 or port 8090 of this host identified itself as XTM One. There is no separate XTM One card. A healthy OpenCTI registration, which was also not observed here, would not by itself create a per-user XTM One session.

## Identity provider

No deployed CyberHub URL or Keycloak issuer was found for this host. The workstation portal still uses:

```text
CYBERHUB_PUBLIC_URL=http://localhost:5173
KEYCLOAK_ISSUER_URL=http://localhost:8080/realms/cyberhub
```

Those are development addresses. The application server cannot use that issuer. HTTP on `192.168.11.56:3002` is not the blocker. The blocker is that the process has no accounts and no native OpenID Connect flow, and Keycloak is not deployed where that server can reach it.

These values are still unknown. Do not invent them:

```text
CYBERHUB_SERVER_REPOSITORY_PATH
CYBER_SENTINEL_SERVER_REPOSITORY_PATH
ACTIVE_COMPOSE_FILES
ACTIVE_PROXY_CONFIGURATION
CURRENT_DEPLOYED_COMMITS
TARGET_DEPLOY_BRANCH_OR_TAG
```

No SSH user, server path, or deployment branch was available, so nothing was pulled or restarted.

## What must exist before a card can open this address

1. The source of the Express application that is actually listening on port 3002, in a repository this deployment pulls.
2. A native Authorization Code flow on that application, with a callback observed from that version, not copied from OpenCTI.
3. A per-user session. The portal role `access` must not make every signed-in person an administrator.
4. A Keycloak issuer that the server and the browser can both reach. Keep it separate from `http://192.168.11.56:3002`.
5. The existing local username/password recovery path, once one exists, left in place until the new flow is proven.

Until then, do not register a CyberHub launch URL of `http://192.168.11.56:3002/`.

## Rollback

No Compose file, proxy file, image, Keycloak client, or product setting was changed. There is nothing to roll back on the server. Discarding the documentation commit does not affect the running process.
