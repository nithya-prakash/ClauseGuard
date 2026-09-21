#!/bin/sh
# Runs before either the backend (uvicorn) or worker (celery) process starts
# - both services share this image (docker-compose's `worker` overrides
# `command:`, which bypasses a plain Dockerfile CMD but not ENTRYPOINT, so
# this wrapper is what guarantees the schema exists no matter which service
# starts first). Idempotent: `alembic upgrade head` is a no-op if the schema
# is already current.
set -e
cd /srv
alembic -c backend/alembic.ini upgrade head
exec "$@"
