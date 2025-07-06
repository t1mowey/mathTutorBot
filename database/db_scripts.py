from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.inspection import inspect
import asyncio
from typing import List
from PIL import Image, ImageDraw, ImageFont
from typing import Type

from conf import Base, engine, get_db, font
from conf import logger
from database.models import Student, Tutor, Admin, RegistrationStack
import database.models


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


async def create_tutor(name: str, telegram_id: int):
    """
    Создаёт нового куратора с указанным именем и telegram_id.
    Если указанный telegram_id уже существует, возбуждает ValueError.
    Возвращает созданный объект Tutor.
    """
    async with get_db() as db:
        # проверим, нет ли уже куратора с таким telegram_id
        result = await db.execute(select(Tutor).where(Tutor.telegram_id == telegram_id))
        if result.scalars().first():
            raise ValueError(f"Tutor with telegram_id={telegram_id} already exists")

        tutor = Tutor(name=name, telegram_id=telegram_id)
        db.add(tutor)
        try:
            await db.commit()
        except IntegrityError as e:
            await db.rollback()
            # на всякий случай отлавливаем другие нарушения уникальности
            raise ValueError("Failed to create tutor, maybe duplicate telegram_id") from e

        # обновим поля из БД (например, чтобы получить сгенерированный id)
        await db.refresh(tutor)
        return tutor


async def add_stack(username: str, telegram_id: int, fullname: str):
    async with get_db() as db:
        await db.execute(select(RegistrationStack).filter(RegistrationStack.telegram_id == telegram_id))
        if db:
            return
        user_to_stack = RegistrationStack(username=username, telegram_id=telegram_id)
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
        student_names = [student.first_name for student in students]
        await db.commit()
    return student_names, tutor_name


async def get_model_fields(model_class):
    return [
        c.name for c in model_class.__table__.columns
        if c.name != "id"
    ]


ROLE_MODEL_MAP = {
    "Ученик": Student,
    "Преподаватель": Tutor,
    "Администратор": Admin
}


async def add_user(instance: Student | Tutor | Admin) -> tuple[bool, str]:
    async with get_db() as db:
        try:
            db.add(instance)
            await db.commit()
            logger.debug(f"Добавлен {repr(instance)}")
            return True, "Объект добавлен"
        except Exception as e:
            logger.exception("Ошибка при сохранении в БД")
            return False, f"Ошибка: {e}"


from sqlalchemy.orm import selectinload

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
        font = ImageFont.truetype(font, size=14)
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
                draw.text((x, y), cell, fill="black", font=font)
                x += col_widths[i]
            y += row_height

        image.save(filename)
        return filename



if __name__ == "__main__":
    asyncio.run(init_db())
