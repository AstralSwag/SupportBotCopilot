import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from fastapi import FastAPI
from .config import settings
from .database import init_db, redis
from .handlers import registration, tickets
from .middlewares.database import DatabaseMiddleware

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация FastAPI
app = FastAPI()

# Инициализация бота
bot = Bot(token=settings.BOT_TOKEN)
storage = RedisStorage(redis=redis)
dp = Dispatcher(storage=storage)

# Регистрация роутеров
dp.include_router(registration.router)
dp.include_router(tickets.router)

# Регистрация middleware
dp.message.middleware(DatabaseMiddleware())
dp.callback_query.middleware(DatabaseMiddleware())

@app.on_event("startup")
async def startup_event():
    """Действия при запуске приложения"""
    # Инициализация базы данных
    await init_db()
    
    # Запуск бота
    asyncio.create_task(dp.start_polling(bot))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
