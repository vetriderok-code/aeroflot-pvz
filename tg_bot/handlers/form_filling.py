from aiogram import Router, F
import datetime
import uuid
from aiogram.types import Message, CallbackQuery
from keyboards import keyboard, menu_keyboard
from utils.media_dispatcher import get_content_info
from utils.format_data import map_result_value
from aiogram.fsm.context import FSMContext
from db_handler import db_class
from states import FormMaking
from decouple import config
import logging
import os
from create_bot import bot


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

db = db_class.PostgresHandler()
form_router = Router()
#form_router.message.filter(ChatTypeFilter(chat_type="chat"))

file_storage_dir = os.path.abspath(os.path.join(os.path.curdir, 'files'))
if not os.path.exists(file_storage_dir):
    os.mkdir(file_storage_dir)


@form_router.callback_query(F.data == "make_form")
async def callname_filling(clbck: CallbackQuery, state: FSMContext):

    query = ("SELECT pilot.callname, pilot.engineer_callname, pilot.driver_callname, pilot.drone_type,"
             "pilot.video_type, pilot.manual_type, flight.number,  flight.explosive_type, flight.explosive_device,"
             "flight.target, flight.direction, flight.drone_remains FROM pilot LEFT JOIN flight ON flight.pilot_id = pilot.id WHERE pilot.tg_id = %s ORDER BY flight.number DESC")
    uid = clbck.from_user.id
    data = db.fetchrow(query, (uid,))
    if data:
        await state.update_data(callname=data[0])
        await state.update_data(engineer_callname=data[1])
        await state.update_data(driver_callname=data[2])
        await state.update_data(dronetype=data[3])
        await state.update_data(video=data[4])
        await state.update_data(manage=data[5])
        await state.update_data(fly_number=data[6])
        await state.update_data(explosives_type=data[7])
        await state.update_data(explosives_device=data[8])
        await state.update_data(target=data[9])
        await state.update_data(direction=data[10])
        await state.update_data(remains=data[1])
        fly_number = data[6]
        if not data[0] or not data[1] or not data[2]or not data[3] or not data[4]:
            await clbck.message.answer(text='Нет информации о позывных',
                                       reply_markup=menu_keyboard.enter_data)
            return
    else:
        fly_number = None
    if fly_number:
        kb = keyboard.make_row_keyboard([str(int(fly_number) + 1),])
    else:
        kb = keyboard.empty_kb()
    await clbck.message.answer(text='Введите номер вылета ВНИМАТЕЛЬНО', reply_markup=kb)
    await state.set_state(FormMaking.fly_nuber_filling)

@form_router.message(FormMaking.fly_nuber_filling)
async def fly_date_filling(message: Message, state: FSMContext):
    try:
        int(message.text)
    except Exception as e:
        print(e)
        data = await state.get_data()
        fly_number = data['fly_number']
        if fly_number:
            kb = keyboard.make_row_keyboard([str(int(fly_number) + 1), ])
        else:
            kb = keyboard.empty_kb()
        await message.answer(text='Введите корректный номер вылета ЧИСЛОМ:', reply_markup=kb)
        await state.set_state(FormMaking.fly_nuber_filling)
    else:
        await state.update_data(fly_number=message.text)
        data = await state.get_data()
        date = data.get('fly_date', None)
        if date:
            kb = keyboard.make_row_keyboard([date, ])
        else:
            kb = keyboard.make_row_keyboard([datetime.date.today().strftime("%d.%m")],)
        await message.answer(
            text="Введите дату вылета",
            reply_markup=kb
        )
        await state.set_state(FormMaking.date_filling)

@form_router.message(FormMaking.date_filling)
async def fly_time_filling(message: Message, state: FSMContext):
    try:
        datetime.date(2025, int(message.text.split('.')[1]), int(message.text.split('.')[0]))
    except Exception as e:
        print(e)
        kb = keyboard.make_row_keyboard([datetime.date.today().strftime("%d/%m/%Y")], )
        await message.answer(
            text="Введите корректную дату вылета в формате ДД.ММ",
            reply_markup=kb
        )
        await state.set_state(FormMaking.date_filling)
    else:
        await state.update_data(fly_date=message.text)
        data = await state.get_data()
        time = data.get('fly_time', None)
        if time:
            kb = keyboard.make_row_keyboard([time, ])
        else:
            kb = keyboard.make_row_keyboard([datetime.datetime.now().strftime("%H:%M")],)
        await message.answer(
            text="Введите время вылета",
            reply_markup=kb
        )
        await state.set_state(FormMaking.time_filling)

@form_router.message(FormMaking.time_filling)
async def dronetype_filling(message: Message, state: FSMContext):
    try:
        datetime.time(int(message.text.split(':')[0]), int(message.text.split(':')[1]))
    except Exception as e:
        print(e)
        kb = keyboard.make_row_keyboard([datetime.datetime.now().strftime("%H:%M")], )
        await message.answer(text="Введите корректное время вылета в формате ЧЧ:ММ",
                             reply_markup=kb)
        await state.set_state(FormMaking.time_filling)
    else:
        await state.update_data(fly_time=message.text)

        query = "SELECT name FROM public.drone ORDER BY name"
        res = db.fetch(query)
        drones = [i[0] for i in res]

        data = await state.get_data()
        drone = data.get('dronetype', None)
        if drone:
            if drone in drones:
                drones.remove(drone)
            kb = keyboard.make_n_column_priority_keyboard(drones, drone, 2)
        else:
            kb = keyboard.make_n_column_keyboard(drones, 2)
        await message.answer(
            text="Тип дрона",
            reply_markup=kb
        )
        await state.set_state(FormMaking.dron_model_filling)

@form_router.message(FormMaking.dron_model_filling)
async def explosives_type_filling(message: Message, state: FSMContext):
    await state.update_data(dronetype=message.text)

    query = "SELECT name FROM public.explosive_type ORDER BY name"
    res = db.fetch(query)
    explosives = [i[0] for i in res]

    data = await state.get_data()
    explosives_type = data.get('explosives_type', None)
    if explosives_type:
        if explosives_type in explosives:
            explosives.remove(explosives_type)
        kb = keyboard.make_n_column_priority_keyboard(explosives, explosives_type, 3)
    else:
        kb = keyboard.make_n_column_keyboard(explosives, 3)
    await message.answer(
        text="""Боевая часть
Выберите из списка, если нет - введите корректно""",
        reply_markup=kb
    )
    await state.set_state(FormMaking.explosives_type_filling)

@form_router.message(FormMaking.explosives_type_filling)
async def explosives_device_filling(message: Message, state: FSMContext):
    await state.update_data(explosives_type=message.text)

    query = "SELECT name FROM public.explosive_device ORDER BY name"
    res = db.fetch(query)
    devices = [i[0] for i in res]

    data = await state.get_data()
    explosives_device = data.get('explosives_device', None)
    if explosives_device:
        if explosives_device in devices:
            devices.remove(explosives_device)
        kb = keyboard.make_n_column_priority_keyboard(devices, explosives_device, 2)
    else:
        kb = keyboard.make_n_column_keyboard(devices, 2)
    await message.answer(
        text="Тип взрывателя",
        reply_markup=kb
    )
    await state.set_state(FormMaking.explosives_device_filling)

@form_router.message(FormMaking.explosives_device_filling)
async def distance_filling(message: Message, state: FSMContext):
    await state.update_data(explosives_device=message.text)
    data = await state.get_data()
    distance = data.get('distance', None)
    if distance:
        kb = keyboard.make_row_keyboard([distance, ])
    else:
        kb = keyboard.empty_kb()
    await message.answer(
        text="Дистанция",
        reply_markup=kb
    )
    await state.set_state(FormMaking.distance_filling)

@form_router.message(FormMaking.distance_filling)
async def video_length_filling(message: Message, state: FSMContext):
    text = message.text
    if 'км' not in text:
        text += ' км'
    await state.update_data(distance=text)
    data = await state.get_data()
    video_length = data.get('video_length', None)
    if video_length:
        kb = keyboard.make_row_keyboard([video_length, ])
    else:
        kb = keyboard.empty_kb()
    await message.answer(
        text="""Введите длительность видео
Укажите длительность видео до момента поражения | потери видео и т.п.""",
        reply_markup=kb
    )
    await state.set_state(FormMaking.video_length_filling)

@form_router.message(FormMaking.video_length_filling)
async def target_filling(message: Message, state: FSMContext):
    text = message.text
    if 'мин' not in text:
        text += ' мин'
    await state.update_data(video_length=text)

    query = "SELECT name FROM public.target_type ORDER BY name"
    res = db.fetch(query)
    targets = [i[0] for i in res]

    data = await state.get_data()
    target = data.get('target', None)
    if target:
        if target in targets:
            targets.remove(target)
        kb = keyboard.make_n_column_priority_keyboard(targets, target, 2)
    else:
        kb = keyboard.make_n_column_keyboard(targets, 2)
    await message.answer(
        text="""Характер цели:
Выбирайте исключительно из списка!
Дома и объекты без наводки это <b>инженерное сооружение</b>, не ПВД""",
        reply_markup=kb
    )
    await state.set_state(FormMaking.target_filling)

@form_router.message(FormMaking.target_filling)
async def correction_filling(message: Message, state: FSMContext):
    await state.update_data(target=message.text)

    query = "SELECT name FROM public.corrective_type ORDER BY created"
    res = db.fetch(query)
    correctives = [i[0] for i in res]

    data = await state.get_data()
    correction = data.get('correction', None)
    if correction:
        if correction in correctives:
            correctives.remove(correction)
        kb = keyboard.make_n_column_priority_keyboard(correctives, correction, 2)
    else:
        kb = keyboard.make_n_column_keyboard(correctives, 2)
    await message.answer(
        text="""Уточните цель. Например:
<b>Уточнение: дом | авто | КАМАЗ | капонир | rxloss</b>""",
        reply_markup=kb
    )
    await state.set_state(FormMaking.correction_filling)

@form_router.message(FormMaking.correction_filling)
async def result_filling(message: Message, state: FSMContext):
    await state.update_data(correction=message.text)
    await message.answer(
        text="""Результат
Если цель горит - 🔥 Уничтожено
Попадание или РЦ - ✅ Поражено
Промах, rxloss и т.п. - ❌ Не поражено""",
        reply_markup=keyboard.make_column_keyboard(['🔥 Уничтожено', '✅ Поражено', '❌ Не поражено'])
    )
    await state.set_state(FormMaking.result_filling)

@form_router.message(FormMaking.result_filling)
async def coordinates_x_filling(message: Message, state: FSMContext):
    await state.update_data(result=message.text)
    data = await state.get_data()
    coordinates = data.get('coordinates', None)
    if coordinates:
        kb = keyboard.make_row_keyboard([coordinates, ])
    else:
        kb = keyboard.empty_kb()
    await message.answer(
        text="Координаты X Y",
        reply_markup=kb
    )
    await state.set_state(FormMaking.coordinates_filling)

@form_router.message(FormMaking.coordinates_filling)
async def direction_filling(message: Message, state: FSMContext):
    await state.update_data(coordinates=message.text)
    data = await state.get_data()
    direction = data.get('direction', None)
    query = "SELECT name FROM public.direction_type ORDER BY name"
    res = db.fetch(query)
    nps = [i[0] for i in res]
    if direction:
        if direction in nps:
            nps.remove(direction)
        kb = keyboard.make_n_column_priority_keyboard(nps, direction, 1)
    else:
        kb = keyboard.make_n_column_keyboard(nps, 1)
    await message.answer(
        text="Направление",
        reply_markup=kb
    )
    await state.set_state(FormMaking.direction_filling)

@form_router.message(FormMaking.direction_filling)
async def comments_filling(message: Message, state: FSMContext):
    await state.update_data(direction=message.text)
    data = await state.get_data()
    comment = data.get('comment', None)
    if comment:
        kb = keyboard.make_row_keyboard([comment,])
    else:
        kb = keyboard.empty_kb()
    await message.answer(
        text="Комментарий",
        reply_markup=kb
    )
    await state.set_state(FormMaking.comment_filling)

@form_router.message(FormMaking.comment_filling)
async def remains_filling(message: Message, state: FSMContext):
    await state.update_data(comment=message.text)
    user_data = await state.get_data()
    remains = user_data.get('remains', False)
    if remains:
        try:
            drone_remains = str(int(remains) - 1)
            kb = keyboard.make_row_keyboard([drone_remains, ' '])
        except Exception as e:
            kb = keyboard.empty_kb()
        finally:
            await message.answer(
                text="Остаток дронов",
                reply_markup=kb
            )
            await state.set_state(FormMaking.remains_filling)
    else:
        await message.answer(
            text="Остаток дронов",
            reply_markup=keyboard.empty_kb()
        )
        await state.set_state(FormMaking.remains_filling)

@form_router.message(FormMaking.remains_filling)
async def objective_filling(message: Message, state: FSMContext):
    await state.update_data(remains=message.text)
    await message.answer(
        text="Объектив",
        reply_markup=keyboard.make_column_keyboard(['✅ Есть', '❌ Нет'])
    )
    await state.set_state(FormMaking.objective_filling)

@form_router.message(FormMaking.objective_filling)
async def form_finished(message: Message, state: FSMContext):
    if message.text == '✅ Есть':
        await state.update_data(objective_control=True)
        await state.update_data(objective_control_str='✅ Есть')
    else:
        await state.update_data(objective_control=False)
        await state.update_data(objective_control_str='❌ Нет')
    user_data = await state.get_data()

    await message.answer(
        text=f"""Данные введены успешно
        
Проверте правильность введенных даных:

ОТЧЕТ
_______________________________
Позывной: <b>{user_data['callname']}</b>
Позывной инженера: <b>{user_data['engineer_callname']}</b>
Позывной водителя: <b>{user_data['driver_callname']}</b>
Номер вылета: <b>{user_data['fly_number']}</b>
Дата вылета: <b>{user_data['fly_date']}</b>
Время вылета: <b>{user_data['fly_time']}</b>
Тип дрона: <b>{user_data['dronetype']}</b>
Боевая часть: <b>{user_data['explosives_type']}</b>
Тип взрывателя: <b>{user_data['explosives_device']}</b>
Видео: <b>{user_data['video']}</b>
Управление: <b>{user_data['manage']}</b>
Дистанция: <b>{user_data['distance']}</b>
Длительность Видео: <b>{user_data['video_length']}</b>
Характер цели:<b> {user_data['target']}</b>
Уточнение: <b>{user_data['correction']}</b>
Результат: <b>{user_data['result']}</b>
Координаты: <b>{user_data['coordinates']}</b>
Направление:<b> {user_data['direction']}</b>
Остаток: <b>{user_data['remains']}</b>

Комментарии: <b> {user_data['comment']}</b>
Объектив: <b> {user_data['objective_control_str']}</b>
_______________________________

Продолжить или внести изменения?
        """,
        reply_markup=keyboard.make_row_keyboard(['◀️ Изменить', '✅ Продолжить']))
    await state.set_state(FormMaking.finished)

@form_router.message(FormMaking.finished, F.text == '✅ Продолжить')
async def send_form(message: Message, state: FSMContext):

    await message.answer(
        text="""Отчет сформирован
Прикрепите видеозапись или отправте отчет без видео""",
        reply_markup=keyboard.make_column_keyboard(['Отправить без видео', '◀️ Выйти в меню (не отправлять)'])
    )
    await state.set_state(FormMaking.video_pining)

@form_router.message(FormMaking.video_pining)
async def video_pining(message: Message, state: FSMContext):
    user_data = await state.get_data()
    query = "UPDATE pilot SET callname = %s WHERE tg_id = %s"
    db.execute(query, (user_data['callname'], message.from_user.id))
    query = "SELECT id FROM pilot WHERE tg_id = %s"
    idx = db.fetchrow(query, (message.from_user.id,))
    mapped_result = map_result_value(user_data['result'])
    user_data['fly_date'] = datetime.date(2025, int(user_data['fly_date'].split('.')[1]), int(user_data['fly_date'].split('.')[0]))

    time = user_data['fly_time']
    user_data['fly_time'] = datetime.time(int(time.split(':')[0]),
                                          int(time.split(':')[1]))

    query = """INSERT INTO public.flight(
    	id, pilot_id, engineer, driver, drone, video, manage, number, explosive_type, explosive_device, target, direction, drone_remains, flight_date, flight_time, distance, corrective, result, "coordinates", comment, objective, created, modified)
    	VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);"""

    row = [
        idx,
        user_data['engineer_callname'],
        user_data['driver_callname'],
        user_data['dronetype'],
        user_data['video'],
        user_data['manage'],
        user_data['fly_number'],
        user_data['explosives_type'],
        user_data['explosives_device'],
        user_data['target'],
        user_data['direction'],
        user_data['remains'],
        user_data['fly_date'],
        user_data['fly_time'],
        user_data['distance'],
        user_data['correction'],
        mapped_result,
        user_data['coordinates'],
        user_data['comment'],
        user_data['objective_control'],
        datetime.datetime.now(),
        datetime.datetime.now(),
    ]
    db.execute(query, row)

    res = db.fetchrow('SELECT id FROM flight WHERE pilot_id = %s ORDER BY id DESC', (idx,))
    if res:
        fly_id = res[0]
    else:
        await message.answer(
            text="Ошибка добавления записи, проверте правильность введеных данных и состояние сервера БД!",
            reply_markup=menu_keyboard.exit_kb
        )
        return
    await state.update_data(fly_id=fly_id)
    #add_row(fly_id)
    data = get_content_info(message)
    if data['content_type'] == 'video':
        file_id = message.video.file_id
        #file = await bot.get_file(file_id)
        #await bot.download_file(file.file_path, os.path.join(file_storage_dir, str(fly_id) + '.mp4'))

    text = f"""
ОТЧЕТ
_______________________________
Позывной: <b><code>{user_data['callname']}</code></b>
Позывной инженера: <b><code>{user_data['engineer_callname']}</code></b>
Позывной водителя: <b><code>{user_data['driver_callname']}</code></b>
Номер вылета: <b><code>{user_data['fly_number']}</code></b>
Дата вылета: <b><code>{user_data['fly_date']}</code></b>
Время вылета: <b><code>{user_data['fly_time']}</code></b>
Тип дрона: <b><code>{user_data['dronetype']}</code></b>
Боевая часть: <b><code>{user_data['explosives_type']}</code></b>
Тип взрывателя: <b><code>{user_data['explosives_device']}</code></b>
Видео: <b><code>{user_data['video']}</code></b>
Управление: <b><code>{user_data['manage']}</code></b>
Дистанция: <b><code>{user_data['distance']}</code></b>
Длительность Видео: <b><code>{user_data['video_length']}</code></b>
Характер цели:<b><code> {user_data['target']}</code></b>
Уточнение: <b><code>{user_data['correction']}</code></b>
Результат: <b><code>{user_data['result']}</code></b>
Координаты: <b>{user_data['coordinates']}</b>
Направление:<b><code> {user_data['direction']}</code></b>
Остаток: <b><code>{user_data['remains']}</code></b>

Комментарии: <b><code> {user_data['comment']}</code></b>
Объектив: <b><code> {user_data['objective_control_str']}</code></b>
_______________________________
"""
    query = "SELECT name FROM public.drone WHERE drone_type = 'st' ORDER BY created"
    res = db.fetch(query)
    st_drones = [i[0] for i in res]

    tg_group = config('TG_GROUP_ID')

    if data['content_type'] == 'video':
        if user_data['dronetype'] in st_drones:
            await bot.send_video(tg_group, file_id, caption=text, reply_to_message_id=config('TG_TOPIC_ST'))
        else:
            await bot.send_video(tg_group, file_id, caption=text, reply_to_message_id=config('TG_TOPIC_KT'))
    else:
        if user_data['dronetype'] in st_drones:
            await bot.send_message(tg_group, text, reply_to_message_id=config('TG_TOPIC_ST'))
        else:
            await bot.send_message(tg_group, text, reply_to_message_id=config('TG_TOPIC_KT'))

    await message.answer(
        text="Отчет отпрален!",
        reply_markup=menu_keyboard.exit_kb
    )
    await state.clear()

@form_router.message(FormMaking.finished, F.text == '◀️ Изменить')
async def fly_number_refilling(message: Message, state: FSMContext):
    data = await state.get_data()
    await message.answer(text='Введите номер вылета ВНИМАТЕЛЬНО', reply_markup=keyboard.make_row_keyboard([data['fly_number'], ]))
    await state.set_state(FormMaking.fly_nuber_filling)