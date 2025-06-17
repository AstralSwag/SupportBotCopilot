from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from bot.models.models import User, Ticket, Message as TicketMessage
from bot.services.plane import PlaneService
from bot.services.mattermost import MattermostService
from typing import Optional, List, Dict
from datetime import datetime

class TicketService:
    def __init__(self):
        self.plane_service = PlaneService()
        self.mattermost_service = MattermostService()

    async def get_user_by_telegram_id(self, session: AsyncSession, telegram_id: int) -> Optional[User]:
        """Получает пользователя по telegram_id"""
        return await session.scalar(
            select(User).where(User.telegram_id == telegram_id)
        )

    async def get_user_by_id(self, session: AsyncSession, user_id: int) -> Optional[User]:
        """Получает пользователя по ID"""
        return await session.scalar(
            select(User).where(User.id == user_id)
        )

    async def get_ticket_by_mattermost_post_id(self, session: AsyncSession, mattermost_post_id: str) -> Optional[Ticket]:
        """Получает тикет по ID поста в Mattermost"""
        return await session.scalar(
            select(Ticket).where(Ticket.mattermost_post_id == mattermost_post_id)
        )

    async def get_active_tickets(self, session: AsyncSession, user_id: int) -> List[Ticket]:
        """Получает активные тикеты пользователя"""
        return list(await session.scalars(
            select(Ticket)
            .where(
                Ticket.user_id == user_id,
                Ticket.status != 'closed'
            )
            .order_by(Ticket.created_at.desc())
        ))

    async def get_ticket_by_id(self, session: AsyncSession, ticket_id: int) -> Optional[Ticket]:
        """Получает тикет по ID"""
        result = await session.execute(
            select(Ticket).where(Ticket.id == ticket_id)
        )
        return result.scalar_one_or_none()

    async def get_last_ticket(self, session: AsyncSession, user_id: int) -> Optional[Ticket]:
        """Получает последний тикет пользователя"""
        return await session.scalar(
            select(Ticket)
            .where(Ticket.user_id == user_id)
            .order_by(Ticket.created_at.desc())
        )

    async def create_ticket(self, session: AsyncSession, user: User, title: str, description: str) -> Ticket:
        """Создает новый тикет"""
        # Для Telegram оставляем оригинальный заголовок
        telegram_title = title
        
        # Для Mattermost и Plane добавляем полное имя пользователя
        full_title = f"{user.full_name}: {title}"
        
        plane_ticket_id = await self.plane_service.create_ticket(full_title, description)
        mattermost_post_id = await self.mattermost_service.create_thread(full_title, description)
        
        new_ticket = Ticket(
            user_id=user.id,
            title=telegram_title,  # Сохраняем оригинальный заголовок для Telegram
            plane_ticket_id=plane_ticket_id,
            mattermost_post_id=mattermost_post_id,
            status="new"
        )
        session.add(new_ticket)
        await session.commit()
        return new_ticket

    async def add_message_to_ticket(self, session: AsyncSession, ticket: Ticket, message_text: str, sender_type: str = "user") -> None:
        """Добавляет сообщение к тикету"""
        # Определяем, является ли сообщение от поддержки
        is_from_support = sender_type == "support"
        
        # Отправляем сообщение в Plane только если это сообщение от пользователя
        if not is_from_support:
            await self.plane_service.update_ticket(ticket.plane_ticket_id, message_text, is_from_support=False)
        
        # Отправляем сообщение в Mattermost только если это сообщение от пользователя
        if not is_from_support:
            await self.mattermost_service.add_comment(
                ticket.mattermost_post_id, 
                message_text,
                is_bot=True
            )
        
        # Сохраняем сообщение в базе данных
        new_message = TicketMessage(
            ticket_id=ticket.id,
            content=message_text,
            sender_type=sender_type
        )
        session.add(new_message)
        await session.commit()

    def format_tickets_for_keyboard(self, tickets: List[Ticket]) -> List[Dict]:
        """Форматирует тикеты для отображения в клавиатуре"""
        return [
            {
                "id": ticket.id,
                "title": ticket.title if ticket.title else f"Тикет #{ticket.id}",
                "status": ticket.status
            }
            for ticket in tickets
        ]

    async def close_ticket(self, session: AsyncSession, ticket: Ticket) -> None:
        """Закрывает тикет"""
        ticket.status = 'closed'
        ticket.closed_at = datetime.utcnow()
        await session.commit()

    async def create_pending_ticket(self, session: AsyncSession, user: User, title: str, description: str) -> Ticket:
        """Создает тикет в статусе pending"""
        ticket = Ticket(
            user_id=user.id,
            title=title,
            description=description,
            status="pending"
        )
        session.add(ticket)
        await session.commit()
        await session.refresh(ticket)
        return ticket

    async def activate_ticket(self, session: AsyncSession, ticket: Ticket) -> None:
        """Активирует тикет, отправляя его в Mattermost и Plane"""
        # Получаем пользователя для добавления его имени в заголовок
        user = await self.get_user_by_id(session, ticket.user_id)
        if not user:
            raise ValueError(f"User not found for ticket {ticket.id}")
        
        # Формируем заголовок с полным именем пользователя
        full_title = f"#{ticket.id} {user.full_name}: {ticket.title}"
        
        # Отправляем в Mattermost
        thread_id = await self.mattermost_service.create_thread(
            title=full_title,
            message=ticket.description
        )
        
        # Отправляем в Plane
        plane_id = await self.plane_service.create_ticket(
            title=full_title,
            description=ticket.description
        )
        
        # Обновляем статус тикета
        ticket.status = "active"
        ticket.mattermost_post_id = thread_id
        ticket.plane_ticket_id = plane_id
        await session.commit()

    async def cancel_ticket(self, session: AsyncSession, ticket: Ticket) -> None:
        """Отменяет тикет"""
        ticket.status = "canceled"
        await session.commit()

    async def add_message(self, session: AsyncSession, ticket: Ticket, message_text: str, is_from_user: bool = True) -> TicketMessage:
        """Добавляет сообщение к тикету"""
        message = TicketMessage(
            ticket_id=ticket.id,
            text=message_text,
            is_from_user=is_from_user
        )
        session.add(message)
        await session.commit()
        await session.refresh(message)
        return message 