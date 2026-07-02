#!/bin/bash
# Страховочная синхронизация primary → secondary: rclone copy, БЕЗ удалений.
#
# Почему copy, а не bisync: bisync у rclone в статусе BETA (сам предупреждает
# "Don't use in production") и при сбое может принять неверное решение об удалении.
# copy стабилен и физически не способен потерять данные (только добавляет).
#
# Роли механизмов:
#   - dual-write в приложении  — основной путь (пишет в оба таргета сразу);
#   - outbox + /api/storage/reconcile — точечный догон В ОБЕ стороны (включая
#     восстановление primary из secondary после даунтайма primary);
#   - этот скрипт — bulk-страховка: доливает в secondary всё, что пролетело мимо
#     (ручные загрузки в бакет, старые файлы, сбои до записи в outbox).
set -uo pipefail

ts() { date '+%Y-%m-%d %H:%M:%S %Z'; }

PRIMARY="primary:${S3_BUCKET_NAME}"
SECONDARY="secondary:${S3_SECONDARY_BUCKET:-$S3_BUCKET_NAME}"

echo "[$(ts)] rclone copy ${PRIMARY} -> ${SECONDARY} (без удалений)"
if rclone copy "$PRIMARY" "$SECONDARY" \
    --transfers 4 --checkers 8 \
    --contimeout 15s --retries 2 --low-level-retries 3 \
    --stats-one-line --stats 0; then
    echo "[$(ts)] copy OK"
else
    echo "[$(ts)] copy ОШИБКА (код $?) — повтор при следующем запуске"
fi

# Точечный догон обоих направлений из outbox приложения (best-effort).
if [ -n "${BACKEND_URL:-}" ] && [ -n "${BACKUP_TRIGGER_SECRET:-}" ]; then
    curl -sS --max-time 60 -X POST "${BACKEND_URL}/api/storage/reconcile" \
        -H "X-Backup-Secret: ${BACKUP_TRIGGER_SECRET}" >> /var/log/reconcile.log 2>&1 || true
fi
