from dotenv import load_dotenv
import os
from sqlalchemy.orm import declarative_base
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from contextlib import asynccontextmanager
from loguru import logger
import sys


load_dotenv()

TOKEN = os.getenv("TOKEN")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_NAME = os.getenv('DB_NAME')
DB_HOST = os.getenv('DB_HOST')
DB_PORT = os.getenv('DB_PORT')

DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_async_engine(DATABASE_URL, echo=False)
SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)

font = os.getenv('FONT')


@asynccontextmanager
async def get_db() -> AsyncSession:
    async with SessionLocal() as session:
        yield session


Base = declarative_base()


def setup_logger():
    logger.remove()
    os.makedirs("logs", exist_ok=True)

    # INFO и выше, кроме ERROR
    logger.add(
        "logs/log_info.log",
        level="INFO",
        filter=lambda record: record["level"].name != "ERROR",
        rotation="10 MB",
        retention="10 days",
        encoding="utf8",
        enqueue=True
    )

    logger.add(
        "logs/log_dev.log",
        level="DEBUG",
        filter=lambda record: record["level"].name != "ERROR",
        rotation="10 MB",
        retention="10 days",
        encoding="utf8",
        enqueue=True
    )

    # Только ERROR и выше
    logger.add(
        "logs/log_error.log",
        level="ERROR",
        rotation="10 MB",
        retention="10 days",
        encoding="utf8",
        enqueue=True
    )

    # В консоль
    logger.add(sys.stdout,
               level="DEBUG",
               format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | {message}")
