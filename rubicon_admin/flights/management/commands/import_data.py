"""
Django management команда для импорта данных из JSON
Использование: python manage.py import_data --input export.json
"""
from django.core.management.base import BaseCommand
from django.core import serializers
from django.db import transaction
import json
import os


class Command(BaseCommand):
    help = 'Импорт данных из JSON файла в БД'

    def add_arguments(self, parser):
        parser.add_argument(
            '--input',
            type=str,
            required=True,
            help='Путь к входному JSON файлу'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Очистить существующие данные перед импортом'
        )
        parser.add_argument(
            '--models',
            nargs='+',
            help='Список моделей для импорта (если не указан, импортируются все)'
        )

    def handle(self, *args, **options):
        input_file = options['input']
        clear = options['clear']
        models_filter = options.get('models', [])

        if not os.path.exists(input_file):
            self.stdout.write(
                self.style.ERROR(f'Файл {input_file} не найден!')
            )
            return

        file_size = os.path.getsize(input_file) / 1024 / 1024
        self.stdout.write(f'Импорт данных из {input_file} ({file_size:.2f} MB)...')

        # Загружаем данные
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if not isinstance(data, list):
            self.stdout.write(
                self.style.ERROR('Неверный формат файла! Ожидается список объектов.')
            )
            return

        # Очистка данных (если нужно)
        if clear:
            self.stdout.write('Очистка существующих данных...')
            for item in data:
                model = item.get('model')
                if model:
                    try:
                        app_label, model_name = model.split('.')
                        from django.apps import apps
                        Model = apps.get_model(app_label, model_name)
                        Model.objects.all().delete()
                        self.stdout.write(f'  Очищено {model}')
                    except Exception as e:
                        self.stdout.write(
                            self.style.WARNING(f'  Ошибка при очистке {model}: {e}')
                        )

        # Импортируем данные
        total_imported = 0
        total_errors = 0

        with transaction.atomic():
            for item in data:
                model = item.get('model')
                if not model:
                    continue

                # Фильтр по моделям (если указан)
                if models_filter and model not in models_filter:
                    continue

                try:
                    app_label, model_name = model.split('.')
                    from django.apps import apps
                    Model = apps.get_model(app_label, model_name)

                    model_data = item.get('data', [])
                    count = len(model_data)

                    if count == 0:
                        continue

                    self.stdout.write(f'  Импорт {model}: {count} записей...')

                    # Десериализуем и сохраняем
                    imported = 0
                    for obj_data in model_data:
                        try:
                            # Используем Django deserializer
                            for obj in serializers.deserialize('json', json.dumps([obj_data])):
                                obj.save()
                                imported += 1
                        except Exception as e:
                            total_errors += 1
                            if total_errors <= 10:  # Показываем только первые 10 ошибок
                                self.stdout.write(
                                    self.style.WARNING(f'    Ошибка импорта записи: {e}')
                                )

                    total_imported += imported
                    self.stdout.write(f'    Импортировано: {imported}/{count}')

                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'  Ошибка при импорте {model}: {e}')
                    )
                    total_errors += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'\n✓ Импорт завершен!'
                f'\n  Импортировано: {total_imported} записей'
                f'\n  Ошибок: {total_errors}'
            )
        )









