#!/usr/bin/env bash
# Идемпотентный деплой на чистый Ubuntu 22.04.
# Запускать из корня репозитория после `git clone` и заполнения .env.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

log() { printf '\033[1;32m[deploy]\033[0m %s\n' "$*"; }
err() { printf '\033[1;31m[deploy]\033[0m %s\n' "$*" >&2; }

require_root() {
    if [ "$(id -u)" -ne 0 ]; then
        err "Запустите через sudo: sudo bash scripts/deploy.sh"
        exit 1
    fi
}

install_docker() {
    if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
        log "Docker и docker compose уже установлены"
        return
    fi
    log "Устанавливаю Docker Engine + compose plugin"
    apt-get update -y
    apt-get install -y ca-certificates curl gnupg
    install -m 0755 -d /etc/apt/keyrings
    if [ ! -f /etc/apt/keyrings/docker.gpg ]; then
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
        chmod a+r /etc/apt/keyrings/docker.gpg
    fi
    echo \
        "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
        $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
        > /etc/apt/sources.list.d/docker.list
    apt-get update -y
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    systemctl enable --now docker
}

check_env() {
    if [ ! -f .env ]; then
        err ".env не найден. Создайте: cp .env.example .env  и заполните значения"
        exit 1
    fi
    if grep -qE '^(SECRET_KEY|DB_PASSWORD|TELEGRAM_BOT_TOKEN)=replace' .env; then
        err ".env содержит плейсхолдеры (replace-*). Заполните реальные значения и повторите."
        exit 1
    fi
}

up_stack() {
    log "Сборка и запуск контейнеров"
    docker compose pull --ignore-buildable || true
    docker compose up -d --build
    log "Состояние сервисов:"
    docker compose ps
}

main() {
    require_root
    install_docker
    check_env
    up_stack
    log "Готово. Проверьте: curl -fsS http://localhost:8000/health"
    log "Frontend: http://<server-ip>/   API docs: http://<server-ip>:8000/docs"
}

main "$@"
