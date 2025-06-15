from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.models import User
from ..fsm import UserRegistration
from sqlalchemy import select

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
            "Отправьте сообщение с описанием вашего вопроса."
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
        "Спасибо за регистрацию! Теперь вы можете отправить сообщение с описанием вашего вопроса."
    )
