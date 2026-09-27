#!/bin/sh
set -eu
cd "${OXOMIUM_DEMO_DIR:-/opt/oxomium-demo}"
docker compose run --rm --no-deps web python manage.py reset_demo
docker compose up -d --wait web
