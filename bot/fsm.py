from aiogram.fsm.state import State, StatesGroup

class UserRegistration(StatesGroup):
    """Состояния для регистрации пользователя"""
    waiting_fullname = State()

class TicketCreation(StatesGroup):
    """Состояния для создания тикета"""
    waiting_description = State()
    waiting_confirmation = State()

class TicketSelection(StatesGroup):
    """Состояния для выбора существующего тикета"""
    selecting_ticket = State()
    waiting_reply = State()
