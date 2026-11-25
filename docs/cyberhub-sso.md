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

`APP__BASE_URL` is built from `OPENCTI_EXTERNAL_SCHEME`, `OPENCTI_HOST`, and `OPENCTI_PORT`. It must match the browser origin.

## Keycloak client

Client id `cyber-sentinel`, confidential, standard flow on:

| Field | Value |
|---|---|
| Valid redirect URIs | `http://192.168.11.56:9080/auth/oic/callback` |
| Valid post logout redirect URIs | `http://192.168.11.56:9080/` |
| Web origins | `http://192.168.11.56:9080` |

Assign the client role `access` to users who may open the portal card. That role is for the portal entitlement. OpenCTI still creates or matches its own user on first successful OpenID sign-in.

From the portal repo: `npm run auth:provision-cyber-sentinel` updates this client when Keycloak is reachable.

## Apply on the VM

```bash
cd /path/to/cyber-sentinel
# edit .env with the values above
docker compose up -d opencti
```

Confirm:

```bash
curl -sI http://192.168.11.56:9080/auth/oic
```

A configured provider redirects to Keycloak (HTTP 302/303). HTTP 503 means the OpenID provider is still missing from the running container env.

## Note on OpenCTI editions

Filigran documents that from OpenCTI `7.260224.0`, SSO strategies are an Enterprise Edition feature. If `/auth/oic` stays unavailable after the env is set, check the OpenCTI version and license. Local password login remains through `PROVIDERS__LOCAL__STRATEGY=LocalStrategy`.
