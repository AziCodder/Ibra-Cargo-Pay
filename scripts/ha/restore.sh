#!/usr/bin/env bash
# КРАЙНИЙ СЛУЧАЙ: восстановление БД из S3-дампа на чистой машине, когда обе БД потеряны
# (реплика недоступна). Тянет дамп из backup-хранилища (Storj/S3, с fallback) и заливает.
#
# Переиспользует уже готовую логику backup_service.restore_backup (DROP SCHEMA → pg_restore
# → alembic upgrade head → сброс пула). Запускается из корня репозитория ПОСЛЕ deploy.sh
# (нужны .env с BACKUP_S3_* и собранный образ backend).
#
# Использование:
#   sudo bash scripts/ha/restore.sh              # восстановить из ПОСЛЕДНЕГО дампа
#   sudo bash scripts/ha/restore.sh <ключ>       # из конкретного (db-backups/2026/07/...)
#   FORCE=1 sudo bash scripts/ha/restore.sh       # без подтверждения
set -euo pipefail

log() { printf '\033[1;32m[restore]\033[0m %s\n' "$*"; }
err() { printf '\033[1;31m[restore]\033[0m %s\n' "$*" >&2; }

REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_DIR"
[ -f .env ] || { err ".env не найден. Заполните .env (BACKUP_S3_*) и повторите."; exit 1; }

COMPOSE="${COMPOSE_CMD:-docker compose}"

# 1. Поднять db + backend (backend несёт pg_restore/alembic и логику восстановления).
log "1/4 Поднимаю db + backend"
$COMPOSE up -d db backend

log "2/4 Жду готовности backend"
for _ in $(seq 1 30); do
    if $COMPOSE exec -T backend python -c "import sys" >/dev/null 2>&1; then
        break
    fi
    sleep 3
done

# 2. Определить ключ дампа.
KEY="${1:-}"
if [ -z "$KEY" ]; then
    log "Ключ не задан — беру последний дамп из хранилища"
    KEY="$($COMPOSE exec -T backend python -c "import asyncio; from app.services import backup_service as b; items=asyncio.run(b.list_backups(1)); print(items[0]['key'] if items else '')" | tr -d '\r')"
fi
if [ -z "$KEY" ]; then
    err "Не удалось найти ни одного дампа в backup-хранилище. Проверьте BACKUP_S3_* в .env."
    exit 1
fi
log "Целевой дамп: ${KEY}"

# 3. Подтверждение (операция перезатирает текущую БД).
if [ "${FORCE:-0}" != "1" ]; then
    echo "⚠️  Текущая БД будет ПОЛНОСТЬЮ заменена содержимым дампа ${KEY}."
    read -r -p "Продолжить? [y/N] " ans
    case "$ans" in y|Y|yes|YES) ;; *) err "Отменено."; exit 1 ;; esac
fi

# 4. Восстановление (внутри backend, там же pg_restore + alembic).
log "3/4 Восстанавливаю (DROP SCHEMA → pg_restore → alembic upgrade head)"
$COMPOSE exec -T backend python -c "
import asyncio, json
from app.services import backup_service as b
print(json.dumps(asyncio.run(b.restore_backup('${KEY}')), ensure_ascii=False))
"

log "4/4 Перезапуск backend (сброс кэшей/пула соединений)"
$COMPOSE restart backend

log "ГОТОВО. БД восстановлена из ${KEY}. Поднимите остальной стек: $COMPOSE up -d"
