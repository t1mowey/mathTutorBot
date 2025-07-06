from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, InlineKeyboardMarkup, InputFile, FSInputFile
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from handlers.filters import IsAdminFilter
from database.db_scripts import get_unregistered_users, get_model_fields, ROLE_MODEL_MAP_RU, add_user, delete_user, \
    get_unchecked_payments, approve_payment, get_pending_payment_by_id, mark_payment_as_checked
from handlers.services import CreateUserStates
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


async def send_current_payment(msg_or_cb, payment_id: int):
    payment = await get_pending_payment_by_id(payment_id)
    if not payment:
        await msg_or_cb.answer("❌ Платёж не найден.")
        return

    await mark_payment_as_checked(payment_id)
    text = (
        f"🧾 Родитель ID: ```{payment.parent_id}```\n"
        f"👦 Родитель: {payment.parent_name}"
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




