from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from datetime import datetime, timedelta
from aiogram import Bot
from database import get_all_bookings

scheduler = AsyncIOScheduler()


async def send_reminder(
    bot: Bot,
    user_id: int,
    client_name: str,
    booking_time: str,
):
    """Отправить напоминание клиенту за 24 часа до визита"""
    message = f"""
🔔 **Напоминание о визите!**

Дорогой {client_name}!

Ждём вас завтра в {booking_time}.

Ждём вас! 💕
"""
    await bot.send_message(chat_id=user_id, text=message)


async def schedule_booking_reminder(
    bot: Bot,
    booking_id: int,
    user_id: int,
    client_name: str,
    booking_date: str,
    booking_time: str,
):
    """Запланировать напоминание для одной записи"""
    booking_dt = datetime.strptime(f"{booking_date} {booking_time}", "%Y-%m-%d %H:%M")
    reminder_time = booking_dt - timedelta(hours=24)

    if reminder_time <= datetime.now():
        return

    scheduler.add_job(
        send_reminder,
        trigger=DateTrigger(run_date=reminder_time),
        args=[bot, user_id, client_name, booking_time],
        id=f"reminder_{booking_id}",
        replace_existing=True,
    )


async def setup_reminders(bot: Bot):
    """Загрузить напоминания для всех существующих записей"""
    bookings = await get_all_bookings()
    for booking in bookings:
        booking_id = booking[0]
        client_name = booking[1]
        booking_date = booking[3]
        booking_time = booking[4]
        user_id = booking[5]

        await schedule_booking_reminder(
            bot,
            booking_id,
            user_id,
            client_name,
            booking_date,
            booking_time,
        )


def start_scheduler():
    """Запустить планировщик"""
    if not scheduler.running:
        scheduler.start()


def stop_scheduler():
    """Остановить планировщик"""
    if scheduler.running:
        scheduler.shutdown(wait=False)


def cancel_booking_reminder(booking_id: int):
    """Убрать запланированное напоминание"""
    job_id = f"reminder_{booking_id}"
    job = scheduler.get_job(job_id)
    if job:
        scheduler.remove_job(job_id)
