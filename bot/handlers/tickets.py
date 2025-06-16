from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from bot.models.models import User
from bot.services.ticket_service import TicketService
from bot.fsm import TicketCreation, TicketSelection
from bot.keyboards import get_tickets_keyboard

router = Router()
ticket_service = TicketService()

@router.message(TicketCreation.waiting_title)
async def process_title(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка ввода названия тикета"""
    title = message.text.strip()
    
    if len(title) > 100:
        await message.answer("Название слишком длинное. Пожалуйста, введите название короче 100 символов:")
        return
    
    user = await ticket_service.get_user_by_telegram_id(session, message.from_user.id)
    if not user:
        await message.answer("Пожалуйста, начните с команды /start для регистрации.")
        await state.clear()
        return
    
    await state.update_data(title=title)
    await state.set_state(TicketCreation.waiting_description)
    await message.answer("Теперь опишите вашу проблему подробнее:")

@router.message(TicketCreation.waiting_description)
async def process_description(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка описания тикета"""
    await state.update_data(initial_message=message.text)
    await state.set_state(TicketCreation.waiting_confirmation)
    
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

    user = await ticket_service.get_user_by_telegram_id(session, message.from_user.id)
    if not user:
        await message.answer("Пожалуйста, начните с команды /start для регистрации.")
        await state.clear()
        return

    try:
        await ticket_service.create_ticket(session, user, title, initial_message)
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
    user = await ticket_service.get_user_by_telegram_id(session, message.from_user.id)
    if not user:
        await message.answer("Пожалуйста, начните с команды /start для регистрации.")
        return

    state_data = await state.get_data()
    selected_ticket_id = state_data.get('selected_ticket_id')
    
    if selected_ticket_id:
        ticket = await ticket_service.get_ticket_by_id(session, selected_ticket_id)
        
        if ticket and ticket.status != 'closed':
            await ticket_service.add_message_to_ticket(session, ticket, message.text)
            await message.answer("Сообщение добавлено к выбранной заявке.")
            return
    
    last_ticket = await ticket_service.get_last_ticket(session, user.id)

    if last_ticket and last_ticket.status != 'closed':
        await ticket_service.add_message_to_ticket(session, last_ticket, message.text)
        await message.answer("Сообщение добавлено к текущей заявке.")
    else:
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
