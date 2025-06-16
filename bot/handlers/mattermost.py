from fastapi import APIRouter, Request, HTTPException
from bot.handlers.tickets import get_ticket_by_mattermost_post_id, get_user_by_id
from bot.bot import bot
from bot.database import get_session
from bot.services.mattermost import mattermost_service
from bot.models.models import Message
from bot.config import settings
from sqlalchemy import select
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/webhook/mattermost")
async def mattermost_webhook(request: Request):
    """Обработка вебхуков от Mattermost"""
    try:
        data = await request.json()
        logger.info(f"Получен вебхук от Mattermost: {data}")
        
        post_id = data.get("post_id")
        if not post_id:
            logger.warning("post_id не найден в данных вебхука")
            return {"status": "post_id not found"}
            
        # Получаем информацию о посте через API Mattermost
        post_info = await mattermost_service.get_post(post_id)
        if not post_info:
            logger.warning(f"Не удалось получить информацию о посте {post_id}")
            return {"status": "post not found"}
            
        root_id = post_info.get("root_id", post_id)  # Если это корневой пост, используем post_id
        
        async for session in get_session():
            # Получаем информацию о тикете по root_id
            ticket = await get_ticket_by_mattermost_post_id(session, root_id)
            if not ticket:
                logger.warning(f"Тикет не найден для root_id: {root_id}")
                return {"status": "ticket not found"}
                
            # Получаем информацию о пользователе
            user = await get_user_by_id(session, ticket.user_id)
            if not user:
                logger.warning(f"Пользователь не найден для ticket_id: {ticket.id}")
                return {"status": "user not found"}
                
            # Сохраняем сообщение в базу данных
            message = Message(
                ticket_id=ticket.id,
                content=data.get("text", ""),
                sender_type="support",
                created_at=datetime.now()
            )
            session.add(message)
            await session.commit()
            # Проверяем, что сообщение от нужного пользователя
            if data.get("user_id") == settings.MATTERMOST_SUPPORT_USER_ID or data.get("user_name") == settings.MATTERMOST_SUPPORT_USERNAME:
                logger.info(f"Сообщение от другого пользователя: {data.get('user_name')} ({data.get('user_id')})")
                return {"status": "ignored"}
        
            # Отправляем сообщение пользователю через бота
            message_text = data.get("text", "").strip()
            if message_text:
                await bot.send_message(
                    chat_id=user.telegram_id,
                    text=f"💬 Новое сообщение в вашем обращении:\n\n{message_text}"
                )
                logger.info(f"Сообщение отправлено пользователю {user.telegram_id}")
                
            return {"status": "success"}
        
    except Exception as e:
        logger.error(f"Ошибка при обработке вебхука: {e}")
        raise HTTPException(status_code=500, detail=str(e)) 