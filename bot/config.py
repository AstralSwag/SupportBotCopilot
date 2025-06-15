from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Telegram
    BOT_TOKEN: str
    
    # PostgreSQL
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str
    
    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    
    # Mattermost
    MATTERMOST_URL: str
    MATTERMOST_TOKEN: str
    MATTERMOST_TEAM: str
    MATTERMOST_CHANNEL: str
    
    # Plane.so
    PLANE_API_URL: str
    PLANE_API_TOKEN: str
    PLANE_WORKSPACE_ID: str
    PLANE_PROJECT_ID: str
    
    # Дополнительные настройки
    TICKET_ACTIVE_TIME: int = 3600  # Время активности тикета в секундах (1 час)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
