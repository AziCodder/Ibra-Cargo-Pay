#!/usr/bin/env bash
# Обновление до последней версии main с пересборкой контейнеров.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

log() { printf '\033[1;32m[update]\033[0m %s\n' "$*"; }

log "git fetch + reset на origin/main"
git fetch origin
git reset --hard origin/main

log "Пересборка и рестарт"
docker compose up -d --build

log "Очистка неиспользуемых образов"
docker image prune -f

log "Готово. Состояние:"
docker compose ps
