from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.audit import router as audit_router
from app.api.auth import router as auth_router
from app.api.backups import router as backups_router
from app.api.bot import router as bot_router
from app.api.dashboard import router as dashboard_router
from app.api.files import router as files_router
from app.api.payment_request_attachments import router as attachments_router
from app.api.payment_request_comments import router as comments_router
from app.api.payment_requests import router as payment_requests_router
from app.api.payments import router as payments_router, router_project as payments_project_router
from app.api.project_item_requirements import router as requirements_router
from app.api.project_notes import router as project_notes_router
from app.api.project_items import router as project_items_router
from app.api.projects import router as projects_router
from app.api.storage import router as storage_router
from app.api.suppliers import router as suppliers_router
from app.api.users import router as users_router
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.limiter import limiter
from app.core.seed import seed_admin


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Проверка безопасности конфигурации
    from app.core.config import validate_production_settings
    for w in validate_production_settings():
        import logging
        logging.getLogger("security").warning("⚠️  %s", w)

    async with AsyncSessionLocal() as db:
        await seed_admin(db)
    yield


app = FastAPI(
    title="Project Manager API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth_router)
app.include_router(bot_router)
app.include_router(files_router)
app.include_router(users_router)
app.include_router(suppliers_router)
app.include_router(projects_router)
app.include_router(project_notes_router)
app.include_router(project_items_router)
app.include_router(requirements_router)
app.include_router(payment_requests_router)
app.include_router(attachments_router)
app.include_router(payments_router)
app.include_router(payments_project_router)
app.include_router(comments_router)
app.include_router(audit_router)
app.include_router(dashboard_router)
app.include_router(backups_router)
app.include_router(storage_router)


@app.get("/health", tags=["system"])
async def health() -> dict:
    return {"status": "ok"}
