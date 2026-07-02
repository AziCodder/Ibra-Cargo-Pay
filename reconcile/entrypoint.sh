#!/bin/bash
# Генерирует rclone.conf из env и запускает crond в foreground.
set -e

: "${S3_ENDPOINT_URL:?S3_ENDPOINT_URL не задан}"

# Если secondary не настроен — dual-write выключен. Не крашлупимся (restart:
# unless-stopped перезапускал бы контейнер бесконечно), а тихо ждём.
if [ -z "${S3_SECONDARY_ENDPOINT_URL:-}" ]; then
    echo "[reconcile-sidecar] S3_SECONDARY_* не задан — синхронизация выключена, простаиваю."
    exec sleep infinity
fi

echo "[reconcile-sidecar] TZ=$(cat /etc/timezone), now=$(date)"
echo "[reconcile-sidecar] primary=${S3_ENDPOINT_URL} secondary=${S3_SECONDARY_ENDPOINT_URL}"

# rclone-конфиг двух S3-remote'ов. provider=Other + path-style — совместимо с Hostkey/Storj.
mkdir -p /root/.config/rclone
cat > /root/.config/rclone/rclone.conf <<EOF
[primary]
type = s3
provider = Other
access_key_id = ${S3_ACCESS_KEY_ID}
secret_access_key = ${S3_SECRET_ACCESS_KEY}
endpoint = ${S3_ENDPOINT_URL}
region = ${S3_REGION:-nl}
force_path_style = true

[secondary]
type = s3
provider = Other
access_key_id = ${S3_SECONDARY_ACCESS_KEY_ID}
secret_access_key = ${S3_SECONDARY_SECRET_ACCESS_KEY}
endpoint = ${S3_SECONDARY_ENDPOINT_URL}
region = ${S3_SECONDARY_REGION:-us-1}
force_path_style = true
EOF

# Прокидываем env в контекст cron (crond их по умолчанию не видит).
{
    echo "S3_BUCKET_NAME=${S3_BUCKET_NAME}"
    echo "S3_SECONDARY_BUCKET=${S3_SECONDARY_BUCKET:-$S3_BUCKET_NAME}"
    echo "BACKEND_URL=${BACKEND_URL:-}"
    echo "BACKUP_TRIGGER_SECRET=${BACKUP_TRIGGER_SECRET:-}"
} > /etc/environment-cron

sed -i 's|/usr/local/bin/bisync.sh|set -a; . /etc/environment-cron; set +a; /usr/local/bin/bisync.sh|' /etc/crontabs/root

touch /var/log/reconcile.log
tail -F /var/log/reconcile.log &

exec crond -f -l 8
