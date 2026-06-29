from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from keyboards import menu_keyboard, keyboard
from aiogram.fsm.context import FSMContext
import text

common_router = Router()


@common_router.message(Command(commands=["cancel"]))
@common_router.message(F.text.lower() == "отмена")
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        text="Действие отменено",
        reply_markup=keyboard.empty_kb()
    )