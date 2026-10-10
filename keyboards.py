from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from config import ADMIN_ID, CHANNEL_LINK


def main_menu_keyboard(user_id: int | None = None) -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="📅 Записаться", callback_data="book_appointment")],
        [InlineKeyboardButton(text="💰 Прайсы", callback_data="prices")],
        [InlineKeyboardButton(text="📸 Портфолио", callback_data="portfolio")],
        [InlineKeyboardButton(text="👤 Мои записи", callback_data="my_bookings")],
    ]
    if user_id is not None and user_id == ADMIN_ID:
        kb.append([InlineKeyboardButton(text="🛠 Админ-панель", callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def my_bookings_keyboard(bookings: list) -> InlineKeyboardMarkup:
    """Кнопки отмены для будущих записей."""
    from datetime import datetime

    kb = []
    now = datetime.now()
    for booking in bookings:
        booking_id = booking[0]
        date_str = booking[3]
        time_str = booking[4]
        booking_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        if booking_dt > now:
            kb.append([
                InlineKeyboardButton(
                    text=f"✏️ Изменить {date_str} {time_str}",
                    callback_data=f"edit_booking_{booking_id}",
                ),
                InlineKeyboardButton(
                    text=f"❌ Отменить",
                    callback_data=f"cancel_booking_{booking_id}",
                ),
            ])

    kb.append([InlineKeyboardButton(text="◀️ В меню", callback_data="back_to_menu")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def edit_booking_menu_keyboard(booking_id: int) -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="👤 Изменить имя", callback_data=f"edit_field_name_{booking_id}")],
        [InlineKeyboardButton(text="📞 Изменить телефон", callback_data=f"edit_field_phone_{booking_id}")],
        [InlineKeyboardButton(text="📅 Изменить дату/время", callback_data=f"edit_field_datetime_{booking_id}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="my_bookings")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def admin_prices_keyboard(items: list) -> InlineKeyboardMarkup:
    kb = []
    for item in items:
        kb.append([
            InlineKeyboardButton(
                text=f"✏️ {item[1]} — {item[2]}₽",
                callback_data=f"admin_price_item_{item[0]}",
            )
        ])
    kb.append([InlineKeyboardButton(text="➕ Добавить услугу", callback_data="admin_price_add")])
    kb.append([InlineKeyboardButton(text="◀️ В админ-панель", callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def admin_price_item_keyboard(item_id: int) -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="📝 Изменить название", callback_data=f"admin_price_edit_title_{item_id}")],
        [InlineKeyboardButton(text="💵 Изменить цену", callback_data=f"admin_price_edit_price_{item_id}")],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"admin_price_delete_{item_id}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_prices")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def admin_portfolio_keyboard() -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="✏️ Изменить ссылку", callback_data="admin_portfolio_edit")],
        [InlineKeyboardButton(text="◀️ В админ-панель", callback_data="admin_panel")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def cancel_booking_confirm_keyboard(booking_id: int) -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="✅ Да, отменить", callback_data=f"confirm_cancel_{booking_id}")],
        [InlineKeyboardButton(text="❌ Нет", callback_data="my_bookings")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def subscribe_keyboard(channel_link: str | None = None) -> InlineKeyboardMarkup:
    link = channel_link or CHANNEL_LINK
    kb = []
    if link:
        kb.append([InlineKeyboardButton(text="📢 Подписаться", url=link)])
    kb.extend([
        [InlineKeyboardButton(text="✅ Проверить подписку", callback_data="check_subscription")],
        [InlineKeyboardButton(text="❌ Назад", callback_data="back_to_menu")],
    ])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def calendar_keyboard(year: int, month: int) -> InlineKeyboardMarkup:
    from calendar import monthcalendar

    kb = []

    month_names = [
        "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
        "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
    ]

    kb.append([
        InlineKeyboardButton(text="◀️", callback_data=f"cal_prev_{year}_{month}"),
        InlineKeyboardButton(text=f"{month_names[month - 1]} {year}", callback_data="cal_current"),
        InlineKeyboardButton(text="▶️", callback_data=f"cal_next_{year}_{month}"),
    ])

    week_days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    kb.append([InlineKeyboardButton(text=d, callback_data="disabled") for d in week_days])

    cal = monthcalendar(year, month)
    today = datetime_now_date()
    for week in cal:
        week_kb = []
        for day in week:
            if day == 0:
                week_kb.append(InlineKeyboardButton(text=" ", callback_data="disabled"))
            else:
                date_str = f"{year}-{month:02d}-{day:02d}"
                if date_str < today:
                    week_kb.append(InlineKeyboardButton(text="·", callback_data="disabled"))
                else:
                    week_kb.append(
                        InlineKeyboardButton(text=str(day), callback_data=f"date_{date_str}")
                    )
        kb.append(week_kb)

    kb.append([InlineKeyboardButton(text="❌ Назад", callback_data="back_to_menu")])

    return InlineKeyboardMarkup(inline_keyboard=kb)


def datetime_now_date() -> str:
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d")


def time_keyboard(slots: list) -> InlineKeyboardMarkup:
    kb = []
    for slot in slots:
        kb.append([InlineKeyboardButton(text=slot, callback_data=f"time_{slot}")])
    kb.append([InlineKeyboardButton(text="❌ Назад", callback_data="back_to_calendar")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def admin_menu_keyboard() -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="📋 Все записи", callback_data="admin_all_bookings")],
        [InlineKeyboardButton(text="🗑 Удалить запись", callback_data="admin_delete")],
        [InlineKeyboardButton(text="⏰ Расписание", callback_data="admin_schedule")],
        [InlineKeyboardButton(text="💰 Прайс", callback_data="admin_prices")],
        [InlineKeyboardButton(text="📸 Ссылка портфолио", callback_data="admin_portfolio")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="❌ Назад", callback_data="back_to_menu")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def admin_schedule_menu_keyboard() -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="⚙️ Общие настройки", callback_data="admin_schedule_settings")],
        [InlineKeyboardButton(text="📅 Слоты на дату", callback_data="admin_schedule_date")],
        [InlineKeyboardButton(text="◀️ В админ-панель", callback_data="admin_panel")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def admin_schedule_settings_keyboard(settings: dict) -> InlineKeyboardMarkup:
    kb = [
        [
            InlineKeyboardButton(text="➖", callback_data="admin_start_down"),
            InlineKeyboardButton(text=f"Начало: {settings['work_start']}:00", callback_data="noop"),
            InlineKeyboardButton(text="➕", callback_data="admin_start_up"),
        ],
        [
            InlineKeyboardButton(text="➖", callback_data="admin_end_down"),
            InlineKeyboardButton(text=f"Конец: {settings['work_end']}:00", callback_data="noop"),
            InlineKeyboardButton(text="➕", callback_data="admin_end_up"),
        ],
        [
            InlineKeyboardButton(text="30 мин", callback_data="admin_interval_30"),
            InlineKeyboardButton(text="60 мин", callback_data="admin_interval_60"),
            InlineKeyboardButton(text="90 мин", callback_data="admin_interval_90"),
            InlineKeyboardButton(text="120 мин", callback_data="admin_interval_120"),
        ],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_schedule")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def admin_calendar_keyboard(year: int, month: int) -> InlineKeyboardMarkup:
    from calendar import monthcalendar

    kb = []
    month_names = [
        "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
        "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
    ]

    kb.append([
        InlineKeyboardButton(text="◀️", callback_data=f"admin_cal_prev_{year}_{month}"),
        InlineKeyboardButton(text=f"{month_names[month - 1]} {year}", callback_data="noop"),
        InlineKeyboardButton(text="▶️", callback_data=f"admin_cal_next_{year}_{month}"),
    ])

    week_days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    kb.append([InlineKeyboardButton(text=d, callback_data="noop") for d in week_days])

    cal = monthcalendar(year, month)
    today = datetime_now_date()
    for week in cal:
        week_kb = []
        for day in week:
            if day == 0:
                week_kb.append(InlineKeyboardButton(text=" ", callback_data="noop"))
            else:
                date_str = f"{year}-{month:02d}-{day:02d}"
                if date_str < today:
                    week_kb.append(InlineKeyboardButton(text="·", callback_data="noop"))
                else:
                    week_kb.append(
                        InlineKeyboardButton(text=str(day), callback_data=f"admin_pick_date_{date_str}")
                    )
        kb.append(week_kb)

    kb.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin_schedule")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def _encode_time(time_str: str) -> str:
    return time_str.replace(":", "-")


def _decode_time(encoded: str) -> str:
    return encoded.replace("-", ":")


def admin_day_slots_keyboard(date: str, slots: list) -> InlineKeyboardMarkup:
    """Кнопки слотов: ✅ свободен, 🔴 занят, ⛔ закрыт."""
    kb = []
    row = []
    for slot in slots:
        time_str = slot["time"]
        status = slot["status"]
        if status == "booked":
            label = f"🔴 {time_str}"
            callback = "noop"
        elif status == "blocked":
            label = f"⛔ {time_str}"
            callback = f"admin_toggle_{date}_{_encode_time(time_str)}"
        else:
            label = f"✅ {time_str}"
            callback = f"admin_toggle_{date}_{_encode_time(time_str)}"

        row.append(InlineKeyboardButton(text=label, callback_data=callback))
        if len(row) == 2:
            kb.append(row)
            row = []
    if row:
        kb.append(row)

    kb.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin_schedule_date")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def confirm_keyboard() -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_yes")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="confirm_no")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)
