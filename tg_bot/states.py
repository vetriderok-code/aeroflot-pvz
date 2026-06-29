from aiogram.fsm.state import StatesGroup, State

class FormMaking(StatesGroup):
    call_name_filling = State()
    fly_nuber_filling = State()
    date_filling = State()
    time_filling = State()
    dron_model_filling = State()
    explosives_type_filling = State()
    explosives_device_filling = State()
    distance_filling = State()
    video_length_filling = State()
    target_filling = State()
    correction_filling = State()
    result_filling = State()
    coordinates_filling = State()
    direction_filling = State()
    video_pining = State()
    finished = State()
    comment_filling = State()
    objective_filling = State()
    remains_filling = State()


class DataChanging(StatesGroup):
    call_name_filling = State()
    engineer_call_name_filling = State()
    driver_call_name_filling = State()
    dronetype_filling = State()
    video_type_filling = State()
    manage_type_filling = State()
    finished = State()

class AdminStates(StatesGroup):
    accepting = State()