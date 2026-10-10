import re
from datetime import datetime, timedelta

_PHONE_DIGITS_RE = re.compile(r"\D")


def normalize_phone(raw: str) -> str | None:
    """Проверить, что строка похожа на телефон, и привести к +цифры."""
    if not raw:
        return None

    text = raw.strip()
    if not text or len(text) > 24:
        return None
    if not re.fullmatch(r"[\d+\-\s().]+", text):
        return None

    digits = _PHONE_DIGITS_RE.sub("", text)
    if not digits:
        return None

    if not text.startswith("+"):
        if len(digits) == 11 and digits.startswith("8"):
            digits = "7" + digits[1:]
        elif len(digits) == 10 and digits.startswith("9"):
            digits = "7" + digits

    if not (8 <= len(digits) <= 15):
        return None
    if len(set(digits)) == 1:
        return None

    return "+" + digits


def normalize_channel_link(raw: str) -> str | None:
    """Привести ссылку на канал к https://t.me/... или https://..."""
    if not raw:
        return None

    text = raw.strip()
    if not text or len(text) > 256:
        return None

    if text.startswith("@"):
        username = text[1:]
        if re.fullmatch(r"[A-Za-z0-9_]{5,32}", username):
            return f"https://t.me/{username}"
        return None

    if text.startswith("t.me/"):
        text = "https://" + text

    if not re.match(r"^https://", text, re.IGNORECASE):
        return None

    return text


def format_date(date_str: str) -> str:
    """Форматировать дату"""
    date = datetime.strptime(date_str, "%Y-%m-%d")
    return date.strftime("%d.%m.%Y")


def format_booking(booking: tuple) -> str:
    """Форматировать запись для отображения"""
    return f"""
📅 **Дата:** {format_date(booking[3])}
⏰ **Время:** {booking[4]}
👤 **Клиент:** {booking[1]}
📞 **Телефон:** {booking[2]}
"""


def is_within_24_hours(date_str: str, time_str: str) -> bool:
    """Проверить, что запись в течение 24 часов"""
    booking_time = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    now = datetime.now()
    return (booking_time - now) < timedelta(hours=24)


async def check_subscription(bot, user_id: int, channel_id: str) -> bool:
    """Проверить подписку пользователя на канал"""
    try:
        member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception:
        return False


async def notify_admin_new_booking(
    bot,
    booking_id: int,
    client_name: str,
    client_phone: str,
    booking_date: str,
    booking_time: str,
    user_id: int,
    username: str | None = None,
):
    """Уведомить админа о новой записи"""
    from config import ADMIN_ID
    import logging

    logger = logging.getLogger(__name__)
    client_info = f"@{username}" if username else f"ID {user_id}"

    text = f"""
🆕 **Новая запись #{booking_id}**

👤 Имя: {client_name}
📞 Телефон: {client_phone}
📅 Дата: {booking_date}
⏰ Время: {booking_time}
💬 Клиент: {client_info}
"""
    try:
        await bot.send_message(chat_id=ADMIN_ID, text=text)
    except Exception as e:
        logger.error("Не удалось отправить уведомление админу: %s", e)


async def format_prices_text() -> str:
    from database import get_all_price_items

    items = await get_all_price_items()
    if not items:
        return "💰 **Прайсы:**\n\nПрайс пока не настроен."

    lines = ["💰 **Прайсы:**", ""]
    for item in items:
        lines.append(f"💅 {item[1]}: {item[2]}₽")
    return "\n".join(lines)


async def notify_admin_booking_updated(
    bot,
    booking_id: int,
    client_name: str,
    client_phone: str,
    booking_date: str,
    booking_time: str,
    user_id: int,
    username: str | None = None,
):
    from config import ADMIN_ID
    import logging

    logger = logging.getLogger(__name__)
    client_info = f"@{username}" if username else f"ID {user_id}"
    text = f"""
✏️ **Запись изменена #{booking_id}**

👤 {client_name}
📞 {client_phone}
📅 {booking_date} в {booking_time}
💬 {client_info}
"""
    try:
        await bot.send_message(chat_id=ADMIN_ID, text=text)
    except Exception as e:
        logger.error("Не удалось отправить уведомление админу: %s", e)


async def notify_admin_cancelled_booking(
    bot,
    booking_id: int,
    client_name: str,
    booking_date: str,
    booking_time: str,
    user_id: int,
    username: str | None = None,
):
    """Уведомить админа об отмене записи клиентом"""
    from config import ADMIN_ID
    import logging

    logger = logging.getLogger(__name__)
    client_info = f"@{username}" if username else f"ID {user_id}"

    text = f"""
🚫 **Запись отменена клиентом #{booking_id}**

👤 {client_name}
📅 {booking_date} в {booking_time}
💬 {client_info}
"""
    try:
        await bot.send_message(chat_id=ADMIN_ID, text=text)
    except Exception as e:
        logger.error("Не удалось отправить уведомление админу: %s", e)
