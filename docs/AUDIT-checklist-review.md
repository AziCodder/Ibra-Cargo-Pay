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

- [ ] 1. `backend/app/core/permissions.py` и вызовы
- [ ] 2. Backend routes: items
- [ ] 3. Backend routes: payment_requests
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

_Пока пусто. Секции добавляются агентом в конец файла после каждого аудит-tick (когда 12/12 ✅)._

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
