#!/bin/bash
# Триггерит бэкап через backend API. Авторизация — заголовок X-Backup-Secret.
set -euo pipefail

: "${BACKEND_URL:?BACKEND_URL не задан}"
: "${BACKUP_TRIGGER_SECRET:?BACKUP_TRIGGER_SECRET не задан}"

ts() { date '+%Y-%m-%d %H:%M:%S %Z'; }

echo "[$(ts)] Запуск бэкапа через ${BACKEND_URL}/api/backups/run"

# 30 минут таймаут на сам бэкап (pg_dump + upload + retention)
http_code=$(curl -sS -o /tmp/backup-resp.json -w "%{http_code}" \
    --max-time 1800 \
    -X POST "${BACKEND_URL}/api/backups/run" \
    -H "X-Backup-Secret: ${BACKUP_TRIGGER_SECRET}" \
    -H "Content-Type: application/json" \
    || echo "000")

if [ "$http_code" = "200" ]; then
    echo "[$(ts)] OK"
    cat /tmp/backup-resp.json
    echo
else
    echo "[$(ts)] ОШИБКА: HTTP $http_code"
    cat /tmp/backup-resp.json 2>/dev/null || true
    echo
    exit 1
fi
