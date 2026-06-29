"""Очищает result_raw, ошибочно заполненный из комментариев (не из колонки «Результат»)."""

from django.core.management.base import BaseCommand



from flights.models import Flight





class Command(BaseCommand):

    help = (

        'Очищает result_raw, заполненный ранее из комментариев. '

        'Для KPI нужен повторный импорт сводной Excel (колонка «Результат применения»).'

    )



    def add_arguments(self, parser):

        parser.add_argument(

            '--dry-run',

            action='store_true',

            help='Только показать, сколько записей будет очищено',

        )



    def handle(self, *args, **options):

        # Значения, которые ставила старая версия команды из текста комментария

        legacy_values = ('доставка', 'успешно', 'успех', 'поражено')

        qs = Flight.objects.filter(result_raw__in=legacy_values)

        count = qs.count()



        if options['dry_run']:

            self.stdout.write(f'Будет очищено записей: {count}')

            return



        cleared = qs.update(result_raw=None)

        self.stdout.write(

            self.style.SUCCESS(

                f'Очищено result_raw у {cleared} записей. '

                f'Перезагрузите сводную Excel, чтобы заполнить колонку «Результат».'

            )

        )

