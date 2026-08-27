#!/bin/sh
# Brings the database up to date before the app starts serving.
#
# Both steps are required, not optional: /api/personas and /api/scenarios read
# from the database, so an unmigrated or unseeded instance serves 503 for
# everything. Both are idempotent — Alembic skips revisions already applied,
# and the seed upserts by natural key — so restarting a container is harmless.
#
# `set -e` matters here: if a migration fails, the app must not come up on a
# half-migrated schema and start writing Sessions into it.
set -e

echo "[entrypoint] Applying database migrations..."
alembic upgrade head

# Also re-syncs reference data with the image, so deploying a build with an
# edited personas.py/scenarios.py updates the tables. Note for ADR 0024: once
# Users can author their own Personas, this would deactivate them (see
# deactivate_missing in the seed script) and needs a provenance column first.
echo "[entrypoint] Seeding reference data..."
python scripts/seed_reference_data.py

echo "[entrypoint] Starting application..."
exec "$@"
