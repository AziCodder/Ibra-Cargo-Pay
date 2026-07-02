#!/usr/bin/env bash
# Включает потоковую репликацию на УЖЕ СУЩЕСТВУЮЩЕЙ (работающей) БД primary.
# Нужен, потому что postgres/primary/init-replication.sh срабатывает только при создании
# нового тома. Здесь всё то же применяется к живому контейнеру через docker compose exec.
#
# Запуск на сервере 1 (primary), из корня репозитория:
#   sudo bash scripts/ha/enable_replication_primary.sh
#
# Требуемые env (из .env):
#   REPLICATOR_PASSWORD  — пароль роли replicator (задать!)
#   STANDBY_WG_IP        — WireGuard-IP сервера 2 (по умолч. 10.8.0.2)
#   DB_USER, DB_NAME     — как в docker-compose (по умолч. postgres / project_manager)
set -euo pipefail

log() { printf '\033[1;32m[repl-primary]\033[0m %s\n' "$*"; }
err() { printf '\033[1;31m[repl-primary]\033[0m %s\n' "$*" >&2; }

REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_DIR"
if [ -f .env ]; then
    set -a
    # shellcheck disable=SC1091
    . .env
    set +a
fi

: "${REPLICATOR_PASSWORD:?Задайте REPLICATOR_PASSWORD в .env}"
STANDBY_WG_IP="${STANDBY_WG_IP:-10.8.0.2}"
DB_USER="${DB_USER:-postgres}"
DB_NAME="${DB_NAME:-project_manager}"
COMPOSE="${COMPOSE_CMD:-docker compose}"

psql_exec() {
    $COMPOSE exec -T db psql -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 "$@"
}

log "1/5 Применяю WAL-параметры репликации (ALTER SYSTEM)"
psql_exec <<'SQL'
ALTER SYSTEM SET wal_level = 'replica';
ALTER SYSTEM SET max_wal_senders = 10;
ALTER SYSTEM SET max_replication_slots = 10;
ALTER SYSTEM SET hot_standby = on;
ALTER SYSTEM SET wal_keep_size = '512MB';
-- wal_log_hints обязателен для pg_rewind (возврат старого primary в реплику при failback).
ALTER SYSTEM SET wal_log_hints = on;
SQL

log "2/5 Создаю роль replicator (если нет)"
psql_exec -v repl_pass="$REPLICATOR_PASSWORD" <<'SQL'
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'replicator') THEN
        EXECUTE format('CREATE ROLE replicator WITH REPLICATION LOGIN PASSWORD %L', :'repl_pass');
    END IF;
END
$$;
SQL

log "3/5 Разрешаю репликацию со standby ${STANDBY_WG_IP} в pg_hba.conf"
HBA_LINE="host replication replicator ${STANDBY_WG_IP}/32 scram-sha-256"
$COMPOSE exec -T db bash -c "grep -qF '${HBA_LINE}' \"\$PGDATA/pg_hba.conf\" || echo '${HBA_LINE}' >> \"\$PGDATA/pg_hba.conf\""

log "4/5 Перезапуск db (wal_level применяется только при рестарте)"
$COMPOSE restart db

log "5/5 Проверка"
# Небольшая пауза на подъём + проверка эффективного wal_level.
for _ in $(seq 1 20); do
    if $COMPOSE exec -T db pg_isready -U "$DB_USER" -d "$DB_NAME" >/dev/null 2>&1; then
        break
    fi
    sleep 2
done
level="$(psql_exec -tA -c 'SHOW wal_level;' | tr -d '[:space:]')"
if [ "$level" = "replica" ]; then
    log "Готово. wal_level=replica, роль replicator создана, pg_hba обновлён."
    log "Теперь на сервере 2 поднимайте standby: docker compose -f docker-compose.yml -f docker-compose.replica.yml up -d"
else
    err "wal_level='${level}', ожидался 'replica'. Проверьте логи: docker compose logs db"
    exit 1
fi
