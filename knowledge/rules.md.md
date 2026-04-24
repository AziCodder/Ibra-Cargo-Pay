# Rules

## Roles
- admin
- client

## Access Restrictions

### Client
- sees only their projects (where client_id = own user id)
- cannot see cost_price
- cannot see profit
- cannot edit projects
- cannot create/edit/delete projects
- cannot manage suppliers or users
- cannot manage nomenclature (project items)
- cannot create/edit/delete payment requests
- can view payment requests
- can add/delete own payments only (created_by = own user id)

### Admin
- full access to all system features
- full visibility of all data including cost_price and profit
- can delete any payment regardless of creator

## Deletion Rules
- Project: can be deleted ONLY if it has NO payment requests
- Payment request: can be deleted ONLY if it has NO payments
- Supplier: allowed, SET NULL on project_items.supplier_id (warn admin)
- User: blocked if assigned to any project

## Commission
- Stored as percentage on project items (DECIMAL 5,2)
- Affects all financial calculations: `effective_price = price * (1 + commission / 100)`
- Client sees price and commission fields, but totals use effective_price

## Currency
- Supported: CNY, USD, RUB
- Mixed currencies allowed within one project
- All calculations (total, remaining, profit) grouped by currency
- No currency conversion

## Language Requirements
- The entire user interface (UI) must be in Russian
- All labels, buttons, forms, messages, and statuses must be displayed in Russian
- The system is intended for Russian-speaking users
- The codebase (backend, frontend logic, database, API) must remain in English
- Do not mix Russian and English in the UI
- All user-facing text must be clear, professional, and consistent in Russian
- Все ответы и объяснения — на русском
- Интерфейс — на русском
- Код — на английском


## Security
- Never expose cost_price or profit to client users (not in API responses, not in UI)
- Passwords stored as bcrypt hashes, never plaintext
- JWT auth: access token 30min, refresh token 7d
- File uploads: validate MIME type, 10MB limit, allowed types only
