from pathlib import Path

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData
from datetime import datetime

from database.db_scripts import get_students_for_tutor, decrease_student_credit
from handlers.filters import IsStudentFilter
from conf import logger


student_router = Router()
student_router.message.filter(IsStudentFilter())


def student_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Оплата")],
            [KeyboardButton(text="---------")],
            [KeyboardButton(text="---------")]
        ],
        resize_keyboard=True
    )


async def save_user_image(message: Message):
    user_id = message.from_user.id

    # 1. Получаем файл
    if not message.photo:
        return await message.answer("Пришли фото.")
    file = message.photo[-1]  # самое большое изображение
    tg_file = await message.bot.get_file(file.file_id)

    # 2. Создаём папку пользователя
    user_dir = Path(f"uploads/{user_id}")
    user_dir.mkdir(parents=True, exist_ok=True)

    # 3. Формируем имя файла
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    file_name = f"{timestamp}.jpg"
    file_path = user_dir / file_name

    # 4. Сохраняем файл
    await message.bot.download_file(tg_file.file_path, destination=file_path)

    # 5. Сохраняем путь в БД (пример)
    # save_image_path_to_db(user_id, str(file_path))

    await message.answer(f"Фото сохранено как: {file_path}")


@student_router.message(F.text == '➕ Оплата')
def start_payment(message: Message, state: FSMContext):
    ...
