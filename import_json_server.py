#!/usr/bin/env python
"""
Скрипт для импорта JSON данных на сервере
Использование: python import_json_server.py /tmp/db_export.json
"""
import os
import sys
import json
import django

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.core import serializers
from flights.models import Pilot, Flight, Drone, ExplosiveType, ExplosiveDevice, TargetType, CorrectiveType, ImportProgress

def import_data(json_file):
    print(f'Загрузка данных из {json_file}...')
    
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Проверяем формат данных
    if isinstance(data, list) and len(data) > 0:
        # Проверяем, это наш формат или стандартный Django формат
        if isinstance(data[0], dict) and 'data' in data[0]:
            # Наш формат с вложенными данными
            print('Обнаружен формат с вложенными данными...')
            total_imported = 0
            for item in data:
                model_name = item.get('model', '')
                model_data = item.get('data', [])
                count = len(model_data)
                print(f'  Импорт {model_name}: {count} записей...')
                
                imported = 0
                for obj_data in model_data:
                    try:
                        for obj in serializers.deserialize('json', json.dumps([obj_data])):
                            obj.save()
                            imported += 1
                    except Exception as e:
                        print(f'    Ошибка: {e}')
                
                total_imported += imported
                print(f'    Импортировано: {imported}/{count}')
            
            print(f'\n✓ Импорт завершен! Всего импортировано: {total_imported} записей')
        else:
            # Стандартный формат Django loaddata
            print('Обнаружен стандартный формат Django...')
            imported = 0
            for obj in serializers.deserialize('json', json.dumps(data)):
                try:
                    obj.save()
                    imported += 1
                    if imported % 1000 == 0:
                        print(f'  Импортировано: {imported} записей...')
                except Exception as e:
                    print(f'  Ошибка импорта записи: {e}')
            
            print(f'\n✓ Импорт завершен! Всего импортировано: {imported} записей')
    else:
        print('Ошибка: Неверный формат данных!')
        return False
    
    # Проверка данных
    print('\nПроверка данных:')
    print(f'  Пилотов: {Pilot.objects.count()}')
    print(f'  Полетов: {Flight.objects.count()}')
    print(f'  Дронов: {Drone.objects.count()}')
    print(f'  Типов взрывчатых веществ: {ExplosiveType.objects.count()}')
    print(f'  Взрывных устройств: {ExplosiveDevice.objects.count()}')
    print(f'  Типов целей: {TargetType.objects.count()}')
    
    return True

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Использование: python import_json_server.py <путь_к_json_файлу>')
        sys.exit(1)
    
    json_file = sys.argv[1]
    if not os.path.exists(json_file):
        print(f'Ошибка: Файл {json_file} не найден!')
        sys.exit(1)
    
    import_data(json_file)









