from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from bot.models.models import User, Ticket, Message as TicketMessage
from bot.services.plane import PlaneService
from bot.services.mattermost import MattermostService
from bot.fsm import TicketCreation, TicketSelection
from bot.config import settings
from sqlalchemy import select, and_
from typing import Optional

router = Router()
plane_service = PlaneService()
mattermost_service = MattermostService()

async def get_ticket_by_mattermost_post_id(session: AsyncSession, mattermost_post_id: str) -> Optional[Ticket]:
    """Получает тикет по ID поста в Mattermost"""
    return await session.scalar(
        select(Ticket).where(Ticket.mattermost_post_id == mattermost_post_id)
    )

async def get_user_by_id(session: AsyncSession, user_id: int) -> Optional[User]:
    """Получает пользователя по ID"""
    return await session.scalar(
        select(User).where(User.id == user_id)
    )

@router.message(TicketCreation.waiting_description)
async def process_description(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка описания тикета"""
    await state.update_data(initial_message=message.text)
    await state.set_state(TicketCreation.waiting_confirmation)
    await message.answer(
        "Я создам новое обращение с вашим сообщением. "
        "Пожалуйста, подтвердите создание обращения (да/нет):"
    )

@router.message(TicketCreation.waiting_confirmation)
async def process_confirmation(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка подтверждения создания тикета"""
    if message.text.lower() not in ['да', 'нет']:
        await message.answer("Пожалуйста, ответьте 'да' или 'нет':")
        return

    if message.text.lower() == 'нет':
        await state.clear()
        await message.answer("Создание обращения отменено.")
        return

    data = await state.get_data()
    initial_message = data.get('initial_message')
    if not initial_message:
        await state.clear()
        await message.answer("Произошла ошибка. Пожалуйста, напишите ваше сообщение заново.")
        return

    user = await session.scalar(
        select(User).where(User.telegram_id == message.from_user.id)
    )
    if not user:
        await message.answer("Пожалуйста, начните с команды /start для регистрации.")
        await state.clear()
        return

    # Создаем тикет в системах
    title = f"Обращение от {user.full_name}"
    try:
        plane_ticket_id = await plane_service.create_ticket(title, initial_message)
        mattermost_post_id = await mattermost_service.create_thread(title, initial_message)
        
        # Создаем тикет в БД
        new_ticket = Ticket(
            user_id=user.id,
            plane_ticket_id=plane_ticket_id,
            mattermost_post_id=mattermost_post_id,
            status="new"
        )
        session.add(new_ticket)
        await session.commit()

        await message.answer(
            "Обращение создано. Мы рассмотрим его как можно скорее.\n"
            "Вы можете продолжать отправлять сообщения в этот тикет."
        )
    except Exception as e:
        await message.answer("Произошла ошибка при создании обращения. Пожалуйста, попробуйте позже.")
        print(f"Error creating ticket: {e}")
    finally:
        await state.clear()

@router.message(~Command(commands=["start", "help"]))
async def process_message(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка входящих сообщений"""
    current_state = await state.get_state()
    if current_state is not None:
        # Если уже есть активное состояние, не обрабатываем сообщение здесь
        return

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
