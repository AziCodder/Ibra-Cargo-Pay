#!/bin/bash
# Триггерит бэкап через backend API. Авторизация — заголовок X-Backup-Secret.
# Файл бэкапа и уведомление в Telegram отправляет сам backend.
set -euo pipefail

: "${BACKEND_URL:?BACKEND_URL не задан}"
: "${BACKUP_TRIGGER_SECRET:?BACKUP_TRIGGER_SECRET не задан}"

ts() { date '+%Y-%m-%d %H:%M:%S %Z'; }

tg_error() {
    local text="$1"
    if [ -z "${TELEGRAM_BOT_TOKEN:-}" ] || [ -z "${TELEGRAM_NOTIFY_CHAT_ID:-}" ]; then
        return 0
    fi
    curl -sS --max-time 15 -X POST \
        "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -H "Content-Type: application/json" \
        -d "{\"chat_id\": \"${TELEGRAM_NOTIFY_CHAT_ID}\", \"text\": \"${text}\", \"parse_mode\": \"HTML\"}" \
        > /dev/null 2>&1 || true
}

# Аргумент "silent" — тихий почасовой бэкап (без отправки файла в Telegram).
QUERY=""
if [ "${1:-}" = "silent" ]; then
    QUERY="?notify=false"
fi

echo "[$(ts)] Запуск бэкапа через ${BACKEND_URL}/api/backups/run${QUERY}"

# 30 минут таймаут на сам бэкап (pg_dump + upload + Telegram send)
http_code=$(curl -sS -o /tmp/backup-resp.json -w "%{http_code}" \
    --max-time 1800 \
    -X POST "${BACKEND_URL}/api/backups/run${QUERY}" \
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

    tg_error "❌ <b>Ошибка бэкапа БД</b>
📅 $(date '+%d.%m.%Y %H:%M') МСК
HTTP код: ${http_code}"

    exit 1
fi
