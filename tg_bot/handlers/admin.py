import datetime

from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext
from create_bot import bot
from utils import table_filler
from db_handler import db_class


db = db_class.PostgresHandler()
admin_router = Router()

@admin_router.callback_query(F.data == "decline")
async def user_accept(clbck: CallbackQuery, state: FSMContext):
    await clbck.answer('Запрос отклонён')
    await clbck.message.edit_reply_markup()

@admin_router.callback_query(F.data.startswith("accept"))
async def user_accept(clbck: CallbackQuery, state: FSMContext):
    tg_id = int(clbck.data.split('::')[1])
    callname = clbck.data.split('::')[2]
    query = "INSERT INTO pilot (id, tg_id, callname, created, modified) VALUES (gen_random_uuid(), %s, %s, %s, %s)"
    db.execute(query, (tg_id, callname, datetime.datetime.now(), datetime.datetime.now()))
    await clbck.answer('Запрос принят')
    await clbck.message.edit_reply_markup()
    await bot.send_message(tg_id, "✅ Администратор бота разрешил доступ")

@admin_router.callback_query(F.data == 'make_total_form')
async def make_total_form(clbck: CallbackQuery, state: FSMContext):
    table_filler.make_doc(datetime.date.today())
    doc = FSInputFile(f"./Отчет_{datetime.date.today().strftime('%Y_%m_%d')}.xlsx")
    await clbck.message.answer_document(doc)
    await clbck.message.edit_reply_markup()

@admin_router.callback_query(F.data == 'make_total_form_before')
async def make_total_form_before(clbck: CallbackQuery, state: FSMContext):
    table_filler.make_doc(datetime.date.today() - datetime.timedelta(days=1))
    doc = FSInputFile(f"./Отчет_{(datetime.date.today()- datetime.timedelta(days=1)).strftime('%Y_%m_%d')}.xlsx")
    await clbck.message.answer_document(doc)
