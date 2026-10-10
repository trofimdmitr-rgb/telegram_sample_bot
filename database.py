import aiosqlite
from datetime import datetime
from typing import List, Optional, Tuple
from config import CHANNEL_LINK, WORK_START, WORK_END, SLOT_INTERVAL

DB_PATH = "salon.db"

SETTING_KEYS = ("work_start", "work_end", "slot_interval", "channel_link")


async def _seed_default_settings():
    """Заполнить настройки расписания из config, если их ещё нет."""
    async with aiosqlite.connect(DB_PATH) as db:
        for key, value in (
            ("work_start", str(WORK_START)),
            ("work_end", str(WORK_END)),
            ("slot_interval", str(SLOT_INTERVAL)),
            ("channel_link", CHANNEL_LINK),
        ):
            await db.execute(
                """
                INSERT INTO settings (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO NOTHING
                """,
                (key, value),
            )
        await db.commit()


async def get_setting(key: str, default: str) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT value FROM settings WHERE key = ?",
            (key,),
        )
        row = await cursor.fetchone()
        return row[0] if row else default


async def set_setting(key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )
        await db.commit()


async def get_channel_link() -> str:
    return await get_setting("channel_link", CHANNEL_LINK)


async def get_schedule_settings() -> dict:
    work_start = int(await get_setting("work_start", str(WORK_START)))
    work_end = int(await get_setting("work_end", str(WORK_END)))
    slot_interval = int(await get_setting("slot_interval", str(SLOT_INTERVAL)))
    return {
        "work_start": work_start,
        "work_end": work_end,
        "slot_interval": slot_interval,
    }


def _format_slot_time(total_minutes: int) -> str:
    hours = total_minutes // 60
    minutes = total_minutes % 60
    return f"{hours}:{minutes:02d}"


def _generate_time_slots(work_start: int, work_end: int, slot_interval: int) -> List[str]:
    slots = []
    current_minutes = work_start * 60
    end_minutes = work_end * 60
    while current_minutes < end_minutes:
        slots.append(_format_slot_time(current_minutes))
        current_minutes += slot_interval
    return slots


async def get_blocked_slots(date: str) -> set:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT booking_time FROM blocked_slots WHERE booking_date = ?",
            (date,),
        )
        rows = await cursor.fetchall()
        return {row[0] for row in rows}


async def is_slot_blocked(date: str, time: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            SELECT 1 FROM blocked_slots
            WHERE booking_date = ? AND booking_time = ?
            """,
            (date, time),
        )
        return await cursor.fetchone() is not None


async def set_slot_blocked(date: str, time: str, blocked: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        if blocked:
            await db.execute(
                """
                INSERT INTO blocked_slots (booking_date, booking_time)
                VALUES (?, ?)
                ON CONFLICT(booking_date, booking_time) DO NOTHING
                """,
                (date, time),
            )
        else:
            await db.execute(
                "DELETE FROM blocked_slots WHERE booking_date = ? AND booking_time = ?",
                (date, time),
            )
        await db.commit()


async def get_slots_overview(date: str) -> List[dict]:
    """Все слоты на дату со статусом: free / booked / blocked."""
    settings = await get_schedule_settings()
    all_slots = _generate_time_slots(
        settings["work_start"],
        settings["work_end"],
        settings["slot_interval"],
    )
    occupied = await get_bookings_by_date(date)
    occupied_times = {row[4] for row in occupied}
    blocked_times = await get_blocked_slots(date)

    result = []
    for slot in all_slots:
        if slot in occupied_times:
            status = "booked"
        elif slot in blocked_times:
            status = "blocked"
        else:
            status = "free"
        result.append({"time": slot, "status": status})
    return result


async def init_db():
    """Инициализация базы данных"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_name TEXT NOT NULL,
                client_phone TEXT NOT NULL,
                booking_date TEXT NOT NULL,
                booking_time TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS clients (
                user_id INTEGER PRIMARY KEY,
                name TEXT,
                phone TEXT,
                subscribed BOOLEAN DEFAULT FALSE
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS blocked_slots (
                booking_date TEXT NOT NULL,
                booking_time TEXT NOT NULL,
                PRIMARY KEY (booking_date, booking_time)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS price_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                price INTEGER NOT NULL,
                sort_order INTEGER DEFAULT 0
            )
        """)

        await db.commit()
        await _seed_default_settings()
        await _seed_default_prices()


DEFAULT_PRICES = (
    ("Маникюр с покрытием", 1500),
    ("Наращивание ресниц", 2000),
    ("Коррекция", 1200),
    ("Снятие", 500),
)


async def _seed_default_prices():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM price_items")
        count = (await cursor.fetchone())[0]
        if count == 0:
            for order, (title, price) in enumerate(DEFAULT_PRICES):
                await db.execute(
                    "INSERT INTO price_items (title, price, sort_order) VALUES (?, ?, ?)",
                    (title, price, order),
                )
            await db.commit()


async def get_all_price_items() -> List[Tuple]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id, title, price, sort_order FROM price_items ORDER BY sort_order, id"
        )
        return await cursor.fetchall()


async def get_price_item(item_id: int) -> Optional[Tuple]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id, title, price, sort_order FROM price_items WHERE id = ?",
            (item_id,),
        )
        return await cursor.fetchone()


async def add_price_item(title: str, price: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COALESCE(MAX(sort_order), -1) + 1 FROM price_items"
        )
        sort_order = (await cursor.fetchone())[0]
        cursor = await db.execute(
            "INSERT INTO price_items (title, price, sort_order) VALUES (?, ?, ?)",
            (title.strip(), price, sort_order),
        )
        await db.commit()
        return cursor.lastrowid


async def update_price_item(item_id: int, title: str | None = None, price: int | None = None) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        item = await get_price_item(item_id)
        if not item:
            return False
        new_title = title.strip() if title else item[1]
        new_price = price if price is not None else item[2]
        await db.execute(
            "UPDATE price_items SET title = ?, price = ? WHERE id = ?",
            (new_title, new_price, item_id),
        )
        await db.commit()
        return True


async def delete_price_item(item_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("DELETE FROM price_items WHERE id = ?", (item_id,))
        await db.commit()
        return cursor.rowcount > 0


async def add_booking(
    client_name: str,
    client_phone: str,
    booking_date: str,
    booking_time: str,
    user_id: int,
) -> int:
    """Добавить запись"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO bookings (client_name, client_phone, booking_date, booking_time, user_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (client_name, client_phone, booking_date, booking_time, user_id),
        )
        await db.commit()
        return cursor.lastrowid


async def get_booking(date: str, time: str) -> Optional[Tuple]:
    """Получить запись по дате и времени"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            SELECT * FROM bookings
            WHERE booking_date = ? AND booking_time = ?
            """,
            (date, time),
        )
        return await cursor.fetchone()


async def get_booking_by_id(booking_id: int) -> Optional[Tuple]:
    """Получить запись по ID"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT * FROM bookings WHERE id = ?",
            (booking_id,),
        )
        return await cursor.fetchone()


async def get_all_bookings() -> List[Tuple]:
    """Получить все записи"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT * FROM bookings ORDER BY booking_date, booking_time"
        )
        return await cursor.fetchall()


async def get_bookings_by_date(date: str) -> List[Tuple]:
    """Получить записи по дате"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            SELECT * FROM bookings
            WHERE booking_date = ?
            ORDER BY booking_time
            """,
            (date,),
        )
        return await cursor.fetchall()


async def delete_booking(booking_id: int) -> bool:
    """Удалить запись. Возвращает True, если запись была удалена."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM bookings WHERE id = ?",
            (booking_id,),
        )
        await db.commit()
        return cursor.rowcount > 0


async def cancel_booking_by_user(booking_id: int, user_id: int) -> bool:
    """Отменить запись клиентом (только свою)."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM bookings WHERE id = ? AND user_id = ?",
            (booking_id, user_id),
        )
        await db.commit()
        return cursor.rowcount > 0


async def get_free_slots(date: str, exclude_booking_id: int | None = None) -> List[str]:
    """Получить свободные слоты на дату"""
    settings = await get_schedule_settings()
    all_slots = _generate_time_slots(
        settings["work_start"],
        settings["work_end"],
        settings["slot_interval"],
    )
    occupied = await get_bookings_by_date(date)
    occupied_times = {row[4] for row in occupied}
    blocked_times = await get_blocked_slots(date)

    if exclude_booking_id:
        excluded = await get_booking_by_id(exclude_booking_id)
        if excluded and excluded[3] == date:
            occupied_times.discard(excluded[4])

    return [
        slot for slot in all_slots
        if slot not in occupied_times and slot not in blocked_times
    ]


async def update_booking(
    booking_id: int,
    user_id: int,
    client_name: str | None = None,
    client_phone: str | None = None,
    booking_date: str | None = None,
    booking_time: str | None = None,
) -> bool:
    """Обновить запись клиента (только свою)."""
    booking = await get_booking_by_id(booking_id)
    if not booking or booking[5] != user_id:
        return False

    new_name = client_name.strip() if client_name else booking[1]
    new_phone = client_phone.strip() if client_phone else booking[2]
    new_date = booking_date or booking[3]
    new_time = booking_time or booking[4]

    if (new_date, new_time) != (booking[3], booking[4]):
        conflict = await get_booking(new_date, new_time)
        if conflict and conflict[0] != booking_id:
            return False

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            UPDATE bookings
            SET client_name = ?, client_phone = ?, booking_date = ?, booking_time = ?
            WHERE id = ? AND user_id = ?
            """,
            (new_name, new_phone, new_date, new_time, booking_id, user_id),
        )
        await db.commit()
        return cursor.rowcount > 0


async def update_client_subscription(user_id: int, subscribed: bool):
    """Обновить подписку клиента"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO clients (user_id, subscribed)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET subscribed = ?
            """,
            (user_id, subscribed, subscribed),
        )
        await db.commit()


async def get_client_subscription(user_id: int) -> bool:
    """Получить статус подписки клиента"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT subscribed FROM clients WHERE user_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        return bool(row[0]) if row else False


async def get_bookings_by_user(user_id: int) -> List[Tuple]:
    """Получить записи пользователя"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            SELECT * FROM bookings
            WHERE user_id = ?
            ORDER BY booking_date, booking_time
            """,
            (user_id,),
        )
        return await cursor.fetchall()


async def get_stats() -> dict:
    """Статистика для админ-панели"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM bookings")
        total_bookings = (await cursor.fetchone())[0]

        cursor = await db.execute("SELECT COUNT(DISTINCT user_id) FROM bookings")
        unique_clients = (await cursor.fetchone())[0]

        today = datetime.now().strftime("%Y-%m-%d")
        cursor = await db.execute(
            "SELECT COUNT(*) FROM bookings WHERE booking_date = ?",
            (today,),
        )
        today_bookings = (await cursor.fetchone())[0]

        return {
            "total_bookings": total_bookings,
            "unique_clients": unique_clients,
            "today_bookings": today_bookings,
        }
