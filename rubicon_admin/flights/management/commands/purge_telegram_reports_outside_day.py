"""Удаление отчётов вне текущих операционных суток (06:00–06:00 МСК)."""
from django.core.management.base import BaseCommand

from flights.models import TelegramFlightReport
from flights.utils.telegram_report_stats import _calendar_day_msk_period_bounds


class Command(BaseCommand):
    help = 'Удалить telegram_flight_report вне текущих календарных суток по МСК'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Только показать, сколько записей будет удалено',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Удалить все отчёты (чистый старт, только новые через polling)',
        )

    def handle(self, *args, **options):
        if options['all']:
            qs = TelegramFlightReport.objects.all()
            count = qs.count()
            if options['dry_run']:
                self.stdout.write(f'Будет удалено всех отчётов: {count}')
                return
            deleted, _ = qs.delete()
            self.stdout.write(self.style.SUCCESS(f'Удалено всех отчётов: {deleted}'))
            return

        period_start, period_end = _calendar_day_msk_period_bounds()
        outside = TelegramFlightReport.objects.exclude(
            sent_at__gte=period_start,
            sent_at__lte=period_end,
        )
        count = outside.count()
        kept = TelegramFlightReport.objects.filter(
            sent_at__gte=period_start,
            sent_at__lte=period_end,
        ).count()

        if options['dry_run']:
            self.stdout.write(
                f'Будет удалено: {count}, останется за сегодня (МСК): {kept}'
            )
            return

        deleted, _ = outside.delete()
        self.stdout.write(
            self.style.SUCCESS(
                f'Удалено {deleted} записей вне суток '
                f'{period_start.strftime("%d.%m.%Y")} МСК. '
                f'Осталось за сегодня: {kept}'
            )
        )
