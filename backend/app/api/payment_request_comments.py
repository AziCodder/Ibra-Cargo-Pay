"""
API комментариев к заявкам на оплату.

Просмотр доступен всем с доступом к проекту, добавление тоже всем,
удаление — автору или admin. Схемы — в schemas/payment_request_comment.py.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.payment_request import PaymentRequest
from app.models.payment_request_comment import PaymentRequestComment
from app.schemas.payment_request_comment import CommentCreate, CommentOut
from app.services import audit_service

router = APIRouter(
    prefix="/api/payment-requests/{req_id}/comments", tags=["payment-request-comments"]
)


async def _load_request_and_check_access(
    req_id: int, db: AsyncSession, current_user
) -> PaymentRequest:
    request_q = (
        select(PaymentRequest)
        .where(PaymentRequest.id == req_id)
        .options(selectinload(PaymentRequest.project))
    )
    req = (await db.execute(request_q)).scalar_one_or_none()
    if req is None:
        raise HTTPException(status_code=404, detail="Заявка на оплату не найдена")
    return req


def _comment_out(comment: PaymentRequestComment) -> CommentOut:
    return CommentOut(
        id=comment.id,
        payment_request_id=comment.payment_request_id,
        author_id=comment.author_id,
        author_login=comment.author.login if comment.author else "—",
        author_full_name=comment.author.full_name if comment.author else "—",
        text=comment.text,
        created_at=comment.created_at,
    )


@router.get("", response_model=list[CommentOut])
async def list_comments(
    req_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CommentOut]:
    await _load_request_and_check_access(req_id, db, current_user)

    result = await db.execute(
        select(PaymentRequestComment)
        .where(PaymentRequestComment.payment_request_id == req_id)
        .options(selectinload(PaymentRequestComment.author))
        .order_by(PaymentRequestComment.created_at.asc())
    )
    comments = result.scalars().all()
    return [_comment_out(c) for c in comments]


@router.post("", response_model=CommentOut, status_code=status.HTTP_201_CREATED)
async def create_comment(
    req_id: int,
    data: CommentCreate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CommentOut:
    await _load_request_and_check_access(req_id, db, current_user)

    comment = PaymentRequestComment(
        payment_request_id=req_id,
        author_id=current_user.id,
        text=data.text.strip(),
    )
    db.add(comment)
    await db.flush()

    await audit_service.log_action(
        db,
        user_id=current_user.id,
        action="created",
        entity_type="payment_request_comment",
        entity_id=comment.id,
        after=audit_service.entity_snapshot(comment),
    )

    await db.commit()
    await db.refresh(comment)

    # Подгружаем author для CommentOut
    result = await db.execute(
        select(PaymentRequestComment)
        .where(PaymentRequestComment.id == comment.id)
        .options(selectinload(PaymentRequestComment.author))
    )
    loaded = result.scalar_one()
    return _comment_out(loaded)


@router.delete("/{comment_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_comment(
    req_id: int,
    comment_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _load_request_and_check_access(req_id, db, current_user)

    result = await db.execute(
        select(PaymentRequestComment).where(
            PaymentRequestComment.id == comment_id,
            PaymentRequestComment.payment_request_id == req_id,
        )
    )
    comment = result.scalar_one_or_none()
    if comment is None:
        raise HTTPException(status_code=404, detail="Комментарий не найден")

    if current_user.role != "admin" and comment.author_id != current_user.id:
        raise HTTPException(status_code=403, detail="Можно удалять только свои комментарии")

    before_snapshot = audit_service.entity_snapshot(comment)
    comment_id_local = comment.id

    await db.delete(comment)
    await db.flush()

    await audit_service.log_action(
        db,
        user_id=current_user.id,
        action="deleted",
        entity_type="payment_request_comment",
        entity_id=comment_id_local,
        before=before_snapshot,
    )

    await db.commit()
