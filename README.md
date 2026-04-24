# Project Management & Payment Tracking Platform

Internal system for managing projects, suppliers, nomenclature, payment requests, and payments. Role-based access (admin / client). Telegram notifications.

## Stack

- **Backend:** FastAPI + SQLAlchemy (async) + PostgreSQL
- **Frontend:** React + TypeScript + Vite + Ant Design
- **Bot:** Telegram (aiogram)
- **Storage:** S3-compatible (configured via environment variables)
- **Infrastructure:** Docker Compose

---

## Quick Start

### 1. Copy environment file

```bash
cp .env .env
```

Edit `.env` and fill in all required values (database password, secret key, S3 credentials, Telegram token).

### 2. Build and start all services

```bash
docker compose up --build
```

### 3. Verify services

| Service  | URL                          |
|----------|------------------------------|
| Backend  | http://localhost:8000        |
| API docs | http://localhost:8000/docs   |
| Frontend | http://localhost:5173        |
| Database | localhost:5432               |

Health check: `curl http://localhost:8000/health` → `{"status":"ok"}`

---

## Development

### Run services individually (without Docker)

**Backend:**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

**Bot:**
```bash
cd bot
pip install -r requirements.txt
python main.py
```

### Database migrations (Alembic)

```bash
# Inside the backend container
docker compose exec backend alembic upgrade head

# Generate a new migration
docker compose exec backend alembic revision --autogenerate -m "description"
```

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `DB_NAME` | PostgreSQL database name |
| `DB_USER` | PostgreSQL user |
| `DB_PASSWORD` | PostgreSQL password |
| `SECRET_KEY` | JWT signing secret (min 32 chars) |
| `FRONTEND_URL` | Frontend origin for CORS |
| `S3_ENDPOINT_URL` | S3-compatible endpoint URL |
| `S3_ACCESS_KEY_ID` | S3 access key |
| `S3_SECRET_ACCESS_KEY` | S3 secret key |
| `S3_BUCKET_NAME` | S3 bucket name |
| `S3_REGION` | S3 region |
| `TELEGRAM_BOT_TOKEN` | Token from @BotFather |
| `BACKEND_URL` | Backend URL for Vite proxy (Docker only) |

---

## Project Structure

```
├── backend/          FastAPI application
│   ├── app/
│   │   ├── api/      Route modules
│   │   ├── core/     Config, DB, security, dependencies
│   │   ├── models/   SQLAlchemy models
│   │   ├── schemas/  Pydantic schemas
│   │   └── services/ Business logic (file upload, notifications)
│   ├── alembic/      Database migrations
│   └── tests/
├── frontend/         React + Vite application
│   └── src/
│       ├── api/      Axios API client modules
│       ├── components/
│       ├── contexts/ AuthContext
│       ├── i18n/     Russian UI strings
│       ├── pages/
│       └── types/
├── bot/              Telegram bot (aiogram)
├── docker-compose.yml
└── .env.example
```
