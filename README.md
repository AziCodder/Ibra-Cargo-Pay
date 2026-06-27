# Ibra Cargo Pay — Project Management & Payment Tracking

Внутренняя система управления проектами, поставщиками, номенклатурой, заявками
на оплату и платежами. Роли: **admin** (полный доступ, включая БД поставщиков и себестоимость) и **client** (проекты, номенклатура с флагом `shared_access`, заявки и платежи). Уведомления через Telegram.

### Бизнес-модель

- **Общие проекты** — поле `client_id` необязательно; все авторизованные пользователи видят список проектов.
- **Номенклатура** — у каждой позиции флаг `shared_access`: если включён, client может редактировать; если выключен — только просмотр (admin управляет флагом).
- **Заметки проекта** — личные (`private`, видит автор и admin) или общие (`shared`, видят все с доступом к проекту).
- **Платежи** — создаются сразу со статусом `confirmed`, без этапа подтверждения.

## Stack

- **Backend:** FastAPI + SQLAlchemy (async) + PostgreSQL 16
- **Frontend:** React + TypeScript + Vite + Ant Design (раздаётся через nginx в проде)
- **Bot:** Telegram (aiogram)
- **Storage:** S3-compatible (для документов и бэкапов БД)
- **Infrastructure:** Docker Compose
- **Backups:** sidecar-контейнер с cron, ежедневно в 03:00 Europe/Moscow

---

## Production deploy на Ubuntu 22.04 (24/7)

Все шаги выполняются от root. Если в `/opt` остались старые попытки —
сначала запустите `sudo bash scripts/server-cleanup.sh` после клонирования.

### 1. Клонирование

```bash
sudo mkdir -p /opt
sudo git clone https://github.com/AziCodder/Ibra-Cargo-Pay.git /opt/ibra-cargo-pay
cd /opt/ibra-cargo-pay
```

### 2. Конфигурация окружения

```bash
sudo cp .env.example .env
sudo nano .env   # заполните DB_PASSWORD, SECRET_KEY, S3_*, TELEGRAM_BOT_TOKEN, BOT_SECRET
```

`SECRET_KEY` сгенерируйте: `openssl rand -hex 32`.

### 3. Запуск (установит Docker если его нет)

```bash
sudo bash scripts/deploy.sh
```

Скрипт идемпотентный: установит Docker Engine + compose plugin, проверит `.env`,
поднимет стек через `docker compose up -d --build`.

### 4. Автозапуск после ребута

`restart: unless-stopped` уже стоит на всех сервисах. Достаточно убедиться,
что docker.service включён (deploy.sh это делает):

```bash
sudo systemctl is-enabled docker   # должен ответить enabled
```

Опционально — оборачивающий systemd-юнит:

```bash
sudo cp scripts/ibra-cargo-pay.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ibra-cargo-pay.service
```

### 5. Проверка

```bash
curl -fsS http://localhost:8000/health    # {"status":"ok"}
docker compose ps                          # все сервисы Up (healthy)
docker compose logs -f --tail=50           # живые логи
```

| Сервис   | URL                                |
|----------|------------------------------------|
| Frontend | `http://<server-ip>/`              |
| Backend  | `http://<server-ip>:8000`          |
| API docs | `http://<server-ip>:8000/docs`     |

---

## Обновление

```bash
cd /opt/ibra-cargo-pay
sudo bash scripts/update.sh
```

Делает `git fetch && git reset --hard origin/main`, пересобирает образы и
рестартует контейнеры.

---

## Локальная разработка

### Через Docker Compose

```bash
cp .env.example .env
docker compose up --build
```

Frontend (nginx-сборка) на `http://localhost:80`. Для горячей перезагрузки
фронта используйте Vite напрямую:

```bash
cd frontend
npm install
npm run dev   # http://localhost:5173, проксирует /api на backend
```

### Backend без Docker

```bash
cd backend
python3.12 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
uvicorn main:app --reload --port 8000
```

### Миграции БД

```bash
docker compose exec backend alembic upgrade head
docker compose exec backend alembic revision --autogenerate -m "description"
```

---

## Переменные окружения

См. [.env.example](.env.example). Ключевые:

| Variable | Description |
|----------|-------------|
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` | PostgreSQL credentials |
| `SECRET_KEY` | JWT signing secret (≥32 символов) |
| `FRONTEND_URL` | Origin фронта для CORS (`http://<домен>`) |
| `S3_*` | S3-совместимое хранилище для файлов |
| `TELEGRAM_BOT_TOKEN` | Токен из @BotFather |
| `BOT_SECRET` | Секрет для подписи запросов bot ↔ backend |
| `BACKUP_S3_BUCKET` | Bucket для дампов БД (пусто = бэкапы выключены) |
| `BACKUP_TRIGGER_SECRET` | Секрет, которым cron-sidecar триггерит /api/backups/run |

---

## Структура

```
├── backend/          FastAPI + SQLAlchemy + Alembic
├── frontend/         React + Vite + nginx (прод)
├── bot/              Telegram bot (aiogram)
├── backup/           Cron-sidecar, ежедневный pg_dump → S3
├── scripts/
│   ├── deploy.sh             первичная установка на Ubuntu 22.04
│   ├── update.sh             git pull + rebuild
│   ├── server-cleanup.sh     снос старых попыток в /opt
│   └── ibra-cargo-pay.service  опциональный systemd unit
├── docker-compose.yml
└── .env.example
```

---

## Эксплуатация

```bash
docker compose ps                     # статус
docker compose logs -f backend        # логи сервиса
docker compose restart backend        # рестарт одного сервиса
docker compose down                   # остановить всё
docker compose down -v                # + удалить volume с БД (ОПАСНО)
docker compose exec db psql -U postgres project_manager   # консоль БД
```

Бэкапы: триггерятся cron-ом в контейнере `backup` ежедневно в 03:00 MSK.
Ручной запуск: `docker compose exec backup /usr/local/bin/run-backup.sh`.
