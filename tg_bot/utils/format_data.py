import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def map_result_value(result_value):
    """
    Преобразование значения результата из True/False в FlightResultTypes
    """
    if isinstance(result_value, bool):
        return 'defeated' if result_value else 'not defeated'
    elif isinstance(result_value, str):
        # Если строка, проверяем значения
        if result_value.lower() in ['true', '1', 'yes', 'да', 'попадание', '✅ поражено']:
            return 'defeated'
        if result_value.lower() in ['уничтожено', '🔥 уничтожено']:
            return 'destroyed'
        elif result_value.lower() in ['false', '0', 'no', 'нет', 'промах']:
            return 'not defeated'
        else:
            # Если неизвестное значение, возвращаем по умолчанию
            return 'not defeated'
    else:
        # Для других типов значений
        logger.info('not defeated')
        return 'not defeated'
