"""Догрузка видео-отчётов из Отчетного квартала ТД."""
import asyncio
import os
import sys
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from flights.utils.telegram_report_sources import (
    get_map_report_sources,
    get_video_reports_chat_id,
    get_video_reports_topic_ids,
)


def _resolve_tg_bot_dir() -> Path:
    candidates = (
        Path(settings.BASE_DIR).parent / 'tg_bot',
        Path(settings.BASE_DIR) / 'tg_bot',
    )
    for path in candidates:
        if path.is_dir():
            return path.resolve()
    raise FileNotFoundError('Каталог tg_bot не найден')


class Command(BaseCommand):
    help = 'Догрузить видео-отчёты из Отчетного квартала ТД (один проход по чату).'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=4500, help='Сколько message_id сканировать')
        parser.add_argument('--from-id', type=int, default=None)
        parser.add_argument('--to-id', type=int, default=None, help='Верхняя граница message_id (по умолч. из .env)')
        parser.add_argument(
            '--today-only',
            action='store_true',
            help='Только текущие операционные сутки (06:00–06:00 МСК)',
        )
        parser.add_argument(
            '--react',
            action='store_true',
            help='Ставить реакцию 👌 на обработанные',
        )

    def handle(self, *args, **options):
        tg_bot_dir = _resolve_tg_bot_dir()
        os.chdir(tg_bot_dir)
        tg_path = str(tg_bot_dir)
        if tg_path not in sys.path:
            sys.path.insert(0, tg_path)

        from create_bot import bot
        from utils.topic_backfill import sync_reports_chat_topics

        sources = get_map_report_sources()
        if not sources:
            self.stderr.write(self.style.ERROR('Не заданы TELEGRAM_VIDEO_REPORTS_* в .env'))
            return

        chat_id, topic_ids = sources[0]
        all_days = not options['today_only']

        self.stdout.write(
            f'Синхронизация chat={chat_id} topics={topic_ids} '
            f'limit={options["limit"]} all_days={all_days} to_id={options["to_id"]}'
        )

        result = asyncio.run(
            sync_reports_chat_topics(
                bot,
                chat_id=chat_id,
                topic_ids=topic_ids,
                limit=options['limit'],
                react_ok=options['react'],
                all_days=all_days,
                assign_thread_id=None,
                from_message_id=options['from_id'],
                to_message_id=options['to_id'],
            )
        )

        if not result.get('ok'):
            self.stderr.write(self.style.ERROR(str(result.get('error'))))
            return

        self.stdout.write(self.style.SUCCESS(
            f"id {result['from_message_id']}–{result['to_message_id']}: "
            f"сохранено {result['saved']}, пропущено {result['skipped']}, "
            f"не сегодня {result['not_today']}, не прочитано {result['unreadable']}, "
            f"scanned {result['scanned']}, ошибок {result['errors']}"
        ))

        if get_video_reports_chat_id():
            self.stdout.write(
                f'Источник: Отчетный квартал ТД, topics={get_video_reports_topic_ids()}'
            )
