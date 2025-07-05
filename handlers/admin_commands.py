from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, FSInputFile
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

from database.db_scripts import ROLE_MODEL_MAP, add_user, delete_user, get_model_fields, generate_table_image
from handlers.services import CreateUserStates, parse_auto_type
from conf import logger
from database.models import Student

dev_router = Router()


@dev_router.message(F.text.startswith("/delete_user"))
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


@dev_router.message(F.text == "/create_user")
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


@dev_router.message(CreateUserStates.choosing_role, F.text.in_(ROLE_MODEL_MAP.keys()))
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


@dev_router.message(F.text.startswith("/show_db"))
async def send_students_image(message: Message):
    filename = await generate_table_image(Student, limit=10)
    if filename:
        await message.answer_photo(FSInputFile(filename))
    else:
        await message.answer("Нет данных в таблице.")



