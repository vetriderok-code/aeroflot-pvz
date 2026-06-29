from django.core.management.base import BaseCommand
from django.db import transaction
from flights.models import Flight  # Замените your_app


class Command(BaseCommand):
    help = 'Предварительное преобразование и кэширование координат'

    def handle(self, *args, **options):
        self.stdout.write('Начало предварительного преобразования координат...')

        # Получаем все полеты без кэшированных координат
        flights = Flight.objects.filter(lat_wgs84__isnull=True)
        total = flights.count()

        self.stdout.write(f'Найдено полетов для обработки: {total}')

        processed = 0
        errors = 0

        # Обрабатываем по 100 записей за раз
        batch_size = 100
        for i in range(0, total, batch_size):
            batch = flights[i:i + batch_size]

            with transaction.atomic():
                for flight in batch:
                    try:
                        # Вызываем save() для триггера преобразования
                        flight.save(update_fields=[])
                        processed += 1

                        if processed % 50 == 0:
                            self.stdout.write(f'Обработано: {processed}/{total}')

                    except Exception as e:
                        errors += 1
                        self.stdout.write(
                            self.style.WARNING(f'Ошибка полета {flight.id}: {e}')
                        )
                        continue

        self.stdout.write(
            self.style.SUCCESS(f'Завершено! Успешно: {processed}, Ошибок: {errors}')
        )