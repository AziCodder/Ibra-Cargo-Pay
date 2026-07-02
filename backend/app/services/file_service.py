"""
Сервис файлового хранилища (S3-совместимое).

Тонкий слой поверх storage_service: валидация имени/расширения + генерация ключа.
Реальная запись/чтение идут через storage_service, который дублирует объекты во все
настроенные таргеты (dual-write: PRIMARY + SECONDARY).
"""

import logging
import uuid
from pathlib import Path

from app.services import storage_service

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
        raise ValueError(
            f"Недопустимый тип файла '{ext}'. "
            f"Разрешены: PDF, Word, Excel, изображения (JPG, PNG, GIF, WebP)"
        )


def _is_s3_configured() -> bool:
    return bool(storage_service.file_targets())


async def upload_file(
    file_bytes: bytes,
    original_filename: str,
    prefix: str = "uploads",
) -> str:
    """
    Загружает файл во все S3-таргеты (dual-write) и возвращает ключ (путь) файла.
    Если S3 не настроен — возвращает заглушку-ключ, ничего не загружая.
    """
    ext = Path(original_filename).suffix.lower()
    file_key = f"{prefix}/{uuid.uuid4().hex}{ext}"

    if not _is_s3_configured():
        logger.warning("S3 не настроен. Файл не будет загружен: %s", file_key)
        return file_key

    await storage_service.put(file_key, file_bytes)
    return file_key


async def delete_file(file_key: str) -> None:
    """Удаляет файл из всех S3-таргетов (best-effort)."""
    if not _is_s3_configured():
        return
    await storage_service.delete(file_key)


async def download_file_bytes(file_key: str) -> bytes | None:
    """Скачивает файл с первого доступного таргета. None если не настроено/не найдено."""
    if not _is_s3_configured():
        return None
    return await storage_service.get(file_key)


async def get_presigned_url(file_key: str, expires_in: int = 3600) -> str | None:
    """Presigned URL для скачивания с первого доступного таргета. None если не настроено."""
    if not _is_s3_configured():
        logger.warning("S3 не настроен. Presigned URL недоступен: %s", file_key)
        return None
    return await storage_service.presigned(file_key, expires_in=expires_in)
