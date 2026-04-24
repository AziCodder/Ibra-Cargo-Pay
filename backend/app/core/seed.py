import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash

logger = logging.getLogger(__name__)


async def seed_admin(db: AsyncSession) -> None:
    """Create the default admin account if it does not exist."""
    from app.models.user import User  # local import to avoid circular deps

    result = await db.execute(select(User).where(User.login == "admin"))
    if result.scalar_one_or_none() is not None:
        return

    import os
    default_password = os.getenv("ADMIN_DEFAULT_PASSWORD", "admin")
    admin = User(
        full_name="Администратор",
        login="admin",
        password_hash=get_password_hash(default_password),
        role="admin",
    )
    db.add(admin)
    await db.commit()
    logger.info("Default admin user created (login: admin). Change password immediately!")
