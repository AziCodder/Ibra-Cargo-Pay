#!/usr/bin/env bash
# Обновление до последней версии main с пересборкой контейнеров.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

log() { printf '\033[1;32m[update]\033[0m %s\n' "$*"; }

# Опционально: `update.sh vps` применит override docker-compose.vps.yml
# (backend на 127.0.0.1:8001, frontend на 8081, bot/backup за профилем full).
# Без аргумента поведение прежнее — только базовый docker-compose.yml.
COMPOSE_ARGS=""
if [ "${1:-}" = "vps" ]; then
    COMPOSE_ARGS="-f docker-compose.yml -f docker-compose.vps.yml"
    log "Режим VPS: применяю docker-compose.vps.yml"
fi

log "git fetch + reset на origin/main"
git fetch origin
git reset --hard origin/main

log "Пересборка и рестарт"
docker compose $COMPOSE_ARGS up -d --build

log "Очистка неиспользуемых образов"
docker image prune -f

log "Готово. Состояние:"
docker compose $COMPOSE_ARGS ps
