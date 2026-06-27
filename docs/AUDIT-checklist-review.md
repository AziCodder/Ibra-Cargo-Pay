# Аудит кода — Ibra Cargo Pay (чек-лист правок)

> **Read-only журнал.** Заполняется агентом в режиме аудита **после** завершения всех 12 блоков чек-листа.  
> Код и конфиги **не менять** в этом режиме — только дописывать секции в «Прогоны» ниже.

**Инициализировано:** 2026-06-27  
**Статус:** готов к аудиту (12/12 блоков ✅ — режим read-only активен)  
**Ветка:** `feature/checklist-pravok`  
**Базовый коммит:** `4ccfd2b`  
**План:** [PLAN-checklist-pravok.md](./PLAN-checklist-pravok.md)  
**Прогресс:** [PLAN-progress.md](./PLAN-progress.md)  
**Workflow:** [PROMPT-checklist-step.md](./PROMPT-checklist-step.md)

---

## Бизнес-правила для сверки

| Правило | Ожидание |
|---------|----------|
| Доступ к позиции | `shared_access=true` → client CRUD; `false` → только просмотр |
| Заявка на оплату | client создаёт всегда; edit/delete — только если все позиции `shared_access=true` |
| Платёж | client add/download всегда; delete — owner + все позиции доступны |
| `client_id` | nullable, не в API/UI |
| Себестоимость NULL | итоги как `price` (маржа = 0) |
| Подтверждение платежа | нет approval — сразу `confirmed` |

---

## Очередь областей (для loop +30m)

Отмечай `[x]` когда область хотя бы раз полностью пройдена.

- [x] 1. `backend/app/core/permissions.py` и вызовы
- [x] 2. Backend routes: items
- [x] 3. Backend routes: payment_requests
- [ ] 4. Backend routes: payments
- [ ] 5. Frontend: раздел 1 (проекты/права)
- [ ] 6. Frontend: раздел 2 (позиции, заявки)
- [ ] 7. Frontend: раздел 3–4 (себестоимость, платежи)
- [ ] 8. Frontend: раздел 5–7 (фильтры, reorder, profit)
- [ ] 9. Frontend: раздел 8–10 (заметки, финал)
- [ ] 10. Тесты vs «Итог» шагов (пробелы)
- [ ] 11. Security (auth, IDOR, uploads)
- [ ] 12. Сводный финальный прогон

---

## Прогоны

## Прогон 2026-06-27 — permissions.py и вызовы

**Режим:** read-only аудит (loop tick #12)  
**Проверено:** `backend/app/core/permissions.py`, `backend/app/api/project_items.py`, `payment_requests.py`, `payments.py`, `project_notes.py`, `projects.py`, `payment_request_comments.py`, `files.py`, `backend/tests/test_permissions.py`, `backend/tests/test_payment_requests.py`

### Находки

| Severity | Файл | Описание | Рекомендация |
|----------|------|----------|--------------|
| high | `backend/app/api/files.py:16-37` | `_user_can_access_file`: для client достаточно существования `file_path` в таблице attachments/payments — нет привязки к проекту/заявке пользователя (IDOR по S3-ключу) | Проверять цепочку file → payment/attachment → request → project; использовать `ensure_project_access` или аналог |
| medium | `backend/app/schemas/project.py:46-47` | `ProjectOut` отдаёт `client_id` и `client` в API | Убрать из response-схемы (или отдельная admin-схема); синхронизировать frontend types |
| low | `backend/app/api/payment_requests.py:65-67` | `_check_access` — пустой stub (`return`), дублирует идею `ensure_project_access` | Заменить на `ensure_project_access` из permissions (REFACTOR_ACCESS_CHECKLIST) |
| low | `backend/app/api/payment_request_comments.py:27-38` | `_load_request_and_check_access` не выполняет проверку доступа — только 404 по req_id | Переименовать или вызывать `ensure_project_access(req.project_id, …)` |
| low | `backend/app/api/payments.py:56-68` | `_get_request_with_access` не проверяет доступ к проекту (только загрузка заявки) | Добавить `ensure_project_access` после загрузки |
| info | `backend/app/core/permissions.py:12-20` | `REFACTOR_ACCESS_CHECKLIST` — 7 файлов ещё с локальными/inline checks | Завершить рефакторинг в отдельном PR после чек-листа |
| info | `backend/app/core/permissions.py:37-39` | `can_access_project` проверяет только `user is not None` | Допустимо при обязательном `get_current_user`; можно упростить |

### Соответствие бизнес-правилам
- [x] shared_access CRUD — `can_edit_item`, `default_shared_access_for_creator` используются в `project_items.py`
- [x] payment request edit/delete — `can_edit_payment_request` / `all_items_accessible` в `payment_requests.py`
- [x] payment delete owner rule — `can_delete_payment` в `payments.py:398`
- [ ] client_id не в API/UI — поле всё ещё в `ProjectOut` и frontend types (UI не показывает)
- [x] cost NULL = price — `effective_cost_price` + тесты
- [x] payments без approval — `status="confirmed"` при создании (`payments.py:282`)

### Итог прогона
0 critical, 1 high, 1 medium, 3 low, 2 info. Центр прав (`permissions.py`) корректен; основные API используют helpers. Главный риск — IDOR в `files.py`. Следующая область: **Backend routes: items** (очередь #2).

---

## Прогон 2026-06-27 (2) — Backend routes: items

**Режим:** read-only аудит (loop tick #13)  
**Проверено:** `backend/app/api/project_items.py`, `project_item_requirements.py`, `backend/app/schemas/project_item.py`, `backend/app/services/import_service.py`, `backend/tests/test_project_items.py`

### Находки

| Severity | Файл | Описание | Рекомендация |
|----------|------|----------|--------------|
| low | `backend/app/api/project_items.py:119-135` | `_get_paid_map`: пропорциональное распределение платежей делит на `PaymentRequest.total_amount` без защиты от нуля | Добавить guard `WHERE total_amount > 0` или `NULLIF` |
| low | `backend/tests/test_project_items.py` | Нет HTTP-тестов endpoints: create/update/delete, move-up/down, import, 409 при delete с заявками | Добавить `TestClient`-тесты в post-checklist PR |
| info | `backend/app/api/project_items.py:310-312` | Client не может менять `shared_access`/`cost_price` через PUT — поля удаляются из update_dict | Соответствует чек-листу; покрыто unit-тестами helpers |
| info | `backend/app/api/project_items.py:392-399` | move-up/down требует `can_edit_item` на обе позиции | Корректно: client не переставляет через private-соседа |
| info | `backend/app/services/import_service.py:218` | Excel-import всегда `shared_access=False`, admin-only route | Соответствует чек-листу |

### Соответствие бизнес-правилам
- [x] shared_access CRUD — create defaults, update/delete/move через `can_edit_item`
- [x] payment request edit/delete — N/A (items scope)
- [x] payment delete owner rule — N/A
- [x] client_id не в API/UI — N/A для items
- [x] cost NULL = price — client: `cost_price=price` при create; `ProjectItemClientOut` без cost_price; import optional NULL
- [x] payments без approval — `_get_paid_map` учитывает только `status='confirmed'`

### Итог прогона
0 critical, 0 high, 0 medium, 2 low, 3 info. Items API в целом соответствует чек-листу; права и сериализация корректны. Следующая область: **Backend routes: payment_requests** (очередь #3).

---

## Прогон 2026-06-27 (3) — Backend routes: payment_requests

**Режим:** read-only аудит (loop tick #14)  
**Проверено:** `backend/app/api/payment_requests.py`, `payment_request_attachments.py`, `payment_request_comments.py`, `backend/app/schemas/payment_request.py`, `backend/tests/test_payment_requests.py`

### Находки

| Severity | Файл | Описание | Рекомендация |
|----------|------|----------|--------------|
| low | `backend/app/schemas/payment_request.py:15-18` | `PaymentRequestCreate` требует `total_amount` и `currency` от клиента, но сервер пересчитывает их (`payment_requests.py:344-346`) | Сделать поля optional или убрать из create-схемы |
| low | `backend/tests/test_payment_requests.py` | Нет HTTP-тестов: create на private items, edit/delete 403, фильтры list, delete 409 с платежами | Добавить integration-тесты post-checklist |
| info | `backend/app/api/payment_requests.py:284-404` | Create без проверки `shared_access` — client может создать заявку на closed items | Соответствует чек-листу |
| info | `backend/app/api/payment_request_attachments.py:49-95` | Upload без `can_edit_payment_request`; delete — с проверкой | Соответствует шагу 2.9 / сценарию 10 |
| info | `backend/app/api/payment_requests.py:525-527` | Log «by admin» при delete, хотя client тоже может удалять | Исправить текст лога |
| info | `backend/app/schemas/payment_request.py:63-67` | `AttachmentOut` отдаёт `file_path` (S3 key) клиенту | Усиливает риск IDOR из `files.py`; рассмотреть скрытие key |

### Соответствие бизнес-правилам
- [x] shared_access CRUD — N/A напрямую; create игнорирует shared_access
- [x] payment request edit/delete — `_ensure_can_edit_request` + `can_edit_payment_request`
- [x] payment delete owner rule — N/A (scope payment_requests)
- [x] client_id не в API/UI — N/A
- [x] cost NULL = price — N/A
- [x] payments без approval — `_compute_remaining` и фильтры list только `confirmed`

### Итог прогона
0 critical, 0 high, 0 medium, 2 low, 4 info. Payment requests API соответствует чек-листу: client create always, edit/delete по shared_access. Следующая область: **Backend routes: payments** (очередь #4).

---

_Секции добавляются агентом в конец файла после каждого аудит-tick (когда 12/12 ✅)._

**Формат секции:**

```markdown
## Прогон YYYY-MM-DD HH:MM — [область]

**Режим:** read-only аудит (loop)
**Проверено:** [файлы/модули]

### Находки

| Severity | Файл | Описание | Рекомендация |
|----------|------|----------|--------------|
| medium | path:line | … | … |

### Соответствие бизнес-правилам
- [ ] shared_access CRUD
- [ ] payment request edit/delete
- [ ] payment delete owner rule
- [ ] client_id не в API/UI
- [ ] cost NULL = price
- [ ] payments без approval (confirmed сразу)

### Итог прогона
N critical, N high, … Следующая область: …
```
