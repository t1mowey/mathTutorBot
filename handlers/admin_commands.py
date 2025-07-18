from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, FSInputFile, ReplyKeyboardRemove, CallbackQuery
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

from database.db_scripts import ROLE_MODEL_MAP_RU, ROLE_MODEL_MAP_ENG, add_user, delete_user, get_model_fields, generate_table_image
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
        if role not in ROLE_MODEL_MAP_RU:
            return await message.answer(f"❌ Роль {role} не распознана. Возможные: {', '.join(ROLE_MODEL_MAP_RU)}")

        telegram_id = int(tid)
        model = ROLE_MODEL_MAP_RU[role]

        await delete_user(model, telegram_id, message)

    except Exception as e:
        logger.exception("Ошибка при удалении пользователя")
        await message.answer(f"❌ Ошибка: {e}")


@dev_router.message(F.text == "/create_user")
async def start_create_user(message: Message, state: FSMContext):
    await message.answer("Выбери роль нового пользователя:", reply_markup=InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Ученик", callback_data='Student')],
            [InlineKeyboardButton(text="Родитель", callback_data='Parent')],
            [InlineKeyboardButton(text="Преподаватель", callback_data='Tutor')],
            [InlineKeyboardButton(text="Администратор", callback_data='Admin')]
                  ]
    ))
    await state.set_state(CreateUserStates.choosing_role)


@dev_router.callback_query(CreateUserStates.choosing_role, F.data.in_(ROLE_MODEL_MAP_ENG.keys()))
async def get_role(callback: CallbackQuery, state: FSMContext):
    role = callback.data
    await state.update_data(role=role)

    model = ROLE_MODEL_MAP_ENG[role]
    fields = await get_model_fields(model)
    await state.update_data(fields=fields)

    await callback.message.answer(
        f"Введи значения для роли '{role}' через запятую:\n" +
        "\n".join(fields)
    )

    await state.set_state(CreateUserStates.entering_data)


@dev_router.message(CreateUserStates.entering_data)
async def enter_user_data(message: Message, state: FSMContext):
    data = await state.get_data()
    role = data["role"]
    fields = data["fields"]
    values = [v.strip() for v in message.text.split(", ")]

    if len(values) != len(fields):
        return await message.answer(
            f"❌ Неверное количество значений. Ожидалось: {len(fields)}, получено: {len(values)}."
        )

    model_cls = ROLE_MODEL_MAP_ENG[role]

    try:
        # Преобразуем значения и собираем в словарь
        parsed_data = {
            field: await parse_auto_type(value)
            for field, value in zip(fields, values)
        }

        # Создаём экземпляр модели
        instance = model_cls(**parsed_data)

        # Сохраняем в БД
        success, msg = await add_user(instance)

        if success:
            await message.answer(f"✅ Пользователь роли '{role}' успешно добавлен.")
        else:
            await message.answer(f"❌ {msg}")

    except Exception as e:
        logger.exception("Ошибка при создании пользователя")
        await message.answer(f"❌ Ошибка при создании пользователя: {e}")

    await state.clear()





@dev_router.message(F.text.startswith("/show_db"))
async def send_students_image(message: Message):
    model_name = message.text.split('_')[2]
    model = ROLE_MODEL_MAP_ENG[model_name]
    filename = await generate_table_image(model, limit=30)
    if filename:
        await message.answer_photo(FSInputFile(filename))
    else:
        await message.answer("Нет данных в таблице.")



