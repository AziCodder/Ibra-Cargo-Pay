import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _apply_s3_vars_from_dotenv(path: Path) -> None:
    """Читает S3_* и BACKUP_* из файла в os.environ (не трогает DATABASE_URL и т.д.)."""
    if not path.is_file():
        return
    from dotenv import dotenv_values

    for key, value in dotenv_values(path).items():
        if not key or value is None:
            continue
        if not (key.startswith("S3_") or key.startswith("BACKUP_")):
            continue
        s = str(value).strip()
        if s and not s.startswith("#"):
            os.environ[key] = s


def _bootstrap_s3_env() -> None:
    """
    В Docker при volume ./backend:/app корневой .env репозитория недоступен по пути кода.
    Compose монтирует его в /config/project.env — подхватываем до инициализации Settings.
    Локально: .env в корне репозитория (родитель каталога backend).
    """
    here = Path(__file__).resolve()
    # .../backend/app/core/config.py -> parents[3] = корень репозитория при полном checkout
    repo_root_env = here.parents[3] / ".env"
    docker_project_env = Path("/config/project.env")
    for p in (repo_root_env, docker_project_env):
        _apply_s3_vars_from_dotenv(p)


_bootstrap_s3_env()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://postgres:changeme@localhost:5432/project_manager"

    # JWT (обязательно задать через переменную окружения!)
    secret_key: str = "change-me-in-production"  # переопределяется через SECRET_KEY в .env
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # S3-compatible storage (PRIMARY — основной таргет, напр. Hostkey)
    s3_endpoint_url: str = ""
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_bucket_name: str = "project-manager"
    s3_region: str = "nl"  # Hostkey NL endpoint ожидает регион nl (см. их AWS CLI-документацию)

    # S3 SECONDARY — второй таргет для dual-write (напр. Storj). Если пусто — dual-write выключен,
    # работает только PRIMARY. Все файлы и дампы пишутся сразу в оба таргета (см. storage_service).
    s3_secondary_endpoint_url: str = ""
    s3_secondary_access_key_id: str = ""
    s3_secondary_secret_access_key: str = ""
    s3_secondary_bucket: str = ""  # если пусто — используется s3_bucket_name
    s3_secondary_region: str = "us-1"  # Storj gateway игнорирует, но boto3 требует непустой

    # Роль узла в схеме active-passive: primary принимает записи, standby — реплика (read-only).
    node_role: str = "primary"
    # WireGuard-IP серверов — для проверки доступности второго сервера в /api/system/status.
    primary_wg_ip: str = ""
    standby_wg_ip: str = ""

    # Frontend
    frontend_url: str = "http://localhost:5173"

    # Telegram
    telegram_bot_token: str = ""
    telegram_notify_chat_id: str = ""
    bot_secret: str = "change-me-bot-secret"  # переопределяется через BOT_SECRET в .env

    # Backups (отдельный bucket для дампов БД)
    backup_s3_bucket: str = ""  # если пусто — фича выключена
    backup_s3_prefix: str = "db-backups/"
    backup_retention_days: int = 30
    # Секрет, по которому sidecar-контейнер триггерит /api/backups/run без JWT
    backup_trigger_secret: str = "change-me-backup-secret"
    # Опциональные отдельные креды для backup-бакета. Если пусты — используются S3_*.
    backup_s3_endpoint_url: str = ""
    backup_s3_access_key_id: str = ""
    backup_s3_secret_access_key: str = ""
    backup_s3_region: str = ""


settings = Settings()


def validate_production_settings() -> list[str]:
    """Возвращает список предупреждений для небезопасных настроек."""
    warnings = []
    if settings.secret_key == "change-me-in-production":
        warnings.append("SECRET_KEY использует значение по умолчанию! Задайте уникальный секрет.")
    if settings.bot_secret == "change-me-bot-secret":
        warnings.append("BOT_SECRET использует значение по умолчанию! Задайте уникальный секрет.")
    if (
        settings.backup_s3_bucket
        and settings.backup_trigger_secret == "change-me-backup-secret"
    ):
        warnings.append(
            "BACKUP_TRIGGER_SECRET использует значение по умолчанию! Задайте уникальный секрет."
        )
    ep = (settings.s3_endpoint_url or "").lower()
    if ep and ("your-endpoint" in ep or "example.com" in ep):
        warnings.append(
            "S3_ENDPOINT_URL похож на шаблон. Проверьте .env в каталоге с docker-compose.yml "
            "и пересоздайте контейнер: docker compose up -d --force-recreate backend"
        )
    return warnings
