# HA / Failover — runbook

Полуавтоматический active-passive: **сервер 1 (primary, Hostkey)** + **сервер 2 (standby,
другой провайдер)**, потоковая репликация PostgreSQL, переключение — одной командой человеком
(split-brain исключён). Файлы и дампы БД реплицируются в два S3 (см. `docs/DUAL-S3-SETUP.md`).

## Карта компонентов

| Слой | Механизм | Артефакт |
|------|----------|----------|
| Данные (файлы+дампы) | dual-write в два S3 + outbox + rclone copy | `storage_service.py`, `reconcile/` |
| БД между серверами | потоковая репликация | `docker-compose.primary.yml` / `.replica.yml` |
| Канал репликации | WireGuard 10.8.0.1↔10.8.0.2 | `scripts/ha/setup_wireguard.sh` |
| Переключение домена | Cloudflare API | `scripts/ha/dns_switch.sh` |
| Авария → standby | pg_promote + DNS | `scripts/ha/promote.sh` |
| Возврат старого узла в реплику | pg_rewind | `scripts/ha/rejoin_as_replica.sh` |
| Плановый возврат ролей | лаг→promote→DNS | `scripts/ha/failback.sh` |
| Крайний случай (обе БД) | restore из S3-дампа | `scripts/ha/restore.sh` |
| Мониторинг | лаг → Telegram | `scripts/ha/check_replication_lag.sh` |

`.env` (обе стороны): `PRIMARY_WG_IP=10.8.0.1`, `STANDBY_WG_IP=10.8.0.2`, `REPLICATOR_PASSWORD`,
`REPLICATION_SLOT=standby_slot`, `CF_API_TOKEN`, `CF_ZONE_ID`, `CF_RECORD_NAME`, `PRIMARY_IP`,
`STANDBY_IP` (публичные IP для DNS), `NODE_ROLE`.

---

## 0. Первичная настройка (один раз)

1. **WireGuard** — на обоих серверах (двухпроходно, обмен ключами):
   ```
   sudo bash scripts/ha/setup_wireguard.sh server1   # на сервере 1
   sudo bash scripts/ha/setup_wireguard.sh server2   # на сервере 2
   # затем повторить с PEER_PUBKEY=<ключ соседа> PEER_ENDPOINT=<публ.IP соседа>:51820
   ```
   Проверка: `ping 10.8.0.2` с сервера 1.

2. **Репликация на primary (сервер 1)** — БД уже существует:
   ```
   sudo bash scripts/ha/enable_replication_primary.sh
   ```

3. **Standby (сервер 2)** — поднять как реплику (том db должен быть пуст → авто-basebackup):
   ```
   docker compose -f docker-compose.yml -f docker-compose.replica.yml up -d
   ```
   Проверка на сервере 1: `SELECT * FROM pg_stat_replication;` → `state=streaming`.
   Проверка на сервере 2: `SELECT pg_is_in_recovery();` → `t`.

4. **DNS**: домен → Cloudflare NS, A-запись `crm.<домен>` → `PRIMARY_IP`, TTL 60.
   Проверка: `bash scripts/ha/dns_switch.sh primary` (идемпотентно).

5. **Мониторинг**: на обоих серверах в cron:
   `*/5 * * * * /path/scripts/ha/check_replication_lag.sh >> /var/log/repl-lag.log 2>&1`

---

## 1. Сценарий A — авария сервера 1 (failover)

Признак: сайт недоступен, алерт «НЕТ реплики»/uptime, сервер 1 не отвечает.

**На сервере 2:**
```
sudo bash scripts/ha/promote.sh
```
Скрипт: проверит, что это реплика → `pg_promote()` → дождётся выхода из recovery →
`dns_switch.sh standby` (домен на сервер 2) → рестарт backend в роли primary.

Через 1–2 минуты (TTL DNS) клиенты на сервере 2. **RPO ≈ 0** (реплика была синхронна).

---

## 2. Сценарий B — сервер 1 вернулся (возврат)

Данные разошлись: сервер 2 принимал записи, пока сервер 1 лежал. Нельзя просто включить
сервер 1 как primary — нужен pg_rewind.

**Шаг 1 — вернуть сервер 1 в реплику (на сервере 1):**
```
NEW_PRIMARY_WG_IP=10.8.0.2 sudo bash scripts/ha/rejoin_as_replica.sh
```
Теперь сервер 1 — реплика сервера 2, догоняет данные.

**Шаг 2 — плановый возврат ролей (когда лаг≈0):**
```
# на сервере 2 (текущий primary) — остановить запись:
docker compose stop backend
# на сервере 1:
sudo bash scripts/ha/failback.sh          # проверит лаг → promote → DNS → backend
# на сервере 2 — вернуть в реплику:
NEW_PRIMARY_WG_IP=10.8.0.1 sudo bash scripts/ha/rejoin_as_replica.sh
docker compose -f docker-compose.yml -f docker-compose.replica.yml up -d
```
Роли вернулись: сервер 1 = primary, сервер 2 = standby.

> Если возврат не срочен — можно оставить сервер 2 как primary, а сервер 1 как реплику
> (симметрично). `failback.sh` нужен, только когда хотите вернуть исходное распределение.

---

## 3. Сценарий C — потеряны ОБЕ БД (disaster recovery)

Крайний случай (оба сервера/тома погибли). Данные живы в S3-дампах (Storj + основной S3).

**На любой чистой машине:**
```
git clone <repo> && cd <repo>
cp .env.example .env    # заполнить секреты (из менеджера паролей!) + BACKUP_S3_*
sudo bash scripts/deploy.sh
sudo bash scripts/ha/restore.sh          # последний дамп из S3 (или указать ключ)
bash scripts/ha/dns_switch.sh primary
```
**RPO** = интервал бэкапа (сейчас ежедневно; при почасовом — до 1 часа). Файлы — из S3 (dual).

---

## 4. Диагностика

```
# роль узла
docker compose exec -T db psql -U postgres -d project_manager -tAc 'SELECT pg_is_in_recovery();'
# на primary: кто реплицируется и лаг
docker compose exec -T db psql -U postgres -d project_manager -c 'SELECT client_addr,state,replay_lsn FROM pg_stat_replication;'
# состояние dual-S3 и очередь догона
curl -H "Authorization: Bearer <admin-jwt>" http://localhost:8000/api/storage/status
# ручной прогон мониторинга
bash scripts/ha/check_replication_lag.sh
```

Все переключающие скрипты спрашивают подтверждение; для автоматизации — `FORCE=1`.
