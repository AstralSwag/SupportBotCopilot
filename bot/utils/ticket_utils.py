from datetime import datetime
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.models import Ticket, User

async def get_active_ticket(session: AsyncSession, user_id: int, active_time: int) -> Optional[Ticket]:
    """
    Получает активный тикет пользователя
    
    Args:
        session: Сессия базы данных
        user_id: Telegram ID пользователя
        active_time: Время в секундах, в течение которого тикет считается активным
        
    Returns:
        Optional[Ticket]: Активный тикет или None
    """
    cutoff_time = datetime.utcnow().timestamp() - active_time
    
    # Находим пользователя
    user = await session.scalar(
        select(User).where(User.telegram_id == user_id)
    )
    
    if not user:
        return None
    
    # Находим активный тикет
    ticket = await session.scalar(
        select(Ticket)
        .where(Ticket.user_id == user.id)
        .where(Ticket.updated_at >= datetime.fromtimestamp(cutoff_time))
        .order_by(Ticket.updated_at.desc())
    )
    
    return ticket

def format_ticket_info(ticket: Ticket) -> str:
    """
    Форматирует информацию о тикете для отображения пользователю
    
    Args:
        ticket: Объект тикета
        
    Returns:
        str: Отформатированная строка с информацией о тикете
    """
    status_emoji = {
        'new': '🆕',
        'in_progress': '⏳',
        'resolved': '✅',
        'closed': '🔒'
    }
    
    return (
        f"{status_emoji.get(ticket.status, '❓')} Тикет #{ticket.id}\n"
        f"Статус: {ticket.status}\n"
        f"Создан: {ticket.created_at.strftime('%d.%m.%Y %H:%M')}\n"
        f"Последнее обновление: {ticket.updated_at.strftime('%d.%m.%Y %H:%M')}"
    )
