# CyberHub SSO for Cyber Sentinel (OpenCTI)

Cyber Sentinel on this host is OpenCTI at `http://192.168.11.56:9080/`. Local username/password login stays available. CyberHub sign-in uses OpenCTI’s OpenID Connect provider against the shared Keycloak realm `cyberhub`.

## Browser addresses

```text
Dashboard:   http://192.168.11.56:9080/
OIDC start:  http://192.168.11.56:9080/auth/oic
OIDC callback: http://192.168.11.56:9080/auth/oic/callback
```

The CyberHub portal card launches `http://192.168.11.56:9080/auth/oic` so a portal session can continue into OpenCTI without a second password when Keycloak already has a session.

## Environment

Add these to the stack `.env` (see `.env.sample`):

```text
OPENCTI_HOST=192.168.11.56
OPENCTI_PORT=9080
OPENCTI_EXTERNAL_SCHEME=http
CYBERHUB_OIDC_ISSUER=http://192.168.11.56:8180/realms/cyberhub
CYBERHUB_OIDC_CLIENT_ID=cyber-sentinel
CYBERHUB_OIDC_CLIENT_SECRET=<Keycloak client secret>
CYBERHUB_OIDC_REDIRECT_URIS=["http://192.168.11.56:9080/auth/oic/callback"]
CYBERHUB_OIDC_LABEL=Sign in with CyberHub
```

`APP__BASE_URL` is built from `OPENCTI_EXTERNAL_SCHEME`, `OPENCTI_HOST`, and `OPENCTI_PORT` **with a trailing slash**. It must match the browser origin.

## Keycloak client

Client id `cyber-sentinel`, confidential, standard flow on:

| Field | Value |
|---|---|
| Valid redirect URIs | `http://192.168.11.56:9080/auth/oic/callback` |
| Valid post logout redirect URIs | `http://192.168.11.56:9080/` |
| Web origins | `http://192.168.11.56:9080` |
| Default client scopes | include `email`, `profile`, `roles` (or Full scope allowed) |

Assign the client role `access` to users who may open the portal card. That role is for the portal entitlement. OpenCTI still creates or matches its own user on first successful OpenID sign-in.

**Every Keycloak user must have an Email.** OpenCTI maps SSO users by the `email` claim. An empty email after a successful CyberHub login ends on `/dashboard` with `Invalid authentication, please ask your administrator`. Set Email (and Email verified) under **Users → [user] → Details**, or re-run `npm run auth:provision-cyber-sentinel` (it backfills `username@cyberhub.local` when email is missing).

From the portal repo: `npm run auth:provision-cyber-sentinel` updates this client when Keycloak is reachable.

## Apply on the VM

```bash
cd /path/to/cyberhub-portal
npm run auth:provision-cyber-sentinel

cd /path/to/cyber-sentinel
# confirm CYBERHUB_OIDC_* in .env match the provisioned client secret
docker compose up -d opencti
# or: docker compose -f docker-compose.opensearch.yml up -d opencti
```

Confirm:

```bash
curl -sI http://192.168.11.56:9080/auth/oic
docker compose logs opencti --tail=200 | grep -iE 'OPENID|Error login|Invalid authentication'
```

A configured provider redirects to Keycloak (HTTP 302/303). HTTP 503 means the OpenID provider is still missing from the running container env.

## OpenSearch unhealthy (`dependency opensearch failed to start`)

If compose shows `xtm-opensearch-1 is unhealthy`, OpenCTI cannot start. On the VM:

```bash
cd /path/to/cyber-sentinel
git pull --ff-only origin feat/cyber-sentinel-server-sso
bash scripts/fix-opensearch.sh
```

Typical causes: weak `OPENSEARCH_ADMIN_PASSWORD` (`changeme` is rejected), low `vm.max_map_count`, heap too large, or reusing the Elasticsearch volume (`xtm_esdata`) which makes OpenSearch exit with `nodes/0: Not a directory`. This compose uses a dedicated `osdata` volume.

## Port refused on `:9080`

If the portal card opens `http://192.168.11.56:9080/auth/oic` and the browser shows **refused to connect**, OpenCTI is not running (often after pinning `OPENCTI_VERSION=6.9.22` onto an existing OpenCTI **7.x** database).

Restore on the VM:

```bash
cd /path/to/cyber-sentinel
git pull --ff-only origin feat/cyber-sentinel-server-sso
bash scripts/recover-opencti-9080.sh
# or manually:
#   set OPENCTI_VERSION=latest in .env
#   docker compose -f docker-compose.opensearch.yml up -d opencti worker
```

Confirm: `curl -sI http://192.168.11.56:9080/auth/oic` returns a Keycloak redirect (302/303).

## Note on OpenCTI editions (Invalid authentication after Keycloak)

From OpenCTI `7.260224.0`, **SSO is Enterprise Edition only**. Community `latest` can still show “Sign in with CyberHub” and redirect to Keycloak, then land on `/dashboard` with **Invalid authentication**.

For an existing 7.x stack:

1. Keep `OPENCTI_VERSION=latest` (do **not** downgrade in place), and  
2. Set `OPENCTI_ENTERPRISE_EDITION_LICENSE` to a Filigran/OpenCTI EE PEM, **or**  
3. Build a **new** Community stack on `OPENCTI_VERSION=6.9.22` with empty volumes (backup first).

Local password login remains through `PROVIDERS__LOCAL__STRATEGY=LocalStrategy`.
