import asyncio
import logging

from decouple import config

from create_bot import bot, dp
from handlers.group_monitor import group_router
from handlers.start import start_router
from handlers.td_reports_monitor import td_reports_router

logger = logging.getLogger(__name__)


async def _run_backfill():
    if config('TELEGRAM_BACKFILL_ON_START', default='false').lower() not in (
        '1',
        'true',
        'yes',
    ):
        return
    try:
        limit = int(config('TELEGRAM_BACKFILL_LIMIT', default='800'))
    except ValueError:
        limit = 800

    from utils.topic_backfill import sync_reports_topic

    logger.info('Догрузка отчётов за сегодня (лимит id=%s, служебный чат)…', limit)
    try:
        result = await sync_reports_topic(bot, limit=limit, react_ok=True)
    except Exception:
        logger.exception('Догрузка отчётов прервана')
        return
    if result.get('ok'):
        logger.info(
            'Догрузка: сохранено %s, реакций %s, уже в БД %s, не сегодня %s, '
            'не прочитано %s, scanned %s',
            result.get('saved'),
            result.get('reacted'),
            result.get('skipped'),
            result.get('not_today'),
            result.get('unreadable'),
            result.get('scanned'),
        )
    else:
        logger.warning('Догрузка отчётов: %s', result.get('error'))


async def _startup_backfill():
    asyncio.create_task(_run_backfill())
    asyncio.create_task(_run_video_sync_loop())
    asyncio.create_task(_run_max_bridge())


async def _run_max_bridge():
    from bridge.poll import run_max_bridge_loop

    await run_max_bridge_loop(bot)


async def _run_video_sync_loop():
    from utils.report_video_sync import (
        sync_pending_report_videos,
        video_sync_batch_size,
        video_sync_enabled,
        video_sync_interval_sec,
    )

    if not video_sync_enabled():
        logger.info('Фоновая догрузка видео отключена (TELEGRAM_VIDEO_SYNC_ENABLED=false)')
        return

    await asyncio.sleep(45)
    interval = video_sync_interval_sec()
    batch_size = video_sync_batch_size()
    logger.info(
        'Фоновая догрузка видео: batch=%s, interval=%ss',
        batch_size,
        interval,
    )
    while True:
        try:
            await sync_pending_report_videos(bot, batch_size=batch_size)
        except Exception:
            logger.exception('Фоновая догрузка видео прервана')
        await asyncio.sleep(interval)


async def main():
    dp.include_router(group_router)
    dp.include_router(td_reports_router)
    dp.include_router(start_router)

    dp.startup.register(_startup_backfill)

    # Не переигрывать старые Старт/Стоп после рестарта — иначе ломается порядок событий.
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
