#!/bin/bash
# docker-entrypoint.sh — runs inside the container on every start

set -e

echo "------------------------------------------------------------"
echo "  Migraine App — container startup"
echo "------------------------------------------------------------"

# ── Ensure required directories exist ────────────────────────────────────────
# On a fresh clone the host directories don't exist yet.
# The bind-mount (.:/app) overrides anything mkdir-ed in the Dockerfile,
# so we re-create here at runtime.
mkdir -p /app/models /app/django_cache /app/staticfiles

# ── Wait for PostgreSQL ───────────────────────────────────────────────────────
DB_HOST="${DB_HOST:-db}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-migraine_user}"

echo "Waiting for PostgreSQL at ${DB_HOST}:${DB_PORT} ..."
until pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -q; do
  echo "  PostgreSQL is not ready yet — retrying in 2 s..."
  sleep 2
done
echo "PostgreSQL is ready."

# ── Compile translation messages (.po -> .mo) ─────────────────────────────────
echo "Compiling translation messages ..."
python manage.py compilemessages --ignore=venv 2>/dev/null || \
  echo "  (compilemessages skipped — no .po files found or gettext unavailable)"

# ── Migrations ────────────────────────────────────────────────────────────────
echo "Running database migrations ..."
python manage.py migrate --noinput

# ── Create a default superuser (skipped if one already exists) ────────────────
# Set DJANGO_SUPERUSER_* env vars in .env to enable automatic creation.
if [ -n "$DJANGO_SUPERUSER_USERNAME" ]; then
  echo "Creating superuser '${DJANGO_SUPERUSER_USERNAME}' if not present ..."
  python manage.py createsuperuser --noinput 2>/dev/null || \
    echo "  (superuser already exists — skipped)"
fi

# ── Collect static files ─────────────────────────────────────────────────────
echo "Collecting static files ..."
python manage.py collectstatic --noinput

# ── Start the application ─────────────────────────────────────────────────────
echo ""
echo "  App running at http://localhost:8000/sk/"
echo "------------------------------------------------------------"
exec python manage.py runserver 0.0.0.0:8000

