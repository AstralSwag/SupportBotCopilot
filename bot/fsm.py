from aiogram.fsm.storage.redis import RedisStorage
from aiogram.fsm.state import State, StatesGroup
from redis.asyncio import Redis

class UserRegistration(StatesGroup):
    """Состояния для регистрации пользователя"""
    waiting_fullname = State()

class TicketCreation(StatesGroup):
    """Состояния для создания тикета"""
    waiting_title = State()
    waiting_description = State()
    waiting_confirmation = State()

class TicketSelection(StatesGroup):
    """Состояния для выбора существующего тикета"""
    selecting_ticket = State()
    waiting_reply = State()

def get_storage(redis_url: str = None) -> RedisStorage:
    """Initialize Redis storage for FSM"""
    if not redis_url:
        redis_url = "redis://localhost:6379/0"
    
    redis = Redis.from_url(redis_url)
    storage = RedisStorage(redis=redis)
    return storage
