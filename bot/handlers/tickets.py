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
from mattermostdriver.exceptions import InvalidOrMissingParameters

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

@router.message(TicketCreation.waiting_title)
async def process_title(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка ввода названия тикета"""
    title = message.text.strip()
    
    if len(title) > 100:
        await message.answer("Название слишком длинное. Пожалуйста, введите название короче 100 символов:")
        return
    
    # Получаем информацию о пользователе
    user = await session.scalar(
        select(User).where(User.telegram_id == message.from_user.id)
    )
    
    # Сохраняем оригинальное название в состоянии
    await state.update_data(title=title)
    
    # Переходим к вводу описания
    await state.set_state(TicketCreation.waiting_description)
    await message.answer("Теперь опишите вашу проблему подробнее:")

@router.message(TicketCreation.waiting_description)
async def process_description(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка описания тикета"""
    await state.update_data(initial_message=message.text)
    await state.set_state(TicketCreation.waiting_confirmation)
    
    # Получаем сохраненное название
    data = await state.get_data()
    title = data.get('title', '')
    
    await message.answer(
        f"Я создам новое обращение:\n"
        f"Название: {title}\n"
        f"Описание: {message.text}\n\n"
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
    title = data.get('title')
    
    if not initial_message or not title:
        await state.clear()
        await message.answer("Произошла ошибка. Пожалуйста, начните создание обращения заново.")
        return

    user = await session.scalar(
        select(User).where(User.telegram_id == message.from_user.id)
    )
    if not user:
        await message.answer("Пожалуйста, начните с команды /start для регистрации.")
        await state.clear()
        return

    # Формируем полное название для Plane и Mattermost
    full_title = f"{user.full_name}: {title}"

    # Создаем тикет в системах
    try:
        plane_ticket_id = await plane_service.create_ticket(full_title, initial_message)
        mattermost_post_id = await mattermost_service.create_thread(full_title, initial_message)
        
        # Создаем тикет в БД с оригинальным названием
        new_ticket = Ticket(
            user_id=user.id,
            title=title,  # Сохраняем оригинальное название без префикса
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

@router.message()
async def process_message(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка всех остальных сообщений"""
    user = await session.scalar(
        select(User).where(User.telegram_id == message.from_user.id)
    )
    if not user:
        await message.answer("Пожалуйста, начните с команды /start для регистрации.")
        return

    # Проверяем, есть ли выбранный тикет в состоянии
    state_data = await state.get_data()
    selected_ticket_id = state_data.get('selected_ticket_id')
    
    if selected_ticket_id:
        # Если есть выбранный тикет, используем его
        ticket = await session.scalar(
            select(Ticket).where(Ticket.id == selected_ticket_id)
        )
        
        if ticket and ticket.status != 'closed':
            # Добавляем сообщение к выбранному тикету
            await plane_service.update_ticket(ticket.plane_ticket_id, message.text)
            await mattermost_service.add_comment(ticket.mattermost_post_id,
                                               message.text)
            
            # Сохраняем сообщение в БД
            new_message = Message(
                ticket_id=ticket.id,
                content=message.text,
                sender_type="user"
            )
            session.add(new_message)
            await session.commit()
            
            await message.answer("Сообщение добавлено к выбранной заявке.")
            return
    
    # Если нет выбранного тикета или он закрыт, получаем последний тикет
    last_ticket = await session.scalar(
        select(Ticket)
        .where(Ticket.user_id == user.id)
        .order_by(Ticket.created_at.desc())
    )

    if last_ticket and last_ticket.status != 'closed':
        # Если есть открытый тикет, добавляем сообщение к нему
        await plane_service.update_ticket(last_ticket.plane_ticket_id, message.text)
        await mattermost_service.add_comment(last_ticket.mattermost_post_id,
                                           message.text)
        
        # Сохраняем сообщение в БД
        new_message = Message(
            ticket_id=last_ticket.id,
            content=message.text,
            sender_type="user"
        )
        session.add(new_message)
        await session.commit()
        
        await message.answer("Сообщение добавлено к текущей заявке.")
    else:
        # Если нет открытого тикета, начинаем создание нового
        await message.answer(
            "У вас нет активной заявки. Давайте создадим новую.\n"
            "Пожалуйста, введите название заявки (не более 100 символов):"
        )
        await state.set_state(TicketCreation.waiting_title)

@router.message(F.text == "Выбрать существующую заявку")
async def select_existing_ticket(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка нажатия кнопки выбора существующей заявки"""
    user = await session.scalar(
        select(User).where(User.telegram_id == message.from_user.id)
    )
    
    # Получаем все тикеты пользователя
    tickets = await session.scalars(
        select(Ticket)
        .where(Ticket.user_id == user.id)
        .order_by(Ticket.created_at.desc())
    )
    tickets = list(tickets)
    
    if not tickets:
        await message.answer("У вас пока нет созданных заявок.")
        return
    
    # Формируем список тикетов для клавиатуры
    tickets_data = [
        {
            "id": ticket.id,
            "title": ticket.title,  # Используем сохраненное название
            "status": ticket.status
        }
        for ticket in tickets
    ]
    
    await state.set_state(TicketSelection.selecting_ticket)
    await message.answer(
        "Выберите заявку:",
        reply_markup=get_tickets_keyboard(tickets_data)
    )
