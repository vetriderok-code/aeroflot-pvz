"""Повторно скачать видео TG-отчётов через aiogram (из контейнера tg_bot)."""
import asyncio
import os
import sys
import time
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from flights.models import TelegramFlightReport
from flights.utils.telegram_report_video import (
    clear_stale_local_video_path,
    report_has_video,
    report_video_too_large_for_bot,
    resolve_local_video_path,
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
    help = 'Скачать локально все видео TG-отчётов, для которых есть telegram_file_id.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=0,
            help='Максимум загрузок за запуск (0 = все недостающие).',
        )
        parser.add_argument(
            '--delay',
            type=float,
            default=0.35,
            help='Пауза между загрузками, сек (лимиты Telegram API).',
        )

        parser.add_argument(
            '--report-id',
            type=str,
            default='',
            help='Скачать одно видео по UUID отчёта.',
        )

    def handle(self, *args, **options):
        tg_bot_dir = _resolve_tg_bot_dir()
        os.chdir(tg_bot_dir)
        tg_path = str(tg_bot_dir)
        if tg_path not in sys.path:
            sys.path.insert(0, tg_path)

        from utils.report_video_download import close_download_bot, download_report_video_bot

        limit = options['limit']
        delay = max(0.0, options['delay'])
        report_id = (options.get('report_id') or '').strip()

        pending_ids = []
        skipped_large = 0
        if report_id:
            report = TelegramFlightReport.objects.filter(pk=report_id).first()
            if not report or not report.telegram_file_id:
                self.stdout.write(self.style.ERROR(f'Отчёт не найден или без видео: {report_id}'))
                return
            clear_stale_local_video_path(report)
            if resolve_local_video_path(report):
                self.stdout.write(self.style.SUCCESS('Видео уже на диске.'))
                return
            pending_ids = [report.id]
        else:
            for report in (
                TelegramFlightReport.objects
                .exclude(telegram_file_id='')
                .order_by('video_size', 'sent_at')
                .iterator()
            ):
                clear_stale_local_video_path(report)
                if resolve_local_video_path(report):
                    continue
                if not report_has_video(report):
                    continue
                if report_video_too_large_for_bot(report):
                    skipped_large += 1
                    continue
                pending_ids.append(report.id)
                if limit and len(pending_ids) >= limit:
                    break

        total = len(pending_ids)
        if skipped_large:
            self.stdout.write(
                f'Пропущено {skipped_large} видео >20 МБ (лимит Bot API, только стрим из TG).'
            )
        if not total:
            self.stdout.write(self.style.SUCCESS('Все доступные видео уже на диске.'))
            return

        self.stdout.write(f'К загрузке: {total} видео (delay={delay}s)')

        async def _run() -> tuple[int, int]:
            ok = failed = 0
            for index, report_id in enumerate(pending_ids, start=1):
                try:
                    if await download_report_video_bot(None, report_id):
                        ok += 1
                    else:
                        failed += 1
                except Exception as exc:
                    failed += 1
                    self.stderr.write(f'{report_id}: {exc}\n')
                if index % 25 == 0 or index == total:
                    self.stdout.write(f'  прогресс {index}/{total}: ok={ok}, errors={failed}')
                if delay and index < total:
                    await asyncio.sleep(delay)
            return ok, failed

        async def _main() -> tuple[int, int]:
            try:
                return await _run()
            finally:
                await close_download_bot()

        ok, failed = asyncio.run(_main())
        self.stdout.write(self.style.SUCCESS(
            f'Готово: скачано {ok}, ошибок {failed}, всего {total}'
        ))
