#!/usr/bin/env bash
# Мониторинг здоровья потоковой репликации → алерт в Telegram.
# Запускать по cron (напр. каждые 5 минут) на СЕРВЕРЕ 1 (primary) и/или СЕРВЕРЕ 2.
#   */5 * * * * /path/scripts/ha/check_replication_lag.sh >> /var/log/repl-lag.log 2>&1
#
# На primary: проверяет, что standby подключён и не отстал (байты WAL).
# На standby: проверяет свежесть проигранного WAL (секунды).
# Алерт шлётся, только когда что-то не так (тихо при норме).
#
# env (.env): TELEGRAM_BOT_TOKEN, TELEGRAM_NOTIFY_CHAT_ID, DB_USER, DB_NAME,
#             LAG_ALERT_BYTES (по умолч. 52428800 = 50 МБ), LAG_ALERT_SEC (по умолч. 300)
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_DIR"
if [ -f .env ]; then
    set -a
    # shellcheck disable=SC1091
    . .env
    set +a
fi

DB_USER="${DB_USER:-postgres}"
DB_NAME="${DB_NAME:-project_manager}"
COMPOSE="${COMPOSE_CMD:-docker compose}"
LAG_ALERT_BYTES="${LAG_ALERT_BYTES:-52428800}"
LAG_ALERT_SEC="${LAG_ALERT_SEC:-300}"

ts() { date '+%Y-%m-%d %H:%M:%S %Z'; }

alert() {
    local text="$1"
    echo "[$(ts)] ALERT: ${text}"
    if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_NOTIFY_CHAT_ID:-}" ]; then
        curl -sS --max-time 15 -X POST \
            "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -H "Content-Type: application/json" \
            -d "{\"chat_id\":\"${TELEGRAM_NOTIFY_CHAT_ID}\",\"text\":\"⚠️ <b>Репликация</b>\n${text}\",\"parse_mode\":\"HTML\"}" \
            >/dev/null 2>&1 || true
    fi
}

psql_q() {
    $COMPOSE exec -T db psql -U "$DB_USER" -d "$DB_NAME" -tA -v ON_ERROR_STOP=1 -c "$1" 2>/dev/null | tr -d '\r'
}

# БД вообще жива?
if ! in_recovery="$(psql_q 'SELECT pg_is_in_recovery();')"; then
    alert "Не удалось опросить БД (контейнер db недоступен?)"
    exit 1
fi
in_recovery="$(echo "$in_recovery" | tr -d '[:space:]')"

if [ "$in_recovery" = "f" ]; then
    # PRIMARY: должен быть хотя бы один подключённый standby.
    count="$(psql_q 'SELECT count(*) FROM pg_stat_replication;' | tr -d '[:space:]')"
    count="${count:-0}"
    if [ "$count" -eq 0 ] 2>/dev/null; then
        alert "PRIMARY: НЕТ подключённых реплик (pg_stat_replication пуст). Standby отвалился?"
        exit 0
    fi
    # Максимальное отставание в байтах среди реплик.
    lag="$(psql_q "SELECT COALESCE(MAX(pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn)),0)::bigint FROM pg_stat_replication;" | tr -d '[:space:]')"
    lag="${lag:-0}"
    if [ "$lag" -gt "$LAG_ALERT_BYTES" ] 2>/dev/null; then
        alert "PRIMARY: реплика отстала на ${lag} байт (> ${LAG_ALERT_BYTES}). Проверьте standby."
    else
        echo "[$(ts)] OK: реплик=${count}, макс.лаг=${lag}б"
    fi
else
    # STANDBY: как давно проигран последний WAL.
    age="$(psql_q "SELECT COALESCE(ROUND(EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp()))),0)::bigint;" | tr -d '[:space:]')"
    age="${age:-99999}"
    if [ "$age" -gt "$LAG_ALERT_SEC" ] 2>/dev/null; then
        alert "STANDBY: последний WAL проигран ${age}s назад (> ${LAG_ALERT_SEC}s). Репликация встала?"
    else
        echo "[$(ts)] OK: standby, лаг=${age}s"
    fi
fi
