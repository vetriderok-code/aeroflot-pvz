from django.core.management.base import BaseCommand
from django.db import transaction
from flights.models import Flight  # Замените your_app


class Command(BaseCommand):
    help = 'Пересчет координат для всех полетов с исправленным порядком'

    def add_arguments(self, parser):
        parser.add_argument('--batch_size', type=int, default=50,
                            help='Размер пакета для обработки')
        parser.add_argument('--reset_cache', action='store_true',
                            help='Сбросить существующий кэш перед пересчетом')

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        reset_cache = options['reset_cache']

        self.stdout.write('Начало пересчета координат с исправленным порядком...')

        # Получаем все полеты
        flights = Flight.objects.all()
        total = flights.count()

        self.stdout.write(f'Найдено полетов: {total}')

        if reset_cache:
            self.stdout.write('Сбрасываем существующий кэш...')
            Flight.objects.all().update(
                lat_sk42=None,
                lon_sk42=None,
                lat_wgs84=None,
                lon_wgs84=None
            )

        processed = 0
        errors = 0
        success = 0

        # Обрабатываем по пакетам
        for i in range(0, total, batch_size):
            batch = flights[i:i + batch_size]

            for flight in batch:
                try:
                    # Получаем обновленный объект если сбросили кэш
                    if reset_cache:
                        flight = Flight.objects.get(id=flight.id)

                    # Вызываем кэширование
                    coord_info = flight.get_coordinates_info_cached()

                    # Проверяем, не является ли это значением по умолчанию
                    if not (coord_info['lat_wgs84'] == 90.0 and coord_info['lon_wgs84'] == 0.0):
                        success += 1

                    processed += 1

                    if processed % 25 == 0:
                        self.stdout.write(f'Обработано: {processed}/{total} (Успешно: {success})')

                except Exception as e:
                    errors += 1
                    self.stdout.write(
                        self.style.WARNING(f'Ошибка полета {flight.id}: {e}')
                    )
                    continue

        self.stdout.write(
            self.style.SUCCESS(f'Завершено! Обработано: {processed}, Успешно: {success}, Ошибок: {errors}')
        )