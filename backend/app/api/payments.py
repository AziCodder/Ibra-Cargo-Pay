"""
API платежей.

Все платежи создаются со status='confirmed' и сразу учитываются в remaining_amount.
"""

from __future__ import annotations

import io
import logging
import zipfile
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.permissions import can_delete_payment
from app.models.payment import Payment
from app.models.payment_request import PaymentRequest
from app.models.payment_request_item import PaymentRequestItem
from app.models.project import Project
from app.models.project_item import ProjectItem
from app.models.user import User
from app.schemas.payment import PaymentOut, PaymentUpdate
from app.services import audit_service, file_service, notification_service

logger = logging.getLogger(__name__)

MAX_PAYMENT_FILE_SIZE = 3 * 1024 * 1024  # 3 МБ

router = APIRouter(prefix="/api/payment-requests/{req_id}/payments", tags=["payments"])
router_project = APIRouter(prefix="/api/projects/{project_id}/payments", tags=["payments"])


async def _load_payment_request_items(
    req_id: int, db: AsyncSession
) -> list[ProjectItem]:
    result = await db.execute(
        select(PaymentRequestItem)
        .where(PaymentRequestItem.payment_request_id == req_id)
        .options(selectinload(PaymentRequestItem.project_item))
    )
    items: list[ProjectItem] = []
    for pri in result.scalars().all():
        if pri.project_item:
            items.append(pri.project_item)
    return items


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

    return req


async def _get_admin_chat_ids(db: AsyncSession) -> list[int]:
    result = await db.execute(
        select(User.telegram_chat_id).where(
            User.role == "admin",
            User.telegram_chat_id.is_not(None),
        )
    )
    return [row[0] for row in result.all()]


def _payment_info_txt(index: int, pay: Payment) -> str:
    from datetime import timezone as _tz
    lines = [
        f"Платёж #{index}",
        f"Сумма: {pay.amount} {pay.currency}",
        f"Дата создания: {pay.created_at.astimezone(_tz.utc).strftime('%d.%m.%Y')}",
        f"Дата оплаты: {pay.payment_date.strftime('%d.%m.%Y') if pay.payment_date else 'не указана'}",
        f"Примечание: {pay.note or '—'}",
    ]
    return "\n".join(lines)


@router_project.get("/download-all-zip")
async def download_all_project_payments_zip(
    project_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Скачать все файлы платежей по всем заявкам проекта в одном ZIP-архиве."""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")

    result = await db.execute(
        select(Payment)
        .join(PaymentRequest, Payment.payment_request_id == PaymentRequest.id)
        .where(PaymentRequest.project_id == project_id, Payment.file_path.isnot(None))
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
        headers={"Content-Disposition": f'attachment; filename="payments_project_{project_id}.zip"'},
    )


@router.get("/download-zip")
async def download_payments_zip(
    req_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Скачать все платежи в ZIP-архиве. Каждый платёж — отдельная папка с info.txt и файлом (если есть)."""
    await _get_request_with_access(req_id, current_user, db)

    result = await db.execute(
        select(Payment)
        .where(Payment.payment_request_id == req_id)
        .order_by(Payment.created_at.asc())
    )
    payments = result.scalars().all()

    if not payments:
        raise HTTPException(status_code=404, detail="Нет платежей для скачивания")

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, pay in enumerate(payments, start=1):
            folder = f"payment_{i}"
            info_text = _payment_info_txt(i, pay)
            zf.writestr(f"{folder}/info.txt", info_text.encode("utf-8"))
            if pay.file_path:
                file_bytes = await file_service.download_file_bytes(pay.file_path)
                if file_bytes is not None:
                    file_name = pay.file_name or f"file_{pay.id}"
                    zf.writestr(f"{folder}/{file_name}", file_bytes)

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
    payment_date: date | None = Form(None),
    file: UploadFile | None = File(None),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaymentOut:
    """Добавить платёж — сразу confirmed, учитывается в остатке заявки."""
    if currency not in ("CNY", "USD", "RUB"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Валюта должна быть CNY, USD или RUB",
        )

    req = await _get_request_with_access(req_id, current_user, db)

    if currency != req.currency:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Валюта платежа ({currency}) не совпадает с валютой заявки ({req.currency})",
        )

    existing_result = await db.execute(
        select(Payment.amount).where(
            Payment.payment_request_id == req_id,
            Payment.status == "confirmed",
        )
    )
    existing_total = sum((row[0] for row in existing_result.all()), Decimal("0"))
    available = req.total_amount - existing_total
    if amount > available:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Сумма платежа превышает остаток по заявке. "
                f"Доступно: {available} {req.currency}"
            ),
        )

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
                detail="Файл слишком большой. Максимум 3 МБ",
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

    now = datetime.now(timezone.utc)
    payment = Payment(
        payment_request_id=req_id,
        amount=amount,
        currency=currency,
        note=note,
        payment_date=payment_date,
        file_path=file_path_val,
        file_name=file_name_val,
        status="confirmed",
        confirmed_by=current_user.id,
        confirmed_at=now,
        created_by=current_user.id,
    )
    db.add(payment)
    await db.flush()

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

    item_names_result = await db.execute(
        select(ProjectItem.name)
        .join(PaymentRequestItem, PaymentRequestItem.project_item_id == ProjectItem.id)
        .where(PaymentRequestItem.payment_request_id == req_id)
    )
    item_names_str = ", ".join(row[0] for row in item_names_result.all())

    file_url_for_notify: str | None = None
    if file_path_val:
        file_url_for_notify = await file_service.get_presigned_url(file_path_val, expires_in=86400)

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

    return PaymentOut.model_validate(payment)


@router.patch("/{pay_id}", response_model=PaymentOut)
async def update_payment(
    req_id: int,
    pay_id: int,
    data: PaymentUpdate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaymentOut:
    """Изменить дату оплаты (admin или автор платежа)."""
    await _get_request_with_access(req_id, current_user, db)

    result = await db.execute(
        select(Payment).where(
            Payment.id == pay_id,
            Payment.payment_request_id == req_id,
        )
    )
    payment = result.scalar_one_or_none()
    if not payment:
        raise HTTPException(status_code=404, detail="Платёж не найден")

    if current_user.role != "admin" and payment.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нет прав на изменение платежа",
        )

    before = audit_service.entity_snapshot(payment)
    payment.payment_date = data.payment_date

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
    return PaymentOut.model_validate(payment)


@router.delete("/{pay_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
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

    request_items = await _load_payment_request_items(req_id, db)
    if not can_delete_payment(current_user, payment, request_items):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нет прав на удаление платежа",
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
