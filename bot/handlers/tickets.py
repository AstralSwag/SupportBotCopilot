from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from bot.models.models import User
from bot.services.ticket_service import TicketService
from bot.fsm import TicketCreation, TicketSelection
from bot.keyboards import get_tickets_keyboard, get_confirmation_keyboard

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
    data = await state.get_data()
    title = data.get('title', '')
    
    # Создаем тикет в базе данных
    user = await ticket_service.get_user_by_telegram_id(session, message.from_user.id)
    if not user:
        await message.answer("Пожалуйста, начните с команды /start для регистрации.")
        await state.clear()
        return

    try:
        # Создаем тикет со статусом "pending"
        ticket = await ticket_service.create_pending_ticket(session, user, title, message.text)
        await state.update_data(ticket_id=ticket.id)
        await state.set_state(TicketCreation.waiting_confirmation)
        
        await message.answer(
            f"Я создам новое обращение:\n"
            f"Название: *#{ticket.id} {title}*\n"
            f"Описание: {message.text}\n\n"
            "Пожалуйста, подтвердите создание обращения:",
            reply_markup=get_confirmation_keyboard(),
            parse_mode="Markdown"
        )
    except Exception as e:
        await message.answer("Произошла ошибка при создании обращения. Пожалуйста, попробуйте позже.")
        print(f"Error creating ticket: {e}")
        await state.clear()

@router.callback_query(F.data == "confirm_ticket")
async def process_confirmation(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработка подтверждения создания тикета"""
    data = await state.get_data()
    ticket_id = data.get('ticket_id')
    
    if not ticket_id:
        await callback.message.edit_text("Произошла ошибка. Пожалуйста, начните создание обращения заново.")
        await state.clear()
        return

    try:
        # Получаем тикет
        ticket = await ticket_service.get_ticket_by_id(session, ticket_id)
        if not ticket:
            await callback.message.edit_text("Тикет не найден. Пожалуйста, начните создание обращения заново.")
            await state.clear()
            return

        # Отправляем тикет в Mattermost и Plane
        await ticket_service.activate_ticket(session, ticket)
        
        await callback.message.edit_text(
            f"Обращение *#{ticket.id} {ticket.title}* создано. Мы ответим вам в течение 5 минут.\n"
            "Вы можете продолжать отправлять сообщения, они будут добавлены к заявке.",
            parse_mode="Markdown"
        )
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при создании обращения. Пожалуйста, попробуйте позже.")
        print(f"Error activating ticket: {e}")
    finally:
        await state.clear()

@router.callback_query(F.data == "cancel_ticket")
async def process_cancellation(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработка отмены создания тикета"""
    data = await state.get_data()
    ticket_id = data.get('ticket_id')
    
    if ticket_id:
        try:
            # Получаем тикет
            ticket = await ticket_service.get_ticket_by_id(session, ticket_id)
            if ticket:
                # Отменяем тикет
                await ticket_service.cancel_ticket(session, ticket)
        except Exception as e:
            print(f"Error canceling ticket: {e}")
    
    await state.clear()
    await callback.message.edit_text("Создание обращения отменено.")

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
