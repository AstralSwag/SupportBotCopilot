from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from bot.models.models import User
from bot.fsm import UserRegistration, TicketCreation, TicketSelection
from bot.keyboards import get_main_keyboard, get_tickets_keyboard
from bot.services.ticket_service import TicketService

router = Router()
ticket_service = TicketService()

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка команды /start"""
    user = await ticket_service.get_user_by_telegram_id(session, message.from_user.id)
    
    if user:
        await message.answer(
            "Здравствуйте! Чем могу помочь?\n"
            "Отправьте сообщение с описанием вашего вопроса.",
            reply_markup=get_main_keyboard()
        )
    else:
        await message.answer(
            "Добро пожаловать! Для начала работы мне нужно знать ваше полное имя.\n"
            "Пожалуйста, введите ваше имя и фамилию. Например, \"Сергей Петров\":"
        )
        await state.set_state(UserRegistration.waiting_fullname)

@router.message(UserRegistration.waiting_fullname)
async def process_fullname(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка ввода полного имени при регистрации"""
    full_name = message.text.strip()
    
    if len(full_name.split()) < 2:
        await message.answer("Пожалуйста, введите полное имя (имя и фамилию):")
        return
    
    await state.update_data(full_name=full_name)
    await state.set_state(UserRegistration.waiting_company)
    await message.answer(
        "В какой компании вы работаете? Например, \"Лента\":"
    )

@router.message(UserRegistration.waiting_company)
async def process_company(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка ввода компании при регистрации"""
    company = message.text.strip()
    
    if not company:
        await message.answer("Пожалуйста, введите название компании:")
        return
    
    await state.update_data(company=company)
    await state.set_state(UserRegistration.waiting_shop)
    await message.answer(
        "На какой торговой точке (магазине) вы работаете? Напишите так как вы её обычно называете:"
    )

@router.message(UserRegistration.waiting_shop)
async def process_shop(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка ввода магазина при регистрации"""
    shop = message.text.strip()
    
    if not shop:
        await message.answer("Пожалуйста, введите название магазина:")
        return
    
    user_data = await state.get_data()
    
    new_user = User(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        full_name=user_data['full_name'],
        company=user_data['company'],
        shop=shop
    )
    session.add(new_user)
    await session.commit()
    
    await state.clear()
    await message.answer(
        "Спасибо за регистрацию! Теперь вы можете отправить сообщение с описанием вашей проблемы.",
        reply_markup=get_main_keyboard()
    )

@router.message(F.text == "Создать новую заявку")
async def create_new_ticket(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка нажатия кнопки создания новой заявки"""
    user = await ticket_service.get_user_by_telegram_id(session, message.from_user.id)
    if not user:
        await message.answer("Пожалуйста, начните с команды /start для регистрации.")
        return
    
    await state.set_state(TicketCreation.waiting_title)
    await message.answer(
        "Пожалуйста, введите название заявки (не более 100 символов):"
    )

@router.message(F.text == "Выбрать существующую заявку")
async def select_existing_ticket(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка нажатия кнопки выбора существующей заявки"""
    user = await ticket_service.get_user_by_telegram_id(session, message.from_user.id)
    if not user:
        await message.answer("Пожалуйста, начните с команды /start для регистрации.")
        return
    
    tickets = await ticket_service.get_active_tickets(session, user.id)
    
    if not tickets:
        await message.answer("У вас нет активных заявок.")
        return
    
    tickets_data = ticket_service.format_tickets_for_keyboard(tickets)
    
    await state.set_state(TicketSelection.selecting_ticket)
    await message.answer(
        "Выберите заявку:",
        reply_markup=get_tickets_keyboard(tickets_data)
    )

@router.callback_query(F.data.startswith("ticket_"))
async def process_ticket_selection(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработка выбора тикета из списка"""
    ticket_id = int(callback.data.split("_")[1])
    
    ticket = await ticket_service.get_ticket_by_id(session, ticket_id)
    if not ticket:
        await callback.answer("Тикет не найден")
        return
    
    await state.update_data(selected_ticket_id=ticket_id)
    await state.set_state(TicketSelection.waiting_reply)
    
    await callback.message.edit_text(
        f"Выбрана заявка: {ticket.title}\n"
        "Теперь вы можете отправлять сообщения в эту заявку."
    )
    await callback.answer()
