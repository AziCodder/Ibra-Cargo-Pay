from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_admin
from app.models.payment_request import PaymentRequest
from app.models.payment_request_attachment import PaymentRequestAttachment
from app.schemas.payment_request import AttachmentOut
from app.services import file_service
from app.services.file_service import upload_file

router = APIRouter(
    prefix="/api/projects/{project_id}/payment-requests/{req_id}/attachments",
    tags=["attachments"],
)

MAX_ATTACHMENTS = 3
MAX_FILE_SIZE_MB = 10
MAX_FILE_SIZE = MAX_FILE_SIZE_MB * 1024 * 1024


async def _get_request_or_404(req_id: int, project_id: int, db: AsyncSession) -> PaymentRequest:
    result = await db.execute(
        select(PaymentRequest).where(
            PaymentRequest.id == req_id,
            PaymentRequest.project_id == project_id,
        )
    )
    req = result.scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=404, detail="Заявка на оплату не найдена")
    return req


@router.post("", response_model=AttachmentOut, status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    project_id: int,
    req_id: int,
    file: UploadFile = File(...),
    _admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AttachmentOut:
    await _get_request_or_404(req_id, project_id, db)

    count_result = await db.execute(
        select(func.count()).where(PaymentRequestAttachment.payment_request_id == req_id)
    )
    if count_result.scalar_one() >= MAX_ATTACHMENTS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Максимум {MAX_ATTACHMENTS} вложений для одной заявки",
        )

    original_name = file.filename or "attachment"
    try:
        file_service.validate_file_extension(original_name)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Файл слишком большой. Максимум {MAX_FILE_SIZE_MB} МБ",
        )

    file_path = await upload_file(file_bytes, original_name, prefix="payment-requests")

    attachment = PaymentRequestAttachment(
        payment_request_id=req_id,
        file_path=file_path,
        file_name=original_name,
    )
    db.add(attachment)
    await db.commit()
    await db.refresh(attachment)
    return AttachmentOut.model_validate(attachment)


@router.delete("/{att_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_attachment(
    project_id: int,
    req_id: int,
    att_id: int,
    _admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    await _get_request_or_404(req_id, project_id, db)

    result = await db.execute(
        select(PaymentRequestAttachment).where(
            PaymentRequestAttachment.id == att_id,
            PaymentRequestAttachment.payment_request_id == req_id,
        )
    )
    att = result.scalar_one_or_none()
    if not att:
        raise HTTPException(status_code=404, detail="Вложение не найдено")

    await db.delete(att)
    await db.commit()
