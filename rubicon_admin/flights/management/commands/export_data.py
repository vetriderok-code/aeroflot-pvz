"""
Django management команда для экспорта данных в JSON
Использование: python manage.py export_data --output export.json
"""
from django.core.management.base import BaseCommand
from django.core import serializers
import json
import os


class Command(BaseCommand):
    help = 'Экспорт данных из БД в JSON файл'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            type=str,
            default='db_export.json',
            help='Путь к выходному JSON файлу'
        )
        parser.add_argument(
            '--models',
            nargs='+',
            default=[
                'flights.Pilot',
                'flights.Flight',
                'flights.Drone',
                'flights.ExplosiveType',
                'flights.ExplosiveDevice',
                'flights.TargetType',
                'flights.CorrectiveType',
                'flights.ImportProgress',
            ],
            help='Список моделей для экспорта'
        )
        parser.add_argument(
            '--indent',
            type=int,
            default=2,
            help='Отступ для JSON (0 = компактный)'
        )

    def handle(self, *args, **options):
        output_file = options['output']
        models = options['models']
        indent = options['indent']

        self.stdout.write(f'Экспорт данных в {output_file}...')

        # Экспортируем данные в формате Django loaddata
        all_objects = []
        for model in models:
            try:
                app_label, model_name = model.split('.')
                from django.apps import apps
                Model = apps.get_model(app_label, model_name)
                
                count = Model.objects.count()
                self.stdout.write(f'  Экспорт {model}: {count} записей...')
                
                # Используем Django serializers в формате для loaddata
                serialized = serializers.serialize('json', Model.objects.all(), indent=indent)
                serialized_data = json.loads(serialized)
                all_objects.extend(serialized_data)
            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(f'  Ошибка при экспорте {model}: {e}')
                )

        # Сохраняем в файл в формате Django loaddata
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(all_objects, f, indent=indent, ensure_ascii=False)

        file_size = os.path.getsize(output_file)
        self.stdout.write(
            self.style.SUCCESS(
                f'\n✓ Экспорт завершен!'
                f'\n  Файл: {output_file}'
                f'\n  Размер: {file_size / 1024 / 1024:.2f} MB'
            )
        )

