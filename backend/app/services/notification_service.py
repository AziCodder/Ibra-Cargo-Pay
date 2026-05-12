import asyncio
import html
import logging
from decimal import Decimal

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_TG_API = "https://api.telegram.org/bot{token}/sendMessage"

# Shared httpx client (создаётся один раз, переиспользуется)
_http_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=10.0)
    return _http_client


def _configured() -> bool:
    return bool(settings.telegram_bot_token)


async def _send(chat_id: int, text: str) -> None:
    if not _configured():
        return
    url = _TG_API.format(token=settings.telegram_bot_token)
    try:
        client = _get_client()
        r = await client.post(
            url,
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
        )
        if r.status_code != 200:
            logger.warning("Telegram sendMessage failed (chat_id=%s): %s", chat_id, r.text)
    except Exception as exc:
        logger.warning("Telegram notification error (chat_id=%s): %s", chat_id, exc)


def _fire(chat_id: int, text: str) -> None:
    """Fire-and-forget: schedule the send in the running event loop."""
    task = asyncio.create_task(_send(chat_id, text))
    task.add_done_callback(_task_done)


def _task_done(task: asyncio.Task) -> None:
    """Обработчик завершения задачи — логирует ошибки."""
    if task.cancelled():
        return
    exc = task.exception()
    if exc:
        logger.error("Notification task failed: %s", exc, exc_info=exc)


def notify_payment_request_created(
    client_chat_id: int | None,
    project_name: str,
    project_id: int,
    req_id: int,
    total_amount: Decimal,
    currency: str,
    items_names: str,
    payment_details: str | None = None,
    requisites: str | None = None,
) -> None:
    """Уведомить клиента о создании заявки на оплату."""
    if not client_chat_id or not _configured():
        return
    req_link = f"{settings.frontend_url}/projects/{project_id}?req={req_id}"
    proj_link = f"{settings.frontend_url}/projects/{project_id}"
    safe_name = html.escape(project_name)
    safe_items = html.escape(items_names)
    text = (
        f'📋 <b><a href="{req_link}">Новая заявка на оплату #{req_id}</a></b>\n'
        f'Проект: <a href="{proj_link}">{safe_name}</a>\n'
        f"Позиции: {safe_items}\n"
        f"Сумма: {total_amount} {currency}\n"
    )
    if payment_details:
        text += f"\nДетали: {html.escape(payment_details)}\n"
    if requisites:
        text += f"\nРеквизиты:\n{html.escape(requisites)}\n"
    _fire(client_chat_id, text)


def notify_payment_added(
    admin_chat_ids: list[int],
    project_name: str,
    project_id: int,
    req_id: int,
    amount: Decimal,
    currency: str,
    item_names: str | None = None,
    note: str | None = None,
    file_url: str | None = None,
) -> None:
    """Уведомить всех admin-ов о добавлении платежа (админом)."""
    if not admin_chat_ids or not _configured():
        return
    req_link = f"{settings.frontend_url}/projects/{project_id}?req={req_id}"
    proj_link = f"{settings.frontend_url}/projects/{project_id}"
    safe_name = html.escape(project_name)
    text = (
        f'💰 <b><a href="{req_link}">Добавлен платёж по заявке #{req_id}</a></b>\n'
        f'Проект: <a href="{proj_link}">{safe_name}</a>\n'
    )
    if item_names:
        text += f"Позиции: {html.escape(item_names)}\n"
    text += f"Сумма: {amount} {currency}\n"
    if note:
        text += f"Примечание: {html.escape(note)}\n"
    if file_url:
        text += f'<a href="{file_url}">Скачать файл</a>\n'
    for chat_id in admin_chat_ids:
        _fire(chat_id, text)


def notify_payment_pending(
    admin_chat_ids: list[int],
    project_name: str,
    project_id: int,
    req_id: int,
    amount: Decimal,
    currency: str,
    client_login: str,
    item_names: str | None = None,
    note: str | None = None,
    file_url: str | None = None,
) -> None:
    """Клиент отправил платёж — уведомить админов о необходимости подтверждения."""
    if not admin_chat_ids or not _configured():
        return
    req_link = f"{settings.frontend_url}/projects/{project_id}?req={req_id}"
    proj_link = f"{settings.frontend_url}/projects/{project_id}"
    safe_name = html.escape(project_name)
    safe_login = html.escape(client_login)
    text = (
        f'🔔 <b><a href="{req_link}">Новый платёж ожидает подтверждения</a></b>\n'
        f'Проект: <a href="{proj_link}">{safe_name}</a>\n'
        f"Клиент: {safe_login}\n"
    )
    if item_names:
        text += f"Позиции: {html.escape(item_names)}\n"
    text += f"Сумма: {amount} {currency}\n"
    if note:
        text += f"Примечание: {html.escape(note)}\n"
    if file_url:
        text += f'<a href="{file_url}">Скачать файл</a>\n'
    text += "Откройте заявку для подтверждения или отклонения."
    for chat_id in admin_chat_ids:
        _fire(chat_id, text)


def notify_payment_confirmed(
    client_chat_id: int | None,
    project_name: str,
    req_id: int,
    amount: Decimal,
    currency: str,
) -> None:
    """Админ подтвердил платёж — уведомить клиента."""
    if not client_chat_id or not _configured():
        return
    safe_name = html.escape(project_name)
    text = (
        f"✅ <b>Ваш платёж подтверждён</b>\n"
        f"Заявка: #{req_id}\n"
        f"Проект: {safe_name}\n"
        f"Сумма: {amount} {currency}"
    )
    _fire(client_chat_id, text)


def notify_payment_rejected(
    client_chat_id: int | None,
    project_name: str,
    req_id: int,
    amount: Decimal,
    currency: str,
    reason: str,
) -> None:
    """Админ отклонил платёж — уведомить клиента с причиной."""
    if not client_chat_id or not _configured():
        return
    safe_name = html.escape(project_name)
    safe_reason = html.escape(reason)
    text = (
        f"❌ <b>Ваш платёж отклонён</b>\n"
        f"Заявка: #{req_id}\n"
        f"Проект: {safe_name}\n"
        f"Сумма: {amount} {currency}\n"
        f"Причина: {safe_reason}"
    )
    _fire(client_chat_id, text)
