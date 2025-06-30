from pydantic import BaseModel
from typing import List, Optional


"""
id = Column(Integer, primary_key=True, autoincrement=True)  # внутренний ID
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    first_name = Column(String)
    last_name = Column(String)
"""

class StudentBase(BaseModel):
    telegram_id: int
    first_name: Optional[str]
    last_name: Optional[str]

class StudentCreate(StudentBase):
    pass

class StudentRead(StudentBase):
    id: int
    tutors: List["TutorShort"] = []  # объявим позже для обратной связи

    class Config:
        orm_mode = True

