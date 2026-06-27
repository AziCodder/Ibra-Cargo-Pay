# Детальный план: чек-лист правок Ibra Cargo Pay

> Источник: https://telegra.ph/CHek-list-pravok-06-26  
> Базовая точка: коммит `4ccfd2b`  
> Дата: 27.06.2026

## Рекомендуемая нарезка по промптам (12-14 блоков)

| # | Блок | Шаги |
|---|------|------|
| 1 | Фаза 0 | 0.1-0.3 |
| 2 | Раздел 1 backend | 1.1-1.7 |
| 3 | Раздел 1 frontend | 1.8-1.13 |
| 4 | Раздел 2 backend items | 2.1-2.6 |
| 5 | Раздел 2 backend payments | 2.7-2.9 |
| 6 | Раздел 2 frontend | 2.10-2.17 |
| 7 | Раздел 3 | 3.1-3.4 |
| 8 | Раздел 4 backend | 4.1-4.3 |
| 9 | Раздел 4 frontend | 4.2, 4.4-4.6 |
| 10 | Раздел 5 | 5.1-5.5 |
| 11 | Раздел 6-7 | 6.1-6.4, 7.1-7.6 |
| 12 | Раздел 8-9 + финал | 8.1-8.8, 9.1-9.3, 10.x |

**Формат каждого шага:**
- **Цель** — зачем делаем
- **Задачи** — что конкретно выполнить
- **Файлы** — какие файлы затронуты
- **Правки** — детали изменений
- **Итог** — проверяемый результат после шага

**Зафиксированные бизнес-правила:**
| Правило | Интерпретация |
|---------|---------------|
| Доступ к позиции | `shared_access=true` → client CRUD; `false` → только просмотр |
| Заявка на оплату | client **создаёт всегда**; edit/delete — только если **все** позиции заявки с `shared_access=true` |
| Платёж | client add/download всегда; delete — только owner + все позиции заявки доступны |
| `client_id` | nullable, не используется в API/UI (колонку не удалять в первой итерации) |
| Себестоимость NULL | итоги считаются как `price` (маржа = 0) |
| Подтверждение платежа | убрать полностью — все платежи сразу `confirmed` |

---

## ФАЗА 0. Подготовка

### Шаг 0.1 — Создание рабочей ветки

> ✅ Выполнено | Тесты: 14/14 | Дата: 2026-06-27

**Цель:** изолировать все правки от `main`, иметь возможность отката к маркеру `4ccfd2b`.

**Задачи:**
1. `git checkout -b feature/checklist-pravok` от текущего `main`
2. Убедиться, что HEAD = `4ccfd2b` или позже (маркер уже есть)

**Файлы:** только git, код не меняется.

**Правки:** нет.

**Итог:** ветка `feature/checklist-pravok` создана; `git log -1` показывает маркер «Состояние перед изменениями».

---

### Шаг 0.2 — Модуль централизованных прав

> ✅ Выполнено | Тесты: 14/14 | Дата: 2026-06-27

**Цель:** единая точка проверки прав вместо разрозненных `require_admin` и `client_id` сравнений.

**Задачи:**
1. Создать [`backend/app/core/permissions.py`](backend/app/core/permissions.py)
2. Реализовать функции (чистые, без DB):
   - `can_access_project(user) -> bool` — всегда `True` для авторизованного
   - `can_edit_project(user) -> bool` — `admin` или `client`
   - `can_edit_item(user, item) -> bool` — admin или (client и `item.shared_access`)
   - `can_view_item_cost(user) -> bool` — только admin
   - `all_items_accessible(user, items) -> bool` — admin или все `shared_access`
   - `can_edit_payment_request(user, items) -> bool` — admin или `all_items_accessible`
   - `can_delete_payment(user, payment, items) -> bool` — admin или (owner и `all_items_accessible`)
   - `default_shared_access_for_creator(role) -> bool` — client→True, admin→False
   - `effective_cost_price(item) -> Decimal` — `cost_price or price`

**Файлы:**
- **Создать:** `backend/app/core/permissions.py`

**Правки:**
```python
# Скелет модуля — все API будут импортировать отсюда
def can_edit_item(user, item) -> bool:
    if user.role == "admin":
        return True
    return user.role == "client" and item.shared_access
```

**Итог:** модуль существует, импортируется без ошибок; пока не подключён к API — это нормально.

---

### Шаг 0.3 — Утилита доступа к проекту (backend)

> ✅ Выполнено | Тесты: 14/14 | Дата: 2026-06-27

**Цель:** заменить `_check_project_access` во всех API одной функцией.

**Задачи:**
1. Добавить в `permissions.py`:
   - `async def ensure_project_access(project_id, user, db)` — загрузить проект или 404; для любого role — OK
2. Подготовить список файлов для рефакторинга (чеклист на шагах 1.8, 2.x)

**Файлы:**
- `backend/app/core/permissions.py`

**Правки:** добавить helper с `db.get(Project, project_id)`.

**Итог:** готов единый helper; дублирующие `_check_access` будут заменены по мере прохождения разделов.

---

## РАЗДЕЛ 1. Проекты и клиенты

### Шаг 1.1 — Миграция БД: отвязка client_id

> ✅ Выполнено | Тесты: 19/19 | Дата: 2026-06-27

**Цель:** проекты перестают быть привязаны к конкретному пользователю-клиенту.

**Задачи:**
1. Создать `backend/alembic/versions/007_checklist_projects.py`
2. `ALTER TABLE projects ALTER COLUMN client_id DROP NOT NULL`
3. `UPDATE projects SET client_id = NULL`
4. `downgrade`: вернуть NOT NULL (с оговоркой — только если все NULL заполнены)

**Файлы:**
- **Создать:** `backend/alembic/versions/007_checklist_projects.py`

**Правки:**
```sql
-- upgrade
ALTER TABLE projects ALTER COLUMN client_id DROP NOT NULL;
UPDATE projects SET client_id = NULL;
```

**Итог:** `alembic upgrade head` проходит; в БД все `projects.client_id IS NULL`; старые данные не потеряны.

---

### Шаг 1.2 — Модель Project

> ✅ Выполнено | Тесты: 19/19 | Дата: 2026-06-27

**Цель:** ORM соответствует nullable `client_id`.

**Задачи:**
1. `client_id: Mapped[int | None]`
2. Relationship `client` — optional

**Файлы:**
- [`backend/app/models/project.py`](backend/app/models/project.py) — строки 29, 42–44

**Правки:**
- `client_id` → optional
- `client: Mapped[User | None]`

**Итог:** модель компилируется; миграция и модель согласованы.

---

### Шаг 1.3 — Pydantic-схемы проекта

> ✅ Выполнено | Тесты: 19/19 | Дата: 2026-06-27

**Цель:** API не принимает и не требует `client_id`.

**Задачи:**
1. `ProjectCreate` — убрать `client_id`; поля: `name`, `description?`, `status?`
2. `ProjectUpdate` — убрать `client_id`
3. `ProjectOut` — `client_id: int | None = None`, `client: UserBrief | None = None`

**Файлы:**
- [`backend/app/schemas/project.py`](backend/app/schemas/project.py)

**Правки:** удалить поле и валидаторы client из Create/Update.

**Итог:** OpenAPI `/docs` — POST `/api/projects` без `client_id`.

---

### Шаг 1.4 — API projects: список и доступ

> ✅ Выполнено | Тесты: 19/19 | Дата: 2026-06-27

**Цель:** все авторизованные видят все проекты; сортировка настраивается.

**Задачи:**
1. `list_projects`: убрать блок `if client: query.where(client_id==...)`
2. Добавить query params: `sort_by: Literal["name","created_at"] = "created_at"`, `sort_order: Literal["asc","desc"] = "desc"`
3. `order_by` динамический
4. `_check_project_access`: убрать сравнение `client_id` (оставить пустую проверку или удалить)

**Файлы:**
- [`backend/app/api/projects.py`](backend/app/api/projects.py) — строки 41–43, 56–58, 67–68

**Правки:**
```python
# list_projects
sort_col = Project.name if sort_by == "name" else Project.created_at
order = sort_col.asc() if sort_order == "asc" else sort_col.desc()
query = query.order_by(order)
```

**Итог:**
- client и admin получают одинаковый список проектов
- `GET /api/projects?sort_by=name&sort_order=asc` работает

---

### Шаг 1.5 — API projects: CRUD для client

> ✅ Выполнено | Тесты: 19/19 | Дата: 2026-06-27

**Цель:** client может создавать, редактировать, удалять проекты (как admin).

**Задачи:**
1. `create_project`: заменить `Depends(require_admin)` на `get_current_user`; убрать валидацию client user; не писать `client_id`
2. `update_project`: снять `require_admin`
3. `delete_project`: снять `require_admin`; правило 409 при наличии заявок — оставить
4. Убрать `selectinload(Project.client)` если client не отдаётся

**Файлы:**
- [`backend/app/api/projects.py`](backend/app/api/projects.py) — строки 78–100, 135–189

**Правки:**
- Удалить блок поиска `client = await db.get(User, data.client_id)`
- `Project(name=..., description=..., status=...)` без client_id

**Итог:**
- client может POST/PUT/DELETE `/api/projects`
- удаление с заявками → 409

---

### Шаг 1.6 — Убрать client_id проверки в остальных API

> ✅ Выполнено | Тесты: 19/19 | Дата: 2026-06-27

**Цель:** доступ к проекту не зависит от владельца.

**Задачи:** в каждом файле заменить:
```python
if current_user.role == "client" and project.client_id != current_user.id:
    raise HTTPException(403, ...)
```
на вызов `ensure_project_access` или просто убрать блок.

**Файлы и строки:**
| Файл | Функция |
|------|---------|
| [`backend/app/api/project_items.py`](backend/app/api/project_items.py) | `_check_access` ~41–43 |
| [`backend/app/api/project_item_requirements.py`](backend/app/api/project_item_requirements.py) | `_check_access` ~39 |
| [`backend/app/api/payment_requests.py`](backend/app/api/payment_requests.py) | `_check_access` ~41 |
| [`backend/app/api/payment_request_comments.py`](backend/app/api/payment_request_comments.py) | ~38 |
| [`backend/app/api/payment_request_attachments.py`](backend/app/api/payment_request_attachments.py) | добавить auth check |
| [`backend/app/api/payments.py`](backend/app/api/payments.py) | `_get_request_with_access` ~58, zip ~95 |
| [`backend/app/api/files.py`](backend/app/api/files.py) | ~32, 45 |

**Итог:** client открывает любой проект по ID без 403.

---

### Шаг 1.7 — users.py и notification_service

> ✅ Выполнено | Тесты: 19/19 | Дата: 2026-06-27

**Цель:** побочные зависимости от `client_id` не ломают систему.

**Задачи:**
1. [`backend/app/api/users.py`](backend/app/api/users.py): удаление user — убрать проверку «есть проекты с client_id=user.id» или заменить на другую логику
2. [`backend/app/api/payments.py`](backend/app/api/payments.py) `_get_client_chat_id`: уведомлять `payment.created_by` через его `telegram_chat_id` вместо join через project.client

**Файлы:**
- `backend/app/api/users.py`
- `backend/app/api/payments.py` — функция `_get_client_chat_id` ~74–81
- `backend/app/services/notification_service.py` — при необходимости

**Итог:** уведомления в Telegram доходят до автора платежа; удаление user не блокируется из-за проектов.

---

### Шаг 1.8 — Frontend types: Project

> ✅ Выполнено | Тесты: tsc OK, 19/19 backend | Дата: 2026-06-27

**Цель:** TypeScript соответствует новому API.

**Задачи:**
1. `Project`: убрать обязательные `client_id`, `client` (сделать optional или удалить)
2. `ProjectCreate` / `ProjectUpdate`: убрать `client_id`

**Файлы:**
- [`frontend/src/types/index.ts`](frontend/src/types/index.ts) — строки 114–137

**Итог:** `tsc --noEmit` не ругается на типы проекта (после правки зависимых компонентов).

---

### Шаг 1.9 — Frontend API: listProjects + сортировка

> ✅ Выполнено | Тесты: tsc OK | Дата: 2026-06-27

**Цель:** фронт передаёт параметры сортировки на backend.

**Задачи:**
1. Расширить params в `listProjects`: `sort_by?: 'name' | 'created_at'`, `sort_order?: 'asc' | 'desc'`
2. Пробросить в query string

**Файлы:**
- [`frontend/src/api/projects.ts`](frontend/src/api/projects.ts) — строки 10–22

**Правки:**
```typescript
params: {
  status: params?.status,
  sort_by: params?.sortBy,
  sort_order: params?.sortOrder,
  ...
}
```

**Итог:** API-клиент умеет запрашивать сортировку.

---

### Шаг 1.10 — ProjectFormModal: убрать клиента

> ✅ Выполнено | Тесты: tsc OK | Дата: 2026-06-27

**Цель:** форма создания/редактирования без выбора клиента.

**Задачи:**
1. Удалить `useQuery(['users'])`, `clientOptions`, `Form.Item client_id`
2. Убрать `client_id` из `handleSave` / `ProjectUpdate`
3. Показывать `status` при create тоже (опционально — только при edit, как сейчас)

**Файлы:**
- [`frontend/src/components/Projects/ProjectFormModal.tsx`](frontend/src/components/Projects/ProjectFormModal.tsx) — строки 19–28, 90–101, 50

**Итог:** модалка содержит только название, описание, статус (при edit).

---

### Шаг 1.11 — ProjectCard: компактная плитка

> ✅ Выполнено | Тесты: tsc OK | Дата: 2026-06-27

**Цель:** убрать клиента и дату создания с карточки.

**Задачи:**
1. Удалить строки 99–104 (`Клиент:`, `Создан:`)

**Файлы:**
- [`frontend/src/components/Projects/ProjectCard.tsx`](frontend/src/components/Projects/ProjectCard.tsx)

**Итог:** карточка показывает №, статус, название, описание; визуально компактнее.

---

### Шаг 1.12 — ProjectsPage: CRUD для client + сортировка + localStorage

> ✅ Выполнено | Тесты: tsc OK | Дата: 2026-06-27

**Цель:** client управляет проектами; сортировка сохраняется после F5.

**Задачи:**
1. Кнопка «Создать проект» — убрать `{isAdmin && ...}`
2. `onEdit`/`onDelete` — передавать всем
3. `ProjectFormModal` — убрать обёртку `isAdmin &&`
4. Добавить `Select` сортировки: 4 варианта (имя ↑↓, дата ↑↓)
5. `localStorage` ключ `ibra_projects_sort` = `{ sortBy, sortOrder }`
6. При mount: читать localStorage → state → `listProjects`
7. При смене сортировки: писать localStorage

**Файлы:**
- [`frontend/src/pages/ProjectsPage.tsx`](frontend/src/pages/ProjectsPage.tsx) — строки 65–73, 105–111, 117–127

**Итог:**
- client создаёт/редактирует/удаляет проекты
- после F5 сортировка не сбрасывается
- закрытые проекты по-прежнему фильтруются через Radio (раздел 9 доработает default)

---

### Шаг 1.13 — ProjectDetailPage: шапка без клиента

> ✅ Выполнено | Тесты: tsc OK | Дата: 2026-06-27

**Цель:** детальная страница не показывает привязку к клиенту; client может edit/delete.

**Задачи:**
1. Удалить блок «Клиент:» (строки 194–196); опционально оставить или убрать «Создан:» (чек-лист — только с карточки; в шапке можно убрать оба)
2. Кнопки Edit/Delete — убрать `isAdmin` guard (строки ~155–179)
3. `ProjectFormModal` — показывать client тоже (строки 252–263, 306–317)

**Файлы:**
- [`frontend/src/pages/ProjectDetailPage.tsx`](frontend/src/pages/ProjectDetailPage.tsx)

**Итог:** client редактирует проект со страницы детали; нет строки «Клиент: Анвар».

---

**ИТОГ РАЗДЕЛА 1:** проекты общие для всех; UI без клиента; сортировка с persistence; client = admin по CRUD проектов.

---

## РАЗДЕЛ 2. Роль клиента — расширение прав

### Шаг 2.1 — Миграция project_items: новые поля

> ✅ Выполнено | Тесты: 30/30 | Дата: 2026-06-27

**Цель:** поддержать общий доступ, автора и порядок позиций.

**Задачи:**
1. Создать `008_checklist_project_items.py` (или объединить с 007)
2. Добавить колонки:
   - `created_by INT NOT NULL REFERENCES users(id)`
   - `shared_access BOOLEAN NOT NULL DEFAULT false`
   - `sort_order INT NOT NULL DEFAULT 0`
3. Data migration: `UPDATE project_items SET created_by = (SELECT id FROM users WHERE role='admin' LIMIT 1)`
4. Data migration: проставить `sort_order` = row_number по `id` внутри каждого `project_id`
5. Индекс `idx_project_items_sort ON (project_id, sort_order)`

**Файлы:**
- **Создать:** `backend/alembic/versions/008_checklist_project_items.py`

**Итог:** таблица `project_items` имеет 3 новых поля; существующие записи валидны.

---

### Шаг 2.2 — Модель и схемы ProjectItem

> ✅ Выполнено | Тесты: 30/30 | Дата: 2026-06-27

**Цель:** API отдаёт `shared_access`, `created_by`, `sort_order`.

**Задачи:**
1. Модель: 3 новых поля
2. `ProjectItemClientOut` / `ProjectItemAdminOut`: добавить `shared_access: bool`, `can_edit: bool` (computed)
3. `ProjectItemCreate`: `cost_price` optional для admin; client не передаёт
4. `ProjectItemUpdate`: admin может передать `shared_access`

**Файлы:**
- [`backend/app/models/project_item.py`](backend/app/models/project_item.py)
- [`backend/app/schemas/project_item.py`](backend/app/schemas/project_item.py)
- [`backend/app/models/__init__.py`](backend/app/models/__init__.py) — если нужен export

**Итог:** схемы отражают новую модель; OpenAPI обновлён.

---

### Шаг 2.3 — API project_items: list + create

> ✅ Выполнено | Тесты: 30/30 | Дата: 2026-06-27

**Цель:** client создаёт позиции; порядок по `sort_order`.

**Задачи:**
1. `list_items`: `ORDER BY sort_order ASC, id ASC`
2. `create_item`: снять `require_admin`
3. При create:
   - `created_by = current_user.id`
   - `shared_access = default_shared_access_for_creator(role)`
   - client: игнорировать `cost_price` из запроса → `cost_price = price`
   - admin: `cost_price` из запроса или NULL
   - `sort_order = max(existing) + 1`
4. В ответе: `can_edit` для client

**Файлы:**
- [`backend/app/api/project_items.py`](backend/app/api/project_items.py) — create ~200+, list

**Итог:**
- client POST item → `shared_access=true`, `cost_price=price`
- admin POST item → `shared_access=false`

---

### Шаг 2.4 — API project_items: update + delete

> ✅ Выполнено | Тесты: 30/30 | Дата: 2026-06-27

**Цель:** client меняет только «свои» открытые позиции.

**Задачи:**
1. `update_item`: проверка `can_edit_item`; client не может менять `shared_access` (только admin)
2. `delete_item`: `can_edit_item`
3. admin: Switch `shared_access` через update

**Файлы:**
- [`backend/app/api/project_items.py`](backend/app/api/project_items.py)

**Итог:** client PUT closed item → 403; PUT open item → 200.

---

### Шаг 2.5 — API project_items: move-up / move-down

> ✅ Выполнено | Тесты: 30/30 | Дата: 2026-06-27

**Цель:** ручная перестановка (раздел 6, backend-часть).

**Задачи:**
1. `POST /api/projects/{pid}/items/{id}/move-up`
2. `POST /api/projects/{pid}/items/{id}/move-down`
3. Логика: найти соседа с `sort_order ± 1`, swap значений
4. Права: `can_edit_item` для обеих позиций (или admin)

**Файлы:**
- [`backend/app/api/project_items.py`](backend/app/api/project_items.py)

**Итог:** два новых endpoint; первая позиция move-up → 400; последняя move-down → 400.

---

### Шаг 2.6 — API project_item_requirements: права client

> ✅ Выполнено | Тесты: 30/30 | Дата: 2026-06-27

**Цель:** требования к позиции — в рамках доступа к позиции.

**Задачи:**
1. add/delete requirement: client если `can_edit_item`

**Файлы:**
- [`backend/app/api/project_item_requirements.py`](backend/app/api/project_item_requirements.py)

**Итог:** client добавляет требования только к открытым позициям.

---

### Шаг 2.7 — API payment_requests: CRUD для client

**Цель:** client создаёт заявки всегда; edit/delete по доступу к позициям.

**Задачи:**
1. `create_payment_request`: снять `require_admin`
2. `update_payment_request` / `delete`: загрузить items заявки → `can_edit_payment_request`
3. `list`: добавить поле `paid_amount = total_amount - remaining_amount`

**Файлы:**
- [`backend/app/api/payment_requests.py`](backend/app/api/payment_requests.py)
- [`backend/app/schemas/payment_request.py`](backend/app/schemas/payment_request.py) — `PaymentRequestListOut.paid_amount`

**Итог:** client создаёт заявку на closed items; не удаляет её без доступа ко всем позициям.

---

### Шаг 2.8 — API payments: delete rules

**Цель:** client удаляет платёж только при доступе ко всем позициям заявки.

**Задачи:**
1. `delete_payment`: заменить проверку `status != confirmed` на `can_delete_payment`
2. Загрузить `PaymentRequestItem` → `ProjectItem` для проверки `shared_access`

**Файлы:**
- [`backend/app/api/payments.py`](backend/app/api/payments.py) — delete ~529–540

**Итог:** client не удаляет платёж по заявке с closed item; admin удаляет любой.

---

### Шаг 2.9 — API attachments: upload для client

**Цель:** client может добавлять файлы к существующей заявке (чек-лист п.4).

**Задачи:**
1. `upload_attachment`: заменить `require_admin` на `get_current_user` (любой авторизованный с доступом к проекту)
2. `delete_attachment`: admin или `can_edit_payment_request`

**Файлы:**
- [`backend/app/api/payment_request_attachments.py`](backend/app/api/payment_request_attachments.py) — строка 41

**Итог:** client POST attachment к существующей заявке → 201.

---

### Шаг 2.10 — Frontend types: ProjectItem

**Цель:** TS знает о `shared_access`, optional `cost_price`.

**Задачи:**
1. `ProjectItem`: добавить `shared_access: boolean`, `can_edit?: boolean`
2. `ProjectItemCreate`: `cost_price?` optional
3. `PaymentRequestList`: добавить `paid_amount: string`

**Файлы:**
- [`frontend/src/types/index.ts`](frontend/src/types/index.ts) — строки 166–201, тип заявок

**Итог:** типы синхронизированы с backend.

---

### Шаг 2.11 — ItemsPanel: UI прав client

**Цель:** client видит кнопки добавления; admin видит Switch доступа.

**Задачи:**
1. `canEdit = isAdmin || item.shared_access` (или `item.can_edit` с API)
2. «Добавить позицию» — всем
3. Import Excel — только admin
4. Колонка admin: `Switch shared_access` → `updateItem`
5. Кнопки delete в таблице — по `canEdit`

**Файлы:**
- [`frontend/src/components/ProjectDetail/ItemsPanel.tsx`](frontend/src/components/ProjectDetail/ItemsPanel.tsx)

**Итог:** client добавляет позиции; не удаляет closed; admin переключает доступ.

---

### Шаг 2.12 — ItemFormModal: без cost_price для client

**Цель:** client не видит себестоимость при создании/редактировании.

**Задачи:**
1. `{isAdmin && <Form.Item name="cost_price" .../>}`
2. Admin: `cost_price` не required
3. Admin: `Form.Item name="shared_access"` Switch

**Файлы:**
- [`frontend/src/components/ProjectDetail/ItemFormModal.tsx`](frontend/src/components/ProjectDetail/ItemFormModal.tsx) — строки 121–127

**Итог:** форма client — 5 полей без себестоимости.

---

### Шаг 2.13 — ItemDetailDrawer: права и скрытие cost

**Цель:** drawer соответствует правам; нет прибыли/себестоимости у client.

**Задачи:**
1. `showEdit = isAdmin || item.shared_access`
2. Убрать блоки cost/profit для client (строки 146–150, 202–208)
3. Admin: cost_price, без profit (раздел 7)

**Файлы:**
- [`frontend/src/components/ProjectDetail/ItemDetailDrawer.tsx`](frontend/src/components/ProjectDetail/ItemDetailDrawer.tsx)

**Итог:** client открывает closed item — только просмотр, без кнопок edit.

---

### Шаг 2.14 — PaymentRequestsPanel: create/delete для client

**Цель:** кнопки заявок доступны по правилам.

**Задачи:**
1. «Создать заявку» — убрать `isAdmin &&` (строка 101)
2. `PaymentRequestFormModal` — открывать всем
3. Delete на карточке — показывать client если `can_edit` (нужно поле с API или вычислять на фронте по items — лучше `can_edit: bool` в `PaymentRequestListOut`)

**Файлы:**
- [`frontend/src/components/ProjectDetail/PaymentRequestsPanel.tsx`](frontend/src/components/ProjectDetail/PaymentRequestsPanel.tsx)
- `backend/app/schemas/payment_request.py` — добавить `can_edit: bool`

**Итог:** client создаёт заявки; delete только при полном доступе к позициям.

---

### Шаг 2.15 — PaymentRequestDetailModal: права edit/delete

**Цель:** модалка детали отражает права client на заявку и платежи.

**Задачи:**
1. Edit/delete заявки — `req.can_edit` или аналог
2. Пересчитать `canDelete` платежа без `status !== 'confirmed'` (после шага 4.1)
3. Добавить upload вложений (шаг 4.3)

**Файлы:**
- [`frontend/src/components/ProjectDetail/PaymentRequestDetailModal.tsx`](frontend/src/components/ProjectDetail/PaymentRequestDetailModal.tsx)

**Итог:** UI согласован с backend permissions.

---

### Шаг 2.16 — PaymentRequestFormModal: доступ client

**Цель:** client создаёт заявку, выбирая любые позиции (в т.ч. closed).

**Задачи:**
1. Убедиться, что модалка не обёрнута в `isAdmin`
2. Список позиций — все items проекта (readonly closed — можно выбирать для заявки)

**Файлы:**
- [`frontend/src/components/ProjectDetail/PaymentRequestFormModal.tsx`](frontend/src/components/ProjectDetail/PaymentRequestFormModal.tsx)

**Итог:** client создаёт заявку на closed номенклатуру — OK.

---

### Шаг 2.17 — Поставщики: client видит при создании item

**Цель:** client выбирает поставщика в форме позиции, но не имеет доступа к `/database`.

**Задачи:**
1. Проверить: `ItemFormModal` загружает suppliers через API — какой endpoint?
2. Если `GET /api/suppliers` только admin — создать `GET /api/suppliers/brief` для всех авторизованных (id + name)
3. [`backend/app/api/suppliers.py`](backend/app/api/suppliers.py) — новый readonly endpoint

**Файлы:**
- `backend/app/api/suppliers.py`
- `frontend` — api/suppliers если используется в ItemFormModal

**Итог:** client выбирает поставщика в форме; `/database/suppliers` по-прежнему admin-only.

---

### Шаг 2.18 — AdminRoute: без изменений

**Цель:** подтвердить, что client не попадает в БД.

**Задачи:** smoke-test — client → `/database` → redirect.

**Файлы:**
- [`frontend/src/components/Auth/AdminRoute.tsx`](frontend/src/components/Auth/AdminRoute.tsx) — без правок

**Итог:** раздел 2 закрыт; client расширен, БД закрыта.

---

**ИТОГ РАЗДЕЛА 2:** полная матрица прав client; `shared_access` работает end-to-end.

---

## РАЗДЕЛ 3. Себестоимость

### Шаг 3.1 — Миграция: cost_price nullable

**Цель:** admin может не заполнять себестоимость.

**Задачи:**
1. `ALTER TABLE project_items ALTER COLUMN cost_price DROP NOT NULL`
2. Constraint `cost_price >= 0` — оставить (NULL проходит)

**Файлы:**
- `backend/alembic/versions/008_checklist_project_items.py` (добавить в ту же миграцию)

**Итог:** `cost_price` может быть NULL в БД.

---

### Шаг 3.2 — Backend: effective_cost_price в расчётах

**Цель:** итоги при NULL cost = расчёт по цене товара.

**Задачи:**
1. `get_project_summary`: `COALESCE(cost_price, price)` вместо `cost_price`
2. Не отдавать `profit` (раздел 7)
3. `export_service.py`: та же формула в агрегатах
4. `import_service.py`: `cost_price` необязателен в Excel

**Файлы:**
- [`backend/app/api/projects.py`](backend/app/api/projects.py) — ~233–297
- [`backend/app/services/export_service.py`](backend/app/services/export_service.py) — ~96–115, 179–193
- [`backend/app/services/import_service.py`](backend/app/services/import_service.py) — ~28, 167

**Итог:** summary `total` = sum(price * qty) независимо от заполнения cost.

---

### Шаг 3.3 — Frontend ItemFormModal: optional cost

**Цель:** admin не обязан вводить себестоимость.

**Задачи:**
1. Убрать `rules={[{ required: true }]}` у cost_price
2. Placeholder: «Не указана — равна цене»

**Файлы:**
- [`frontend/src/components/ProjectDetail/ItemFormModal.tsx`](frontend/src/components/ProjectDetail/ItemFormModal.tsx)

**Итог:** admin сохраняет item без cost_price.

---

### Шаг 3.4 — Frontend ItemDetailDrawer: отображение NULL cost

**Цель:** admin видит «—» или подпись «= цена» при пустой себестоимости.

**Задачи:**
1. `costPrice === null` → Text «Не указана (итог по цене)»

**Файлы:**
- [`frontend/src/components/ProjectDetail/ItemDetailDrawer.tsx`](frontend/src/components/ProjectDetail/ItemDetailDrawer.tsx) — строки 84–93

**Итог:** admin понимает, что cost не задан.

---

**ИТОГ РАЗДЕЛА 3:** себестоимость опциональна; client никогда не видит поле.

---

## РАЗДЕЛ 4. Оплаты / платежи

### Шаг 4.1 — Убрать approval workflow (backend)

**Цель:** платёж сразу учитывается в остатке; нет pending/rejected.

**Задачи:**
1. `add_payment`: `new_status = "confirmed"` всегда; `confirmed_at`, `confirmed_by` всегда заполнять
2. Убрать ветку `notify_payment_pending`; для всех — `notify_payment_added`
3. Overpay check: `status.in_(("confirmed",))` или все платежи
4. Удалить или пометить deprecated: `confirm_payment`, `reject_payment`
5. Миграция `009_payments_simplify.py`: `UPDATE payments SET status='confirmed' WHERE status IN ('pending','rejected')`

**Файлы:**
- [`backend/app/api/payments.py`](backend/app/api/payments.py) — строки 298–375, 380+
- **Создать:** `backend/alembic/versions/009_payments_simplify.py`
- [`backend/app/services/notification_service.py`](backend/app/services/notification_service.py) — `notify_payment_pending` можно оставить мёртвым

**Итог:** client создаёт платёж → сразу в `remaining_amount`; нет pending в БД.

---

### Шаг 4.2 — Убрать approval workflow (frontend)

**Цель:** UI без кнопок подтверждения и бейджей pending.

**Задачи:**
1. Удалить `confirmPayment`, `rejectPayment` из [`frontend/src/api/payments.ts`](frontend/src/api/payments.ts) — строки 29–46
2. `PaymentRequestDetailModal`: убрать кнопки Confirm/Reject, Tag pending/rejected
3. `canDelete`: `isAdmin || (isOwner && allItemsAccessible)` — без проверки status
4. [`frontend/src/i18n/ru.ts`](frontend/src/i18n/ru.ts): удалить `pendingNote`, `rejectedNote`, `confirmedNote` или оставить неиспользуемыми

**Файлы:**
- `frontend/src/api/payments.ts`
- `frontend/src/components/ProjectDetail/PaymentRequestDetailModal.tsx`
- `frontend/src/i18n/ru.ts`

**Итог:** в UI нет следов workflow подтверждения.

---

### Шаг 4.3 — PATCH payment_date (backend)

**Цель:** менять дату оплаты без удаления платежа.

**Задачи:**
1. `PATCH /api/payment-requests/{req_id}/payments/{pay_id}`
2. Body: `{ "payment_date": "2025-01-15" | null }`
3. Права: admin или `payment.created_by == current_user.id`
4. Схема `PaymentUpdate` в [`backend/app/schemas/payment.py`](backend/app/schemas/payment.py)

**Файлы:**
- `backend/app/api/payments.py`
- `backend/app/schemas/payment.py`

**Итог:** PATCH меняет дату; audit log optional.

---

### Шаг 4.4 — PATCH payment_date (frontend)

**Цель:** inline редактирование даты в модалке заявки.

**Задачи:**
1. `updatePayment(reqId, payId, { payment_date })` в `payments.ts`
2. `DatePicker` на каждой строке платежа (admin или owner)
3. **Стиль:** убрать `type="secondary"`, `fontSize: 11` серый → `color: token.colorText`
4. При создании: обернуть DatePicker в `Form.Item label="Дата оплаты"`

**Файлы:**
- `frontend/src/api/payments.ts`
- `frontend/src/components/ProjectDetail/PaymentRequestDetailModal.tsx` — ~960–971, ~1024–1032

**Итог:** дата читаема в тёмной теме; редактируется кликом.

---

### Шаг 4.5 — Вложения к существующей заявке (frontend)

**Цель:** догрузка файлов без пересоздания заявки.

**Задачи:**
1. В секции «Вложения» — кнопка «Добавить файл» если `attachments.length < 3`
2. `Upload beforeUpload` → `uploadAttachment(projectId, reqId, file)` → refresh
3. Счётчик `(n/3)` в заголовке секции
4. Показывать секцию вложений client всегда (не только когда есть файлы)

**Файлы:**
- `frontend/src/components/ProjectDetail/PaymentRequestDetailModal.tsx` — ~774–828

**Итог:** client добавляет 2-й/3-й файл к старой заявке.

---

### Шаг 4.6 — Столбец «Фактически оплачено»

**Цель:** в списке заявок видна сумма confirmed-платежей.

**Задачи:**
1. Backend: `paid_amount` в list (шаг 2.7)
2. Frontend: в карточке/таблице явная строка «Фактически оплачено: {fmt(paid_amount)}»
3. Опционально: перейти на `Table` с колонками: Номенклатура | Сумма | Фактически оплачено | Остаток | Дата | Статус

**Файлы:**
- `frontend/src/components/ProjectDetail/PaymentRequestsPanel.tsx` — блок ~192–206

**Итог:** три суммы видны: всего / фактически / остаток.

---

**ИТОГ РАЗДЕЛА 4:** платежи без модерации; дата редактируется; вложения догружаются; новый столбец.

---

## РАЗДЕЛ 5. Фильтры и сортировка заявок

### Шаг 5.1 — Backend: query params для list payment_requests

**Цель:** серверная фильтрация при большом числе заявок.

**Задачи:**
1. Params: `sort_by=created_at|total_amount|item_name`, `sort_order=asc|desc`
2. `status_filter=all|paid|unpaid` (paid = remaining <= 0)
3. `date_from`, `date_to` (по `created_at`)
4. `item_ids=1,2,3` — заявки, содержащие хотя бы одну из позиций
5. Default sort: `created_at desc`

**Файлы:**
- [`backend/app/api/payment_requests.py`](backend/app/api/payment_requests.py) — `list_payment_requests`

**Итог:** `GET .../payment-requests?sort_by=total_amount&status_filter=unpaid` работает.

---

### Шаг 5.2 — Frontend API: params в listPaymentRequests

**Цель:** клиент передаёт фильтры на сервер.

**Задачи:**
1. Интерфейс `PaymentRequestListParams`
2. Проброс в `client.get`

**Файлы:**
- [`frontend/src/api/paymentRequests.ts`](frontend/src/api/paymentRequests.ts) — строки 10–14

**Итог:** API-функция принимает фильтры.

---

### Шаг 5.3 — UI: панель фильтров над заявками

**Цель:** гибридный фильтр из чек-листа.

**Задачи:**
1. **Сверху:** `RangePicker` дата; `Select` статус (все/оплачено/не оплачено)
2. **Рядом с позициями:** `Select mode="multiple"` — позиции в порядке `sort_order` из `listItems`
3. **Сортировка:** Select (дата / сумма / номенклатура) + asc/desc; default дата desc
4. Убрать старую сортировку по priority (строки 119–130)
5. **НЕ делать:** фильтр по сумме от–до, частичная/полная оплата

**Файлы:**
- [`frontend/src/components/ProjectDetail/PaymentRequestsPanel.tsx`](frontend/src/components/ProjectDetail/PaymentRequestsPanel.tsx)

**Итог:** пользователь фильтрует заявки по дате, статусу, номенклатуре.

---

### Шаг 5.4 — localStorage для фильтров заявок

**Цель:** фильтры не сбрасываются при обновлении страницы проекта.

**Задачи:**
1. Ключ `ibra_pr_filters_{projectId}`
2. Сохранять: date range, status, item_ids, sort
3. Restore on mount

**Файлы:**
- `PaymentRequestsPanel.tsx`

**Итог:** F5 на странице проекта — фильтры на месте.

---

### Шаг 5.5 — Синхронизация порядка позиций в фильтре

**Цель:** выпадающий список номенклатуры = ручной порядок.

**Задачи:**
1. `listItems` уже сортируется по `sort_order` (шаг 2.3)
2. Options в Select строить из `items` в том же порядке

**Итог:** порядок в фильтре = порядок в таблице номенклатуры.

---

**ИТОГ РАЗДЕЛА 5:** фильтрация и сортировка заявок по чек-листу.

---

## РАЗДЕЛ 6. Ручное упорядочивание номенклатуры

### Шаг 6.1 — Backend move endpoints (если не сделано в 2.5)

**Цель:** API для ↑↓.

**Итог:** endpoints работают.

---

### Шаг 6.2 — Frontend API moveItemUp/Down

**Задачи:**
```typescript
export async function moveItemUp(projectId, itemId) {
  await client.post(`/projects/${projectId}/items/${itemId}/move-up`);
}
```

**Файлы:**
- [`frontend/src/api/projectItems.ts`](frontend/src/api/projectItems.ts)

**Итог:** функции экспортированы.

---

### Шаг 6.3 — ItemsPanel: кнопки ↑↓

**Задачи:**
1. Колонка «Порядок» с `ArrowUpOutlined` / `ArrowDownOutlined`
2. disabled на index 0 / last
3. `onSuccess` → invalidate `project-items`, `payment-requests` (фильтр)

**Файлы:**
- [`frontend/src/components/ProjectDetail/ItemsPanel.tsx`](frontend/src/components/ProjectDetail/ItemsPanel.tsx)

**Итог:** admin и client (с доступом) меняют порядок.

---

### Шаг 6.4 — create_item: sort_order = max + 1

**Цель:** новые позиции в конец списка.

**Итог:** после добавления item он внизу.

---

**ИТОГ РАЗДЕЛА 6:** drag-free reorder через кнопки.

---

## РАЗДЕЛ 7. Сводка — убрать прибыль

### Шаг 7.1 — Backend schema: убрать profit

**Файлы:** [`backend/app/schemas/project.py`](backend/app/schemas/project.py) — `CurrencySummary`

**Итог:** API summary без поля profit.

---

### Шаг 7.2 — Backend get_project_summary

**Задачи:** удалить вычисление и присвоение `profit_val`

**Файлы:** [`backend/app/api/projects.py`](backend/app/api/projects.py) — ~233–297

**Итог:** response currencies без profit.

---

### Шаг 7.3 — Frontend SummaryRow

**Задачи:** удалить блок `isAdmin && summary.profit` (строки 86–92)

**Файлы:** [`frontend/src/components/ProjectDetail/ItemsPanel.tsx`](frontend/src/components/ProjectDetail/ItemsPanel.tsx)

**Итог:** сводка: итого, выставлено, оплачено, остатки, комиссия — без прибыли.

---

### Шаг 7.4 — ItemDetailDrawer: убрать прибыль у admin

**Файлы:** [`frontend/src/components/ProjectDetail/ItemDetailDrawer.tsx`](frontend/src/components/ProjectDetail/ItemDetailDrawer.tsx) — ~202–208

**Итог:** нет строки «Прибыль» нигде.

---

### Шаг 7.5 — export_service: убрать profit из Excel

**Задачи:**
1. Лист «Сводка» — без колонки profit
2. Лист «Позиции» — убрать колонку profit; cost_price оставить для admin export

**Файлы:** [`backend/app/services/export_service.py`](backend/app/services/export_service.py)

**Итог:** Excel без прибыли.

---

### Шаг 7.6 — i18n cleanup

**Файлы:** [`frontend/src/i18n/ru.ts`](frontend/src/i18n/ru.ts) — ключ `profit`

**Итог:** нет мёртвых строк.

---

**ИТОГ РАЗДЕЛА 7:** прибыль нигде не показывается и не считается.

---

## РАЗДЕЛ 8. Заметки по проекту

### Шаг 8.1 — Миграция project_notes

**Файлы:** **Создать** `backend/alembic/versions/010_project_notes.py`

**SQL:** таблица `project_notes` (id, project_id, content, visibility, created_by, created_at, updated_at)

**Итог:** таблица создана.

---

### Шаг 8.2 — Модель ProjectNote

**Файлы:**
- **Создать** [`backend/app/models/project_note.py`](backend/app/models/project_note.py)
- [`backend/app/models/__init__.py`](backend/app/models/__init__.py)

**Итог:** ORM модель + relationship в Project (optional).

---

### Шаг 8.3 — Схемы ProjectNote

**Файлы:** **Создать** [`backend/app/schemas/project_note.py`](backend/app/schemas/project_note.py)

- `ProjectNoteCreate`: content, visibility: 'private'|'shared'
- `ProjectNoteOut`: id, content, visibility, created_by, author_name, created_at, can_edit

**Итог:** Pydantic модели готовы.

---

### Шаг 8.4 — API project_notes

**Файлы:** **Создать** [`backend/app/api/project_notes.py`](backend/app/api/project_notes.py)

| Method | Path | Правила |
|--------|------|---------|
| GET | `/api/projects/{id}/notes` | private: автор+admin; shared: все |
| POST | `/api/projects/{id}/notes` | любой авторизованный |
| PUT | `/api/projects/{id}/notes/{nid}` | автор или admin |
| DELETE | `/api/projects/{id}/notes/{nid}` | автор или admin |

**Подключить в** [`backend/main.py`](backend/main.py)

**Итог:** CRUD заметок работает в Swagger.

---

### Шаг 8.5 — Frontend types + API

**Файлы:**
- **Создать** [`frontend/src/api/projectNotes.ts`](frontend/src/api/projectNotes.ts)
- [`frontend/src/types/index.ts`](frontend/src/types/index.ts) — `ProjectNote`

**Итог:** клиент API готов.

---

### Шаг 8.6 — Компонент NotesPanel

**Файлы:** **Создать** [`frontend/src/components/ProjectDetail/NotesPanel.tsx`](frontend/src/components/ProjectDetail/NotesPanel.tsx)

**UI:**
- List с Tag «Личная» (default) / «Общая»
- TextArea + Radio.Group visibility
- Edit inline / Delete Popconfirm
- Empty state

**Итог:** изолированный компонент заметок.

---

### Шаг 8.7 — Интеграция в ProjectDetailPage

**Задачи:**
1. **Mobile:** добавить Tab «Заметки» в `Tabs` (строки 227–242)
2. **Desktop:** вариант A — третья колонка 20% справа; вариант B — collapsible panel под header. Рекомендация: **Tab на mobile + боковая панель 25% на desktop** между items и payments или под split.

**Файлы:** [`frontend/src/pages/ProjectDetailPage.tsx`](frontend/src/pages/ProjectDetailPage.tsx)

**Итог:** заметки доступны на странице проекта.

---

### Шаг 8.8 — Аудит заметок (опционально)

**Задачи:** `audit_service.log_action` при create/update/delete note.

**Файлы:** `project_notes.py`, `audit_service.py`

**Итог:** действия с заметками в audit log (желательно, не блокер).

---

**ИТОГ РАЗДЕЛА 8:** заметки с private/shared visibility.

---

## РАЗДЕЛ 9. Фильтр проектов по умолчанию «В работе»

### Шаг 9.1 — initialStatus = active

**Задачи:**
1. `initialStatus()`: если нет `?status` → return `'active'` (было `'all'`, строка 22)

**Файлы:** [`frontend/src/pages/ProjectsPage.tsx`](frontend/src/pages/ProjectsPage.tsx)

**Итог:** первый заход — только активные проекты.

---

### Шаг 9.2 — Порядок кнопок Radio

**Задачи:** options порядок: В работе → Закрытые → Все (строки 90–94)

**Итог:** UI соответствует чек-листу.

---

### Шаг 9.3 — URL sync при default active

**Задачи:**
1. `useEffect` on mount: если URL без params → `setSearchParams({ status: 'active' })`
2. `listProjects({ status: 'active' })` при default

**Итог:** URL `?status=active`; закрытые не мешают при входе.

---

**ИТОГ РАЗДЕЛА 9:** список проектов открывается на «В работе».

---

## ФАЗА 10. Финализация

### Шаг 10.1 — Чеклист ручного тестирования

**Цель:** убедиться, что все 9 разделов работают.

**Сценарии (admin + client):**

| # | Сценарий | Ожидание |
|---|----------|----------|
| 1 | client открывает /projects | видит все проекты, default «В работе» |
| 2 | client создаёт проект | без поля клиента, 201 |
| 3 | client создаёт item | shared_access=true, нет cost в UI |
| 4 | admin создаёт item | shared_access=false |
| 5 | admin выключает shared_access | client не edit item |
| 6 | client создаёт заявку на closed items | OK |
| 7 | client не удаляет заявку с closed items | 403 |
| 8 | client добавляет платёж | сразу confirmed, остаток уменьшается |
| 9 | client не удаляет платёж по closed заявке | кнопки нет / 403 |
| 10 | client добавляет вложение к старой заявке | OK |
| 11 | edit payment_date | сохраняется |
| 12 | фильтры заявок + F5 | сохранены |
| 13 | reorder items | порядок в фильтре меняется |
| 14 | private note | видит только автор+admin |
| 15 | shared note | видят все |
| 16 | сортировка projects + F5 | localStorage OK |

**Итог:** таблица пройдена без критических багов.

---

### Шаг 10.2 — Миграции на prod-копии

**Задачи:**
1. `docker compose exec backend alembic upgrade head`
2. Проверить данные: projects.client_id NULL, items.sort_order, payments confirmed

**Итог:** миграции без ошибок на реальных данных.

---

### Шаг 10.3 — README

**Файлы:** [`README.md`](README.md)

**Правки:**
- Убрать «привязка к клиенту»
- Описать: общие проекты, shared_access, заметки
- Роли: admin (БД) vs client (проекты+номенклатура с флагом)

**Итог:** документация актуальна.

---

### Шаг 10.4 — docker compose build

**Задачи:** `docker compose up --build` — все 5 сервисов healthy.

**Итог:** стек поднимается с нуля.

---

### Шаг 10.5 — Коммиты (рекомендуемая нарезка)

| Коммит | Шаги | Содержание |
|--------|------|------------|
| 1 | 1.1, 2.1, 3.1, 4.1 миграция, 8.1 | `feat(db): миграции чек-листа` |
| 2 | 0.2–0.3, 1.2–1.7, 2.2–2.9 | `feat(backend): общие проекты и права client` |
| 3 | 3.2, 4.1–4.3, 5.1, 7.1–7.2, 8.2–8.4 | `feat(backend): платежи, фильтры, заметки` |
| 4 | 1.8–1.13, 2.10–2.17, 3.3–3.4, 6.2–6.3, 7.3–7.6, 9.1–9.3 | `feat(frontend): проекты, номенклатура, сводка` |
| 5 | 4.2–4.6, 5.2–5.5, 8.5–8.7 | `feat(frontend): заявки, платежи, заметки` |

**Итог:** 5 reviewable коммитов; можно merge в main.

---

## Сводная карта файлов

### Backend — изменяемые
- `backend/app/core/permissions.py` **NEW**
- `backend/app/models/project.py`
- `backend/app/models/project_item.py`
- `backend/app/models/project_note.py` **NEW**
- `backend/app/schemas/project.py`
- `backend/app/schemas/project_item.py`
- `backend/app/schemas/project_note.py` **NEW**
- `backend/app/schemas/payment_request.py`
- `backend/app/schemas/payment.py`
- `backend/app/api/projects.py`
- `backend/app/api/project_items.py`
- `backend/app/api/project_item_requirements.py`
- `backend/app/api/payment_requests.py`
- `backend/app/api/payment_request_attachments.py`
- `backend/app/api/payment_request_comments.py`
- `backend/app/api/payments.py`
- `backend/app/api/files.py`
- `backend/app/api/users.py`
- `backend/app/api/suppliers.py`
- `backend/app/api/project_notes.py` **NEW**
- `backend/app/services/export_service.py`
- `backend/app/services/import_service.py`
- `backend/app/services/notification_service.py`
- `backend/main.py`
- `backend/alembic/versions/007_*.py` **NEW**
- `backend/alembic/versions/008_*.py` **NEW**
- `backend/alembic/versions/009_*.py` **NEW**
- `backend/alembic/versions/010_*.py` **NEW**

### Frontend — изменяемые
- `frontend/src/types/index.ts`
- `frontend/src/api/projects.ts`
- `frontend/src/api/projectItems.ts`
- `frontend/src/api/paymentRequests.ts`
- `frontend/src/api/payments.ts`
- `frontend/src/api/projectNotes.ts` **NEW**
- `frontend/src/pages/ProjectsPage.tsx`
- `frontend/src/pages/ProjectDetailPage.tsx`
- `frontend/src/components/Projects/ProjectFormModal.tsx`
- `frontend/src/components/Projects/ProjectCard.tsx`
- `frontend/src/components/ProjectDetail/ItemsPanel.tsx`
- `frontend/src/components/ProjectDetail/ItemFormModal.tsx`
- `frontend/src/components/ProjectDetail/ItemDetailDrawer.tsx`
- `frontend/src/components/ProjectDetail/PaymentRequestsPanel.tsx`
- `frontend/src/components/ProjectDetail/PaymentRequestDetailModal.tsx`
- `frontend/src/components/ProjectDetail/PaymentRequestFormModal.tsx`
- `frontend/src/components/ProjectDetail/NotesPanel.tsx` **NEW**
- `frontend/src/i18n/ru.ts`

### Без изменений (проверить only)
- `frontend/src/components/Auth/AdminRoute.tsx`
- `frontend/src/pages/DatabasePage.tsx`
- `bot/main.py`

---

## Оценка: ~78 микро-шагов, ~34–50 часов

| Раздел | Шаги | Часы |
|--------|------|------|
| 0 | 0.1–0.3 | 1 |
| 1 | 1.1–1.13 | 5–7 |
| 2 | 2.1–2.18 | 10–14 |
| 3 | 3.1–3.4 | 2–3 |
| 4 | 4.1–4.6 | 5–7 |
| 5 | 5.1–5.5 | 4–6 |
| 6 | 6.1–6.4 | 2–3 |
| 7 | 7.1–7.6 | 1–2 |
| 8 | 8.1–8.8 | 5–7 |
| 9 | 9.1–9.3 | 0.5 |
| 10 | 10.1–10.5 | 4–6 |
