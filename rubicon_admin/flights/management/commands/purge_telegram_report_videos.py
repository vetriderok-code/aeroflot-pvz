from django.core.management.base import BaseCommand

from flights.utils.telegram_report_video import purge_expired_report_videos, video_retention_days


class Command(BaseCommand):
    help = 'Удалить локальные видео TG-отчётов старше N дней (file_id в БД сохраняется).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--older-than-days',
            type=int,
            default=None,
            help=f'Порог в днях (по умолчанию {video_retention_days()}).',
        )

    def handle(self, *args, **options):
        result = purge_expired_report_videos(
            older_than_days=options.get('older_than_days'),
        )
        self.stdout.write(self.style.SUCCESS(
            'Очистка видео: удалено файлов {deleted_files}, обновлено записей {updated_rows} '
            '(старше {older_than_days} дн.)'.format(**result)
        ))
