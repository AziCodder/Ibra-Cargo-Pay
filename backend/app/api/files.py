from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.payment import Payment
from app.models.payment_request import PaymentRequest
from app.models.payment_request_attachment import PaymentRequestAttachment
from app.models.user import User
from app.services.file_service import get_presigned_url

router = APIRouter(prefix="/api/files", tags=["files"])


async def _user_can_access_file(
    key: str, current_user: User, db: AsyncSession
) -> bool:
    """Проверяет, что пользователь имеет доступ к файлу по его S3-ключу."""
    if current_user.role == "admin":
        return True

    att_result = await db.execute(
        select(PaymentRequestAttachment).where(
            PaymentRequestAttachment.file_path == key,
        )
    )
    if att_result.scalar_one_or_none():
        return True

    pay_result = await db.execute(
        select(Payment).where(Payment.file_path == key)
    )
    if pay_result.scalar_one_or_none():
        return True

    return False


@router.get("/download-url")
async def get_download_url(
    key: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Возвращает presigned URL для скачивания файла по его S3-ключу."""
    if not await _user_can_access_file(key, current_user, db):
        raise HTTPException(status_code=403, detail="Нет доступа к этому файлу")

    url = await get_presigned_url(key)
    if not url:
        raise HTTPException(
            status_code=503,
            detail="Файловое хранилище недоступно или не настроено",
        )
    return {"url": url}
