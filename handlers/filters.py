from aiogram.types import Message
from aiogram.filters import BaseFilter

from handlers.services import get_role
# from database.models import User


class IsAdminFilter(BaseFilter):
    async def __call__(self, message: Message):
        role, _, is_admin = await get_role(message)
        return is_admin


class IsTutorFilter(BaseFilter):
    async def __call__(self, message: Message):
        role, _, is_admin = await get_role(message)
        return role == 'tutor'


class IsStudentFilter(BaseFilter):
    async def __call__(self, message: Message):
        role, _, is_admin = await get_role(message)
        return role == 'student'


