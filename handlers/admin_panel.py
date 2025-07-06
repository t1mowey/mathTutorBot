from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, InlineKeyboardMarkup, InputFile, FSInputFile
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from handlers.filters import IsAdminFilter
from database.db_scripts import get_unregistered_users, get_model_fields, ROLE_MODEL_MAP_RU, add_user, delete_user, \
    get_unchecked_payments, approve_payment, get_pending_payment_by_id, mark_payment_as_checked, ROLE_MODEL_MAP_ENG
from handlers.services import CreateUserStates, AssignRoleState
from conf import logger
from handlers.services import parse_auto_type


admin_router = Router()
admin_router.message.filter(IsAdminFilter())


# Base Admin buttons
def admin_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Добавить пользователя")],
            [KeyboardButton(text="➕ Проверить оплаты")],
            [KeyboardButton(text="⚙️ Настройки")]
        ],
        resize_keyboard=True
    )


@admin_router.message(F.text == "➕ Добавить пользователя")
async def start_assign_role(message: Message, state: FSMContext):
    users = await get_unregistered_users()
    if not users:
        await message.answer("Нет новых пользователей.")
        return

    kb_builder = InlineKeyboardBuilder()
    for user in users:
        kb_builder.add(
            InlineKeyboardButton(
                text=f"{user.name} (ID: {user.telegram_id})",
                callback_data=f"select_user:{user.telegram_id}"
            )
        )

    await state.set_state(AssignRoleState.choosing_user)
    await message.answer("Выбери пользователя для назначения роли:",
                         reply_markup=kb_builder.as_markup())

# --- Шаг 2: выбор пользователя, сохранение в state ---
@admin_router.callback_query(AssignRoleState.choosing_user, F.data.startswith("select_user:"))
async def process_user_selected(callback: CallbackQuery, state: FSMContext):
    telegram_id = int(callback.data.split(":")[1])
    users = await get_unregistered_users()

    # Находим юзера по telegram_id из уже загруженных
    user = next((u for u in users if u.telegram_id == telegram_id), None)
    if not user:
        await callback.message.answer("❌ Пользователь не найден.")
        await callback.answer()
        return

    await state.update_data(telegram_id=telegram_id, name=user.name)
    await state.set_state(AssignRoleState.choosing_role)

    kb_builder = InlineKeyboardBuilder()
    for role in ["Student", "Parent", "Tutor", "Admin"]:
        kb_builder.add(
            InlineKeyboardButton(
                text=role.capitalize(),
                callback_data=f"select_role:{role}"
            )
        )

    await callback.message.edit_text(
        f"Выбери роль для пользователя {user.name}:",
        reply_markup=kb_builder.as_markup()
    )
    await callback.answer()

# --- Шаг 3: выбор роли, создание юзера ---
@admin_router.callback_query(AssignRoleState.choosing_role, F.data.startswith("select_role:"))
async def process_role_selected(callback: CallbackQuery, state: FSMContext):
    role = callback.data.split(":")[1]
    data = await state.get_data()
    await state.clear()

    telegram_id = data["telegram_id"]
    name = data["name"]

    model_class = ROLE_MODEL_MAP_ENG.get(role)
    if not model_class:
        print(f"[ERROR] Неизвестная роль: {role}")
        await callback.message.answer("❌ Ошибка: неизвестная роль.")
        await callback.answer()
        return

    try:
        instance = model_class(telegram_id=telegram_id, name=name)
        print(f"[INFO] Создан экземпляр {model_class.__name__} для {telegram_id} ({name})")
    except Exception as e:
        print(f"[ERROR] Не удалось создать экземпляр {model_class.__name__}: {e}")
        await callback.message.answer("❌ Ошибка при создании пользователя.")
        await callback.answer()
        return

    success, message = await add_user(instance)

    if success:
        print(f"[OK] Роль '{role}' назначена пользователю {telegram_id}")
        await callback.message.edit_text(f"✅ Пользователю {name} назначена роль '{role}'.")
    else:
        print(f"[FAIL] Не удалось добавить пользователя {telegram_id}: {message}")
        await callback.message.answer("❌ Не удалось назначить роль.")

    await callback.answer()


async def send_current_payment(msg_or_cb, payment_id: int):
    payment = await get_pending_payment_by_id(payment_id)
    if not payment:
        await msg_or_cb.answer("❌ Платёж не найден.")
        return

    await mark_payment_as_checked(payment_id)
    text = (
        f"🧾 Родитель ID: {payment.parent_id}\n"
        f"👦 Родитель: {payment.parent_name}\n"
        f"👦 Ученик: {payment.student_name}\n"
        f"📚 Оплачено занятий: {payment.lessons}\n"
        f"🕒 Дата: {payment.created_at.strftime('%d.%m.%Y %H:%M')}"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"approve_{payment.id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"decline_{payment.id}")
        ],
        [
            InlineKeyboardButton(text="⏭ Далее", callback_data="next_payment"),
            InlineKeyboardButton(text="⏹ Завершить", callback_data="stop_review")
        ]
    ])

    photo = FSInputFile(path=payment.file_path)

    await msg_or_cb.answer_photo(
        photo=photo,
        caption=text,
        reply_markup=kb
    )



@admin_router.message(F.text == "➕ Проверить оплаты")
async def start_review_payments(msg: Message, state: FSMContext):
    payments = await get_unchecked_payments()
    if not payments:
        await msg.answer("Нет неподтверждённых оплат.")
        return

    await state.update_data(pending_payments=[p.id for p in payments], current_index=0)
    await send_current_payment(msg, payments[0].id)


@admin_router.callback_query(F.data == "next_payment")
async def next_payment(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    payments = data.get("pending_payments", [])
    index = data.get("current_index", 0) + 1

    if index >= len(payments):
        await callback.message.answer("Больше нет заявок.")
        await state.clear()
        await callback.answer()
        return

    await state.update_data(current_index=index)
    next_payment_id = payments[index]

    await send_current_payment(callback.message, next_payment_id)
    await callback.answer()


@admin_router.callback_query(F.data == "stop_review")
async def stop_review(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("Просмотр заявок завершён.")
    await callback.answer()


@admin_router.callback_query(F.data.startswith("approve_"))
async def approve_payment_handler(callback: CallbackQuery, state: FSMContext):
    payment_id = int(callback.data.split("_")[1])
    approver_id = callback.from_user.id
    approver_name = callback.from_user.full_name

    success = await approve_payment(payment_id, approver_id, approver_name)
    if not success:
        await callback.message.answer("❌ Не удалось подтвердить оплату. Возможно, она уже удалена.")
        await callback.answer()
        return

    # Переходим к следующему платежу
    data = await state.get_data()
    payments = data.get("pending_payments", [])
    index = data.get("current_index", 0)

    # Удаляем текущий payment из списка (по id)
    updated_payments = [p for p in payments if p != payment_id]

    if index >= len(updated_payments):
        await state.clear()
        await callback.message.answer("✅ Оплата подтверждена.\nБольше нет заявок.")
        await callback.answer()
        return

    await state.update_data(pending_payments=updated_payments)
    next_payment_id = updated_payments[index if index < len(updated_payments) else 0]

    await callback.message.answer("✅ Оплата подтверждена.")
    await send_current_payment(callback.message, next_payment_id)
    await callback.answer()




