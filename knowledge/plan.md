# Implementation Plan: Project Management & Payment Tracking Platform

## Context

Building a greenfield internal project management and payment tracking platform from scratch. The project directory currently has only a `knowledge/` folder with business specs. No code, no git repo, no infrastructure exists yet.

**Business need:** A system for managing projects, suppliers, nomenclature (project items), payment requests, and payments with strict role-based access (admin/client). Notifications via Telegram bot.

---

## Key Decisions (Confirmed)

1. **Mixed currencies:** Yes -- items in one project can have different currencies. All totals displayed per-currency.
2. **Commission:** Percentage added on top of price. `effective_price = price * (1 + commission/100)`. Used in total and profit formulas.
3. **File storage:** External S3-compatible storage (Hostkey). Configured via env vars. Backend uses boto3/aiobotocore. No MinIO container needed.
4. **UI library:** Ant Design with built-in `ru_RU` locale.

---

## Critical Gaps Found in Spec (Resolved)

### GAP 1: Currency Handling
Project items have a currency field (CNY/USD/RUB). Mixed currencies in one project are allowed. All calculations grouped by currency. Payments have their own currency field matching the request currency.

### GAP 2: Telegram Account Linking
Added `telegram_chat_id` to users table. Admin generates a one-time link token; user sends `/start <token>` to the bot to link.

### GAP 3: Commission Field
Commission is a **percentage added on top of price**. It affects all calculations:
- `effective_price = price * (1 + commission / 100)`
- `total = SUM(effective_price * quantity)` per currency
- `profit = SUM((effective_price - cost_price) * quantity)` per currency, admin only
- `remaining = total - paid` per currency

Client sees `price` and `commission` separately, but totals reflect the commission-inclusive effective price.

### GAP 4: Payment Request Deletion with Payments
Block deletion if payments exist (matching the project deletion pattern).

### GAP 5: "Requirements" Structure
Separate `project_item_requirements` table with text-only entries. Add/delete individually. Max 5 enforced at API level.

### GAP 6: Missing Tables
`project_item_requirements` and `payment_request_attachments` added beyond the original 7 tables.

### GAP 7: Payment Ownership
Added `created_by` on payments. Client can only delete payments they created. Admin can delete any.

### GAP 8: Supplier/User Deletion Guards
- Supplier deletion: SET NULL on project_items.supplier_id. Warn admin before deleting referenced supplier.
- User deletion: Blocked if user is assigned to any project.

---

## Implementation Phases

### Phase 0: Project Scaffolding ✅ COMPLETED (2026-04-02)
**Goal:** All services boot via docker compose.

```
backend/
  app/
    api/          models/        schemas/
    services/     core/
  alembic/        tests/
  main.py         requirements.txt    Dockerfile
frontend/
  src/
    api/          components/    pages/
    hooks/        contexts/      types/       i18n/
  package.json    vite.config.ts  Dockerfile
bot/
  app/            main.py        requirements.txt    Dockerfile
docker-compose.yml    .env.example    .gitignore    README.md
```

Services: `db` (postgres:16-alpine), `backend` (FastAPI), `frontend` (Vite), `bot` (aiogram)
File storage: external S3-compatible (Hostkey) via env vars — no container needed.

**Verify:** `docker compose up --build` starts all; `GET /health` returns 200; frontend loads at :5173.

### Phase 1: Database & Auth ✅ COMPLETED (2026-04-02)
**Goal:** Schema deployed, JWT auth working, login page functional.

- All 9 SQLAlchemy models with relationships
- Alembic initial migration
- JWT auth (access 30min + refresh 7d) via python-jose + passlib/bcrypt
- Endpoints: `POST /api/auth/login`, `POST /api/auth/refresh`, `GET /api/auth/me`
- `get_current_user` and `require_admin` dependencies
- Seed default admin user (admin/admin)
- Frontend: AuthContext, Axios interceptor, LoginPage, ProtectedRoute, AdminRoute

**Verify:** Login works in browser. Protected routes redirect. Invalid creds show Russian error.

### Phase 2: User & Supplier CRUD ✅ COMPLETED (2026-04-05)
**Goal:** Admin manages users and suppliers through UI.

- Backend CRUD endpoints for users (admin only) and suppliers (admin only)
- File upload service using MinIO (boto3/aiobotocore) -- `backend/app/services/file_service.py`
- MinIO buckets: `supplier-docs`, `payment-request-files`, `payment-files`
- Frontend: MainPage with role-based nav, DatabasePage with tabs
- UsersTab and SuppliersTab with Ant Design Table + modals
- Deletion guards: user with projects blocked, supplier referenced by items warned

**Verify:** Full CRUD works. Files upload to MinIO. Russian labels everywhere. Non-admin gets 403.

**Реализовано:**
- `file_service.py`: добавлен `get_presigned_url()` для скачивания файлов
- `backend/app/api/files.py`: `GET /api/files/download-url?key=...` (требует авторизации)
- `suppliers.py`: `POST /api/suppliers/{id}/documents` (slot+file, multipart), `DELETE /api/suppliers/{id}/documents/{slot}`
- `payments.py`: `add_payment` переведён на multipart Form, принимает опциональный файл (`file_path`, `file_name`)
- `payment_request.py` схема: добавлен `file_path` в `PaymentShortOut`
- `main.py`: зарегистрирован `files_router`
- Frontend `api/files.ts`: `getFileDownloadUrl(key)`
- Frontend `api/suppliers.ts`: `uploadSupplierDocument`, `deleteSupplierDocument`
- Frontend `api/payments.ts`: `addPayment` отправляет FormData с опциональным файлом
- Frontend `SuppliersTab.tsx`: drawer поставщика с 3 слотами документов (загрузка/скачивание/удаление)
- Frontend `PaymentRequestDetailModal.tsx`: кнопка скачивания у вложений заявки и файлов платежей; форма добавления платежа поддерживает прикрепление файла
- TypeScript: 0 ошибок

### Phase 3: Projects List & CRUD ✅ COMPLETED (2026-04-04)
**Goal:** Project cards, filtering, role-based access.

- `GET /api/projects` -- admin=all, client=own only, filter by status, paginated, sorted by created_at DESC
- Admin CRUD. Delete blocked if payment requests exist.
- Frontend: ProjectsPage with cards, status filter tabs
- Client: no create/edit/delete actions visible
- `project_number` sequential field via Postgres sequence (migration 002)
- Backend validates that selected user has role='client' on create/update

**Verify:** Admin creates project for client. Client sees only theirs. Filter works. Delete with requests blocked.

### Phase 4: Project Detail -- Nomenclature (Left Panel) ✅ COMPLETED (2026-04-04)
**Goal:** Items table, detail view, requirements, financial calculations.

- Items CRUD under `/api/projects/{id}/items` -- cost_price excluded from client response
- Requirements CRUD with max 5 enforcement
- Project summary endpoint with per-currency calculations (including commission)
- Frontend: 2-panel layout (1/3 left, 2/3 right), ItemsTable, ItemDetailModal, RequirementsList, CalculationsSummary

**Verify:** Client can't see cost_price (check network tab). Mixed currency totals correct. Profit hidden from client.

**Реализовано:**
- Backend: CRUD items + requirements (max 5) + project summary endpoint
- `ProjectItemClientOut` (без cost_price), `ProjectItemAdminOut` (с cost_price)
- Frontend: ItemsPanel (таблица + SummaryRow по валютам), ItemDetailDrawer (детали + требования), ItemFormModal
- 2-панельный layout в ProjectDetailPage: 40% левая / 60% правая (placeholder для Phase 5)

### Phase 5: Payment Requests (Right Panel) ✅ COMPLETED (2026-04-04)
**Goal:** Admin creates payment requests from items. File attachments via MinIO.

- Payment request CRUD under `/api/projects/{id}/payment-requests`
- Multi-item selection with per-item amounts. Max 3 file attachments.
- Computed remaining_amount in responses
- Frontend: PaymentRequestList, CreateModal with item selector, DetailModal, "Copy Info" button

**Verify:** Create request with 2 items. Total auto-calculates. 3 files accepted, 4th rejected. Client can view but not create/edit/delete.

**Реализовано:**
- Backend: CRUD payment_requests, вложения (max 3, max 10MB), remaining_amount вычисляется на лету
- Frontend: PaymentRequestsPanel (карточки + прогресс), PaymentRequestFormModal (выбор позиций + суммы + файлы), PaymentRequestDetailModal (просмотр/ред., Copy Info, вложения)
- ProjectDetailPage: правая панель теперь показывает PaymentRequestsPanel
- TypeScript: 0 ошибок

### Phase 6: Payments ✅ COMPLETED (2026-04-04)
**Goal:** Add/delete payments, remaining balance tracking.

- Payments CRUD under `/api/payment-requests/{req_id}/payments`
- Any authenticated user with project access can add. Delete: creator or admin only.
- Frontend: AddPaymentForm, payments list in request detail, completion indicator when remaining=0

**Verify:** Payment reduces remaining. Full payment shows completion badge. Client can't delete admin's payment.

**Реализовано:**
- Backend: уже был готов (list, add, delete с проверкой created_by)
- Frontend: в PaymentRequestDetailModal добавлена инлайн-форма добавления платежа (сумма, валюта, примечание) + кнопка удаления у каждого платежа (admin или создатель)
- Завершённая заявка (remaining=0) показывает тег "Оплачено", форма добавления скрыта
- TypeScript: 0 ошибок

### Phase 7: Telegram Bot ✅ COMPLETED (2026-04-04)
**Goal:** Automated notifications to linked users.

- `notification_service.py` -- async Telegram API calls (fire-and-forget via asyncio.create_task)
- Payment request created -> notify client. Payment added -> notify admins.
- Bot: `/start` greeting, `/start <token>` linking flow
- Token generation endpoint for admin
- Frontend: telegram_chat_id field on user form

**Verify:** Bot starts. Linking works. Notifications sent. Unlinked users don't cause errors.

**Реализовано:**
- `backend/app/services/notification_service.py` — fire-and-forget уведомления через Telegram Bot API (httpx)
- `backend/app/api/bot.py` — `POST /api/bot/verify-link` (защищён X-Bot-Secret)
- `backend/app/api/users.py` — `POST /api/users/{id}/telegram-link` → JWT-токен (24ч)
- `backend/app/core/config.py` — добавлен `bot_secret`
- `backend/main.py` — зарегистрирован bot_router
- `payment_requests.py` — уведомление клиента при создании заявки
- `payments.py` — уведомление всех admin-ов при добавлении платежа
- `bot/main.py` — `/start` приветствие + `/start <token>` → вызов backend verify-link
- `bot/requirements.txt` — добавлен httpx
- `.env.example`, `docker-compose.yml` — добавлен BOT_SECRET
- Frontend `UsersTab.tsx` — кнопка "Ссылка Telegram" (иконка Link) → модальное окно с токеном и инструкцией
- TypeScript: 0 ошибок

### Phase 8: Polish & Security ✅ COMPLETED (2026-04-05)
- Pydantic validation, rate limiting on login, CORS
- Loading spinners, empty states, 404 page -- all in Russian
- Full Russian text audit
- Security: IDOR testing, file upload validation, no cost_price leaks

**Реализовано:**
- `slowapi==0.1.9` — rate limiting: `POST /api/auth/login` ограничен 10 запросами/минуту с IP
- `backend/app/core/limiter.py` — Limiter(key_func=get_remote_address)
- `main.py` — подключён limiter и RateLimitExceeded handler
- `file_service.py` — `validate_file_extension()` разрешает только PDF, Word, Excel, изображения (JPG, PNG, GIF, WebP)
- `payment_request_attachments.py`, `payments.py`, `suppliers.py` — MIME-type валидация перед загрузкой
- `frontend/src/pages/NotFoundPage.tsx` — страница 404 на русском с кнопкой "На главную"
- `App.tsx` — маршрут `path="*"` → NotFoundPage (вместо редиректа на /)
- TypeScript: 0 ошибок

### Phase 9: Improvements П1–П8 ✅ COMPLETED (2026-04-22)
**Goal:** Реализованы пункты из раздела «Предложения по улучшению» (`knowledge/tz.md`): П1 (Excel-экспорт), П2 (дашборд), П3 (дедлайны заявок), П4 (журнал изменений с JSON-diff), П6 (импорт номенклатуры из Excel), П7 (приоритет заявок), П8 (комментарии к заявкам). Пропущены: П5 (глобальный поиск), П9–П11 (низкий приоритет).

**Backend:**
- Миграция `004_improvements.py` (revision `c5d3e6f7a8b9`, down_revision `b4c2d5e6f7a8`):
  - `payment_requests.due_date DATE NULL`, `payment_requests.priority VARCHAR(10) NOT NULL DEFAULT 'normal'` + CheckConstraint
  - Новая таблица `audit_log` (JSONB `changes`, индексы `(entity_type, entity_id)`, `user_id`, `created_at DESC`)
  - Новая таблица `payment_request_comments` (CASCADE на payment_request, RESTRICT на author)
- Модели: `models/audit_log.py`, `models/payment_request_comment.py`; расширены `payment_request.py`, `user.py`
- Схемы: `schemas/audit_log.py`, `schemas/payment_request_comment.py`, `schemas/dashboard.py`; `PaymentRequest*` расширены `due_date`, `priority`
- Сервисы:
  - `services/audit_service.py` — `log_action(db, user_id, action, entity_type, entity_id, before, after)`; `diff_dict()` вычисляет пер-полевой diff; create → `{after: {...}}`, delete → `{before: {...}}`
  - `services/export_service.py` — `generate_project_excel(db, project_id, is_admin) -> bytes` (openpyxl, 3 листа: «Позиции», «Заявки на оплату», «Сводка по валютам»; cost_price/profit скрыты для client)
  - `services/import_service.py` — `generate_items_template()` + `parse_items_xlsx()` с построчной валидацией и `errors: [{row, message}]`
- API-роуты новые:
  - `api/audit.py` — `GET /api/audit` (admin only; фильтры `entity_type`, `user_id`, `entity_id`; пагинация `page`/`page_size`)
  - `api/dashboard.py` — `GET /api/dashboard/summary` (admin only)
  - `api/payment_request_comments.py` — GET/POST/DELETE; DELETE только автор или admin
- API-роуты расширенные:
  - `api/projects.py` — `GET /api/projects/{id}/export` (StreamingResponse xlsx, доступен и client — server-side фильтрация)
  - `api/project_items.py` — `GET /import-template` + `POST /import` (admin only)
  - `api/payment_requests.py` — POST/PUT принимают `due_date`, `priority`; Out-схемы возвращают их
- `audit_service.log_action` интегрирован во все CRUD: project, payment_request, payment, project_item, project_item_requirement, supplier, user, payment_request_comment (все 8 типов также в `ALLOWED_ENTITY_TYPES` роутера audit)
- `main.py` — подключены `audit_router`, `dashboard_router`, `comments_router`
- `requirements.txt` — `openpyxl==3.1.5`

**Frontend:**
- Типы: `PaymentRequestPriority`, `AuditAction`, `AuditLog`, `AuditLogListOut`, `PaymentRequestComment`, `CommentCreate`, `CurrencyBalance`, `RecentPayment`, `DashboardSummary`; `PaymentRequest*` расширены `due_date`, `priority`
- API: `api/audit.ts`, `api/dashboard.ts`, `api/paymentRequestComments.ts`; `api/projects.ts::downloadProjectExport`; `api/projectItems.ts::downloadItemsTemplate`, `importItems`
- Компоненты обновлены:
  - `PaymentRequestFormModal.tsx` — DatePicker (`due_date`) + Select (`priority`)
  - `PaymentRequestsPanel.tsx` — сортировка priority→due_date→created_at, теги priority + `renderDueDate()` с цветовой индикацией (красный/оранжевый/жёлтый/зелёный)
  - `PaymentRequestDetailModal.tsx` — поля due_date+priority (просмотр/ред.), секция «Комментарии» (List авторов+таймштампов, кнопка удалить у своих/admin, Input.TextArea до 4000 символов)
  - `ItemsPanel.tsx` — admin-кнопки «Шаблон» и «Импорт» (xlsx) + модалка результата `{created, errors[]}`
  - `ProjectDetailPage.tsx` — кнопка «Excel» (DownloadOutlined) доступна всем
- Компоненты новые:
  - `pages/DashboardPage.tsx` — Statistic карточки (активные/закрытые проекты, закрытые заявки), Card «Остатки по валютам», List «Последние платежи»
  - `components/Database/AuditLogTab.tsx` — Table с фильтрами entity_type/user_id, серверная пагинация, expandable строки → таблица «Поле / Было / Стало»
- Роутинг:
  - `App.tsx::RootRedirect` — admin → DashboardPage, client → /projects; добавлен маршрут `/database/audit` под AdminRoute
  - `DatabasePage.tsx` — третья вкладка «Журнал изменений»
  - `MainPage.tsx` — пункт меню «Главная» (HomeOutlined) для admin
- `i18n/ru.ts` — секции `dashboard`, `audit`, `export` + расширены `paymentRequests` (priority/comments/dueDate)
- TypeScript: 0 ошибок

**Verify:**
- Excel-экспорт: client не видит cost_price/profit в файле (is_admin-фильтрация в export_service)
- Дашборд: только admin (require_admin), остатки по 3 валютам, 10 последних платежей
- Журнал изменений: admin-only, фильтры работают, раскрытие → diff видно
- Комментарии: автор удаляет свои, admin удаляет любые (IDOR защита)
- Импорт Excel: построчная валидация, ошибки не блокируют валидные строки
- Приоритет/дедлайн: сортировка в PaymentRequestsPanel корректна

### Phase 10: Bug Fixes & Payment Approval Workflow ✅ COMPLETED (2026-04-24)
**Goal:** Исправлены три пользовательских бага и переработана логика платежей с подтверждением админом.

**Проблема 1 — `sqlalchemy.exc.MissingGreenlet` при обновлении позиции:**
- **Причина:** `audit_service.entity_snapshot()` после `db.flush()` читал expired атрибут `updated_at` (`onupdate=func.now()`), что триггерило async lazy-refresh вне greenlet-контекста.
- **Фикс (`backend/app/services/audit_service.py`):** переписан `entity_snapshot()` через `sqlalchemy.inspect()` — читает из `obj.__dict__` и пропускает поля из `state.unloaded`, избегая lazy-load. Теперь snapshot безопасен после flush.

**Проблема 2 — клиент на входе видит чужие проекты:**
- **Причина:** React Query кэш от предыдущего пользователя (admin) сохранялся после logout/login.
- **Фикс (`frontend/src/contexts/AuthContext.tsx`):** в `login()` и `logout()` вызывается `queryClient.clear()` (через `useQueryClient`).

**Проблема 3 — workflow подтверждения платежей:**
- Клиент добавляет платёж → создаётся со статусом `pending`, админы получают Telegram-уведомление.
- Админ подтверждает или отклоняет с обязательной причиной.
- `remaining_amount` во всех местах учитывает ТОЛЬКО `confirmed` платежи.

**Backend:**
- Миграция `005_payment_approval.py` (revision `d7e4f8a9b0c1`, down_revision `c5d3e6f7a8b9`):
  - `payments.status VARCHAR(10) NOT NULL DEFAULT 'confirmed'` (server_default) + CheckConstraint (`pending`/`confirmed`/`rejected`)
  - `payments.confirmed_by INT NULL` (FK → users, ON DELETE SET NULL)
  - `payments.confirmed_at TIMESTAMPTZ NULL`
  - `payments.rejection_reason TEXT NULL`
  - Индекс `idx_payments_status`
  - Data migration: `UPDATE payments SET confirmed_at = created_at, confirmed_by = created_by WHERE status = 'confirmed'` — существующие платежи помечаются подтверждёнными.
- `models/payment.py`: добавлены поля `status` (Python default `pending`, SQL server_default `confirmed` для обратной совместимости), `confirmed_by`, `confirmed_at`, `rejection_reason`, relationship `confirmer`.
- `schemas/payment.py`: `PaymentStatus = Literal["pending","confirmed","rejected"]`, новая схема `PaymentReject` (`reason: str, min=1, max=1000`), `PaymentOut` расширена полями статуса.
- `schemas/payment_request.py::PaymentShortOut`: добавлены `status`, `confirmed_by`, `confirmed_at`, `rejection_reason`.
- `api/payments.py` переписан:
  - `POST /api/payment-requests/{req_id}/payments` — admin → `confirmed` сразу; client → `pending` + `notify_payment_pending` всем админам
  - `POST /api/payment-requests/{req_id}/payments/{pay_id}/confirm` — admin only, `409` если не pending, выставляет `confirmed_by`/`confirmed_at`, `notify_payment_confirmed`
  - `POST /api/payment-requests/{req_id}/payments/{pay_id}/reject` (body `PaymentReject`) — admin only, сохраняет `rejection_reason`, `notify_payment_rejected` с причиной
  - `DELETE` — client может удалять только свои `pending`/`rejected`; admin — любые
- `api/payment_requests.py::_compute_remaining` и N+1-запрос в `list_payment_requests` фильтруют `Payment.status == "confirmed"`.
- `api/dashboard.py`: три запроса (`paid_q`, `recent_q`, `completed_q` outerjoin) фильтруют `status == "confirmed"`.
- `services/export_service.py`: `summary_paid_q` и per-request `paid` фильтруют `status == "confirmed"`.
- `services/notification_service.py` добавлены 3 функции:
  - `notify_payment_pending(admin_chat_ids, ...)` — 🔔 «Новый платёж ожидает подтверждения»
  - `notify_payment_confirmed(client_chat_id, ...)` — ✅ «Ваш платёж подтверждён»
  - `notify_payment_rejected(client_chat_id, ..., reason)` — ❌ «Ваш платёж отклонён» + причина

**Frontend:**
- `types/index.ts`: `PaymentStatus = 'pending'|'confirmed'|'rejected'`, `Payment`/`PaymentShort` расширены `status`, `confirmed_by`, `confirmed_at`, `rejection_reason`; новая `PaymentReject`.
- `api/payments.ts`: добавлены `confirmPayment(reqId, payId)`, `rejectPayment(reqId, payId, reason)`.
- `contexts/AuthContext.tsx`: `queryClient.clear()` в login (перед apiLogin) и logout.
- `components/ProjectDetail/PaymentRequestDetailModal.tsx`:
  - `PAYMENT_STATUS_LABEL`/`PAYMENT_STATUS_COLOR` (orange/green/red)
  - Tag статуса у каждого платежа в списке
  - Для admin при `pending`: кнопки «Подтвердить» (Popconfirm) и «Отклонить» (открывает модалку)
  - Модалка отклонения с `Input.TextArea` (max 1000) для причины
  - Для client при `rejected` — отображение `rejection_reason` красным текстом
  - Client может удалить только свой `pending`/`rejected` платёж
  - Сообщение при создании: client видит «Платёж отправлен на подтверждение»
- `i18n/ru.ts::payments`: добавлены ключи `statusPending`/`statusConfirmed`/`statusRejected`, `confirm`/`reject`, `rejectReason`, `pendingNote`, `addedPending`, и др.
- TypeScript: 0 ошибок.

**Verify:**
- ✅ Миграция 005 применена: `c5d3e6f7a8b9 -> d7e4f8a9b0c1` (видно в логах backend при рестарте)
- ✅ Структура таблицы `payments` проверена через `\d payments`: status/confirmed_by/confirmed_at/rejection_reason + CHECK + индекс + FK (ON DELETE SET NULL) на месте
- ✅ Backend и frontend контейнеры в статусе healthy, `/health` возвращает 200
- ✅ `remaining_amount` пересчитывается только по `confirmed` платежам (payment_requests.py, dashboard.py, export_service.py)
- ✅ MissingGreenlet устранён: `entity_snapshot` теперь читает `obj.__dict__`, не триггерит lazy-load
- ✅ Кэш React Query очищается при смене пользователя

---

## Risks

| # | Risk | Severity | Mitigation |
|---|------|----------|------------|
| R1 | Mixed currency math produces nonsense | HIGH | Group all calculations by currency from day 1 |
| R2 | File upload attacks (exe, oversized) | MEDIUM | Validate MIME type, 10MB limit, random filenames in MinIO |
| R3 | Race conditions on payment amounts | MEDIUM | Compute remaining at query time, never store it |
| R4 | No audit trail for financial data | MEDIUM | Track created_by, created_at on all mutable records |
| R5 | Telegram notification silently lost | LOW | Log all attempts; future: retry queue |
