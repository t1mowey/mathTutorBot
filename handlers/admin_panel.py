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


@admin_router.message(F.text == "/create_user")
async def start_create_user(message: Message, state: FSMContext):
    await message.answer("Выбери роль нового пользователя:", reply_markup=ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Ученик")],
            [KeyboardButton(text="Преподаватель")],
            [KeyboardButton(text="Администратор")]
                  ],
        resize_keyboard=True,
        one_time_keyboard=True
    ))
    await state.set_state(CreateUserStates.choosing_role)


@admin_router.message(CreateUserStates.choosing_role, F.text.in_(ROLE_MODEL_MAP.keys()))
async def get_role(message: Message, state: FSMContext):
    role = message.text
    await state.update_data(role=role)

    model = ROLE_MODEL_MAP[role]
    fields = await get_model_fields(model)
    await state.update_data(fields=fields)

    await message.answer(
        f"Введи значения для роли '{role}' через запятую:\n" +
        ", ".join(fields)
    )

    await state.set_state(CreateUserStates.entering_data)


@admin_router.message(CreateUserStates.entering_data)
async def process_data(message: Message, state: FSMContext):
    data = await state.get_data()
    role = data["role"]
    fields = data["fields"]
    values = [v.strip() for v in message.text.strip().split(",")]

    if len(values) != len(fields):
        return await message.answer(f"❌ Ожидалось {len(fields)} значений, а введено {len(values)}.")

    model_class = ROLE_MODEL_MAP[role]
    try:
        kwargs = dict(zip(fields, values))

        for key in kwargs:
            kwargs[key] = parse_auto_type(kwargs[key])

        instance = model_class(**kwargs)
        success, result = await add_user(instance)

        await message.answer(result)
    except Exception as e:
        await message.answer(f"❌ Ошибка при обработке данных: {e}")
        logger.exception(f"Ошибка создания пользователя {role}")

    await state.clear()


@admin_router.message(F.text.startswith("/delete_user"))
async def delete_user_direct(message: Message):
    try:
        parts = message.text.split()
        if len(parts) != 3:
            return await message.answer("❌ Используй формат: /delete_user <role> <telegram_id>")

        _, role, tid = parts
        if role not in ROLE_MODEL_MAP:
            return await message.answer(f"❌ Роль {role} не распознана. Возможные: {', '.join(ROLE_MODEL_MAP)}")

        telegram_id = int(tid)
        model = ROLE_MODEL_MAP[role]

        await delete_user(model, telegram_id, message)

    except Exception as e:
        logger.exception("Ошибка при удалении пользователя")
        await message.answer(f"❌ Ошибка: {e}")