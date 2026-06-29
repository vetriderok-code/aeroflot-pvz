from django.core.management.base import BaseCommand

from flights.models import TelegramFlightReport
from flights.utils.telegram_report_stats import (
    parse_report_coordinates,
    parse_telegram_report_message,
)


class Command(BaseCommand):
    help = 'Заполнить координаты TG-отчётов из raw_text (для уже сохранённых записей).'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=5000)
        parser.add_argument(
            '--reparse',
            action='store_true',
            help='Переразобрать номер вылета и позывной из raw_text',
        )

    def handle(self, *args, **options):
        qs = TelegramFlightReport.objects.exclude(
            raw_text='',
        ).order_by('-sent_at')[: options['limit']]

        updated = 0
        for report in qs.iterator():
            coords = parse_report_coordinates(report.raw_text)
            fields = []
            if coords:
                report.coordinates_sk42 = coords['coordinates_sk42']
                report.lat_wgs84 = coords['lat_wgs84']
                report.lon_wgs84 = coords['lon_wgs84']
                fields.extend(['coordinates_sk42', 'lat_wgs84', 'lon_wgs84'])

            if options['reparse']:
                parsed = parse_telegram_report_message(report.raw_text)
                if parsed.get('parse_ok'):
                    if parsed.get('flight_number'):
                        report.flight_number = parsed['flight_number']
                        fields.append('flight_number')
                    if parsed.get('pilot_callsign'):
                        report.pilot_callsign = parsed['pilot_callsign']
                        fields.append('pilot_callsign')
                    if parsed.get('result'):
                        report.result = parsed['result'][:512]
                        fields.append('result')

            if not fields:
                continue
            fields.append('modified')
            report.save(update_fields=fields)
            updated += 1

        self.stdout.write(self.style.SUCCESS(f'Обновлено записей: {updated}'))
