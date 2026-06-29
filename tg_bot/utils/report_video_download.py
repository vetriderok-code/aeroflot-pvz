"""Скачивание видео TG-отчётов через aiogram (rubicon-api до Telegram не достучится)."""
from __future__ import annotations

import asyncio
import logging
import mimetypes
from pathlib import Path

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from decouple import config
from django.utils import timezone

from flights.models import TelegramFlightReport
from flights.utils.telegram_report_video import (
    clear_stale_local_video_path,
    resolve_local_video_path,
    video_storage_root,
)

logger = logging.getLogger(__name__)

_active_downloads: set = set()
_active_lock = asyncio.Lock()
_download_bot: Bot | None = None


def _guess_extension(mime_type: str | None) -> str:
    mime = (mime_type or 'video/mp4').split(';', 1)[0].strip()
    ext = mimetypes.guess_extension(mime) or '.mp4'
    if ext == '.jpe':
        ext = '.mp4'
    return ext


def get_download_bot() -> Bot:
    """Бот для get_file/download_file: Local Bot API если настроен, иначе основной."""
    global _download_bot
    if _download_bot is not None:
        return _download_bot

    token = config('TOKEN')
    local_api_url = config('TELEGRAM_BOT_API_URL', default='').strip().rstrip('/')
    if local_api_url:
        from aiogram.client.session.aiohttp import AiohttpSession
        from aiogram.client.telegram import TelegramAPIServer

        session = AiohttpSession(
            api=TelegramAPIServer.from_base(local_api_url),
            timeout=900,
        )
        _download_bot = Bot(
            token=token,
            session=session,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        logger.info('TG video download via Local Bot API: %s', local_api_url)
        return _download_bot

    from create_bot import bot

    _download_bot = bot
    return bot


async def close_download_bot() -> None:
    global _download_bot
    if _download_bot is None:
        return
    from create_bot import bot as main_bot

    if _download_bot is not main_bot and _download_bot.session:
        await _download_bot.session.close()
    _download_bot = None


async def download_report_video_bot(bot: Bot | None, report_id) -> bool:
    async with _active_lock:
        if report_id in _active_downloads:
            return False
        _active_downloads.add(report_id)
    try:
        return await _download_report_video_bot(get_download_bot(), report_id)
    finally:
        async with _active_lock:
            _active_downloads.discard(report_id)


async def _download_file_to_path(bot: Bot, tg_file_path: str, dest: Path) -> None:
    local_api_url = config('TELEGRAM_BOT_API_URL', default='').strip().rstrip('/')
    if local_api_url:
        import aiohttp

        token = config('TOKEN')
        url = f'{local_api_url}/file/bot{token}/{tg_file_path}'
        timeout = aiohttp.ClientTimeout(total=1800, sock_connect=60, sock_read=300)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                response.raise_for_status()
                with dest.open('wb') as out:
                    async for chunk in response.content.iter_chunked(256 * 1024):
                        out.write(chunk)
        return

    await bot.download_file(tg_file_path, destination=dest)


async def _download_report_video_bot(bot: Bot, report_id) -> bool:
    report = await asyncio.to_thread(
        TelegramFlightReport.objects.get,
        pk=report_id,
    )
    if not report.telegram_file_id:
        return False
    clear_stale_local_video_path(report)
    if resolve_local_video_path(report):
        return True

    last_error = None
    for attempt in range(1, 4):
        try:
            tg_file = await bot.get_file(report.telegram_file_id)
            if not tg_file.file_path:
                return False

            root = video_storage_root()
            root.mkdir(parents=True, exist_ok=True)
            rel_name = f'{report.id}{_guess_extension(report.video_mime)}'
            dest = root / rel_name
            temp = dest.with_suffix(dest.suffix + '.part')

            if temp.exists():
                temp.unlink(missing_ok=True)

            logger.info(
                'TG video download start: report=%s size=%s attempt=%s',
                report_id,
                report.video_size,
                attempt,
            )
            await _download_file_to_path(bot, tg_file.file_path, temp)
            dest.parent.mkdir(parents=True, exist_ok=True)
            temp.replace(dest)

            def _save_meta() -> None:
                report.local_video_path = rel_name
                report.video_downloaded_at = timezone.now()
                report.save(update_fields=['local_video_path', 'video_downloaded_at', 'modified'])

            await asyncio.to_thread(_save_meta)
            logger.info('TG video saved via bot: report=%s path=%s', report_id, rel_name)
            return True
        except Exception as exc:
            last_error = exc
            logger.warning(
                'TG video download failed: report=%s attempt=%s error=%s',
                report_id,
                attempt,
                exc,
            )
            if attempt < 3:
                await asyncio.sleep(min(30, attempt * 10))
    if last_error:
        raise last_error
    return False


def schedule_report_video_download_bot(report_id, bot: Bot) -> None:
    async def _job() -> None:
        try:
            await download_report_video_bot(bot, report_id)
        except Exception:
            logger.exception('bot video download failed report=%s', report_id)

    asyncio.create_task(_job())
