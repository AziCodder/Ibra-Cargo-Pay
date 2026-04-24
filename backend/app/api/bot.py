from fastapi import APIRouter, Depends, HTTPException, Header, status
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User

router = APIRouter(prefix="/api/bot", tags=["bot"])


class LinkRequest(BaseModel):
    token: str
    telegram_chat_id: int


@router.post("/verify-link", status_code=status.HTTP_200_OK)
async def verify_link(
    data: LinkRequest,
    x_bot_secret: str = Header(..., alias="X-Bot-Secret"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if x_bot_secret != settings.bot_secret:
        raise HTTPException(status_code=403, detail="Неверный секрет бота")

    try:
        payload = jwt.decode(
            data.token, settings.secret_key, algorithms=[settings.algorithm]
        )
        if payload.get("type") != "tg_link":
            raise JWTError("Invalid token type")
        user_id = int(payload["sub"])
    except (JWTError, ValueError, KeyError):
        raise HTTPException(
            status_code=400, detail="Недействительный или просроченный токен"
        )

    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    # Проверяем, что этот chat_id не занят другим пользователем
    existing = await db.execute(
        select(User).where(
            User.telegram_chat_id == data.telegram_chat_id,
            User.id != user_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="Этот Telegram аккаунт уже привязан к другому пользователю",
        )

    user.telegram_chat_id = data.telegram_chat_id
    await db.commit()
    return {"success": True, "user_id": user_id, "full_name": user.full_name}
