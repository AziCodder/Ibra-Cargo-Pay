#!/bin/sh
set -e

echo "Applying database migrations..."
alembic upgrade head

echo "Starting backend server..."
if [ "$ENV" = "development" ]; then
  exec uvicorn main:app --host 0.0.0.0 --port 8000 --reload
else
  exec uvicorn main:app --host 0.0.0.0 --port 8000
fi
