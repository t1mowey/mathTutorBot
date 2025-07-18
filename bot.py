import asyncio
from aiogram import Bot, Dispatcher

from conf import TOKEN, setup_logger
from handlers.auth import auth
from handlers.admin_panel import admin_router
from handlers.parent_panel import parent_router
from handlers.student_panel import student_router
from handlers.tutor_panel import tutor_router
from handlers.admin_commands import dev_router
from database.db_scripts import init_db


async def main():
    setup_logger()
    # await init_db()
    bot = Bot(token=TOKEN)
    dp = Dispatcher()

    dp.include_router(auth)
    dp.include_router(admin_router)
    dp.include_router(tutor_router)
    dp.include_router(student_router)
    dp.include_router(parent_router)
    dp.include_router(dev_router)
    await bot.delete_webhook(drop_pending_updates=True)
    print('Бот готов к использованию!✅')
    await dp.start_polling(bot)



if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Бот отключён вручную')