#!/bin/bash
# PostgreSQL backup to S3 — run via cron every 6 hours
# Crontab: 0 */6 * * * /app/infrastructure/backup.sh >> /var/log/backup.log 2>&1

set -euo pipefail

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_DIR="/tmp/db_backups"
BACKUP_FILE="society_software_${TIMESTAMP}.sql.gz"
S3_BUCKET="${AWS_STORAGE_BUCKET_NAME:-society-software-backups}"
S3_PATH="s3://${S3_BUCKET}/db-backups/${BACKUP_FILE}"

DB_NAME="${DB_NAME:-society_software}"
DB_USER="${DB_USER:-society_user}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"

mkdir -p "${BACKUP_DIR}"

echo "[$(date)] Starting backup of ${DB_NAME}..."

PGPASSWORD="${DB_PASSWORD}" pg_dump \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    -d "${DB_NAME}" \
    --no-owner \
    --no-privileges \
    | gzip > "${BACKUP_DIR}/${BACKUP_FILE}"

FILESIZE=$(du -h "${BACKUP_DIR}/${BACKUP_FILE}" | cut -f1)
echo "[$(date)] Backup created: ${BACKUP_FILE} (${FILESIZE})"

echo "[$(date)] Uploading to S3: ${S3_PATH}"
aws s3 cp "${BACKUP_DIR}/${BACKUP_FILE}" "${S3_PATH}" --storage-class STANDARD_IA

echo "[$(date)] Cleaning up local backups older than 7 days..."
find "${BACKUP_DIR}" -name "society_software_*.sql.gz" -mtime +7 -delete

echo "[$(date)] Backup complete."
