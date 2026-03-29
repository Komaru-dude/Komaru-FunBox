#!/bin/sh
mkdir -p /backups

echo "=== Backup service started at $(date) ==="
echo "Бэкапы будут сохраняться в /backups каждые 24 часа"

while true; do
  TIMESTAMP=$(date +%Y-%m-%d_%H-%M-%S)
  BACKUP_FILE="/backups/funbox_db_${TIMESTAMP}.sql.gz"

  echo "[${TIMESTAMP}] Starting backup of database ${DB_NAME}..."

  pg_dump -h ${DB_HOST} -U ${DB_USER} -d ${DB_NAME} --clean --if-exists | gzip > "${BACKUP_FILE}"

  if [ $? -eq 0 ]; then
    SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
    echo "[${TIMESTAMP}] ✅ Backup completed (${SIZE}) → ${BACKUP_FILE}"
  else
    echo "[${TIMESTAMP}] ❌ ERROR: Backup failed!"
  fi

  # Удаляем старые бэкапы (старше 30 дней)
  find /backups -name "funbox_db_*.sql.gz" -mtime +30 -delete

  sleep 86400
done