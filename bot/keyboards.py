from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Dict, Any

def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Создает основную клавиатуру с кнопками"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Создать новую заявку")],
            [KeyboardButton(text="Выбрать существующую заявку")]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_tickets_keyboard(tickets: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """Создает клавиатуру со списком тикетов"""
    keyboard = []
    for ticket in tickets:
        # Если title отсутствует, используем номер тикета
        button_text = ticket.get('title', f"Тикет #{ticket['id']}")
        if ticket['status'] == 'new':
            button_text += " -new"
        keyboard.append([InlineKeyboardButton(
            text=button_text,
            callback_data=f"ticket_{ticket['id']}"
        )])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру подтверждения с кнопками 'Подтвердить' и 'Отмена'"""
    keyboard = [
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_ticket"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_ticket")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard) 