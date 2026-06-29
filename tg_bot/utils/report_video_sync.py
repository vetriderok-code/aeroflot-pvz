"""Фоновая догрузка видео TG-отчётов на диск."""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from decouple import config

from flights.models import TelegramFlightReport
from flights.utils.telegram_report_video import (
    clear_stale_local_video_path,
    report_has_video,
    report_video_too_large_for_bot,
    resolve_local_video_path,
)
from utils.report_video_download import download_report_video_bot

logger = logging.getLogger(__name__)


def _collect_pending_ids(limit: int) -> list:
    pending = []
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
            continue
        pending.append(report.id)
        if limit and len(pending) >= limit:
            break
    return pending


async def sync_pending_report_videos(
    bot: Bot,
    *,
    batch_size: int = 50,
    delay: float = 0.35,
) -> tuple[int, int]:
    pending_ids = await asyncio.to_thread(_collect_pending_ids, batch_size)
    if not pending_ids:
        return 0, 0

    ok = failed = 0
    for index, report_id in enumerate(pending_ids, start=1):
        try:
            if await download_report_video_bot(bot, report_id):
                ok += 1
            else:
                failed += 1
        except Exception:
            failed += 1
            logger.exception('video sync failed report=%s', report_id)
        if delay and index < len(pending_ids):
            await asyncio.sleep(delay)

    logger.info('TG video sync batch: ok=%s failed=%s total=%s', ok, failed, len(pending_ids))
    return ok, failed


def video_sync_enabled() -> bool:
    return config('TELEGRAM_VIDEO_SYNC_ENABLED', default='true').lower() in ('1', 'true', 'yes')


def video_sync_interval_sec() -> int:
    try:
        return max(60, int(config('TELEGRAM_VIDEO_SYNC_INTERVAL_SEC', default='300')))
    except ValueError:
        return 300


def video_sync_batch_size() -> int:
    try:
        return max(1, int(config('TELEGRAM_VIDEO_SYNC_BATCH_SIZE', default='50')))
    except ValueError:
        return 50
