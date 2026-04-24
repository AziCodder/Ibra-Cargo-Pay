import asyncio
import logging
import os

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")
BOT_SECRET = os.getenv("BOT_SECRET", "")


async def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN is not set. Bot cannot start.")
        import sys
        sys.exit(1)

    import httpx
    from aiogram import Bot, Dispatcher
    from aiogram.filters import CommandStart
    from aiogram.types import Message

    bot = Bot(token=token)
    dp = Dispatcher()

    @dp.message(CommandStart())
    async def handle_start(message: Message) -> None:
        # Извлекаем аргумент после /start
        args = (message.text or "").split(maxsplit=1)
        link_token = args[1].strip() if len(args) >= 2 and args[1].strip() else None

        if not link_token:
            await message.answer(
                "👋 Привет! Я бот для уведомлений системы управления проектами.\n\n"
                "Чтобы привязать свой аккаунт и получать уведомления, "
                "попросите администратора сгенерировать вам токен привязки "
                "и отправьте его командой:\n<code>/start ВАШ_ТОКЕН</code>",
                parse_mode="HTML",
            )
            return

        chat_id = message.from_user.id  # type: ignore[union-attr]

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{BACKEND_URL}/api/bot/verify-link",
                    json={"token": link_token, "telegram_chat_id": chat_id},
                    headers={"X-Bot-Secret": BOT_SECRET},
                )
            if resp.status_code == 200:
                data = resp.json()
                full_name = data.get("full_name", "")
                await message.answer(
                    f"✅ Аккаунт успешно привязан!\n"
                    f"Теперь вы будете получать уведомления, {full_name}.",
                )
            else:
                detail = resp.json().get("detail", "Ошибка привязки")
                await message.answer(f"❌ {detail}")
        except Exception as exc:
            logger.error("Error linking Telegram account: %s", exc, exc_info=True)
            await message.answer(
                "❌ Не удалось подключиться к серверу. Попробуйте позже."
            )

    logger.info("Telegram bot starting (polling)...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
