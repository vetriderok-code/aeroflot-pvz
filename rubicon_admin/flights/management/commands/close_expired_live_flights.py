from django.core.management.base import BaseCommand

from flights.utils.live_flight import close_expired_live_flights


class Command(BaseCommand):
    help = 'Закрывает оперативные вылеты без «Стоп» по таймауту 40 минут'

    def handle(self, *args, **options):
        count = close_expired_live_flights()
        self.stdout.write(self.style.SUCCESS(f'Закрыто вылетов: {count}'))
