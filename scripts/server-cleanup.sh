#!/usr/bin/env bash
# Удаляет старые попытки деплоя из /opt и чистит docker-кэш.
# Запускать ОДИН раз перед свежим клонированием. После — не нужен.
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "Нужны права root: sudo bash server-cleanup.sh" >&2
    exit 1
fi

echo "[cleanup] Останавливаю любые запущенные контейнеры проекта"
for d in /opt/Ibra-Cargo-Pay /opt/ibra-cargo /opt/ibra-cargo-pay; do
    if [ -d "$d" ]; then
        if [ -f "$d/docker-compose.yml" ]; then
            (cd "$d" && docker compose down -v --remove-orphans) || true
        fi
    fi
done

echo "[cleanup] Удаляю старые директории"
rm -rf /opt/Ibra-Cargo-Pay /opt/ibra-cargo /opt/ibra-cargo-pay

echo "[cleanup] Чищу неиспользуемые docker-объекты"
docker system prune -af --volumes || true

echo "[cleanup] Готово. Можно делать свежий git clone в /opt/ibra-cargo-pay"
