#!/bin/bash
set -euo pipefail
# Wait for Postgres to be available
host="${POSTGRES_HOST:-postgres}"
port=5432
until pg_isready -h "$host" -p "$port" -U "${POSTGRES_USER:-postgres}"; do
  echo "Waiting for Postgres..."
  sleep 1
done

# Apply schema
psql "$DATABASE_URL" -f /app/schema.sql

# Run sample data loader
python3 /app/create_sample_data.py

# Keep container alive briefly so logs are visible
sleep 2
