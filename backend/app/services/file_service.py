"""
Сервис файлового хранилища (S3-совместимое).

В Phase 1 файловая загрузка не требуется — этот модуль является заглушкой.
Реальная интеграция с S3/Hostkey будет добавлена в Phase 2.
"""

import logging
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

# Разрешённые расширения файлов
ALLOWED_EXTENSIONS: frozenset[str] = frozenset({
    ".pdf",
    ".doc", ".docx",
    ".xls", ".xlsx",
    ".jpg", ".jpeg", ".png", ".gif", ".webp",
})


def sanitize_filename(filename: str) -> str:
    """Очищает имя файла от опасных символов и путей."""
    # Берём только имя файла (убираем пути)
    name = Path(filename).name
    # Заменяем опасные символы
    safe = "".join(c if c.isalnum() or c in "._- " else "_" for c in name)
    return safe or "file"


def validate_file_extension(original_filename: str) -> None:
    """Проверяет расширение файла. Выбрасывает ValueError если тип не разрешён."""
    ext = Path(original_filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise ValueError(
            f"Недопустимый тип файла '{ext}'. "
            f"Разрешены: PDF, Word, Excel, изображения (JPG, PNG, GIF, WebP)"
        )


def _is_s3_configured() -> bool:
    from app.core.config import settings
    return bool(
        settings.s3_endpoint_url
        and settings.s3_access_key_id
        and settings.s3_secret_access_key
    )


def _s3_client_config():
    """Конфиг для S3-совместимых сервисов (Hostkey: регион nl, path-style в URL)."""
    from botocore.config import Config as BotocoreConfig

    return BotocoreConfig(
        signature_version="s3v4",
        s3={"addressing_style": "path"},
        connect_timeout=5,
        read_timeout=15,
        retries={"max_attempts": 1},
    )


def _s3_client_config_short_timeout():
    from botocore.config import Config as BotocoreConfig

    return BotocoreConfig(
        signature_version="s3v4",
        s3={"addressing_style": "path"},
        connect_timeout=5,
        read_timeout=10,
        retries={"max_attempts": 1},
    )


async def upload_file(
    file_bytes: bytes,
    original_filename: str,
    prefix: str = "uploads",
) -> str:
    """
    Загружает файл в S3-хранилище и возвращает ключ (путь) файла.
    Если S3 не настроен — возвращает заглушку.
    """
    from app.core.config import settings

    ext = Path(original_filename).suffix.lower()
    file_key = f"{prefix}/{uuid.uuid4().hex}{ext}"

    if not _is_s3_configured():
        logger.warning("S3 не настроен. Файл не будет загружен: %s", file_key)
        return file_key

    try:
        import aioboto3
        session = aioboto3.Session(
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
            region_name=settings.s3_region,
        )
        async with session.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            config=_s3_client_config(),
        ) as s3:
            await s3.put_object(
                Bucket=settings.s3_bucket_name,
                Key=file_key,
                Body=file_bytes,
            )
        return file_key
    except Exception:
        logger.exception("Ошибка загрузки файла в S3: %s", file_key)
        raise RuntimeError(f"Не удалось загрузить файл в хранилище: {file_key}")


async def delete_file(file_key: str) -> None:
    """Удаляет файл из S3-хранилища."""
    from app.core.config import settings

    if not _is_s3_configured():
        return

    try:
        import aioboto3
        session = aioboto3.Session(
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
            region_name=settings.s3_region,
        )
        async with session.client(
            "s3", endpoint_url=settings.s3_endpoint_url, config=_s3_client_config_short_timeout()
        ) as s3:
            await s3.delete_object(Bucket=settings.s3_bucket_name, Key=file_key)
    except Exception:
        logger.exception("Ошибка удаления файла из S3: %s", file_key)


async def download_file_bytes(file_key: str) -> bytes | None:
    """Скачивает файл из S3 и возвращает байты. None если S3 не настроен или ошибка."""
    from app.core.config import settings

    if not _is_s3_configured():
        return None

    try:
        import aioboto3
        session = aioboto3.Session(
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
            region_name=settings.s3_region,
        )
        async with session.client(
            "s3", endpoint_url=settings.s3_endpoint_url, config=_s3_client_config()
        ) as s3:
            response = await s3.get_object(Bucket=settings.s3_bucket_name, Key=file_key)
            body = await response["Body"].read()
        return body
    except Exception:
        logger.exception("Ошибка скачивания файла из S3: %s", file_key)
        return None


async def get_presigned_url(file_key: str, expires_in: int = 3600) -> str | None:
    """Возвращает presigned URL для скачивания файла. None если S3 не настроен."""
    from app.core.config import settings

    if not _is_s3_configured():
        logger.warning("S3 не настроен. Presigned URL недоступен: %s", file_key)
        return None

    try:
        import aioboto3
        session = aioboto3.Session(
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
            region_name=settings.s3_region,
        )
        async with session.client(
            "s3", endpoint_url=settings.s3_endpoint_url, config=_s3_client_config_short_timeout()
        ) as s3:
            url = await s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": settings.s3_bucket_name, "Key": file_key},
                ExpiresIn=expires_in,
            )
        return url
    except Exception:
        logger.exception("Ошибка получения presigned URL: %s", file_key)
        return None
