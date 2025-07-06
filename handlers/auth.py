from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext

from handlers.admin_panel import admin_kb
from handlers.tutor_panel import tutor_kb
from handlers.student_panel import student_kb
from handlers.parent_panel import parent_kb
from handlers.services import get_role
from database.db_scripts import add_stack
from handlers.services import RegistrationState


auth = Router()


@auth.message(Command("start"))
async def start_handler(message: Message, state: FSMContext):
    role, user, is_admin = await get_role(message)

    if role == 'admin':
        await message.answer(text=f"✅ Привет, {user.name}! Ты админ.",
                             reply_markup=admin_kb())
    elif role == 'tutor':
        await message.answer(f"✅ Привет, {user.name}! Ты тьютор.",
                             reply_markup=tutor_kb())
    elif role == 'student':
        await message.answer(f"✅ Привет, {user.name}! Ты студент.",
                             reply_markup=student_kb())
    elif role == 'parent':
        await message.answer(f"✅ Здравствуйте, {user.name}! вы родитель.",
                             reply_markup=parent_kb())
    else:
        await message.answer(
            "📝 Пожалуйста, введите свою Фамилию и Имя (например: Иванов Иван):",
            reply_markup=ReplyKeyboardRemove()
        )
        await state.set_state(RegistrationState.waiting_for_name)


@auth.message(RegistrationState.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    name = message.text.strip()
    telegram_id = message.from_user.id

    # Добавляем в stack
    await add_stack(telegram_id=telegram_id, name=name)

    # Отвечаем пользователю
    await message.answer(
        "✅ Спасибо! Ваши данные записаны.\n"
        "Дождитесь регистрации администратором."
    )

    # Сбрасываем состояние
    await state.clear()
