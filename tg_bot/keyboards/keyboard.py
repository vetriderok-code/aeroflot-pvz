from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.utils.formatting import Bold


def make_row_keyboard(items: list[str]) -> ReplyKeyboardMarkup:
    row = [KeyboardButton(text=item) for item in items]
    return ReplyKeyboardMarkup(keyboard=[row], resize_keyboard=True)

def make_column_keyboard(items: list[str]) -> ReplyKeyboardMarkup:
    row = list()
    for item in items:
        row.append([KeyboardButton(text=item)])
    return ReplyKeyboardMarkup(keyboard=row, resize_keyboard=True)

def make_n_column_keyboard(items: list[str], n: int) -> ReplyKeyboardMarkup:
    rows = list()
    for i in range(0, len(items), n):
        rows.append([KeyboardButton(text=item) for item in items[i:i + n]])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)

def make_n_column_priority_keyboard(items: list[str], priority: str, n: int) -> ReplyKeyboardMarkup:
    rows = list()
    rows.append([KeyboardButton(text=f'{priority}')])
    for i in range(0, len(items), n):
        rows.append([KeyboardButton(text=item) for item in items[i:i + n]])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def empty_kb() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()