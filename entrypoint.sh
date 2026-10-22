#!/usr/bin/env bash
set -e

echo "Applying database migrations..."
python manage.py migrate --noinput

echo "Starting S4-RSK service on port ${PORT:-8084}..."
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:${PORT:-8084} \
    --workers 3 \
    --access-logfile - \
    --error-logfile -