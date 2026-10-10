import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramNetworkError
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, PROXY_URL
from database import init_db
from handlers import admin, client, common
from scheduler import setup_reminders, start_scheduler, stop_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)

logger = logging.getLogger(__name__)


def create_bot() -> Bot:
    session_kwargs = {}
    if PROXY_URL:
        session_kwargs["proxy"] = PROXY_URL
        logger.info("Используется прокси: %s", PROXY_URL)

    session = AiohttpSession(**session_kwargs)
    return Bot(
        token=BOT_TOKEN,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )


bot = create_bot()
dp = Dispatcher(storage=MemoryStorage())

dp.include_router(common.router)
dp.include_router(client.router)
dp.include_router(admin.router)


async def verify_telegram_connection() -> None:
    """Проверить доступ к Telegram API до старта polling."""
    try:
        me = await bot.get_me()
        logger.info("Подключение OK, бот: @%s", me.username)
    except TelegramNetworkError as e:
        hint = (
            "\n\nНе удалось подключиться к api.telegram.org.\n"
            "Что проверить:\n"
            "  1. Включён ли VPN\n"
            "  2. Добавьте в .env прокси, например:\n"
            "     PROXY_URL=socks5://127.0.0.1:1080\n"
            "  3. Установите: pip install aiohttp-socks"
        )
        raise ConnectionError(f"{e}{hint}") from e


async def main():
    try:
        logger.info("Инициализация БД...")
        await init_db()
        logger.info("БД инициализирована")

        start_scheduler()
        await setup_reminders(bot)
        logger.info("Напоминания загружены")

        await verify_telegram_connection()

        logger.info("Запуск бота...")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        raise
    finally:
        stop_scheduler()
        await bot.session.close()


if __name__ == "__main__":
    try:
        logger.info("Начало запуска bot.py")
        asyncio.run(main())
        logger.info("Бот завершил работу")
    except Exception as e:
        logger.error(f"Ошибка запуска: {e}")
        print(f"\nОшибка: {e}")
        sys.exit(1)
