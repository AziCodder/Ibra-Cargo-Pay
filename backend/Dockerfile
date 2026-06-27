# pg_dump берём из postgres:16-bookworm (тот же glibc, что у python:3.12-slim/bookworm).
FROM postgres:16-bookworm AS pg_tools

FROM python:3.12-slim

# libpq5 и libgssapi-krb5-2 — runtime-зависимости pg_dump из стандартных bookworm-репозиториев.
# SONAME libpq.so.5 совместим между версиями 15.x и 16.x — major ABI не меняется.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 libgssapi-krb5-2 \
    && rm -rf /var/lib/apt/lists/*

# /usr/bin/pg_dump — Perl-обёртка (pg_wrapper), нужен реальный ELF-бинарник.
# pg_restore нужен для восстановления БД из бэкапа (custom-формат).
COPY --from=pg_tools /usr/lib/postgresql/16/bin/pg_dump /usr/local/bin/pg_dump
COPY --from=pg_tools /usr/lib/postgresql/16/bin/pg_restore /usr/local/bin/pg_restore

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN sed -i 's/\r//' entrypoint.sh && chmod +x entrypoint.sh

EXPOSE 8000

CMD ["./entrypoint.sh"]
