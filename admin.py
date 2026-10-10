from datetime import datetime

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from config import ADMIN_ID
from database import (
    add_price_item,
    delete_booking,
    delete_price_item,
    get_all_bookings,
    get_all_price_items,
    get_booking_by_id,
    get_channel_link,
    get_price_item,
    get_schedule_settings,
    get_slots_overview,
    get_stats,
    is_slot_blocked,
    set_setting,
    set_slot_blocked,
    update_price_item,
)
from keyboards import (
    admin_calendar_keyboard,
    admin_day_slots_keyboard,
    admin_menu_keyboard,
    admin_portfolio_keyboard,
    admin_price_item_keyboard,
    admin_prices_keyboard,
    admin_schedule_menu_keyboard,
    admin_schedule_settings_keyboard,
)
from scheduler import cancel_booking_reminder
from utils import normalize_channel_link

router = Router()


class AdminFSM(StatesGroup):
    waiting_delete_id = State()
    waiting_channel_link = State()


class AdminPriceFSM(StatesGroup):
    waiting_new_title = State()
    waiting_new_price = State()
    waiting_edit_title = State()
    waiting_edit_price = State()


def _is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


async def _show_schedule_settings(target):
    settings = await get_schedule_settings()
    text = f"""
⚙️ **Общие настройки расписания**

🕘 Начало работы: **{settings['work_start']}:00**
🕗 Конец работы: **{settings['work_end']}:00**
⏱ Интервал слотов: **{settings['slot_interval']} мин**

Используйте кнопки ниже для изменения.
"""
    await target.answer(text, reply_markup=admin_schedule_settings_keyboard(settings))


async def _show_day_slots(target, date: str):
    slots = await get_slots_overview(date)
    free_count = sum(1 for s in slots if s["status"] == "free")
    blocked_count = sum(1 for s in slots if s["status"] == "blocked")
    booked_count = sum(1 for s in slots if s["status"] == "booked")

    text = f"""
📅 **Слоты на {date}**

✅ Свободно: {free_count}
⛔ Закрыто: {blocked_count}
🔴 Занято: {booked_count}

Нажмите на слот, чтобы открыть/закрыть запись.
🔴 — занято (нельзя изменить)
"""
    await target.answer(text, reply_markup=admin_day_slots_keyboard(date, slots))


@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery):
    await callback.answer()


@router.callback_query(F.data == "admin_panel")
async def cb_admin_panel(callback: CallbackQuery, state: FSMContext):
    """Открыть админ-панель"""
    if not _is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ только для админа!", show_alert=True)
        return

    await state.clear()
    await callback.message.answer(
        "🛠 **Админ-панель**\n\nВыберите действие:",
        reply_markup=admin_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_schedule")
async def cb_admin_schedule(callback: CallbackQuery):
    """Меню управления расписанием"""
    if not _is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ только для админа!", show_alert=True)
        return

    await callback.message.answer(
        "⏰ **Управление расписанием**\n\nВыберите действие:",
        reply_markup=admin_schedule_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_schedule_settings")
async def cb_admin_schedule_settings(callback: CallbackQuery):
    """Показать общие настройки"""
    if not _is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ только для админа!", show_alert=True)
        return

    await _show_schedule_settings(callback.message)
    await callback.answer()


@router.callback_query(F.data.in_({"admin_start_up", "admin_start_down"}))
async def cb_adjust_start(callback: CallbackQuery):
    if not _is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ только для админа!", show_alert=True)
        return

    settings = await get_schedule_settings()
    delta = 1 if callback.data == "admin_start_up" else -1
    new_start = max(6, min(settings["work_start"] + delta, settings["work_end"] - 1))
    await set_setting("work_start", str(new_start))

    settings = await get_schedule_settings()
    await callback.message.edit_text(
        f"⚙️ **Общие настройки расписания**\n\n"
        f"🕘 Начало работы: **{settings['work_start']}:00**\n"
        f"🕗 Конец работы: **{settings['work_end']}:00**\n"
        f"⏱ Интервал слотов: **{settings['slot_interval']} мин**",
        reply_markup=admin_schedule_settings_keyboard(settings),
    )
    await callback.answer()


@router.callback_query(F.data.in_({"admin_end_up", "admin_end_down"}))
async def cb_adjust_end(callback: CallbackQuery):
    if not _is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ только для админа!", show_alert=True)
        return

    settings = await get_schedule_settings()
    delta = 1 if callback.data == "admin_end_up" else -1
    new_end = max(settings["work_start"] + 1, min(settings["work_end"] + delta, 23))
    await set_setting("work_end", str(new_end))

    settings = await get_schedule_settings()
    await callback.message.edit_text(
        f"⚙️ **Общие настройки расписания**\n\n"
        f"🕘 Начало работы: **{settings['work_start']}:00**\n"
        f"🕗 Конец работы: **{settings['work_end']}:00**\n"
        f"⏱ Интервал слотов: **{settings['slot_interval']} мин**",
        reply_markup=admin_schedule_settings_keyboard(settings),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_interval_"))
async def cb_set_interval(callback: CallbackQuery):
    if not _is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ только для админа!", show_alert=True)
        return

    interval = int(callback.data.removeprefix("admin_interval_"))
    await set_setting("slot_interval", str(interval))

    settings = await get_schedule_settings()
    await callback.message.edit_text(
        f"⚙️ **Общие настройки расписания**\n\n"
        f"🕘 Начало работы: **{settings['work_start']}:00**\n"
        f"🕗 Конец работы: **{settings['work_end']}:00**\n"
        f"⏱ Интервал слотов: **{settings['slot_interval']} мин**",
        reply_markup=admin_schedule_settings_keyboard(settings),
    )
    await callback.answer(f"Интервал: {interval} мин")


@router.callback_query(F.data == "admin_schedule_date")
async def cb_admin_schedule_date(callback: CallbackQuery):
    """Выбор даты для управления слотами"""
    if not _is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ только для админа!", show_alert=True)
        return

    now = datetime.now()
    await callback.message.answer(
        "📅 **Выберите дату для управления слотами:**",
        reply_markup=admin_calendar_keyboard(now.year, now.month),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_cal_prev_"))
async def cb_admin_cal_prev(callback: CallbackQuery):
    if not _is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ только для админа!", show_alert=True)
        return

    _, _, _, year, month = callback.data.split("_")
    year, month = int(year), int(month)
    month -= 1
    if month < 1:
        month = 12
        year -= 1

    await callback.message.edit_reply_markup(reply_markup=admin_calendar_keyboard(year, month))
    await callback.answer()


@router.callback_query(F.data.startswith("admin_cal_next_"))
async def cb_admin_cal_next(callback: CallbackQuery):
    if not _is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ только для админа!", show_alert=True)
        return

    _, _, _, year, month = callback.data.split("_")
    year, month = int(year), int(month)
    month += 1
    if month > 12:
        month = 1
        year += 1

    await callback.message.edit_reply_markup(reply_markup=admin_calendar_keyboard(year, month))
    await callback.answer()


@router.callback_query(F.data.startswith("admin_pick_date_"))
async def cb_admin_pick_date(callback: CallbackQuery):
    if not _is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ только для админа!", show_alert=True)
        return

    date_str = callback.data.removeprefix("admin_pick_date_")
    await _show_day_slots(callback.message, date_str)
    await callback.answer()


@router.callback_query(F.data.startswith("admin_toggle_"))
async def cb_admin_toggle_slot(callback: CallbackQuery):
    """Открыть/закрыть слот на дату"""
    if not _is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ только для админа!", show_alert=True)
        return

    parts = callback.data.removeprefix("admin_toggle_").split("_", 1)
    if len(parts) != 2:
        await callback.answer("❌ Ошибка данных", show_alert=True)
        return

    date_str = parts[0]
    time_str = parts[1].replace("-", ":")

    slots = await get_slots_overview(date_str)
    slot = next((s for s in slots if s["time"] == time_str), None)
    if not slot:
        await callback.answer("❌ Слот не найден", show_alert=True)
        return
    if slot["status"] == "booked":
        await callback.answer("❌ Слот занят записью", show_alert=True)
        return

    currently_blocked = await is_slot_blocked(date_str, time_str)
    await set_slot_blocked(date_str, time_str, not currently_blocked)

    status_text = "закрыт" if not currently_blocked else "открыт"
    await callback.answer(f"Слот {time_str} {status_text}")

    slots = await get_slots_overview(date_str)
    free_count = sum(1 for s in slots if s["status"] == "free")
    blocked_count = sum(1 for s in slots if s["status"] == "blocked")
    booked_count = sum(1 for s in slots if s["status"] == "booked")

    await callback.message.edit_text(
        f"📅 **Слоты на {date_str}**\n\n"
        f"✅ Свободно: {free_count}\n"
        f"⛔ Закрыто: {blocked_count}\n"
        f"🔴 Занято: {booked_count}\n\n"
        f"Нажмите на слот, чтобы открыть/закрыть запись.\n"
        f"🔴 — занято (нельзя изменить)",
        reply_markup=admin_day_slots_keyboard(date_str, slots),
    )


@router.callback_query(F.data == "admin_all_bookings")
async def cb_admin_all(callback: CallbackQuery):
    """Показать все записи"""
    if not _is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ только для админа!", show_alert=True)
        return

    bookings = await get_all_bookings()

    if not bookings:
        await callback.message.answer(
            "📋 Записей нет.",
            reply_markup=admin_menu_keyboard(),
        )
        await callback.answer()
        return

    text = "📋 **Все записи:**\n\n"
    for booking in bookings:
        text += (
            f"🔹 ID: {booking[0]} | {booking[1]} | {booking[3]} {booking[4]} | {booking[2]}\n"
        )

    await callback.message.answer(text, reply_markup=admin_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin_delete")
async def cb_admin_delete(callback: CallbackQuery, state: FSMContext):
    """Удалить запись"""
    if not _is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ только для админа!", show_alert=True)
        return

    await state.set_state(AdminFSM.waiting_delete_id)
    await callback.message.answer(
        "🗑 **Введите ID записи для удаления:**",
        reply_markup=admin_menu_keyboard(),
    )
    await callback.answer()


@router.message(AdminFSM.waiting_delete_id)
async def process_delete_booking(message: Message, state: FSMContext):
    """Удалить запись по ID"""
    if not _is_admin(message.from_user.id):
        await message.answer("❌ Доступ только для админа!")
        await state.clear()
        return

    if not message.text or not message.text.strip().isdigit():
        await message.answer("❌ Введите числовой ID записи:")
        return

    booking_id = int(message.text.strip())
    booking = await get_booking_by_id(booking_id)

    if not booking:
        await message.answer(
            f"❌ Запись с ID {booking_id} не найдена.",
            reply_markup=admin_menu_keyboard(),
        )
        await state.clear()
        return

    deleted = await delete_booking(booking_id)
    await state.clear()

    if deleted:
        cancel_booking_reminder(booking_id)
        await message.answer(
            f"✅ Запись ID {booking_id} удалена!",
            reply_markup=admin_menu_keyboard(),
        )
    else:
        await message.answer(
            f"❌ Не удалось удалить запись ID {booking_id}.",
            reply_markup=admin_menu_keyboard(),
        )


@router.callback_query(F.data == "admin_stats")
async def cb_admin_stats(callback: CallbackQuery):
    """Показать статистику"""
    if not _is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ только для админа!", show_alert=True)
        return

    stats = await get_stats()
    settings = await get_schedule_settings()
    await callback.message.answer(
        f"""
📊 **Статистика:**

📋 Всего записей: {stats['total_bookings']}
👥 Уникальных клиентов: {stats['unique_clients']}
📅 Записей на сегодня: {stats['today_bookings']}

⏰ Расписание: {settings['work_start']}:00 – {settings['work_end']}:00, шаг {settings['slot_interval']} мин
""",
        reply_markup=admin_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_portfolio")
async def cb_admin_portfolio(callback: CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ только для админа!", show_alert=True)
        return

    await state.clear()
    link = await get_channel_link()
    await callback.message.answer(
        f"📸 **Ссылка на канал в портфолио**\n\nТекущая: {link or 'не задана'}",
        reply_markup=admin_portfolio_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_portfolio_edit")
async def cb_admin_portfolio_edit(callback: CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ только для админа!", show_alert=True)
        return

    await state.set_state(AdminFSM.waiting_channel_link)
    await callback.message.answer(
        "🔗 **Введите новую ссылку на канал**\n\n"
        "Можно так: `https://t.me/channel`, `t.me/channel` или `@channel`"
    )
    await callback.answer()


@router.message(AdminFSM.waiting_channel_link)
async def process_channel_link(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        await state.clear()
        return

    link = normalize_channel_link(message.text.strip() if message.text else "")
    if not link:
        await message.answer(
            "❌ Это не похоже на ссылку.\n"
            "Отправьте `https://t.me/channel` или `@channel`"
        )
        return

    await set_setting("channel_link", link)
    await state.clear()
    await message.answer(
        f"✅ Ссылка в портфолио обновлена:\n{link}",
        reply_markup=admin_portfolio_keyboard(),
    )


@router.callback_query(F.data == "admin_prices")
async def cb_admin_prices(callback: CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ только для админа!", show_alert=True)
        return

    await state.clear()
    items = await get_all_price_items()
    text = "💰 **Управление прайсом**\n\nНажмите на услугу для редактирования:"
    await callback.message.answer(text, reply_markup=admin_prices_keyboard(items))
    await callback.answer()


@router.callback_query(F.data == "admin_price_add")
async def cb_admin_price_add(callback: CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ только для админа!", show_alert=True)
        return

    await state.set_state(AdminPriceFSM.waiting_new_title)
    await callback.message.answer("➕ **Новая услуга**\n\nВведите название:")
    await callback.answer()


@router.message(AdminPriceFSM.waiting_new_title)
async def admin_price_new_title(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        await state.clear()
        return

    title = message.text.strip() if message.text else ""
    if not title:
        await message.answer("❌ Введите название:")
        return

    await state.update_data(new_title=title)
    await state.set_state(AdminPriceFSM.waiting_new_price)
    await message.answer("💵 Введите цену (число, например 1500):")


@router.message(AdminPriceFSM.waiting_new_price)
async def admin_price_new_price(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        await state.clear()
        return

    if not message.text or not message.text.strip().isdigit():
        await message.answer("❌ Введите цену числом:")
        return

    data = await state.get_data()
    price = int(message.text.strip())
    await add_price_item(data["new_title"], price)
    await state.clear()

    items = await get_all_price_items()
    await message.answer(
        "✅ Услуга добавлена!",
        reply_markup=admin_prices_keyboard(items),
    )


@router.callback_query(F.data.startswith("admin_price_item_"))
async def cb_admin_price_item(callback: CallbackQuery):
    if not _is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ только для админа!", show_alert=True)
        return

    item_id = int(callback.data.removeprefix("admin_price_item_"))
    item = await get_price_item(item_id)
    if not item:
        await callback.answer("❌ Услуга не найдена", show_alert=True)
        return

    await callback.message.answer(
        f"✏️ **{item[1]}**\n\n💵 Цена: **{item[2]}₽**",
        reply_markup=admin_price_item_keyboard(item_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_price_edit_title_"))
async def cb_admin_price_edit_title(callback: CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ только для админа!", show_alert=True)
        return

    item_id = int(callback.data.removeprefix("admin_price_edit_title_"))
    await state.set_state(AdminPriceFSM.waiting_edit_title)
    await state.update_data(price_item_id=item_id)
    await callback.message.answer("📝 Введите новое название услуги:")
    await callback.answer()


@router.callback_query(F.data.startswith("admin_price_edit_price_"))
async def cb_admin_price_edit_price(callback: CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ только для админа!", show_alert=True)
        return

    item_id = int(callback.data.removeprefix("admin_price_edit_price_"))
    await state.set_state(AdminPriceFSM.waiting_edit_price)
    await state.update_data(price_item_id=item_id)
    await callback.message.answer("💵 Введите новую цену (число):")
    await callback.answer()


@router.message(AdminPriceFSM.waiting_edit_title)
async def admin_price_edit_title(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        await state.clear()
        return

    title = message.text.strip() if message.text else ""
    if not title:
        await message.answer("❌ Введите название:")
        return

    data = await state.get_data()
    item_id = data["price_item_id"]
    await update_price_item(item_id, title=title)
    await state.clear()

    item = await get_price_item(item_id)
    await message.answer(
        f"✅ Название обновлено: **{item[1]}**",
        reply_markup=admin_price_item_keyboard(item_id),
    )


@router.message(AdminPriceFSM.waiting_edit_price)
async def admin_price_edit_price(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        await state.clear()
        return

    if not message.text or not message.text.strip().isdigit():
        await message.answer("❌ Введите цену числом:")
        return

    data = await state.get_data()
    item_id = data["price_item_id"]
    price = int(message.text.strip())
    await update_price_item(item_id, price=price)
    await state.clear()

    item = await get_price_item(item_id)
    await message.answer(
        f"✅ Цена обновлена: **{item[2]}₽**",
        reply_markup=admin_price_item_keyboard(item_id),
    )


@router.callback_query(F.data.startswith("admin_price_delete_"))
async def cb_admin_price_delete(callback: CallbackQuery):
    if not _is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ только для админа!", show_alert=True)
        return

    item_id = int(callback.data.removeprefix("admin_price_delete_"))
    deleted = await delete_price_item(item_id)
    if not deleted:
        await callback.answer("❌ Не удалось удалить", show_alert=True)
        return

    items = await get_all_price_items()
    await callback.message.answer(
        "✅ Услуга удалена из прайса.",
        reply_markup=admin_prices_keyboard(items),
    )
    await callback.answer()
