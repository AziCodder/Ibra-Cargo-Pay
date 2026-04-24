#!/bin/bash
# Запускает crond в foreground. Логи cron + дочерних задач уходят в stdout контейнера.
set -e

: "${BACKEND_URL:?BACKEND_URL не задан}"
: "${BACKUP_TRIGGER_SECRET:?BACKUP_TRIGGER_SECRET не задан}"

echo "[backup-sidecar] TZ=$(cat /etc/timezone), now=$(date)"
echo "[backup-sidecar] Backend: ${BACKEND_URL}"
echo "[backup-sidecar] Расписание:"
cat /etc/crontabs/root

# Прокидываем env-переменные в контекст cron (по умолчанию crond их не видит).
# Пишем env в /etc/environment-cron, и run-backup.sh их подхватывает.
{
    echo "BACKEND_URL=${BACKEND_URL}"
    echo "BACKUP_TRIGGER_SECRET=${BACKUP_TRIGGER_SECRET}"
} > /etc/environment-cron

# Заменяем команду в crontab, чтобы экспортировать env перед запуском.
sed -i 's|/usr/local/bin/run-backup.sh|set -a; . /etc/environment-cron; set +a; /usr/local/bin/run-backup.sh|' /etc/crontabs/root

# Создаём лог-файл и tail-им параллельно с crond, чтобы видеть вывод задач в stdout.
touch /var/log/backup.log
tail -F /var/log/backup.log &

exec crond -f -l 8
