from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove

def make_accept_keyboard(user_tg_id: int, callname: str) -> InlineKeyboardMarkup:
    menu = [
        [InlineKeyboardButton(text="✅ Принять", callback_data=f'accept::{user_tg_id}::{callname}')],
        [InlineKeyboardButton(text="❌ Отклонить", callback_data="decline")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=menu)

def admin_menu() -> InlineKeyboardMarkup:
    menu = [
        [InlineKeyboardButton(text="Сформировать суточный отчет", callback_data='make_total_form')],
        [InlineKeyboardButton(text="Сформировать суточный отчет за предыдущий день", callback_data='make_total_form_before')],
    ]
    return InlineKeyboardMarkup(inline_keyboard=menu)