from functools import wraps
from loguru import logger
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.state import StatesGroup, State
from sqlalchemy import select
from aiogram.fsm.state import StatesGroup, State
from aiogram.filters import StateFilter

from conf import get_db
from database.models import Admin, Tutor, Student


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

        return 'unknown', None, None


class AddTutorStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_telegram_id = State()


class RegistrationState(StatesGroup):
    waiting_for_name = State()


class CreateUserStates(StatesGroup):
    choosing_role = State()
    entering_data = State()


def parse_auto_type(value: str):
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
