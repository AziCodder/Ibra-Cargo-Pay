# Database Schema

## Tables: 9 total

### users
| Column | Type | Constraints |
|--------|------|-------------|
| id | SERIAL | PK |
| full_name | VARCHAR(255) | NOT NULL |
| login | VARCHAR(100) | UNIQUE, NOT NULL |
| password_hash | VARCHAR(255) | NOT NULL |
| role | VARCHAR(10) | NOT NULL, CHECK IN ('admin','client') |
| description | TEXT | nullable |
| telegram_chat_id | BIGINT | UNIQUE, nullable |
| created_at | TIMESTAMP | DEFAULT NOW() |
| updated_at | TIMESTAMP | DEFAULT NOW() |

### suppliers
| Column | Type | Constraints |
|--------|------|-------------|
| id | SERIAL | PK |
| full_name | VARCHAR(255) | NOT NULL |
| phone | VARCHAR(50) | NOT NULL |
| wechat_id | VARCHAR(100) | NOT NULL |
| document_1 | VARCHAR(500) | nullable (MinIO key) |
| document_2 | VARCHAR(500) | nullable (MinIO key) |
| document_3 | VARCHAR(500) | nullable (MinIO key) |
| description | TEXT | nullable |
| created_at | TIMESTAMP | DEFAULT NOW() |
| updated_at | TIMESTAMP | DEFAULT NOW() |

### projects
| Column | Type | Constraints |
|--------|------|-------------|
| id | SERIAL | PK |
| name | VARCHAR(255) | NOT NULL |
| description | TEXT | nullable |
| client_id | INTEGER | NOT NULL, FK -> users(id) |
| status | VARCHAR(10) | DEFAULT 'active', CHECK IN ('active','closed') |
| created_at | TIMESTAMP | DEFAULT NOW() |
| updated_at | TIMESTAMP | DEFAULT NOW() |

Indexes: `idx_projects_client_id`, `idx_projects_status`, `idx_projects_created_at_desc`

### project_items
| Column | Type | Constraints |
|--------|------|-------------|
| id | SERIAL | PK |
| project_id | INTEGER | NOT NULL, FK -> projects(id) CASCADE |
| name | VARCHAR(255) | NOT NULL |
| details | TEXT | nullable |
| quantity | DECIMAL(12,2) | NOT NULL, >0 |
| supplier_id | INTEGER | FK -> suppliers(id) SET NULL, nullable |
| price | DECIMAL(14,2) | NOT NULL, >=0 |
| cost_price | DECIMAL(14,2) | NOT NULL, >=0 |
| currency | VARCHAR(3) | NOT NULL, CHECK IN ('CNY','USD','RUB') |
| commission | DECIMAL(5,2) | DEFAULT 0 (percentage) |
| created_at | TIMESTAMP | DEFAULT NOW() |
| updated_at | TIMESTAMP | DEFAULT NOW() |

Index: `idx_project_items_project_id`

### project_item_requirements
| Column | Type | Constraints |
|--------|------|-------------|
| id | SERIAL | PK |
| item_id | INTEGER | NOT NULL, FK -> project_items(id) CASCADE |
| text | TEXT | NOT NULL |
| created_at | TIMESTAMP | DEFAULT NOW() |

Max 5 per item (enforced at API level). Index: `idx_requirements_item_id`

### payment_requests
| Column | Type | Constraints |
|--------|------|-------------|
| id | SERIAL | PK |
| project_id | INTEGER | NOT NULL, FK -> projects(id) RESTRICT |
| total_amount | DECIMAL(14,2) | NOT NULL, >0 |
| currency | VARCHAR(3) | NOT NULL, CHECK IN ('CNY','USD','RUB') |
| requisites | TEXT | nullable |
| payment_details | TEXT | nullable |
| created_by | INTEGER | NOT NULL, FK -> users(id) |
| created_at | TIMESTAMP | DEFAULT NOW() |
| updated_at | TIMESTAMP | DEFAULT NOW() |

Index: `idx_payment_requests_project_id`

### payment_request_items
| Column | Type | Constraints |
|--------|------|-------------|
| id | SERIAL | PK |
| payment_request_id | INTEGER | FK -> payment_requests(id) CASCADE |
| project_item_id | INTEGER | FK -> project_items(id) CASCADE |
| amount | DECIMAL(14,2) | NOT NULL, >0 |

UNIQUE constraint on (payment_request_id, project_item_id)

### payment_request_attachments
| Column | Type | Constraints |
|--------|------|-------------|
| id | SERIAL | PK |
| payment_request_id | INTEGER | FK -> payment_requests(id) CASCADE |
| file_path | VARCHAR(500) | NOT NULL (MinIO key) |
| file_name | VARCHAR(255) | NOT NULL |
| created_at | TIMESTAMP | DEFAULT NOW() |

Max 3 per request (enforced at API level).

### payments
| Column | Type | Constraints |
|--------|------|-------------|
| id | SERIAL | PK |
| payment_request_id | INTEGER | FK -> payment_requests(id) RESTRICT |
| amount | DECIMAL(14,2) | NOT NULL, >0 |
| currency | VARCHAR(3) | NOT NULL, CHECK IN ('CNY','USD','RUB') |
| file_path | VARCHAR(500) | nullable (MinIO key) |
| file_name | VARCHAR(255) | nullable |
| note | TEXT | nullable |
| created_by | INTEGER | NOT NULL, FK -> users(id) |
| created_at | TIMESTAMP | DEFAULT NOW() |

Index: `idx_payments_request_id`

---

## Computed Values (never stored, always calculated at query time)

- `effective_price = price * (1 + commission / 100)`
- Payment request remaining: `total_amount - COALESCE(SUM(payments.amount), 0)`
- Project total per currency: `SUM(effective_price * quantity)` grouped by currency
- Project remaining per currency: `total - paid`
- Project profit per currency: `SUM((effective_price - cost_price) * quantity)` -- ADMIN ONLY

---

## Relationships

```
users 1--N projects (via client_id)
users 1--N payment_requests (via created_by)
users 1--N payments (via created_by)
suppliers 1--N project_items (via supplier_id, SET NULL on delete)
projects 1--N project_items (CASCADE on delete)
projects 1--N payment_requests (RESTRICT -- block project delete if requests exist)
project_items 1--N project_item_requirements (CASCADE on delete)
project_items 1--N payment_request_items (CASCADE on delete)
payment_requests 1--N payment_request_items (CASCADE on delete)
payment_requests 1--N payment_request_attachments (CASCADE on delete)
payment_requests 1--N payments (RESTRICT -- block request delete if payments exist)
```

---

## Deletion Rules

- **Project:** can be deleted ONLY if it has NO payment requests
- **Payment request:** can be deleted ONLY if it has NO payments
- **Supplier:** SET NULL on project_items.supplier_id (warn admin)
- **User:** blocked if assigned to any project
