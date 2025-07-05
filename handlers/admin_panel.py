from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from handlers.filters import IsAdminFilter
from database.db_scripts import get_unregistered_users, get_model_fields, ROLE_MODEL_MAP, add_user, delete_user
from handlers.services import CreateUserStates
from conf import logger
from handlers.services import parse_auto_type


admin_router = Router()
admin_router.message.filter(IsAdminFilter())


# Base Admin buttons
def admin_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Добавить преподавателя")],
            [KeyboardButton(text="➕ Добавить ученика")],
            [KeyboardButton(text="⚙️ Настройки")]
        ],
        resize_keyboard=True
    )


# Tutor add logic
@admin_router.message(F.text == "➕ Добавить преподавателя")
async def show_unregistered_users(message: Message):
    users = await get_unregistered_users()
    if not users:
        await message.answer("Нет новых пользователей")
        return
    kb_builder = InlineKeyboardBuilder()
    for user in users:
        kb_builder.add(
            InlineKeyboardButton(
                text=f"{user.username} (ID: {user.telegram_id})",
                callback_data=f"assign_role:{user.username}:{user.telegram_id}"
            )
        )
    await message.answer("Выбери пользователя для назначения роли:",
                         reply_markup=kb_builder.as_markup())


@admin_router.callback_query(F.data.startswith("assign_role:"))
async def choose_role(callback: CallbackQuery):
    username = callback.data.split(":")[1]
    telegram_id = callback.data.split(":")[2]

    kb_builder = InlineKeyboardBuilder()
    for role in ["student", "tutor"]:
        kb_builder.add(
            InlineKeyboardButton(
                text=role.capitalize(),
                callback_data=f"set_role:{telegram_id}:{role}"
            )
        )
    await callback.message.delete()
    await callback.message.answer(
        f"Выбери роль для пользователя {username}:",
        reply_markup=kb_builder.as_markup()
    )
    await callback.answer()


@admin_router.callback_query(F.data.startswith("set_role:"))
async def set_user_role(callback: CallbackQuery):
    _, telegram_id, role = callback.data.split(":")

    # TODO: ТУТ ТЫ ЗАПИСЫВАЕШЬ В БД, ЧТО ТАКОМУ telegram_id ПРИСВОЕНА РОЛЬ
    # например, вызовешь create_user_with_role(telegram_id, role)

    print(f"Назначить роль '{role}' пользователю с ID {telegram_id}")
    # await create_user_with_role(int(telegram_id), role)

    await callback.message.answer(
        f"✅ Пользователю с ID {telegram_id} назначена роль '{role}'."
    )
    await callback.answer()




