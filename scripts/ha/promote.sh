#!/usr/bin/env bash
# FAILOVER: продвигает standby (сервер 2) в primary и переключает домен на него.
# Запускается ВРУЧНУЮ на сервере 2, когда сервер 1 недоступен (полуавтоматический режим —
# split-brain исключён, потому что промоут инициирует человек).
#
# Шаги: проверка что это реплика → pg_promote() → ждём выход из recovery →
#        DNS crm.<домен> → сервер 2 → рестарт backend (снять standby-режим).
#
# Запуск на сервере 2, из корня репозитория:
#   sudo bash scripts/ha/promote.sh            # с подтверждением
#   FORCE=1 sudo bash scripts/ha/promote.sh    # без подтверждения (для автоматизации)
set -euo pipefail

log() { printf '\033[1;32m[promote]\033[0m %s\n' "$*"; }
err() { printf '\033[1;31m[promote]\033[0m %s\n' "$*" >&2; }

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

psql_exec() {
    $COMPOSE exec -T db psql -U "$DB_USER" -d "$DB_NAME" -tA -v ON_ERROR_STOP=1 "$@"
}

# 1. Убедиться, что это реплика (в recovery). Промоутить primary нельзя/незачем.
in_recovery="$(psql_exec -c 'SELECT pg_is_in_recovery();' | tr -d '[:space:]')"
if [ "$in_recovery" != "t" ]; then
    err "Эта БД не в режиме реплики (pg_is_in_recovery=${in_recovery:-?}). Промоут не нужен."
    exit 1
fi

if [ "${FORCE:-0}" != "1" ]; then
    echo "⚠️  Сейчас standby станет PRIMARY и домен переключится на этот сервер."
    echo "    Делайте это, только если сервер 1 действительно недоступен (иначе split-brain)."
    read -r -p "Продолжить? [y/N] " ans
    case "$ans" in
        y|Y|yes|YES) ;;
        *) err "Отменено."; exit 1 ;;
    esac
fi

# 2. Промоут реплики в primary.
log "1/4 pg_promote(): реплика → primary"
psql_exec -c 'SELECT pg_promote(wait => true, wait_seconds => 60);' >/dev/null

# 3. Дождаться выхода из recovery.
log "2/4 Жду выхода из recovery"
for _ in $(seq 1 30); do
    st="$(psql_exec -c 'SELECT pg_is_in_recovery();' | tr -d '[:space:]')"
    [ "$st" = "f" ] && break
    sleep 2
done
if [ "${st:-t}" != "f" ]; then
    err "БД не вышла из recovery за отведённое время. Проверьте: $COMPOSE logs db"
    exit 1
fi
log "БД теперь принимает запись (primary)."

# 4. Переключить домен на этот сервер (standby-IP).
log "3/4 Переключаю DNS на сервер 2 (standby)"
if bash "$REPO_DIR/scripts/ha/dns_switch.sh" standby; then
    log "DNS переключён."
else
    err "DNS не переключён автоматически — сделайте вручную (см. scripts/ha/dns_switch.sh)."
fi

# 5. Перезапустить backend, чтобы снять standby-режим (NODE_ROLE) и сбросить пул соединений.
log "4/4 Перезапуск backend"
NODE_ROLE=primary $COMPOSE up -d backend || $COMPOSE restart backend || true

log "ГОТОВО. Сервер 2 стал рабочим. Когда сервер 1 вернётся — используйте scripts/ha/failback.sh"
