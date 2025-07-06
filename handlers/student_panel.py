from pathlib import Path

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData
from datetime import datetime

from database.db_scripts import get_students_for_tutor, decrease_student_credit
from handlers.filters import IsStudentFilter
from conf import logger


student_router = Router()
student_router.message.filter(IsStudentFilter())


def student_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="---------")],
            [KeyboardButton(text="---------")],
            [KeyboardButton(text="---------")]
        ],
        resize_keyboard=True
    )


