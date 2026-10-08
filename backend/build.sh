#!/usr/bin/env bash
# Exit on any error
set -o errexit

echo "==> Installing Python dependencies..."
pip install -r requirements.txt

echo "==> Collecting static assets..."
python manage.py collectstatic --no-input

echo "==> Running database migrations..."
python manage.py migrate

echo "==> Seeding default Junction A data..."
python manage.py seed_junction

echo "==> Build completed successfully!"
