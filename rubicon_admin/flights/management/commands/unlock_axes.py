"""
Django management команда для разблокировки IP адресов и пользователей в django-axes
"""
from django.core.management.base import BaseCommand
from axes.models import AccessAttempt
from axes.utils import reset


class Command(BaseCommand):
    help = 'Разблокирует все заблокированные IP адреса и пользователей'

    def add_arguments(self, parser):
        parser.add_argument(
            '--ip',
            type=str,
            help='Разблокировать конкретный IP адрес',
        )
        parser.add_argument(
            '--username',
            type=str,
            help='Разблокировать конкретного пользователя',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Разблокировать все IP адреса и пользователей',
        )

    def handle(self, *args, **options):
        from django.conf import settings
        failure_limit = getattr(settings, 'AXES_FAILURE_LIMIT', 3)
        
        if options['all']:
            # Разблокируем все записи с failures >= limit
            attempts = AccessAttempt.objects.filter(failures_since_start__gte=failure_limit)
            count = attempts.count()
            for attempt in attempts:
                reset(ip_address=attempt.ip_address, username=attempt.username)
            self.stdout.write(
                self.style.SUCCESS(f'Разблокировано {count} записей')
            )
        elif options['ip']:
            # Разблокируем конкретный IP
            reset(ip=options['ip'])
            self.stdout.write(
                self.style.SUCCESS(f'Разблокирован IP: {options["ip"]}')
            )
        elif options['username']:
            # Разблокируем конкретного пользователя
            reset(username=options['username'])
            self.stdout.write(
                self.style.SUCCESS(f'Разблокирован пользователь: {options["username"]}')
            )
        else:
            # Показываем заблокированные записи
            attempts = AccessAttempt.objects.filter(failures_since_start__gte=failure_limit)
            if attempts.exists():
                self.stdout.write(f'Заблокированные записи (лимит: {failure_limit}):')
                for attempt in attempts:
                    self.stdout.write(
                        f'  IP: {attempt.ip_address}, Username: {attempt.username}, '
                        f'Попыток: {attempt.failures_since_start}'
                    )
                self.stdout.write(
                    self.style.WARNING('\nИспользуйте --all для разблокировки всех, '
                                    'или --ip/--username для конкретной записи')
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS('Нет заблокированных записей')
                )

