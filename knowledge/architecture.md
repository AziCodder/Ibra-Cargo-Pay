# Architecture

## Stack
- Backend: FastAPI (Python 3.12)
- Frontend: React 18 + TypeScript + Vite
- UI Library: Ant Design (ru_RU locale)
- Database: PostgreSQL 16
- ORM: SQLAlchemy (async, asyncpg)
- Migrations: Alembic
- Bot: Telegram (aiogram)
- File Storage: MinIO (S3-compatible)
- Containerization: Docker Compose
- Auth: JWT (python-jose + passlib/bcrypt)

## Services (Docker Compose)
- `db` -- postgres:16-alpine, port 5432
- `backend` -- FastAPI, port 8000
- `frontend` -- Vite dev server, port 5173
- `bot` -- aiogram long-polling, no port
- `minio` -- MinIO, ports 9000 (API) / 9001 (console)

## Backend Structure
```
backend/
  app/
    api/              # Route modules
      auth.py
      users.py
      suppliers.py
      projects.py
      project_items.py
      project_item_requirements.py
      payment_requests.py
      payments.py
    models/           # SQLAlchemy models
      user.py
      supplier.py
      project.py
      project_item.py
      project_item_requirement.py
      payment_request.py
      payment_request_item.py
      payment_request_attachment.py
      payment.py
    schemas/          # Pydantic request/response schemas
      auth.py
      user.py
      supplier.py
      project.py
      project_item.py
      payment_request.py
      payment.py
    services/         # Business logic
      file_service.py
      notification_service.py
    core/             # App config and infrastructure
      config.py
      database.py
      security.py
      dependencies.py
      seed.py
  alembic/
  tests/
  main.py
  requirements.txt
  Dockerfile
```

## Frontend Structure
```
frontend/
  src/
    api/              # Axios client and API modules
      client.ts
      auth.ts
      users.ts
      suppliers.ts
      projects.ts
      projectItems.ts
      paymentRequests.ts
      payments.ts
    components/       # Reusable UI components
      Auth/
      Common/
      ProjectDetail/
      Projects/
    pages/            # Route-level page components
      LoginPage.tsx
      MainPage.tsx
      DatabasePage.tsx
      ProjectsPage.tsx
      ProjectDetailPage.tsx
    hooks/            # Custom React hooks
    contexts/         # AuthContext
      AuthContext.tsx
    types/            # TypeScript type definitions
    i18n/             # Russian strings
      ru.ts
  package.json
  tsconfig.json
  vite.config.ts
  Dockerfile
```

## Bot Structure
```
bot/
  app/
    handlers/
  main.py
  requirements.txt
  Dockerfile
```

## API Endpoints

### Auth
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /api/auth/login | No | Returns access + refresh tokens |
| POST | /api/auth/refresh | Refresh token | Returns new access token |
| GET | /api/auth/me | Yes | Current user info |

### Users (admin only)
| Method | Path | Description |
|--------|------|-------------|
| GET | /api/users | List, paginated |
| POST | /api/users | Create |
| GET | /api/users/{id} | Detail |
| PUT | /api/users/{id} | Update |
| DELETE | /api/users/{id} | Delete (blocked if has projects) |
| POST | /api/users/{id}/telegram-link | Generate Telegram link token |

### Suppliers (admin only)
| Method | Path | Description |
|--------|------|-------------|
| GET | /api/suppliers | List, paginated |
| POST | /api/suppliers | Create (multipart) |
| GET | /api/suppliers/{id} | Detail |
| PUT | /api/suppliers/{id} | Update |
| DELETE | /api/suppliers/{id} | Delete (SET NULL on items) |

### Projects (role-filtered)
| Method | Path | Role | Description |
|--------|------|------|-------------|
| GET | /api/projects | Any | Admin=all, client=own. Filter: status |
| POST | /api/projects | Admin | Create |
| GET | /api/projects/{id} | Any | Detail (client: only if assigned) |
| PUT | /api/projects/{id} | Admin | Update |
| DELETE | /api/projects/{id} | Admin | Delete (blocked if has requests) |
| GET | /api/projects/{id}/summary | Any | Financial summary per currency |

### Project Items
| Method | Path | Role | Description |
|--------|------|------|-------------|
| GET | /api/projects/{id}/items | Any | List (cost_price excluded for client) |
| POST | /api/projects/{id}/items | Admin | Create |
| GET | /api/projects/{id}/items/{item_id} | Any | Detail |
| PUT | /api/projects/{id}/items/{item_id} | Admin | Update |
| DELETE | /api/projects/{id}/items/{item_id} | Admin | Delete |

### Item Requirements
| Method | Path | Role | Description |
|--------|------|------|-------------|
| GET | /api/projects/{id}/items/{item_id}/requirements | Any | List |
| POST | /api/projects/{id}/items/{item_id}/requirements | Admin | Add (max 5) |
| DELETE | /api/projects/{id}/items/{item_id}/requirements/{req_id} | Admin | Delete |

### Payment Requests
| Method | Path | Role | Description |
|--------|------|------|-------------|
| GET | /api/projects/{id}/payment-requests | Any | List with remaining_amount |
| POST | /api/projects/{id}/payment-requests | Admin | Create (multipart) |
| GET | /api/projects/{id}/payment-requests/{req_id} | Any | Detail with items + payments |
| PUT | /api/projects/{id}/payment-requests/{req_id} | Admin | Update |
| DELETE | /api/projects/{id}/payment-requests/{req_id} | Admin | Delete (blocked if payments exist) |

### Payments
| Method | Path | Role | Description |
|--------|------|------|-------------|
| GET | /api/payment-requests/{req_id}/payments | Any | List (project access check) |
| POST | /api/payment-requests/{req_id}/payments | Any | Add (multipart) |
| DELETE | /api/payment-requests/{req_id}/payments/{pay_id} | Any | Delete (creator or admin) |

### Files
| Method | Path | Description |
|--------|------|-------------|
| GET | /api/files/{file_key} | Serve file from MinIO (auth required) |

## Frontend Routes
```
/login              -> LoginPage
/                   -> MainPage (admin: dashboard, client: redirect to /projects)
/database           -> DatabasePage (admin only)
/database/suppliers -> SuppliersTab
/database/users     -> UsersTab
/projects           -> ProjectsPage
/projects/:id       -> ProjectDetailPage (2-panel: left 1/3 items, right 2/3 requests)
```

## Modules
- users
- suppliers
- projects
- project_items
- project_item_requirements
- payment_requests
- payment_request_items
- payment_request_attachments
- payments

## Backups (Phase 11, добавлено 2026-04-25)

Ежедневные резервные копии БД в отдельный S3-бакет.

**Архитектура:**
- Sidecar-контейнер `backup` (alpine + crond + curl) с TZ=Europe/Moscow.
- Cron `0 3 * * *` дёргает `POST /api/backups/run` на backend, передавая `X-Backup-Secret`.
- Backend выполняет `pg_dump --format=custom --compress=9` (subprocess), кладёт результат в `BACKUP_S3_BUCKET` под ключом `db-backups/YYYY/MM/dump_YYYYMMDD_HHMMSSZ.dump`.
- После загрузки запускается retention: удаляются объекты старше `BACKUP_RETENTION_DAYS` (по умолчанию 30).
- Логика бэкапа живёт только в backend (`app/services/backup_service.py`); sidecar — тонкий триггер.
- `postgresql-client-16` устанавливается в backend Dockerfile через PGDG-репозиторий (версия клиента должна совпадать с сервером).

**API (`/api/backups`):**
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /api/backups/run | X-Backup-Secret | Триггер от sidecar/cron |
| POST | /api/backups/run-admin | Admin JWT | Ручной запуск из UI |
| GET | /api/backups | Admin JWT | Список бэкапов |
| GET | /api/backups/download-url?key=… | Admin JWT | Presigned URL (1ч) |

**Env переменные (`.env`):**
- `BACKUP_S3_BUCKET` — отдельный бакет для дампов БД (если пусто — фича выключена).
- `BACKUP_S3_PREFIX` — префикс ключей (по умолчанию `db-backups/`).
- `BACKUP_RETENTION_DAYS` — сколько дней хранить (по умолчанию 30).
- `BACKUP_TRIGGER_SECRET` — секрет для авторизации sidecar (обязательно сменить от дефолта).

**UI:** вкладка «Бэкапы» в `/database/backups` (admin only). Кнопка «Создать бэкап сейчас», список с скачиванием через presigned URL.
