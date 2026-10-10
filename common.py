from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from keyboards import main_menu_keyboard, admin_menu_keyboard
from config import ADMIN_ID

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message):
    """Обработка команды /start"""
    await message.answer(
        "👋 **Добро пожаловать!**\n\n"
        "Я бот мастера по маникюру. Запишусь на визит, покажу прайсы и портфолио!\n\n"
        "Выберите действие:",
        reply_markup=main_menu_keyboard(message.from_user.id)
    )


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    """Обработка команды /admin - админ панель"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Доступ только для админа!")
        return

    await message.answer(
        "🛠 **Админ-панель**\n\nВыберите действие:",
        reply_markup=admin_menu_keyboard()
    )