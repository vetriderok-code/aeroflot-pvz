from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

start_router = Router()


@start_router.message(CommandStart())
async def cmd_start(message: Message):
    if message.chat.type in ('group', 'supergroup'):
        return
    await message.answer(
        'Бот работает в оперативной группе:\n'
        '• «Старт» / «Стоп» — учёт вылетов\n'
        '• топик отчётов — счётчик на дашборде\n'
        '• топик оповещений — лента на дашборде'
    )
