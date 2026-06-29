from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
menu = [
    [InlineKeyboardButton(text="✍ Создать отчет", callback_data="make_form")],
    [InlineKeyboardButton(text="👤 Просмотр профиля", callback_data="show_data"),
    InlineKeyboardButton(text="🔁 Изменить данные", callback_data="change_data")],
]
enter_data = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Ввести данные", callback_data="change_data")]])
menu = InlineKeyboardMarkup(inline_keyboard=menu)
exit_kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="◀️ Выйти в меню")]], resize_keyboard=True, one_time_keyboard=True)
iexit_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Выйти в меню", callback_data="menu")]])