from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData

from database.db_scripts import get_students_for_tutor, decrease_student_credit
from handlers.filters import IsTutorFilter
from conf import logger

tutor_router = Router()
tutor_router.message.filter(IsTutorFilter())


class StudentCallback(CallbackData, prefix="student"):
    telegram_id: int


student_cb = StudentCallback


def tutor_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Отметить занятия")],
            [KeyboardButton(text="➕ Добавить ученика")],
            [KeyboardButton(text="⚙️ Настройки")]
        ],
        resize_keyboard=True
    )


def get_keyboard(students, selected_ids):
    builder = InlineKeyboardBuilder()
    for student in students:
        is_selected = student.telegram_id in selected_ids
        emoji = "✅" if is_selected else "☐"
        builder.button(
            text=f"{emoji} {student.first_name}",
            callback_data=StudentCallback(telegram_id=student.telegram_id).pack()
        )
    builder.button(text="Готово", callback_data="done")
    builder.adjust(1)
    return builder.as_markup()


@tutor_router.message(F.text == "➕ Отметить занятия")
async def start_check_payment(message: Message, state: FSMContext):
    tutor_id = message.from_user.id
    students = await get_students_for_tutor(tutor_id)

    if not students:
        await message.answer("У вас пока нет учеников.")
        return

    await state.update_data(selected_ids=[])  # очищаем предыдущий выбор

    markup = get_keyboard(students, selected_ids=[])
    await message.answer("Выберите учеников, оплативших занятия:", reply_markup=markup)


@tutor_router.callback_query(student_cb.filter())
async def toggle_student(callback: CallbackQuery, callback_data: student_cb, state: FSMContext):
    tutor_id = callback.from_user.id
    data = await state.get_data()
    selected_ids = set(data.get("selected_ids", []))
    student_id = int(callback_data.telegram_id)

    if student_id in selected_ids:
        selected_ids.remove(student_id)
    else:
        selected_ids.add(student_id)

    await state.update_data(selected_ids=list(selected_ids))

    # перерисовать клавиатуру
    students = await get_students_for_tutor(tutor_id) # список учеников
    markup = get_keyboard(students, selected_ids)
    await callback.message.edit_reply_markup(reply_markup=markup)
    await callback.answer()


@tutor_router.callback_query(F.data == "done")
async def finish(callback: CallbackQuery, state: FSMContext):
    tutor_id = callback.from_user.id
    data = await state.get_data()
    selected_ids = data.get("selected_ids", [])
    student_names, tutor_name = await decrease_student_credit(selected_ids, tutor_id)
    print(f"Преподаватель {tutor_name} списал занятия у {student_names}")
    logger.info(f"Преподаватель {tutor_name} списал занятия у {student_names}")
    # сохраняем их куда надо
    await callback.message.edit_text(f"Прошли занятия с: {', '.join(student_names)}")
    await state.clear()
