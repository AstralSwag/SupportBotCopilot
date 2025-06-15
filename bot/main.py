import asyncio
import logging
from aiogram import Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from fastapi import FastAPI
from bot.config import settings
from bot.database import init_db, redis, close_db
from bot.handlers import registration, tickets, mattermost
from bot.middlewares.database import DatabaseMiddleware
from bot.bot import bot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
storage = RedisStorage(redis=redis)
dp = Dispatcher(storage=storage)
polling_task = None

# Регистрация роутеров и middleware
dp.include_router(registration.router)
dp.include_router(tickets.router)
dp.message.middleware(DatabaseMiddleware())
dp.callback_query.middleware(DatabaseMiddleware())

# Регистрация роутера для вебхуков Mattermost
app.include_router(mattermost.router, prefix="/api")

@app.on_event("startup")
async def startup_event():
    global polling_task
    await init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    polling_task = asyncio.create_task(dp.start_polling(bot))
    logger.info("Бот запущен")

@app.on_event("shutdown")
async def shutdown_event():
    global polling_task
    logger.info("Начало процесса завершения работы...")
    
    try:
        # Останавливаем поллинг
        await dp.stop_polling()
        
        if polling_task:
            polling_task.cancel()
            try:
                await polling_task
            except asyncio.CancelledError:
                pass
        
        # Закрываем соединения
        await dp.storage.close()
        await bot.session.close()
        await close_db()
        
        logger.info("Завершение работы выполнено успешно")
    except Exception as e:
        logger.error(f"Ошибка при завершении работы: {e}")