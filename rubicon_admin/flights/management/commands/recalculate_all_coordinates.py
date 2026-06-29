from django.core.management.base import BaseCommand

from flights.models import Flight


class Command(BaseCommand):
    help = 'Пересчитать WGS84 для всех полётов с координатами (сброс кэша lat/lon)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            type=int,
            default=200,
            help='Размер пакета bulk_update',
        )

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        queryset = Flight.objects.filter(
            coordinates__isnull=False,
        ).exclude(
            coordinates='',
        )
        total = queryset.count()
        self.stdout.write(f'Полётов с координатами: {total}')

        fixed_strings = 0
        for flight in queryset.iterator(chunk_size=500):
            normalized = Flight.normalize_coordinates_field(flight.coordinates)
            if normalized and normalized != flight.coordinates:
                flight.coordinates = normalized
                flight.save(update_fields=['coordinates'])
                fixed_strings += 1
        if fixed_strings:
            self.stdout.write(f'Исправлено строк координат: {fixed_strings}')

        cleared = queryset.update(
            lat_sk42=None,
            lon_sk42=None,
            lat_wgs84=None,
            lon_wgs84=None,
        )
        self.stdout.write(f'Сброшен кэш координат: {cleared}')

        success, errors = Flight.batch_process_coordinates(
            queryset=queryset,
            batch_size=batch_size,
            update_callback=lambda done, total_count: self.stdout.write(
                f'  обработано {done}/{total_count}',
            ),
        )

        if errors:
            self.stdout.write(self.style.WARNING('Не удалось обработать:'))
            failed = queryset.filter(lat_wgs84__isnull=True) | queryset.filter(
                lat_wgs84=90.0,
                lon_wgs84=0.0,
            )
            for flight in failed.distinct()[:20]:
                self.stdout.write(f'  {flight.id}  {flight.coordinates}')

        self.stdout.write(
            self.style.SUCCESS(
                f'Готово: успешно {success}, ошибок {errors}',
            ),
        )
