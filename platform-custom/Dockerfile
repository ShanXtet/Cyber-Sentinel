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
# OpenCTI 7.x: /opt/opencti/public/assets
# OpenCTI 6.9.x: /opt/opencti/public (standalone build output)
# Never fail the image build — stock UI is better than a down platform.
RUN set -eux; \
  if [ -d /opt/opencti/public/assets ]; then \
    python3 /tmp/patch_frontend.py /opt/opencti/public/assets || true; \
  elif [ -d /opt/opencti/public ]; then \
    python3 /tmp/patch_frontend.py /opt/opencti/public || true; \
  else \
    echo "[warn] no frontend public dir found; shipping stock UI"; \
  fi; \
  rm -f /tmp/patch_frontend.py
