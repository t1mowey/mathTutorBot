from aiogram.types import Message
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert

from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.inspection import inspect
import asyncio
from typing import List
from PIL import Image, ImageDraw, ImageFont
from typing import Type

from conf import Base, engine, get_db, font, logger
from database.models import Student, Parent, Tutor, Admin, RegistrationStack, PendingPayment
import database.models
from handlers.services import save_user_image


async def init_db():
    import database.models
    print("🔧 Инициализация базы данных...")

    try:
        print("📡 Попытка подключения к базе...")
        async with engine.begin() as conn:
            print("✅ Подключение установлено")

            print("📦 Импортировано таблиц:", list(Base.metadata.tables.keys()))
            print("🛠️ Создание таблиц...")
            await conn.run_sync(Base.metadata.create_all)
            print("✅ Схема и таблицы успешно созданы")
            conn.close()

    except Exception as e:
        print("❌ Ошибка при создании таблиц:", e)

    async with engine.begin() as conn:
        await conn.execute(text("""
            ALTER TABLE students ADD COLUMN IF NOT EXISTS parent_id INTEGER;
        """))
        await conn.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.table_constraints
                    WHERE constraint_name = 'fk_parent'
                ) THEN
                    ALTER TABLE students
                    ADD CONSTRAINT fk_parent
                    FOREIGN KEY (parent_id)
                    REFERENCES parents(id)
                    ON DELETE SET NULL;
                END IF;
            END
            $$;
        """))


async def add_stack(telegram_id: int, name: str):
    async with get_db() as db:
        exist = (await db.execute(select(RegistrationStack).filter(RegistrationStack.telegram_id == telegram_id))).scalars().first()
        if exist:
            print('exist')
            return
        user_to_stack = RegistrationStack(name=name, telegram_id=telegram_id)
        db.add(user_to_stack)
        try:
            await db.commit()
        except IntegrityError as e:
            await db.rollback()
            # на всякий случай отлавливаем другие нарушения уникальности
            raise ValueError("Failed to create tutor, maybe duplicate telegram_id") from e
        await db.refresh(user_to_stack)


async def get_students_for_tutor(telegram_id: int) -> list:
    """
    Возвращает список студентов, привязанных к тьютору с указанным telegram_id.
    """
    async with get_db() as db:
        result = await db.execute(
            select(Tutor)
            .where(Tutor.telegram_id == telegram_id)
            .options(selectinload(Tutor.students))
        )
        tutor = result.scalars().first()
    return tutor.students if tutor else []


async def get_unregistered_users() -> List[RegistrationStack]:
    async with get_db() as db:
        result = await db.execute(select(RegistrationStack))
        return result.scalars().all()


async def decrease_student_credit(students_ids: List[int], tutor_id: int):
    async with get_db() as db:
        students = (await db.execute(
            select(Student).filter(Student.telegram_id.in_(students_ids))
        )
                    ).scalars().all()
        tutor_name = (await db.execute(
            select(Tutor).filter(Tutor.telegram_id == tutor_id)
        )
                      ).scalars().first().name
        for student in students:
            student.payed_lessons -= 1
        student_names = [student.name for student in students]
        await db.commit()
    return student_names, tutor_name


async def increase_student_credit(students_id: int, admin_id: int, payed_lessons: int):
    async with get_db() as db:
        student = (await db.execute(
            select(Student).filter(Student.telegram_id == students_id)
        )
                    ).scalars().first()
        admin_name = (await db.execute(
            select(Admin).filter(Admin.telegram_id == admin_id)
        )
                      ).scalars().first().name
        student.payed_lessons += payed_lessons
        student_name = student.name
        await db.commit()
    return student_name, admin_name


async def get_model_fields(model_class):
    return [
        c.name for c in model_class.__table__.columns
        if c.name != "id"
    ]


ROLE_MODEL_MAP_RU = {
    "Ученик": Student,
    "Родитель": Parent,
    "Преподаватель": Tutor,
    "Администратор": Admin
}

ROLE_MODEL_MAP_ENG = {
    "Student": Student,
    "Parent": Parent,
    "Tutor": Tutor,
    "Admin": Admin
}


async def add_user(instance: Student | Parent | Tutor | Admin) -> tuple[bool, str]:
    async with get_db() as db:
        try:
            db.add(instance)
            await db.commit()
            logger.debug(f"Добавлен {repr(instance)}")
            return True, "Объект добавлен"
        except Exception as e:
            logger.exception("Ошибка при сохранении в БД")
            return False, f"Ошибка: {e}"


async def delete_user(model, telegram_id: int, message):
    async with get_db() as db:
        # Загружаем со всеми связями
        result = await db.execute(
            select(model)
            .where(model.telegram_id == telegram_id)
            .options(selectinload("*"))  # или отдельно: selectinload(model.students)
        )
        instance = result.scalars().first()

        if not instance:
            return await message.answer(f"❌ В таблице {model.__tablename__} telegram_id {telegram_id} не найден.")

        if model == Tutor:
            instance.students.clear()
            await db.flush()

        if model == Student:
            instance.tutors.clear()
            await db.flush()

        await db.delete(instance)
        await db.commit()

        logger.info(f"{model.__tablename__} {telegram_id} удалён")
        await message.answer(f"✅ {telegram_id} успешно удалён из {model.__tablename__}")


async def generate_table_image(model: Type, limit: int = 20, filename: str = "table_preview.png") -> str | None:
    async with get_db() as session:
        result = await session.execute(select(model).limit(limit))
        objects = result.scalars().all()

        if not objects:
            return None

        columns = [c.name for c in inspect(model).columns]
        rows = [columns]

        for obj in objects:
            row = [str(getattr(obj, col, "")) for col in columns]
            rows.append(row)

        # Расчёт размеров
        font_im = ImageFont.truetype(font, size=14)
        row_height = 20
        col_widths = [max(len(row[i]) for row in rows) * 10 for i in range(len(columns))]

        img_width = sum(col_widths) + 20
        img_height = row_height * len(rows) + 20

        image = Image.new("RGB", (img_width, img_height), "white")
        draw = ImageDraw.Draw(image)

        y = 10
        for row in rows:
            x = 10
            for i, cell in enumerate(row):
                draw.text((x, y), cell, fill="black", font=font_im)
                x += col_widths[i]
            y += row_height

        image.save(filename)
        return filename


async def get_students_lessons_by_parent(parent_telegram_id: int):
    async with get_db() as session:
        result = await session.execute(
            select(Parent).where(Parent.telegram_id == parent_telegram_id)
        )
        parent = result.scalars().first()
        if not parent:
            return []

        await session.refresh(parent)  # подтягиваем связь
        students_info = []
        for student in parent.students:  # один-ко-многим
            students_info.append({
                "id": student.id,
                "name": f"{student.name}",
                "payed_lessons": student.payed_lessons
            })

        return students_info


async def create_pending_payment(
    message: Message,
    parent_id: int,
    parent_name: str,
    student_id: int,
    student_name: str,
    lessons: int
):
    # Сохраняем файл и получаем путь
    file_path = await save_user_image(message)

    # Записываем в базу
    async with get_db() as db:
        stmt = insert(PendingPayment).values(
            parent_id=parent_id,
            parent_name=parent_name,
            student_id=student_id,
            student_name=student_name,
            lessons=lessons,
            file_path=str(file_path)
        )
        await db.execute(stmt)
        await db.commit()


async def get_unchecked_payments():
    async with get_db() as db:
        result = await db.execute(
            select(PendingPayment).where(PendingPayment.is_approved.is_not(True))
        )
        return result.scalars().all()


async def get_pending_payment_by_id(payment_id: int):
    async with get_db() as db:
        payment = await db.get(PendingPayment, payment_id)
        if payment is None:
            return False
        return payment


async def get_parent_by_id(telegram_id):
    async with get_db() as db:
        parent = (await db.execute(select(Parent).where(Parent.telegram_id == telegram_id))).scalars().first()
        if parent is None:
            return False
        return parent


async def mark_payment_as_checked(payment_id: int):
    async with get_db() as db:
        payment = (await db.execute(select(PendingPayment).where(PendingPayment.id == payment_id))).scalars().first()
        if payment:
            payment.is_checked = True
            await db.commit()
            logger.info(f"Платёж с ID {payment_id} просмотрен")


async def approve_payment(payment_id: int, approver_id: int, approver_name: str):
    async with get_db() as db:
        payment = await db.get(PendingPayment, payment_id)
        if payment is None:
            return False, None, None

        payment.approved_by_admin_id = approver_id
        payment.approved_by_admin_name = approver_name
        payment.is_approved = True

        student = (
            await db.execute(select(Student).where(Student.id == payment.student_id))
        ).scalars().first()

        admin = (
            await db.execute(select(Admin).where(Admin.telegram_id == approver_id))
        ).scalars().first()

        if student is None or admin is None:
            if student is None:
                print(f"[ERROR] Student not found with telegram_id: {payment.student_id}")
            if admin is None:
                print(f"[ERROR] Admin not found with telegram_id: {approver_id}")
            return False, None, None

        student.payed_lessons += payment.lessons

        await db.commit()
        print(f"[INFO] Платёж #{payment_id} подтверждён админом {approver_name} (ID {approver_id}); "
              f"{payment.lessons} уроков начислено студенту {student.name} (ID {student.telegram_id})")
        return True, student.name, admin.name



if __name__ == "__main__":
    asyncio.run(init_db())
