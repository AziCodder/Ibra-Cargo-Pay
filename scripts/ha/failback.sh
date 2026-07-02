#!/usr/bin/env bash
# FAILBACK: плановый возврат роли primary на сервер 1 после восстановления.
# Предполагается, что сервер 1 уже вернулся в строй как РЕПЛИКА сервера 2
# (через scripts/ha/rejoin_as_replica.sh) и догнал данные.
#
# Запускается ВРУЧНУЮ на СЕРВЕРЕ 1. Порядок безопасного возврата (без split-brain):
#   [сервер 2] остановить приём записи:  docker compose stop backend
#   [сервер 1] запустить этот скрипт     — дождаться лага≈0, промоут, переключить DNS
#   [сервер 2] вернуть как реплику:       NEW_PRIMARY_WG_IP=<WG сервера 1> \
#                                         sudo bash scripts/ha/rejoin_as_replica.sh
#
# env (.env):
#   PRIMARY_WG_IP / STANDBY_WG_IP — WG-IP серверов (для DNS уже в .env)
#   FAILBACK_MAX_LAG_SEC — допустимый лаг реплики перед промоутом (по умолч. 5)
set -euo pipefail

log() { printf '\033[1;32m[failback]\033[0m %s\n' "$*"; }
err() { printf '\033[1;31m[failback]\033[0m %s\n' "$*" >&2; }

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
MAX_LAG="${FAILBACK_MAX_LAG_SEC:-5}"

psql_exec() {
    $COMPOSE exec -T db psql -U "$DB_USER" -d "$DB_NAME" -tA -v ON_ERROR_STOP=1 "$@"
}

# 1. Этот узел должен быть репликой.
in_recovery="$(psql_exec -c 'SELECT pg_is_in_recovery();' | tr -d '[:space:]')"
if [ "$in_recovery" != "t" ]; then
    err "Сервер 1 не в режиме реплики (pg_is_in_recovery=${in_recovery:-?})."
    err "Сначала верните его как реплику: scripts/ha/rejoin_as_replica.sh"
    exit 1
fi

# 2. Проверить лаг репликации (задержка проигрывания WAL в секундах).
lag="$(psql_exec -c "SELECT COALESCE(ROUND(EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp()))), 0);" | tr -d '[:space:]')"
lag="${lag:-999}"
log "Текущий лаг реплики: ${lag}s (порог ${MAX_LAG}s)"
if [ "$lag" -gt "$MAX_LAG" ] 2>/dev/null; then
    err "Лаг ${lag}s > ${MAX_LAG}s. Убедитесь, что сервер 2 остановил запись (stop backend)"
    err "и дайте реплике догнать. Повторите, или увеличьте FAILBACK_MAX_LAG_SEC осознанно."
    exit 1
fi

if [ "${FORCE:-0}" != "1" ]; then
    echo "⚠️  Сервер 1 станет PRIMARY, домен вернётся на него."
    echo "    Убедитесь, что на сервере 2 УЖЕ остановлен backend (нет параллельной записи)."
    read -r -p "Продолжить? [y/N] " ans
    case "$ans" in y|Y|yes|YES) ;; *) err "Отменено."; exit 1 ;; esac
fi

# 3. Промоут сервера 1 в primary.
log "1/4 pg_promote(): сервер 1 → primary"
psql_exec -c 'SELECT pg_promote(wait => true, wait_seconds => 60);' >/dev/null
for _ in $(seq 1 30); do
    st="$(psql_exec -c 'SELECT pg_is_in_recovery();' | tr -d '[:space:]')"
    [ "$st" = "f" ] && break
    sleep 2
done
if [ "${st:-t}" != "f" ]; then
    err "БД не вышла из recovery. Проверьте: $COMPOSE logs db"
    exit 1
fi

# 4. Вернуть домен на сервер 1 (primary IP).
log "2/4 Переключаю DNS на сервер 1 (primary)"
bash "$REPO_DIR/scripts/ha/dns_switch.sh" primary || err "DNS не переключён — сделайте вручную."

# 5. Перезапуск backend в роли primary.
log "3/4 Перезапуск backend (NODE_ROLE=primary)"
NODE_ROLE=primary $COMPOSE up -d backend || $COMPOSE restart backend || true

log "4/4 ГОТОВО. Сервер 1 снова primary."
log "ТЕПЕРЬ на СЕРВЕРЕ 2 верните его в реплики:"
log "  NEW_PRIMARY_WG_IP=${PRIMARY_WG_IP:-10.8.0.1} sudo bash scripts/ha/rejoin_as_replica.sh"
