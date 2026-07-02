# Dual-write S3 — репликация файлов и дампов в два хранилища

Фаза 1 плана отказоустойчивости. Все файлы (вложения, документы поставщиков) и дампы БД
пишутся **сразу в два S3-хранилища** (PRIMARY + SECONDARY). Если одно недоступно — запись
идёт в живое, а отставшее догоняется автоматически.

## Как это работает

- **Запись** идёт через `backend/app/services/storage_service.py` (`put`/`delete`) — дублирует
  объект во все настроенные таргеты. Успех, если записалось хотя бы в один.
- **Файлы**: `file_service.upload_file/delete_file` → `storage_service`.
- **Дампы БД**: `backup_service._upload` заливает дамп в оба backup-таргета; retention и
  restore работают с fallback (если один провайдер недоступен — берём копию с другого).
- **Чтение / presigned**: с первого доступного таргета (PRIMARY → SECONDARY).
- **Догон отставшего**:
  1. `storage_replication_pending` (outbox) — точечные операции, не прошедшие в один таргет;
     реконсилятор `storage_reconcile.reconcile_once()` проигрывает их В ОБЕ стороны (эндпоинт
     `POST /api/storage/reconcile`, секрет `X-Backup-Secret`). Это основной механизм догона.
  2. Сайдкар `reconcile/` — каждые 15 мин `rclone copy primary→secondary` (стабильный,
     БЕЗ удалений — bisync не используем: он в BETA) как bulk-страховка + дёргает outbox.

## Настройка `.env`

PRIMARY (уже есть, напр. Hostkey):
```
S3_ENDPOINT_URL=...
S3_ACCESS_KEY_ID=...
S3_SECRET_ACCESS_KEY=...
S3_BUCKET_NAME=project-manager
S3_REGION=nl
```

SECONDARY (новое, напр. Storj) — включает dual-write:
```
S3_SECONDARY_ENDPOINT_URL=https://gateway.storjshare.io
S3_SECONDARY_ACCESS_KEY_ID=...
S3_SECONDARY_SECRET_ACCESS_KEY=...
S3_SECONDARY_BUCKET=ibra-files
S3_SECONDARY_REGION=us-1
```

Дампы БД (Storj-бакет для дампов; можно тот же провайдер, отдельный бакет):
```
BACKUP_S3_ENDPOINT_URL=https://gateway.storjshare.io
BACKUP_S3_ACCESS_KEY_ID=...
BACKUP_S3_SECRET_ACCESS_KEY=...
BACKUP_S3_REGION=us-1
BACKUP_S3_BUCKET=ibra-db-backups
BACKUP_S3_PREFIX=db-backups/
BACKUP_RETENTION_DAYS=30
BACKUP_TRIGGER_SECRET=<случайная строка>
```

> Если `S3_SECONDARY_*` пусты — dual-write выключен, работает только PRIMARY (обратная
> совместимость). Дампы всё равно уйдут и в основной S3, и в backup-бакет (две копии).

## Применение

```bash
# 1. Применить миграцию (создаёт outbox-таблицу storage_replication_pending)
docker compose exec backend alembic upgrade head

# 2. Пересоздать backend с новым .env
docker compose up -d --build backend

# 3. Поднять сайдкар синхронизации (на VPS — с профилем full)
docker compose up -d --build reconcile
# на VPS:  docker compose -f docker-compose.yml -f docker-compose.vps.yml --profile full up -d reconcile
```

## Проверка

```bash
# Оба таргета + сквозная dual-запись (ничего не оставляет в бакетах)
docker compose exec backend python scripts/test_storage.py

# Статус таргетов и размер очереди догона
curl -H "Authorization: Bearer <admin-jwt>" http://localhost:8000/api/storage/status
```

Ожидаемо: `test_storage.py` — все ✅, `dual_write: true`, `pending_replications: 0`.

### Проверка отказоустойчивости (симуляция даунтайма)
1. Временно испортить `S3_SECONDARY_SECRET_ACCESS_KEY` в `.env` → `up -d backend`.
2. Загрузить файл через UI → запись проходит (в PRIMARY), в `/api/storage/status`
   `pending_replications` растёт.
3. Вернуть корректный ключ → `up -d backend` → `POST /api/storage/reconcile` (или подождать
   сайдкар) → `pending_replications` вернулось к 0, объект появился в обоих хранилищах.
