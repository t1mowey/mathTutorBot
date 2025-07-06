from sqlalchemy import Column, Integer, BigInteger, String, ForeignKey, Table, Boolean, DateTime, func
from sqlalchemy.orm import relationship
from conf import Base

# Ассоциативная таблица many-to-many
student_tutor_association = Table(
    'student_tutor',
    Base.metadata,
    Column('student_id', Integer, ForeignKey('students.id')),
    Column('tutor_id', Integer, ForeignKey('tutors.id'))
)


class ReprMixin:
    def __repr__(self):
        fields = []
        for key in self.__table__.columns.keys():
            value = getattr(self, key, None)
            fields.append(f"{key}={value!r}")
        return f"<{self.__class__.__name__}({', '.join(fields)})>"

    def __str__(self):
        # Можно вывести только самые важные поля (например, name или telegram_id)
        important = [getattr(self, k, None) for k in ("first_name", "last_name", "telegram_id") if hasattr(self, k)]
        label = " ".join(str(x) for x in important if x)
        return f"{self.__class__.__name__}({label})"


class Student(Base, ReprMixin):
    __tablename__ = 'students'

    id = Column(Integer, primary_key=True, autoincrement=True)  # внутренний ID
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    first_name = Column(String)
    last_name = Column(String)
    is_admin = Column(Boolean, default=False, nullable=False)
    payed_lessons = Column(Integer, default=0, nullable=False)

    parent_id = Column(Integer, ForeignKey('parents.id'), nullable=True)
    parent = relationship("Parent", back_populates="students")

    tutors = relationship(
        "Tutor",
        secondary=student_tutor_association,
        back_populates="students"
    )


class Parent(Base, ReprMixin):
    __tablename__ = 'parents'

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    full_name = Column(String)
    students = relationship('Student', back_populates='parent', lazy="selectin")


class Tutor(Base, ReprMixin):
    __tablename__ = 'tutors'

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    name = Column(String)
    is_admin = Column(Boolean, default=False, nullable=False)

    students = relationship(
        "Student",
        secondary=student_tutor_association,
        back_populates="tutors"
    )


class Admin(Base, ReprMixin):
    __tablename__ = 'admins'
    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    name = Column(String)
    is_admin = Column(Boolean, default=True, nullable=False)


class RegistrationStack(Base, ReprMixin):
    __tablename__ = 'stack'
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    fullname = Column(String)


class PendingPayment(Base):
    __tablename__ = "pending_payments"

    id = Column(Integer, primary_key=True)
    parent_id = Column(BigInteger, nullable=False)
    parent_name = Column(String, nullable=False)
    student_id = Column(BigInteger, nullable=False)
    student_name = Column(String, nullable=False)
    lessons = Column(Integer, nullable=False)
    file_path = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    is_checked = Column(Boolean, default=False)
    is_approved = Column(Boolean, nullable=True)
    approved_by_admin_id = Column(BigInteger, nullable=True)
    approved_by_admin_name = Column(String, nullable=True)





