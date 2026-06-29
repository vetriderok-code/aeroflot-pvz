"""Догрузка отчётов за сегодня через forward в личку админа (группа не затрагивается)."""
import asyncio
import os
import sys
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand


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
    help = (
        'Догрузить отчёты топика 2406 за текущие сутки (МСК). '
        'Forward в служебный TELEGRAM_BACKFILL_CHAT_ID — рабочая группа не затрагивается.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=2000, help='Сколько message_id сканировать')
        parser.add_argument('--from-id', type=int, default=None, help='Нижняя граница message_id')
        parser.add_argument('--to-id', type=int, default=None, help='Верхняя граница message_id')
        parser.add_argument(
            '--no-react',
            action='store_true',
            help='Не ставить реакцию 👌',
        )

    def handle(self, *args, **options):
        tg_bot_dir = _resolve_tg_bot_dir()
        os.chdir(tg_bot_dir)
        tg_path = str(tg_bot_dir)
        if tg_path not in sys.path:
            sys.path.insert(0, tg_path)

        from create_bot import bot
        from utils.topic_backfill import sync_reports_topic

        async def run():
            return await sync_reports_topic(
                bot,
                limit=options['limit'],
                react_ok=not options['no_react'],
                from_message_id=options['from_id'],
                to_message_id=options['to_id'],
            )

        result = asyncio.run(run())
        if not result.get('ok'):
            self.stderr.write(self.style.ERROR(result.get('error', 'ошибка')))
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"id {result['from_message_id']}–{result['to_message_id']}: "
                f"сохранено {result['saved']}, реакций {result['reacted']}, "
                f"уже в БД {result['skipped']}, не сегодня {result['not_today']}, "
                f"не прочитано {result['unreadable']}, scanned {result['scanned']}"
            )
        )
