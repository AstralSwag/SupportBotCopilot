from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from bot.models.models import User, Ticket
from bot.fsm import UserRegistration, TicketCreation, TicketSelection
from sqlalchemy import select
from datetime import datetime, timedelta
from bot.keyboards import get_main_keyboard, get_tickets_keyboard
from bot.config import settings

router = Router()

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка команды /start"""
    # Проверяем, зарегистрирован ли пользователь
    user = await session.scalar(
        select(User).where(User.telegram_id == message.from_user.id)
    )
    
    if user:
        await message.answer(
            "Здравствуйте! Чем могу помочь?\n"
            "Отправьте сообщение с описанием вашего вопроса.",
            reply_markup=get_main_keyboard()
        )
    else:
        await message.answer(
            "Добро пожаловать! Для начала работы мне нужно знать ваше полное имя.\n"
            "Пожалуйста, введите ваше полное имя:"
        )
        await state.set_state(UserRegistration.waiting_fullname)

@router.message(UserRegistration.waiting_fullname)
async def process_fullname(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка ввода полного имени при регистрации"""
    full_name = message.text.strip()
    
    if len(full_name.split()) < 2:
        await message.answer("Пожалуйста, введите полное имя (имя и фамилию):")
        return
    
    # Создаем нового пользователя
    new_user = User(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        full_name=full_name
    )
    session.add(new_user)
    await session.commit()
    
    await state.clear()
    await message.answer(
        "Спасибо за регистрацию! Теперь вы можете отправить сообщение с описанием вашего вопроса.",
        reply_markup=get_main_keyboard()
    )

@router.message(F.text == "Создать новую заявку")
async def create_new_ticket(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка нажатия кнопки создания новой заявки"""
    user = await session.scalar(
        select(User).where(User.telegram_id == message.from_user.id)
    )
    
    # Переходим к вводу названия
    await state.set_state(TicketCreation.waiting_title)
    await message.answer(
        "Пожалуйста, введите название заявки (не более 100 символов):"
    )

@router.message(F.text == "Выбрать существующую заявку")
async def select_existing_ticket(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка нажатия кнопки выбора существующей заявки"""
    user = await session.scalar(
        select(User).where(User.telegram_id == message.from_user.id)
    )
    
    # Получаем только активные тикеты пользователя (не закрытые)
    tickets = await session.scalars(
        select(Ticket)
        .where(
            Ticket.user_id == user.id,
            Ticket.status != 'closed'  # Исключаем закрытые тикеты
        )
        .order_by(Ticket.created_at.desc())
    )
    tickets = list(tickets)
    
    if not tickets:
        await message.answer("У вас нет активных заявок.")
        return
    
    # Формируем список тикетов для клавиатуры
    tickets_data = [
        {
            "id": ticket.id,
            "title": ticket.title if ticket.title else f"Тикет #{ticket.id}",
            "status": ticket.status
        }
        for ticket in tickets
    ]
    
    await state.set_state(TicketSelection.selecting_ticket)
    await message.answer(
        "Выберите заявку:",
        reply_markup=get_tickets_keyboard(tickets_data)
    )

@router.callback_query(F.data.startswith("ticket_"))
async def process_ticket_selection(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработка выбора тикета из списка"""
    ticket_id = int(callback.data.split("_")[1])
    
    # Получаем тикет
    ticket = await session.scalar(
        select(Ticket).where(Ticket.id == ticket_id)
    )
    
    if not ticket:
        await callback.answer("Тикет не найден")
        return
    
    # Сохраняем ID выбранного тикета в состоянии
    await state.update_data(selected_ticket_id=ticket_id)
    await state.set_state(TicketSelection.waiting_reply)
    
    await callback.message.edit_text(
        f"Выбрана заявка: {ticket.title}\n"
        "Теперь вы можете отправлять сообщения в эту заявку."
    )
    await callback.answer()
