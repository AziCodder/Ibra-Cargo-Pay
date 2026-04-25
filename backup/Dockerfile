FROM alpine:3.20

# tzdata — чтобы cron работал в Europe/Moscow.
# curl — чтобы дёргать backend endpoint.
RUN apk add --no-cache tzdata curl bash \
    && cp /usr/share/zoneinfo/Europe/Moscow /etc/localtime \
    && echo "Europe/Moscow" > /etc/timezone

ENV TZ=Europe/Moscow

COPY crontab /etc/crontabs/root
COPY entrypoint.sh /entrypoint.sh
COPY run-backup.sh /usr/local/bin/run-backup.sh
RUN chmod +x /entrypoint.sh /usr/local/bin/run-backup.sh

ENTRYPOINT ["/entrypoint.sh"]
