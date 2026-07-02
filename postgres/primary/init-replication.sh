#!/bin/bash
# Инициализация PRIMARY для потоковой репликации. Выполняется ТОЛЬКО при первом создании
# тома БД (docker-entrypoint-initdb.d). Для уже существующей БД используйте
# scripts/ha/enable_replication_primary.sh (применяет то же к работающему серверу).
set -euo pipefail

: "${REPLICATOR_PASSWORD:?REPLICATOR_PASSWORD не задан}"
STANDBY_CIDR="${STANDBY_WG_IP:-10.8.0.2}/32"

# Роль репликации (идемпотентно).
psql -v ON_ERROR_STOP=1 \
    --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    -v repl_pass="$REPLICATOR_PASSWORD" <<-'SQL'
	DO $$
	BEGIN
	    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'replicator') THEN
	        EXECUTE format(
	            'CREATE ROLE replicator WITH REPLICATION LOGIN PASSWORD %L',
	            :'repl_pass'
	        );
	    END IF;
	END
	$$;
SQL

# Разрешаем подключение репликации только со standby (через WireGuard-туннель).
HBA_LINE="host replication replicator ${STANDBY_CIDR} scram-sha-256"
if ! grep -qF "$HBA_LINE" "$PGDATA/pg_hba.conf"; then
    echo "$HBA_LINE" >> "$PGDATA/pg_hba.conf"
    echo "[init-replication] добавлено правило pg_hba: $HBA_LINE"
fi

echo "[init-replication] PRIMARY готов к репликации (standby=${STANDBY_CIDR})"
