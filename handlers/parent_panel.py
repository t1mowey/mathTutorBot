from pathlib import Path

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData
from datetime import datetime

from database.db_scripts import get_students_lessons_by_parent, create_pending_payment, get_parent_by_id
from handlers.filters import IsParentFilter
from handlers.services import PaymentStates
from conf import logger


parent_router = Router()
parent_router.message.filter(IsParentFilter())


def parent_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Оплата")],
            [KeyboardButton(text="---------")],
            [KeyboardButton(text="---------")]
        ],
        resize_keyboard=True
    )


@parent_router.message(F.text == "➕ Оплата")
async def handle_payment_check(msg: Message):
    parent_id = msg.from_user.id
    students_info = await get_students_lessons_by_parent(parent_id)

    if not students_info:
        await msg.answer("У вас пока нет привязанных учеников.")
        return

    text = "Оставшиеся занятия у ваших детей:\n\n"
    kb = InlineKeyboardMarkup(inline_keyboard=[])

    for s in students_info:
        student_id = s['id']
        full_name = s['full_name']
        text += f"{full_name}: {s['payed_lessons']} занятий\n"

        kb.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"💳 Оплатить — {s['full_name']}",
                callback_data=f"pay_student_{student_id}_{full_name}"
            )
        ])

    await msg.answer(text, reply_markup=kb)


@parent_router.callback_query(F.data.startswith("pay_student_"))
async def handle_pay_student_callback(callback: CallbackQuery, state: FSMContext):
    student_id, full_name = callback.data.replace("pay_student_", "").split('_', 1)
    student_id = int(student_id)
    await state.update_data(student_id=student_id, student_name=full_name)

    await callback.message.answer("Сколько занятий вы хотите оплатить?")
    await state.set_state(PaymentStates.waiting_for_lesson_count)
    await callback.answer()


@parent_router.message(PaymentStates.waiting_for_lesson_count)
async def process_lesson_count_input(msg: Message, state: FSMContext):
    try:
        count = int(msg.text)
        if count <= 0:
            raise ValueError
    except ValueError:
        await msg.answer("Введите положительное целое число.")
        return

    await state.update_data(lesson_count=count)
    await msg.answer("Пришлите, пожалуйста, скриншот оплаты.")
    await state.set_state(PaymentStates.waiting_for_screenshot)


@parent_router.message(PaymentStates.waiting_for_screenshot)
async def handle_payment_screenshot(msg: Message, state: FSMContext):
    data = await state.get_data()
    student_id = data.get("student_id")
    student_name = data.get("student_name")
    lesson_count = data.get("lesson_count")
    parent_tg_id = msg.from_user.id
    parent_name = (await get_parent_by_id(parent_tg_id)).full_name

    if not msg.photo:
        await msg.answer("Пожалуйста, пришлите изображение.")
        return

    try:
        await create_pending_payment(
            message=msg,
            parent_id=parent_tg_id,
            parent_name=parent_name,
            student_id=student_id,
            student_name=student_name,
            lessons=lesson_count
        )
    except Exception as e:
        await msg.answer("Произошла ошибка при сохранении оплаты.")
        raise e

    await msg.answer(
        f"Спасибо! Мы проверим оплату и начислим {lesson_count} занятий ученику {student_name}."
    )
    await state.clear()



