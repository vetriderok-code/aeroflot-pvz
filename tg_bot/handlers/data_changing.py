from aiogram import Router, F
import datetime
from aiogram.types import Message, CallbackQuery
from keyboards import keyboard, menu_keyboard
from aiogram.fsm.context import FSMContext
from db_handler import db_class
from states import DataChanging
import logging


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


db = db_class.PostgresHandler()
userdata_router = Router()

@userdata_router.callback_query(F.data == "show_data")
async def show_data(clbck: CallbackQuery, state: FSMContext):
    query = "SELECT pilot.callname, pilot.engineer_callname, pilot.driver_callname, pilot.drone_type, pilot.video_type, pilot.manual_type FROM pilot WHERE pilot.tg_id = %s"
    uid = clbck.from_user.id
    data = db.fetchrow(query, (uid,))

    text = f"""
Позывной: <b>{data[0]}</b>
Позывной инженера: <b>{data[1]}</b>
Позывной водителя: <b>{data[2]}</b>
Тип дрона: <b>{data[3]}</b>
Видео: <b>{data[4]}</b>
Управление: <b>{data[5]}</b>
"""
    await clbck.message.answer(text=text, reply_markup=menu_keyboard.exit_kb)

@userdata_router.callback_query(F.data == "change_data")
async def callname_filling(clbck: CallbackQuery, state: FSMContext):
    query = "SELECT * FROM pilot WHERE pilot.tg_id = %s"
    uid = clbck.from_user.id
    data = db.fetchrow(query, (uid,))
    if data:
        await state.update_data(callname=data[3])
        await state.update_data(engineer_callname=data[5])
        await state.update_data(driver_callname=data[6])
        await state.update_data(dronetype=data[7])
        await state.update_data(video=data[8])
        await state.update_data(manage=data[9])
        callname = data[3]
    else:
        callname = clbck.from_user.full_name
    await clbck.message.answer(text='Введите позывной', reply_markup=keyboard.make_row_keyboard([callname,]))
    await state.set_state(DataChanging.call_name_filling)

@userdata_router.message(DataChanging.call_name_filling)
async def engineer_callname_filling(message: Message, state: FSMContext):
    await state.update_data(callname=message.text)
    data = await state.get_data()
    engineer_callname = data.get('engineer_callname', None)
    if engineer_callname:
        kb = keyboard.make_row_keyboard([engineer_callname,])
    else:
        kb = keyboard.empty_kb()
    await message.answer(
        text="Введите позывной инженера",
        reply_markup=kb
    )
    await state.set_state(DataChanging.engineer_call_name_filling)

@userdata_router.message(DataChanging.engineer_call_name_filling)
async def driver_callname_filling(message: Message, state: FSMContext):
    await state.update_data(engineer_callname=message.text)
    data = await state.get_data()
    driver_callname = data.get('driver_callname', None)
    if driver_callname:
        kb = keyboard.make_row_keyboard([driver_callname,])
    else:
        kb = keyboard.empty_kb()
    await message.answer(
        text="Введите позывной водителя",
        reply_markup=kb
    )
    await state.set_state(DataChanging.driver_call_name_filling)

@userdata_router.message(DataChanging.driver_call_name_filling)
async def dronetype_filling(message: Message, state: FSMContext):
    await state.update_data(driver_callname=message.text)
    query = "SELECT name FROM public.drone ORDER BY name"
    res = db.fetch(query)
    drones = [i[0] for i in res]

    data = await state.get_data()
    dronetype = data.get('dronetype', None)
    if dronetype:
        if dronetype in drones:
            drones.remove(dronetype)
        kb = keyboard.make_n_column_priority_keyboard(drones, dronetype, 2)
    else:
        kb = keyboard.make_n_column_keyboard(drones, 2)
    await message.answer(
        text="Введите модель дрона",
        reply_markup=kb
    )
    await state.set_state(DataChanging.dronetype_filling)


@userdata_router.message(DataChanging.dronetype_filling)
async def video_filling(message: Message, state: FSMContext):
    await state.update_data(dronetype=message.text)
    data = await state.get_data()
    video_type = data.get('video', None)
    if video_type:
        kb = keyboard.make_row_keyboard([video_type,])
    else:
        kb = keyboard.empty_kb()
    await message.answer(
        text="Введите тип видео",
        reply_markup=kb
    )
    await state.set_state(DataChanging.video_type_filling)

@userdata_router.message(DataChanging.video_type_filling)
async def manage_filling(message: Message, state: FSMContext):
    await state.update_data(video=message.text)
    data = await state.get_data()
    manage_type = data.get('manage', None)
    if manage_type:
        kb = keyboard.make_row_keyboard([manage_type,])
    else:
        kb = keyboard.empty_kb()
    await message.answer(
        text="Введите тип управления",
        reply_markup=kb
    )
    await state.set_state(DataChanging.manage_type_filling)


@userdata_router.message(DataChanging.manage_type_filling)
async def form_finished(message: Message, state: FSMContext):
    await state.update_data(manage=message.text)
    user_data = await state.get_data()
    await message.answer(
        text=f"""Данные введены успешно

Проверте правильность введенных даных:

_______________________________
Позывной: <b>{user_data['callname']}</b>
Позывной инженера: <b>{user_data['engineer_callname']}</b>
Позывной водителя: <b>{user_data['driver_callname']}</b>
Тип дрона: <b>{user_data['dronetype']}</b>
Видео: <b>{user_data['video']}</b>
Управление: <b>{user_data['manage']}</b>
_______________________________

Сохранить или внести изменения?
        """,
        reply_markup=keyboard.make_row_keyboard(['◀️ Изменить', '✅ Сохранить']))
    await state.set_state(DataChanging.finished)


@userdata_router.message(DataChanging.finished, F.text == '✅ Сохранить')
async def save_form(message: Message, state: FSMContext):
    user_data = await state.get_data()
    uid = message.from_user.id
    query = "UPDATE pilot SET callname = %s WHERE tg_id = %s"
    db.execute(query, (user_data['callname'], uid))
    query = "UPDATE pilot SET engineer_callname = %s WHERE tg_id = %s"
    db.execute(query, (user_data['engineer_callname'], uid))
    query = "UPDATE pilot SET driver_callname = %s WHERE tg_id = %s"
    db.execute(query, (user_data['driver_callname'], uid))
    query = "UPDATE pilot SET drone_type = %s WHERE tg_id = %s"
    db.execute(query, (user_data['dronetype'], uid))
    query = "UPDATE pilot SET video_type = %s WHERE tg_id = %s"
    db.execute(query, (user_data['video'], uid))
    query = "UPDATE pilot SET manual_type = %s WHERE tg_id = %s"
    db.execute(query, (user_data['manage'], uid))

    await message.answer(
        text="Данные сохранены успешно!!",
        reply_markup=menu_keyboard.exit_kb
    )
    await state.clear()

@userdata_router.message(DataChanging.finished, F.text == '◀️ Изменить')
async def callname_refilling(message: Message, state: FSMContext):
    user_data = await state.get_data()
    await message.answer(text='Введите позывной', reply_markup=keyboard.make_row_keyboard([user_data['callname'],]))
    await state.set_state(DataChanging.call_name_filling)