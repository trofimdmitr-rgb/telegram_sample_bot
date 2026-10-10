import logging
from datetime import datetime

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from config import CHANNEL_ID
from database import (
    add_booking,
    cancel_booking_by_user,
    get_booking,
    get_booking_by_id,
    get_bookings_by_user,
    get_channel_link,
    get_free_slots,
    update_booking,
)
from keyboards import (
    calendar_keyboard,
    cancel_booking_confirm_keyboard,
    confirm_keyboard,
    edit_booking_menu_keyboard,
    main_menu_keyboard,
    my_bookings_keyboard,
    subscribe_keyboard,
    time_keyboard,
)
from scheduler import cancel_booking_reminder, schedule_booking_reminder
from utils import (
    check_subscription,
    format_prices_text,
    normalize_phone,
    notify_admin_booking_updated,
    notify_admin_cancelled_booking,
    notify_admin_new_booking,
)

logger = logging.getLogger(__name__)

router = Router()


class BookingFSM(StatesGroup):
    waiting_name = State()
    waiting_date = State()
    waiting_time = State()
    waiting_phone = State()
    confirming = State()


class EditBookingFSM(StatesGroup):
    waiting_name = State()
    waiting_phone = State()
    waiting_date = State()
    waiting_time = State()


def _menu(user_id: int):
    return main_menu_keyboard(user_id)


def _booking_is_future(booking) -> bool:
    booking_dt = datetime.strptime(f"{booking[3]} {booking[4]}", "%Y-%m-%d %H:%M")
    return booking_dt > datetime.now()


async def _after_booking_updated(bot, booking_id: int, user_id: int, username: str | None):
    booking = await get_booking_by_id(booking_id)
    if not booking:
        return

    cancel_booking_reminder(booking_id)
    await schedule_booking_reminder(
        bot,
        booking_id,
        user_id,
        booking[1],
        booking[3],
        booking[4],
    )
    await notify_admin_booking_updated(
        bot,
        booking_id,
        booking[1],
        booking[2],
        booking[3],
        booking[4],
        user_id,
        username,
    )


async def _require_subscription(callback: CallbackQuery) -> bool:
    """Проверить подписку; при отсутствии показать сообщение."""
    if await check_subscription(callback.bot, callback.from_user.id, CHANNEL_ID):
        return True

    channel_link = await get_channel_link()
    await callback.message.answer(
        f"📢 Для записи подпишитесь на наш канал:\n{channel_link}",
        reply_markup=subscribe_keyboard(channel_link),
    )
    return False


@router.callback_query(F.data == "check_subscription")
async def cb_check_subscription(callback: CallbackQuery, state: FSMContext):
    """Повторная проверка подписки"""
    if await check_subscription(callback.bot, callback.from_user.id, CHANNEL_ID):
        await state.set_state(BookingFSM.waiting_name)
        await callback.message.answer("✅ Подписка подтверждена!\n\n📝 **Для записи введите ваше имя:**")
    else:
        channel_link = await get_channel_link()
        await callback.message.answer(
            f"❌ Вы ещё не подписаны.\n\nПодпишитесь на канал:\n{channel_link}",
            reply_markup=subscribe_keyboard(channel_link),
        )
    await callback.answer()


@router.callback_query(F.data == "book_appointment")
async def cb_book_appointment(callback: CallbackQuery, state: FSMContext):
    """Начать запись"""
    if not await _require_subscription(callback):
        await callback.answer()
        return

    await state.set_state(BookingFSM.waiting_name)
    await callback.message.answer("📝 **Для записи введите ваше имя:**")
    await callback.answer()


@router.message(BookingFSM.waiting_name)
async def process_name(message: Message, state: FSMContext):
    """Сохранить имя"""
    name = message.text.strip() if message.text else ""
    if not name:
        await message.answer("❌ Пожалуйста, введите имя:")
        return

    await state.update_data(name=name)
    now = datetime.now()
    await message.answer(
        "📅 **Выберите дату записи:**",
        reply_markup=calendar_keyboard(now.year, now.month),
    )
    await state.set_state(BookingFSM.waiting_date)
    logger.info(f"Имя сохранено: {name}")


@router.callback_query(F.data.startswith("cal_prev_"))
async def cb_cal_prev(callback: CallbackQuery):
    """Предыдущий месяц"""
    _, _, year, month = callback.data.split("_")
    year, month = int(year), int(month)
    month -= 1
    if month < 1:
        month = 12
        year -= 1

    await callback.message.edit_reply_markup(
        reply_markup=calendar_keyboard(year, month)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cal_next_"))
async def cb_cal_next(callback: CallbackQuery):
    """Следующий месяц"""
    _, _, year, month = callback.data.split("_")
    year, month = int(year), int(month)
    month += 1
    if month > 12:
        month = 1
        year += 1

    await callback.message.edit_reply_markup(
        reply_markup=calendar_keyboard(year, month)
    )
    await callback.answer()


@router.callback_query(F.data == "cal_current")
async def cb_cal_current(callback: CallbackQuery):
    """Текущий месяц — без действия"""
    await callback.answer()


@router.callback_query(F.data == "disabled")
async def cb_disabled(callback: CallbackQuery):
    """Неактивные кнопки календаря"""
    await callback.answer()


@router.callback_query(F.data == "back_to_calendar")
async def cb_back_calendar(callback: CallbackQuery, state: FSMContext):
    """Вернуться к выбору даты"""
    now = datetime.now()
    await callback.message.edit_text(
        "📅 **Выберите дату записи:**",
        reply_markup=calendar_keyboard(now.year, now.month),
    )
    await state.set_state(BookingFSM.waiting_date)
    await callback.answer()


@router.callback_query(F.data.startswith("date_"), BookingFSM.waiting_date)
async def cb_select_date(callback: CallbackQuery, state: FSMContext):
    """Выбрать дату"""
    date_str = callback.data.removeprefix("date_")
    today = datetime.now().strftime("%Y-%m-%d")

    if date_str < today:
        await callback.answer("❌ Нельзя записаться на прошедшую дату", show_alert=True)
        return

    free_slots = await get_free_slots(date_str)
    if not free_slots:
        await callback.message.answer(
            "❌ На эту дату все слоты заняты! Выберите другую дату.",
            reply_markup=calendar_keyboard(
                int(date_str[:4]),
                int(date_str[5:7]),
            ),
        )
        await callback.answer()
        return

    await state.update_data(date=date_str)
    await callback.message.answer(
        f"✅ Дата: {date_str}\n\n**Свободные слоты:**",
        reply_markup=time_keyboard(free_slots),
    )
    await state.set_state(BookingFSM.waiting_time)
    await callback.answer()


@router.callback_query(F.data.startswith("time_"), BookingFSM.waiting_time)
async def cb_select_time(callback: CallbackQuery, state: FSMContext):
    """Выбрать время"""
    time_str = callback.data.removeprefix("time_")
    await state.update_data(time=time_str)

    await callback.message.answer(
        f"✅ Время: {time_str}\n\n**Введите ваш телефон** (например, +7 999 123-45-67 или +1 212 555 0123):"
    )
    await state.set_state(BookingFSM.waiting_phone)
    await callback.answer()


@router.message(BookingFSM.waiting_phone)
async def process_phone(message: Message, state: FSMContext):
    """Сохранить телефон и подтвердить"""
    raw_phone = ""
    if message.contact and message.contact.phone_number:
        raw_phone = message.contact.phone_number
    elif message.text:
        raw_phone = message.text.strip()

    phone = normalize_phone(raw_phone)
    if not phone:
        await message.answer(
            "❌ Это не похоже на настоящий номер.\n"
            "Введите телефон, например: `+7 999 123-45-67` или `+1 212 555-0123`"
        )
        return

    data = await state.get_data()
    date_str = data.get("date")
    time_str = data.get("time")

    if date_str and time_str:
        existing = await get_booking(date_str, time_str)
        if existing:
            await message.answer(
                "❌ Этот слот уже занят! Выберите другое время.",
                reply_markup=_menu(message.from_user.id),
            )
            await state.clear()
            return

    await state.update_data(phone=phone)
    data = await state.get_data()

    await message.answer(
        f"""
📝 **Подтвердите запись:**

👤 Имя: {data['name']}
📞 Телефон: {data['phone']}
📅 Дата: {date_str}
⏰ Время: {time_str}
""",
        reply_markup=confirm_keyboard(),
    )
    await state.set_state(BookingFSM.confirming)


@router.callback_query(F.data == "confirm_yes", BookingFSM.confirming)
async def cb_confirm(callback: CallbackQuery, state: FSMContext):
    """Подтвердить запись"""
    data = await state.get_data()
    date_str = data.get("date")
    time_str = data.get("time")

    existing = await get_booking(date_str, time_str)
    if existing:
        await callback.message.answer(
            "❌ Этот слот уже занят! Выберите другое время.",
            reply_markup=_menu(callback.from_user.id),
        )
        await state.clear()
        await callback.answer()
        return

    booking_id = await add_booking(
        client_name=data["name"],
        client_phone=data["phone"],
        booking_date=date_str,
        booking_time=time_str,
        user_id=callback.from_user.id,
    )

    await schedule_booking_reminder(
        callback.bot,
        booking_id,
        callback.from_user.id,
        data["name"],
        date_str,
        time_str,
    )

    await notify_admin_new_booking(
        callback.bot,
        booking_id,
        data["name"],
        data["phone"],
        date_str,
        time_str,
        callback.from_user.id,
        callback.from_user.username,
    )

    await callback.message.answer(
        "✅ **Запись успешно создана!**\n\nЖдём вас! 💕",
        reply_markup=_menu(callback.from_user.id),
    )
    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "confirm_no", BookingFSM.confirming)
async def cb_cancel(callback: CallbackQuery, state: FSMContext):
    """Отменить оформление записи"""
    await callback.message.answer(
        "❌ Запись отменена.",
        reply_markup=_menu(callback.from_user.id),
    )
    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "prices")
async def cb_prices(callback: CallbackQuery):
    """Показать прайсы"""
    text = await format_prices_text()
    await callback.message.answer(text, reply_markup=_menu(callback.from_user.id))
    await callback.answer()


@router.callback_query(F.data == "portfolio")
async def cb_portfolio(callback: CallbackQuery):
    """Показать портфолио"""
    channel_link = await get_channel_link()
    if channel_link:
        text = (
            "📸 **Портфолио:**\n\n"
            f"Наши работы в Telegram-канале:\n[{channel_link}]({channel_link})"
        )
    else:
        text = "📸 **Портфолио:**\n\nСсылка на канал пока не задана."
    await callback.message.answer(text, reply_markup=_menu(callback.from_user.id))
    await callback.answer()


@router.callback_query(F.data == "my_bookings")
async def cb_my_bookings(callback: CallbackQuery):
    """Показать мои записи"""
    bookings = await get_bookings_by_user(callback.from_user.id)

    if not bookings:
        await callback.message.answer(
            "📋 У вас нет записей.",
            reply_markup=_menu(callback.from_user.id),
        )
    else:
        text = "📋 **Мои записи:**\n\n"
        for booking in bookings:
            text += f"🔹 #{booking[0]} | {booking[3]} {booking[4]} | {booking[1]} | {booking[2]}\n"

        await callback.message.answer(
            text,
            reply_markup=my_bookings_keyboard(bookings),
        )

    await callback.answer()


@router.callback_query(F.data.startswith("edit_booking_"))
async def cb_edit_booking(callback: CallbackQuery, state: FSMContext):
    """Меню изменения записи"""
    booking_id = int(callback.data.removeprefix("edit_booking_"))
    booking = await get_booking_by_id(booking_id)

    if not booking or booking[5] != callback.from_user.id:
        await callback.answer("❌ Запись не найдена", show_alert=True)
        return
    if not _booking_is_future(booking):
        await callback.answer("❌ Нельзя изменить прошедшую запись", show_alert=True)
        return

    await state.clear()
    await callback.message.answer(
        f"""
✏️ **Изменение записи #{booking_id}**

👤 {booking[1]}
📞 {booking[2]}
📅 {booking[3]} в {booking[4]}

Что изменить?
""",
        reply_markup=edit_booking_menu_keyboard(booking_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("edit_field_name_"))
async def cb_edit_field_name(callback: CallbackQuery, state: FSMContext):
    booking_id = int(callback.data.removeprefix("edit_field_name_"))
    booking = await get_booking_by_id(booking_id)
    if not booking or booking[5] != callback.from_user.id or not _booking_is_future(booking):
        await callback.answer("❌ Запись недоступна", show_alert=True)
        return

    await state.set_state(EditBookingFSM.waiting_name)
    await state.update_data(booking_id=booking_id)
    await callback.message.answer(
        f"Текущее имя: **{booking[1]}**\n\nВведите новое имя:"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("edit_field_phone_"))
async def cb_edit_field_phone(callback: CallbackQuery, state: FSMContext):
    booking_id = int(callback.data.removeprefix("edit_field_phone_"))
    booking = await get_booking_by_id(booking_id)
    if not booking or booking[5] != callback.from_user.id or not _booking_is_future(booking):
        await callback.answer("❌ Запись недоступна", show_alert=True)
        return

    await state.set_state(EditBookingFSM.waiting_phone)
    await state.update_data(booking_id=booking_id)
    await callback.message.answer(
        f"Текущий телефон: **{booking[2]}**\n\nВведите новый телефон (например, +7 999 123-45-67 или +1 212 555 0123):"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("edit_field_datetime_"))
async def cb_edit_field_datetime(callback: CallbackQuery, state: FSMContext):
    booking_id = int(callback.data.removeprefix("edit_field_datetime_"))
    booking = await get_booking_by_id(booking_id)
    if not booking or booking[5] != callback.from_user.id or not _booking_is_future(booking):
        await callback.answer("❌ Запись недоступна", show_alert=True)
        return

    await state.set_state(EditBookingFSM.waiting_date)
    await state.update_data(booking_id=booking_id)
    now = datetime.now()
    await callback.message.answer(
        "📅 **Выберите новую дату:**",
        reply_markup=calendar_keyboard(now.year, now.month),
    )
    await callback.answer()


@router.message(EditBookingFSM.waiting_name)
async def edit_process_name(message: Message, state: FSMContext):
    name = message.text.strip() if message.text else ""
    if not name:
        await message.answer("❌ Введите имя:")
        return

    data = await state.get_data()
    booking_id = data["booking_id"]
    updated = await update_booking(booking_id, message.from_user.id, client_name=name)
    await state.clear()

    if not updated:
        await message.answer("❌ Не удалось изменить запись.", reply_markup=_menu(message.from_user.id))
        return

    await _after_booking_updated(
        message.bot, booking_id, message.from_user.id, message.from_user.username
    )
    await message.answer(
        f"✅ Имя в записи #{booking_id} обновлено!",
        reply_markup=_menu(message.from_user.id),
    )


@router.message(EditBookingFSM.waiting_phone)
async def edit_process_phone(message: Message, state: FSMContext):
    raw_phone = ""
    if message.contact and message.contact.phone_number:
        raw_phone = message.contact.phone_number
    elif message.text:
        raw_phone = message.text.strip()

    phone = normalize_phone(raw_phone)
    if not phone:
        await message.answer(
            "❌ Это не похоже на настоящий номер.\n"
            "Введите телефон, например: `+7 999 123-45-67` или `+1 212 555-0123`"
        )
        return

    data = await state.get_data()
    booking_id = data["booking_id"]
    updated = await update_booking(booking_id, message.from_user.id, client_phone=phone)
    await state.clear()

    if not updated:
        await message.answer("❌ Не удалось изменить запись.", reply_markup=_menu(message.from_user.id))
        return

    await _after_booking_updated(
        message.bot, booking_id, message.from_user.id, message.from_user.username
    )
    await message.answer(
        f"✅ Телефон в записи #{booking_id} обновлён!",
        reply_markup=_menu(message.from_user.id),
    )


@router.callback_query(F.data.startswith("date_"), EditBookingFSM.waiting_date)
async def edit_select_date(callback: CallbackQuery, state: FSMContext):
    date_str = callback.data.removeprefix("date_")
    today = datetime.now().strftime("%Y-%m-%d")
    if date_str < today:
        await callback.answer("❌ Нельзя выбрать прошедшую дату", show_alert=True)
        return

    data = await state.get_data()
    booking_id = data["booking_id"]
    free_slots = await get_free_slots(date_str, exclude_booking_id=booking_id)
    if not free_slots:
        await callback.message.answer(
            "❌ На эту дату нет свободных слотов.",
            reply_markup=calendar_keyboard(int(date_str[:4]), int(date_str[5:7])),
        )
        await callback.answer()
        return

    await state.update_data(date=date_str)
    await callback.message.answer(
        f"✅ Дата: {date_str}\n\n**Выберите время:**",
        reply_markup=time_keyboard(free_slots),
    )
    await state.set_state(EditBookingFSM.waiting_time)
    await callback.answer()


@router.callback_query(F.data.startswith("time_"), EditBookingFSM.waiting_time)
async def edit_select_time(callback: CallbackQuery, state: FSMContext):
    time_str = callback.data.removeprefix("time_")
    data = await state.get_data()
    booking_id = data["booking_id"]
    date_str = data["date"]

    updated = await update_booking(
        booking_id,
        callback.from_user.id,
        booking_date=date_str,
        booking_time=time_str,
    )
    await state.clear()

    if not updated:
        await callback.message.answer(
            "❌ Этот слот занят. Выберите другое время.",
            reply_markup=_menu(callback.from_user.id),
        )
        await callback.answer()
        return

    await _after_booking_updated(
        callback.bot, booking_id, callback.from_user.id, callback.from_user.username
    )
    await callback.message.answer(
        f"✅ Запись #{booking_id} перенесена на {date_str} {time_str}",
        reply_markup=_menu(callback.from_user.id),
    )
    await callback.answer()


@router.callback_query(F.data == "back_to_calendar", EditBookingFSM.waiting_time)
async def edit_back_to_calendar(callback: CallbackQuery, state: FSMContext):
    now = datetime.now()
    await callback.message.edit_text(
        "📅 **Выберите новую дату:**",
        reply_markup=calendar_keyboard(now.year, now.month),
    )
    await state.set_state(EditBookingFSM.waiting_date)
    await callback.answer()


@router.callback_query(F.data.startswith("cancel_booking_"))
async def cb_cancel_booking(callback: CallbackQuery):
    """Запросить подтверждение отмены записи"""
    booking_id = int(callback.data.removeprefix("cancel_booking_"))
    booking = await get_booking_by_id(booking_id)

    if not booking or booking[5] != callback.from_user.id:
        await callback.answer("❌ Запись не найдена", show_alert=True)
        return

    await callback.message.answer(
        f"""
⚠️ **Отменить запись?**

📅 {booking[3]} в {booking[4]}
👤 {booking[1]}
""",
        reply_markup=cancel_booking_confirm_keyboard(booking_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_cancel_"))
async def cb_confirm_cancel(callback: CallbackQuery):
    """Подтвердить отмену записи"""
    booking_id = int(callback.data.removeprefix("confirm_cancel_"))
    booking = await get_booking_by_id(booking_id)

    if not booking or booking[5] != callback.from_user.id:
        await callback.answer("❌ Запись не найдена", show_alert=True)
        return

    cancelled = await cancel_booking_by_user(booking_id, callback.from_user.id)
    if not cancelled:
        await callback.answer("❌ Не удалось отменить запись", show_alert=True)
        return

    cancel_booking_reminder(booking_id)

    await notify_admin_cancelled_booking(
        callback.bot,
        booking_id,
        booking[1],
        booking[3],
        booking[4],
        callback.from_user.id,
        callback.from_user.username,
    )

    await callback.message.answer(
        f"✅ Запись #{booking_id} отменена.",
        reply_markup=_menu(callback.from_user.id),
    )
    await callback.answer()


@router.callback_query(F.data == "back_to_menu")
async def cb_back_menu(callback: CallbackQuery, state: FSMContext):
    """Назад в меню"""
    await state.clear()
    await callback.message.answer(
        "Выберите действие:",
        reply_markup=_menu(callback.from_user.id),
    )
    await callback.answer()
