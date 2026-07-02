#!/bin/bash
# Entrypoint для STANDBY (сервер 2). При пустом PGDATA делает pg_basebackup с primary
# и настраивает потоковую репликацию (standby.signal + primary_conninfo + слот).
# Затем передаёт управление штатному docker-entrypoint.sh, который поднимает PG в hot standby.
#
# Требуемые env:
#   PRIMARY_WG_IP        — WireGuard-IP сервера 1 (по умолч. 10.8.0.1)
#   REPLICATOR_PASSWORD  — пароль роли replicator (как на primary)
#   REPLICATION_SLOT     — имя слота репликации (по умолч. standby_slot)
set -euo pipefail

: "${PRIMARY_WG_IP:=10.8.0.1}"
: "${REPLICATOR_PASSWORD:?REPLICATOR_PASSWORD не задан}"
: "${REPLICATION_SLOT:=standby_slot}"
PGDATA="${PGDATA:-/var/lib/postgresql/data}"

if [ ! -s "$PGDATA/PG_VERSION" ]; then
    echo "[setup-replica] Пустой PGDATA — базовая копия с primary ${PRIMARY_WG_IP}"
    rm -rf "${PGDATA:?}/"* 2>/dev/null || true

    # -C -S: создать слот на primary (если нет). -Xs: стримить WAL. -P: прогресс.
    PGPASSWORD="$REPLICATOR_PASSWORD" pg_basebackup \
        -h "$PRIMARY_WG_IP" -p 5432 -U replicator \
        -D "$PGDATA" -Fp -Xs -P -C -S "$REPLICATION_SLOT"

    # Явно прописываем подключение к primary (с паролем) и слот.
    cat >> "$PGDATA/postgresql.auto.conf" <<EOF
primary_conninfo = 'host=${PRIMARY_WG_IP} port=5432 user=replicator password=${REPLICATOR_PASSWORD} application_name=standby'
primary_slot_name = '${REPLICATION_SLOT}'
EOF
    touch "$PGDATA/standby.signal"

    chown -R postgres:postgres "$PGDATA"
    chmod 0700 "$PGDATA"
    echo "[setup-replica] Базовая копия готова, standby.signal установлен"
else
    echo "[setup-replica] PGDATA не пуст — стартую как есть (standby/primary по содержимому)"
fi

# Дальше — штатный запуск PostgreSQL (docker-entrypoint сам сделает gosu на postgres).
exec docker-entrypoint.sh postgres -c hot_standby=on
