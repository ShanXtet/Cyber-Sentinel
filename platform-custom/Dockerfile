# Custom OpenCTI platform image: hide Filigran Experience menu/routes.
# Extends the official image so backend stays identical; only frontend assets are patched.
#
# Build:
#   docker compose build opencti
# Upgrade later:
#   1) bump BASE_TAG / pull opencti/platform:<tag>
#   2) docker compose build --no-cache opencti
#   3) docker compose up -d opencti

ARG BASE_IMAGE=opencti/platform
ARG BASE_TAG=latest
FROM ${BASE_IMAGE}:${BASE_TAG}

COPY patch_frontend.py /tmp/patch_frontend.py
RUN python3 /tmp/patch_frontend.py /opt/opencti/public/assets \
 && rm -f /tmp/patch_frontend.py
