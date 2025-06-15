import sys
import os
import signal
import asyncio
import logging
from typing import Any

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot"))

from bot.main import app, shutdown_event

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def handle_exit(signum, frame):
    logger.info("Получен сигнал завершения работы")
    sys.exit(0)

if __name__ == "__main__":
    import uvicorn
    
    # Регистрируем обработчики сигналов
    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)
    
    # Запускаем с помощью uvicorn напрямую
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        use_colors=True,
        loop="asyncio"
    )