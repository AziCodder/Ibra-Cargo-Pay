#!/usr/bin/env bash
# Переключение A-записи домена между серверами через Cloudflare API.
# Используется при failover (promote) и возврате (failback): флип crm.<домен> на нужный IP.
#
# Запуск:
#   scripts/ha/dns_switch.sh primary    # указать домен на СЕРВЕР 1 (основной)
#   scripts/ha/dns_switch.sh standby    # указать домен на СЕРВЕР 2 (резервный)
#
# Требуемые env (из .env или окружения):
#   CF_API_TOKEN    — Cloudflare API token с правом Edit DNS для зоны
#   CF_ZONE_ID      — ID зоны (домена) в Cloudflare
#   CF_RECORD_NAME  — полное имя записи, напр. crm.example.ru
#   PRIMARY_IP      — IP сервера 1
#   STANDBY_IP      — IP сервера 2
#   CF_TTL          — TTL записи (по умолчанию 60)
set -euo pipefail

log() { printf '\033[1;32m[dns-switch]\033[0m %s\n' "$*"; }
err() { printf '\033[1;31m[dns-switch]\033[0m %s\n' "$*" >&2; }

# Подхватываем .env из корня репозитория, если он есть.
REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
if [ -f "$REPO_DIR/.env" ]; then
    set -a
    # shellcheck disable=SC1091
    . "$REPO_DIR/.env"
    set +a
fi

require_bins() {
    for b in curl jq; do
        if ! command -v "$b" >/dev/null 2>&1; then
            err "Нужна утилита '$b'. Установите: apt-get install -y $b"
            exit 1
        fi
    done
}

require_env() {
    local missing=0
    for v in CF_API_TOKEN CF_ZONE_ID CF_RECORD_NAME PRIMARY_IP STANDBY_IP; do
        if [ -z "${!v:-}" ]; then
            err "Не задан $v (нужен в .env или окружении)"
            missing=1
        fi
    done
    [ "$missing" -eq 0 ] || exit 1
}

main() {
    local target="${1:-}"
    case "$target" in
        primary) new_ip="$PRIMARY_IP" ;;
        standby) new_ip="$STANDBY_IP" ;;
        *)
            err "Использование: $0 <primary|standby>"
            exit 2
            ;;
    esac

    require_bins
    require_env

    local ttl="${CF_TTL:-60}"
    local api="https://api.cloudflare.com/client/v4"
    local auth=(-H "Authorization: Bearer ${CF_API_TOKEN}" -H "Content-Type: application/json")

    log "Ищу A-запись ${CF_RECORD_NAME} в зоне ${CF_ZONE_ID}"
    local list rec_id cur_ip
    list=$(curl -fsS "${auth[@]}" \
        "${api}/zones/${CF_ZONE_ID}/dns_records?type=A&name=${CF_RECORD_NAME}")

    if [ "$(echo "$list" | jq -r '.success')" != "true" ]; then
        err "Cloudflare API вернул ошибку: $(echo "$list" | jq -c '.errors')"
        exit 1
    fi

    rec_id=$(echo "$list" | jq -r '.result[0].id // empty')
    cur_ip=$(echo "$list" | jq -r '.result[0].content // empty')

    if [ -z "$rec_id" ]; then
        err "A-запись ${CF_RECORD_NAME} не найдена — создайте её в Cloudflare вручную один раз."
        exit 1
    fi

    if [ "$cur_ip" = "$new_ip" ]; then
        log "Запись уже указывает на ${new_ip} (${target}) — ничего не меняю."
        exit 0
    fi

    log "Переключаю ${CF_RECORD_NAME}: ${cur_ip} → ${new_ip} (${target}), TTL=${ttl}"
    local body resp
    body=$(jq -nc \
        --arg name "$CF_RECORD_NAME" \
        --arg ip "$new_ip" \
        --argjson ttl "$ttl" \
        '{type:"A", name:$name, content:$ip, ttl:$ttl, proxied:false}')

    resp=$(curl -fsS -X PUT "${auth[@]}" \
        "${api}/zones/${CF_ZONE_ID}/dns_records/${rec_id}" \
        --data "$body")

    if [ "$(echo "$resp" | jq -r '.success')" = "true" ]; then
        log "Готово. Домен теперь указывает на ${target} (${new_ip})."
    else
        err "Не удалось обновить запись: $(echo "$resp" | jq -c '.errors')"
        exit 1
    fi
}

main "$@"
