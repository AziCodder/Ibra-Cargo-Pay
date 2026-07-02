FROM alpine:3.20

# rclone — двусторонняя синхронизация S3↔S3 (bisync).
# curl — дёргать /api/storage/reconcile (outbox). tzdata — время для cron.
RUN apk add --no-cache rclone curl bash tzdata \
    && cp /usr/share/zoneinfo/Europe/Moscow /etc/localtime \
    && echo "Europe/Moscow" > /etc/timezone

ENV TZ=Europe/Moscow

COPY crontab /etc/crontabs/root
COPY entrypoint.sh /entrypoint.sh
COPY bisync.sh /usr/local/bin/bisync.sh
RUN sed -i 's/\r//' /entrypoint.sh /usr/local/bin/bisync.sh \
    && chmod +x /entrypoint.sh /usr/local/bin/bisync.sh

ENTRYPOINT ["/entrypoint.sh"]
