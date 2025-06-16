from fastapi import APIRouter, Request, HTTPException, Depends
from bot.services.ticket_service import TicketService
from bot.services.mattermost import MattermostService
from bot.services.plane import PlaneService
from bot.database import get_session
from sqlalchemy.ext.asyncio import AsyncSession
import logging
from typing import Dict, Any
from bot.config import settings
from bot.bot import bot

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/webhook/mattermost")
async def mattermost_webhook(
    request: Request,
    session: AsyncSession = Depends(get_session)
) -> Dict[str, str]:
    """
    Обработчик вебхуков от Mattermost.
    Получает сообщения из тредов и отправляет их пользователям в Telegram.
    """
    try:
        # Пробуем получить данные как JSON
        try:
            data_dict = await request.json()
        except:
            # Если не получилось, пробуем как form-data
            form_data = await request.form()
            data_dict = dict(form_data)
            
        logger.info(f"Получен вебхук от Mattermost: {data_dict}")

        # Проверяем токен
        if data_dict.get('token') != settings.MATTERMOST_WEBHOOK_TOKEN:
            logger.error(f"Неверный токен. Получен: {data_dict.get('token')}, Ожидался: {settings.MATTERMOST_WEBHOOK_TOKEN}")
            raise HTTPException(status_code=403, detail="Invalid token")

        # Получаем информацию о посте
        post_id = data_dict.get('post_id')
        if not post_id:
            raise HTTPException(status_code=400, detail="No post_id provided")

        # Получаем полную информацию о посте через API Mattermost
        mattermost_service = MattermostService()
        post_info = await mattermost_service.get_post(post_id)
        
        # Проверяем, что это ответ в треде
        root_id = post_info.get('root_id')
        if not root_id:
            logger.warning(f"Тикет не найден для root_id: {root_id}")
            return {"status": "ok", "message": "Not a thread reply"}

        # Получаем тикет по root_id
        ticket_service = TicketService()
        ticket = await ticket_service.get_ticket_by_mattermost_post_id(session, root_id)
        if not ticket:
            logger.warning(f"Тикет не найден для root_id: {root_id}")
            return {"status": "ok", "message": "Ticket not found"}

        # Получаем информацию о пользователе
        user = await ticket_service.get_user_by_id(session, ticket.user_id)
        if not user:
            logger.warning(f"Пользователь не найден для тикета {ticket.id}")
            return {"status": "ok", "message": "User not found"}

        # Получаем текст сообщения
        message_text = post_info.get('message', '')
        if not message_text:
            return {"status": "ok", "message": "Empty message"}

        # Проверяем, является ли сообщение от бота
        user_id = post_info.get('user_id')
        if user_id == settings.MATTERMOST_SUPPORT_USER_ID:
            logger.info("Сообщение от бота, игнорируем")
            return {"status": "ok", "message": "Message from bot"}

        # Отправляем сообщение в Telegram
        try:
            await bot.send_message(
                chat_id=user.telegram_id,
                text=f"Сообщение от поддержки:\n\n{message_text}"
            )
            logger.info(f"Сообщение отправлено пользователю {user.telegram_id}")
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения в Telegram: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to send message to Telegram: {str(e)}")

        # Добавляем сообщение в тикет
        await ticket_service.add_message_to_ticket(
            session=session,
            ticket=ticket,
            message_text=message_text,
            sender_type="support"
        )

        # Отправляем сообщение в Plane
        plane_service = PlaneService()
        await plane_service.update_ticket(ticket.plane_ticket_id, message_text, is_from_support=True)

        return {"status": "ok", "message": "Message processed"}

    except Exception as e:
        logger.error(f"Ошибка при обработке вебхука: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))