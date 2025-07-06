from datetime import datetime
from functools import wraps
from pathlib import Path

from loguru import logger
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.state import StatesGroup, State
from sqlalchemy import select
from aiogram.fsm.state import StatesGroup, State
from aiogram.filters import StateFilter

from conf import get_db
from database.models import Admin, Tutor, Student, Parent


async def get_role(message: Message):
    async with get_db() as db:

        result = await db.execute(select(Admin).where(Admin.telegram_id == message.from_user.id))
        admin = result.scalars().first()
        if admin:
            return 'admin', admin, admin.is_admin

        result = await db.execute(select(Tutor).where(Tutor.telegram_id == message.from_user.id))
        tutor = result.scalars().first()
        if tutor:
            return 'tutor', tutor, tutor.is_admin

        result = await db.execute(select(Student).where(Student.telegram_id == message.from_user.id))
        student = result.scalars().first()
        if student:
            return 'student', student, student.is_admin

        result = await db.execute(select(Parent).where(Parent.telegram_id == message.from_user.id))
        parent = result.scalars().first()
        if parent:
            return 'parent', parent, False

        return 'unknown', None, False


class AddTutorStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_telegram_id = State()


class RegistrationState(StatesGroup):
    waiting_for_name = State()


class CreateUserStates(StatesGroup):
    choosing_role = State()
    entering_data = State()


class PaymentStates(StatesGroup):
    waiting_for_lesson_count = State()
    waiting_for_screenshot = State()


async def parse_auto_type(value: str):
    val = value.strip()

    # Bool
    if val.lower() in ("true", "1", "yes", "да"):
        return True
    if val.lower() in ("false", "0", "no", "нет"):
        return False

    # Int
    try:
        return int(val)
    except ValueError:
        pass

    # Float
    try:
        return float(val)
    except ValueError:
        pass

    # Вернуть как строку
    return val


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

    return file_path


def logging(func):
    @wraps(func)
    async def wrapper(message, *args, **kwargs):
        logger.info(f"User {message.from_user.full_name} sent: {message.text}")
        try:
            return await func(message, *args, **kwargs)
        except Exception as e:
            logger.exception(f"Handler {func.__name__} failed: {e}")
            raise
    return wrapper
