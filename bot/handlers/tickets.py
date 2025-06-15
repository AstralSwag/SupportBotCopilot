from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from ..models.models import User, Ticket, Message as TicketMessage
from ..services.plane import PlaneService
from ..services.mattermost import MattermostService
from ..fsm import TicketCreation, TicketSelection
from ..config import settings
from sqlalchemy import select

router = Router()
plane_service = PlaneService()
mattermost_service = MattermostService()

@router.message(F.text & ~Command("start"))
async def process_message(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка входящих сообщений"""
    # Проверяем регистрацию пользователя
    user = await session.scalar(
        select(User).where(User.telegram_id == message.from_user.id)
    )
    if not user:
        await message.answer("Пожалуйста, начните с команды /start для регистрации.")
        return

    # Проверяем наличие активного тикета
    active_time = datetime.utcnow() - timedelta(seconds=settings.TICKET_ACTIVE_TIME)
    active_ticket = await session.scalar(
        select(Ticket)
        .where(Ticket.user_id == user.id)
        .where(Ticket.updated_at >= active_time)
        .order_by(Ticket.updated_at.desc())
    )

    if active_ticket:
        # Добавляем сообщение к существующему тикету
        new_message = TicketMessage(
            ticket_id=active_ticket.id,
            sender_type="user",
            content=message.text
        )
        session.add(new_message)
        await session.commit()

        # Обновляем тикет в Plane.so и Mattermost
        await plane_service.update_ticket(active_ticket.plane_ticket_id, message.text)
        await mattermost_service.add_comment(active_ticket.mattermost_post_id, 
            f"Сообщение от клиента:\n{message.text}")
        
        await message.answer("Ваше сообщение добавлено к текущему обращению.")
    else:
        # Начинаем создание нового тикета
        await state.set_state(TicketCreation.waiting_description)
        await state.update_data(initial_message=message.text)
        await message.answer(
            "Я создам новое обращение с вашим сообщением. "
            "Пожалуйста, подтвердите создание обращения (да/нет):"
        )

@router.message(TicketCreation.waiting_confirmation)
async def confirm_ticket(message: Message, state: FSMContext, session: AsyncSession):
    """Подтверждение создания тикета"""
    if message.text.lower() not in ['да', 'нет']:
        await message.answer("Пожалуйста, ответьте 'да' или 'нет':")
        return

    if message.text.lower() == 'нет':
        await state.clear()
        await message.answer("Создание обращения отменено.")
        return

    # Получаем данные из состояния
    data = await state.get_data()
    initial_message = data['initial_message']

    # Создаем тикет в Plane.so
    title = f"Обращение от {message.from_user.full_name}"
    plane_ticket_id = await plane_service.create_ticket(title, initial_message)

    # Создаем тему в Mattermost
    mattermost_post_id = await mattermost_service.create_thread(title, initial_message)

    # Создаем тикет в базе данных
    user = await session.scalar(select(User).where(User.telegram_id == message.from_user.id))
    new_ticket = Ticket(
        user_id=user.id,
        plane_ticket_id=plane_ticket_id,
        mattermost_post_id=mattermost_post_id,
        status="new"
    )
    session.add(new_ticket)

    # Добавляем первое сообщение
    new_message = TicketMessage(
        ticket=new_ticket,
        sender_type="user",
        content=initial_message
    )
    session.add(new_message)
    await session.commit()

    await state.clear()
    await message.answer(
        "Обращение создано. Мы рассмотрим его как можно скорее. "
        "Вы можете продолжать отправлять сообщения в этот тикет."
    )
