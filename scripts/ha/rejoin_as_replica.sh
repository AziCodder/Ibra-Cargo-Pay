#!/usr/bin/env bash
# Возвращает СТАРЫЙ primary (сервер 1) в строй как РЕПЛИКУ нового primary (сервер 2).
# Используется после failover: сервер 1 восстановился, но данные разошлись с сервером 2,
# который уже принимал записи. pg_rewind быстро синхронизирует, не делая полный base backup.
#
# Требует: на старом primary был включён wal_log_hints=on (см. docker-compose.primary.yml /
# enable_replication_primary.sh). Новый primary (сервер 2) должен быть доступен по WireGuard.
#
# Запуск на сервере 1, из корня репозитория:
#   sudo bash scripts/ha/rejoin_as_replica.sh
#
# Требуемые env (.env):
#   NEW_PRIMARY_WG_IP    — WG-IP нового primary (сервер 2), по умолч. 10.8.0.2
#   REPLICATOR_PASSWORD  — пароль роли replicator
#   REPLICATION_SLOT     — имя слота (по умолч. standby_slot)
set -euo pipefail

log() { printf '\033[1;32m[rejoin]\033[0m %s\n' "$*"; }
err() { printf '\033[1;31m[rejoin]\033[0m %s\n' "$*" >&2; }

REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_DIR"
if [ -f .env ]; then
    set -a
    # shellcheck disable=SC1091
    . .env
    set +a
fi

NEW_PRIMARY_WG_IP="${NEW_PRIMARY_WG_IP:-10.8.0.2}"
: "${REPLICATOR_PASSWORD:?Задайте REPLICATOR_PASSWORD в .env}"
REPLICATION_SLOT="${REPLICATION_SLOT:-standby_slot}"
COMPOSE="${COMPOSE_CMD:-docker compose}"
PGDATA_IN="/var/lib/postgresql/data"

if [ "${FORCE:-0}" != "1" ]; then
    echo "⚠️  Локальная БД будет ПЕРЕЗАПИСАНА состоянием сервера 2 (pg_rewind)."
    echo "    Расхождения этого узла потеряются — это и есть цель отката к общему предку."
    read -r -p "Продолжить? [y/N] " ans
    case "$ans" in y|Y|yes|YES) ;; *) err "Отменено."; exit 1 ;; esac
fi

# 1. Остановить локальный postgres (чистое завершение — обязательно для pg_rewind).
log "1/3 Останавливаю локальную БД"
$COMPOSE stop db

# 2. pg_rewind + запись recovery-конфига. Выполняем одноразовым контейнером той же
#    image с тем же томом, от пользователя postgres.
log "2/3 pg_rewind с нового primary ${NEW_PRIMARY_WG_IP}"
SRC="host=${NEW_PRIMARY_WG_IP} port=5432 user=replicator password=${REPLICATOR_PASSWORD} dbname=postgres"
$COMPOSE run --rm --no-deps --user postgres --entrypoint bash db -c "
set -euo pipefail
pg_rewind --target-pgdata='${PGDATA_IN}' --source-server='${SRC}' -R --progress
cat >> '${PGDATA_IN}/postgresql.auto.conf' <<EOF
primary_conninfo = 'host=${NEW_PRIMARY_WG_IP} port=5432 user=replicator password=${REPLICATOR_PASSWORD} application_name=standby'
primary_slot_name = '${REPLICATION_SLOT}'
EOF
touch '${PGDATA_IN}/standby.signal'
echo '[rejoin] pg_rewind завершён, standby.signal установлен'
"

# 3. Поднять БД как реплику (оверлей replica: PGDATA не пуст → стартует как standby).
log "3/3 Запускаю как реплику"
$COMPOSE -f docker-compose.yml -f docker-compose.replica.yml up -d db

log "ГОТОВО. Сервер 1 снова реплика сервера 2. Проверка лага: на новом primary — pg_stat_replication."
log "Для планового возврата ролей (сделать сервер 1 снова primary) используйте scripts/ha/failback.sh"
