#!/bin/bash
# Deployment script for EC2 production server
set -euo pipefail

APP_DIR="/app"
VENV_DIR="/app/venv"

echo "[$(date)] Starting deployment..."

cd "${APP_DIR}"

echo "[1/6] Pulling latest code..."
git pull origin main

echo "[2/6] Installing dependencies..."
"${VENV_DIR}/bin/pip" install -r requirements.txt

echo "[3/6] Running migrations for all tenant schemas..."
"${VENV_DIR}/bin/python" manage.py migrate_schemas --settings=config.settings.production

echo "[4/6] Collecting static files..."
"${VENV_DIR}/bin/python" manage.py collectstatic --noinput --settings=config.settings.production

echo "[5/6] Restarting services..."
sudo systemctl restart gunicorn
sudo systemctl restart celery
sudo systemctl restart celerybeat

echo "[6/6] Checking service status..."
sudo systemctl is-active --quiet gunicorn && echo "  gunicorn: running" || echo "  gunicorn: FAILED"
sudo systemctl is-active --quiet celery && echo "  celery: running" || echo "  celery: FAILED"
sudo systemctl is-active --quiet celerybeat && echo "  celerybeat: running" || echo "  celerybeat: FAILED"

echo "[$(date)] Deployment complete."
