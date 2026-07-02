#!/usr/bin/env bash
# Идемпотентная настройка WireGuard-туннеля между сервером 1 и сервером 2.
# Туннель даёт приватный канал (10.8.0.0/24) для потоковой репликации PostgreSQL
# между разными провайдерами — WAL не ходит по открытому интернету.
#
# Запускать на КАЖДОМ сервере (Ubuntu). Обмен публичными ключами — в два прохода:
#   1) на обоих серверах: sudo bash scripts/ha/setup_wireguard.sh <server1|server2>
#      (скрипт создаст ключи и напечатает свой ПУБЛИЧНЫЙ ключ)
#   2) повторить, добавив ключ и адрес соседа:
#      PEER_PUBKEY=<ключ соседа> PEER_ENDPOINT=<публ.IP соседа>:51820 \
#      sudo bash scripts/ha/setup_wireguard.sh <server1|server2>
#
# Итог: server1 = 10.8.0.1, server2 = 10.8.0.2 (совпадает с PRIMARY_WG_IP/STANDBY_WG_IP).
set -euo pipefail

log() { printf '\033[1;32m[wireguard]\033[0m %s\n' "$*"; }
err() { printf '\033[1;31m[wireguard]\033[0m %s\n' "$*" >&2; }

[ "$(id -u)" -eq 0 ] || { err "Запустите через sudo."; exit 1; }

ROLE="${1:-}"
WG_PORT="${WG_PORT:-51820}"
WG_IF="wg0"
WG_DIR="/etc/wireguard"

case "$ROLE" in
    server1) THIS_IP="10.8.0.1"; PEER_IP="10.8.0.2" ;;
    server2) THIS_IP="10.8.0.2"; PEER_IP="10.8.0.1" ;;
    *) err "Использование: $0 <server1|server2>"; exit 2 ;;
esac

# 1. Установка wireguard, если нет.
if ! command -v wg >/dev/null 2>&1; then
    log "Устанавливаю wireguard"
    apt-get update -y && apt-get install -y wireguard
fi

mkdir -p "$WG_DIR"
chmod 700 "$WG_DIR"

# 2. Ключи (генерируем один раз, не перезаписываем).
if [ ! -f "$WG_DIR/privatekey" ]; then
    log "Генерирую ключевую пару"
    umask 077
    wg genkey | tee "$WG_DIR/privatekey" | wg pubkey > "$WG_DIR/publickey"
fi
PRIV="$(cat "$WG_DIR/privatekey")"
PUB="$(cat "$WG_DIR/publickey")"

# 3. Включаем IP-forwarding (на будущее, безвредно).
sysctl -q -w net.ipv4.ip_forward=1 || true

# 4. Конфиг интерфейса.
CONF="$WG_DIR/${WG_IF}.conf"
{
    echo "[Interface]"
    echo "Address = ${THIS_IP}/24"
    echo "ListenPort = ${WG_PORT}"
    echo "PrivateKey = ${PRIV}"
    if [ -n "${PEER_PUBKEY:-}" ]; then
        echo ""
        echo "[Peer]"
        echo "PublicKey = ${PEER_PUBKEY}"
        echo "AllowedIPs = ${PEER_IP}/32"
        [ -n "${PEER_ENDPOINT:-}" ] && echo "Endpoint = ${PEER_ENDPOINT}"
        echo "PersistentKeepalive = 25"
    fi
} > "$CONF"
chmod 600 "$CONF"

# 5. Поднять/перезагрузить интерфейс.
if wg show "$WG_IF" >/dev/null 2>&1; then
    log "Перечитываю конфиг ${WG_IF}"
    wg-quick down "$WG_IF" || true
fi
wg-quick up "$WG_IF"
systemctl enable "wg-quick@${WG_IF}" >/dev/null 2>&1 || true

log "Интерфейс ${WG_IF} поднят: ${THIS_IP} (роль ${ROLE})"
echo "──────────────────────────────────────────────────────"
echo "МОЙ публичный ключ (передайте соседнему серверу):"
echo "  ${PUB}"
echo "Мой Endpoint для соседа:  <публичный_IP_этого_сервера>:${WG_PORT}"
echo "──────────────────────────────────────────────────────"
if [ -z "${PEER_PUBKEY:-}" ]; then
    log "Сосед не настроен (нет PEER_PUBKEY). Повторите запуск с PEER_PUBKEY и PEER_ENDPOINT."
else
    log "Проверка связи: ping -c2 ${PEER_IP}"
fi
