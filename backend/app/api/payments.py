"""
API платежей с workflow подтверждения.

Клиент создаёт платёж -> status='pending', админ получает уведомление.
Админ подтверждает (/confirm) -> status='confirmed'.
Админ отклоняет (/reject) с причиной -> status='rejected'.
Клиенту отправляется уведомление о решении админа.

remaining_amount учитывает ТОЛЬКО confirmed платежи.
"""

from __future__ import annotations

import io
import logging
import zipfile
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_admin
from app.models.payment import Payment
from app.models.payment_request import PaymentRequest
from app.models.payment_request_item import PaymentRequestItem
from app.models.project import Project
from app.models.project_item import ProjectItem
from app.models.user import User
from app.schemas.payment import PaymentOut, PaymentReject
from app.services import audit_service, file_service, notification_service

logger = logging.getLogger(__name__)

MAX_PAYMENT_FILE_SIZE = 10 * 1024 * 1024  # 10 МБ

router = APIRouter(prefix="/api/payment-requests/{req_id}/payments", tags=["payments"])


async def _get_request_with_access(
    req_id: int, current_user, db: AsyncSession
) -> PaymentRequest:
    result = await db.execute(
        select(PaymentRequest)
        .where(PaymentRequest.id == req_id)
        .options(selectinload(PaymentRequest.project))
    )
    req = result.scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=404, detail="Заявка на оплату не найдена")

    project: Project = req.project
    if current_user.role == "client" and project.client_id != current_user.id:
        raise HTTPException(status_code=403, detail="Нет доступа к этому проекту")

    return req


async def _get_admin_chat_ids(db: AsyncSession) -> list[int]:
    result = await db.execute(
        select(User.telegram_chat_id).where(
            User.role == "admin",
            User.telegram_chat_id.is_not(None),
        )
    )
    return [row[0] for row in result.all()]


async def _get_client_chat_id(project_id: int, db: AsyncSession) -> int | None:
    result = await db.execute(
        select(User.telegram_chat_id)
        .join(Project, Project.client_id == User.id)
        .where(Project.id == project_id)
    )
    row = result.first()
    return row[0] if row else None


@router.get("/download-zip")
async def download_payments_zip(
    req_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Скачать все файлы платежей в одном ZIP-архиве."""
    await _get_request_with_access(req_id, current_user, db)

    result = await db.execute(
        select(Payment)
        .where(Payment.payment_request_id == req_id, Payment.file_path.isnot(None))
        .order_by(Payment.created_at.asc())
    )
    payments_with_files = result.scalars().all()

    if not payments_with_files:
        raise HTTPException(status_code=404, detail="Нет файлов для скачивания")

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        seen_names: dict[str, int] = {}
        for pay in payments_with_files:
            file_bytes = await file_service.download_file_bytes(pay.file_path)
            if file_bytes is None:
                continue
            base_name = pay.file_name or f"payment_{pay.id}"
            if base_name in seen_names:
                seen_names[base_name] += 1
                dot = base_name.rfind(".")
                if dot > 0:
                    name_in_zip = f"{base_name[:dot]}_{seen_names[base_name]}{base_name[dot:]}"
                else:
                    name_in_zip = f"{base_name}_{seen_names[base_name]}"
            else:
                seen_names[base_name] = 0
                name_in_zip = base_name
            zf.writestr(name_in_zip, file_bytes)

    zip_buffer.seek(0)
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="payments_{req_id}.zip"'},
    )


@router.get("", response_model=list[PaymentOut])
async def list_payments(
    req_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[PaymentOut]:
    await _get_request_with_access(req_id, current_user, db)

    result = await db.execute(
        select(Payment)
        .where(Payment.payment_request_id == req_id)
        .order_by(Payment.created_at.asc())
    )
    payments = result.scalars().all()
    return [PaymentOut.model_validate(p) for p in payments]


@router.post("", response_model=PaymentOut, status_code=status.HTTP_201_CREATED)
async def add_payment(
    req_id: int,
    amount: Decimal = Form(...),
    currency: str = Form(...),
    note: str | None = Form(None),
    file: UploadFile | None = File(None),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaymentOut:
    """
    Добавить платёж.

    - Клиент -> платёж создаётся со статусом 'pending', админы уведомляются.
    - Админ -> платёж сразу 'confirmed' (сам себе подтверждать не нужно).
    """
    if currency not in ("CNY", "USD", "RUB"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Валюта должна быть CNY, USD или RUB",
        )

    req = await _get_request_with_access(req_id, current_user, db)

    # Валюта платежа должна совпадать с валютой заявки
    if currency != req.currency:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Валюта платежа ({currency}) не совпадает с валютой заявки ({req.currency})",
        )
    # Читаем данные до commit
    project_name = req.project.name
    project_id = req.project_id

    file_path_val: str | None = None
    file_name_val: str | None = None
    if file and file.filename:
        try:
            file_service.validate_file_extension(file.filename)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            )
        file_bytes = await file.read()
        if len(file_bytes) > MAX_PAYMENT_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Файл слишком большой. Максимум 10 МБ",
            )
        try:
            file_path_val = await file_service.upload_file(
                file_bytes, file.filename, prefix="payments"
            )
        except Exception as exc:
            logger.error("S3 upload failed for payment file: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Не удалось загрузить файл в хранилище. Попробуйте без прикреплённого файла или обратитесь к администратору.",
            )
        file_name_val = file_service.sanitize_filename(file.filename)

    # Админ добавляет -> сразу confirmed, клиент -> pending
    is_admin = current_user.role == "admin"
    new_status = "confirmed" if is_admin else "pending"
    confirmed_at_val = datetime.now(timezone.utc) if is_admin else None
    confirmed_by_val = current_user.id if is_admin else None

    payment = Payment(
        payment_request_id=req_id,
        amount=amount,
        currency=currency,
        note=note,
        file_path=file_path_val,
        file_name=file_name_val,
        status=new_status,
        confirmed_by=confirmed_by_val,
        confirmed_at=confirmed_at_val,
        created_by=current_user.id,
    )
    db.add(payment)
    await db.flush()

    # Снимок ДО flush'а бы испортил id; после flush - но до expire
    after_snapshot = audit_service.entity_snapshot(payment)

    await audit_service.log_action(
        db,
        user_id=current_user.id,
        action="created",
        entity_type="payment",
        entity_id=payment.id,
        after=after_snapshot,
    )

    await db.commit()
    await db.refresh(payment)

    # Получаем названия позиций заявки для уведомления
    item_names_result = await db.execute(
        select(ProjectItem.name)
        .join(PaymentRequestItem, PaymentRequestItem.project_item_id == ProjectItem.id)
        .where(PaymentRequestItem.payment_request_id == req_id)
    )
    item_names_str = ", ".join(row[0] for row in item_names_result.all())

    # Presigned URL файла для уведомления (24 часа)
    file_url_for_notify: str | None = None
    if file_path_val:
        file_url_for_notify = await file_service.get_presigned_url(file_path_val, expires_in=86400)

    # Уведомления
    if is_admin:
        admin_chat_ids = await _get_admin_chat_ids(db)
        notification_service.notify_payment_added(
            admin_chat_ids=admin_chat_ids,
            project_name=project_name,
            project_id=project_id,
            req_id=req_id,
            amount=payment.amount,
            currency=payment.currency,
            item_names=item_names_str or None,
            note=note,
            file_url=file_url_for_notify,
        )
    else:
        admin_chat_ids = await _get_admin_chat_ids(db)
        notification_service.notify_payment_pending(
            admin_chat_ids=admin_chat_ids,
            project_name=project_name,
            project_id=project_id,
            req_id=req_id,
            amount=payment.amount,
            currency=payment.currency,
            client_login=current_user.login,
            item_names=item_names_str or None,
            note=note,
            file_url=file_url_for_notify,
        )

    return PaymentOut.model_validate(payment)


@router.post("/{pay_id}/confirm", response_model=PaymentOut)
async def confirm_payment(
    req_id: int,
    pay_id: int,
    current_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> PaymentOut:
    """Админ подтверждает pending-платёж."""
    req = await _get_request_with_access(req_id, current_user, db)

    result = await db.execute(
        select(Payment)
        .where(Payment.id == pay_id, Payment.payment_request_id == req_id)
        .options(selectinload(Payment.creator))
    )
    payment = result.scalar_one_or_none()
    if not payment:
        raise HTTPException(status_code=404, detail="Платёж не найден")

    if payment.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Платёж уже обработан (статус: {payment.status})",
        )

    before = audit_service.entity_snapshot(payment)
    payment.status = "confirmed"
    payment.confirmed_by = current_user.id
    payment.confirmed_at = datetime.now(timezone.utc)
    payment.rejection_reason = None

    # Данные для уведомления читаем до flush/commit
    project_name = req.project.name
    client_chat_id = await _get_client_chat_id(req.project_id, db)
    amount = payment.amount
    currency = payment.currency

    await db.flush()
    after = audit_service.entity_snapshot(payment)

    await audit_service.log_action(
        db,
        user_id=current_user.id,
        action="updated",
        entity_type="payment",
        entity_id=payment.id,
        before=before,
        after=after,
    )

    await db.commit()
    await db.refresh(payment)

    notification_service.notify_payment_confirmed(
        client_chat_id=client_chat_id,
        project_name=project_name,
        req_id=req_id,
        amount=amount,
        currency=currency,
    )

    return PaymentOut.model_validate(payment)


@router.post("/{pay_id}/reject", response_model=PaymentOut)
async def reject_payment(
    req_id: int,
    pay_id: int,
    data: PaymentReject = Body(...),
    current_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> PaymentOut:
    """Админ отклоняет pending-платёж с указанием причины."""
    req = await _get_request_with_access(req_id, current_user, db)

    result = await db.execute(
        select(Payment).where(
            Payment.id == pay_id, Payment.payment_request_id == req_id
        )
    )
    payment = result.scalar_one_or_none()
    if not payment:
        raise HTTPException(status_code=404, detail="Платёж не найден")

    if payment.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Платёж уже обработан (статус: {payment.status})",
        )

    before = audit_service.entity_snapshot(payment)
    payment.status = "rejected"
    payment.confirmed_by = current_user.id
    payment.confirmed_at = datetime.now(timezone.utc)
    payment.rejection_reason = data.reason.strip()

    # Данные для уведомления
    project_name = req.project.name
    client_chat_id = await _get_client_chat_id(req.project_id, db)
    amount = payment.amount
    currency = payment.currency
    reason_text = payment.rejection_reason

    await db.flush()
    after = audit_service.entity_snapshot(payment)

    await audit_service.log_action(
        db,
        user_id=current_user.id,
        action="updated",
        entity_type="payment",
        entity_id=payment.id,
        before=before,
        after=after,
    )

    await db.commit()
    await db.refresh(payment)

    notification_service.notify_payment_rejected(
        client_chat_id=client_chat_id,
        project_name=project_name,
        req_id=req_id,
        amount=amount,
        currency=currency,
        reason=reason_text,
    )

    return PaymentOut.model_validate(payment)


@router.delete("/{pay_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_payment(
    req_id: int,
    pay_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_request_with_access(req_id, current_user, db)

    result = await db.execute(
        select(Payment).where(
            Payment.id == pay_id, Payment.payment_request_id == req_id
        )
    )
    payment = result.scalar_one_or_none()
    if not payment:
        raise HTTPException(status_code=404, detail="Платёж не найден")

    # Клиент может удалять только свои платежи (и только pending/rejected)
    if current_user.role == "client":
        if payment.created_by != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Можно удалять только собственные платежи",
            )
        if payment.status == "confirmed":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Нельзя удалить подтверждённый платёж",
            )

    logger.info(
        "Payment deleted: id=%s, amount=%s %s, status=%s, req_id=%s, by user=%s (%s)",
        payment.id, payment.amount, payment.currency, payment.status,
        req_id, current_user.id, current_user.login,
    )
    before = audit_service.entity_snapshot(payment)
    payment_id_snapshot = payment.id
    await db.delete(payment)

    await audit_service.log_action(
        db,
        user_id=current_user.id,
        action="deleted",
        entity_type="payment",
        entity_id=payment_id_snapshot,
        before=before,
    )

    await db.commit()
