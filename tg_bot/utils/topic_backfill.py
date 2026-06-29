"""Догрузка отчётов: forward в служебный чат бота (не в рабочую группу)."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from decouple import config
from django.core.cache import cache
from django.db.models import Max

from flights.models import TelegramFlightReport
from flights.utils.telegram_report_ingest import (
    extract_message_text,
    normalize_sent_at,
    process_report_message,
)
from flights.utils.telegram_report_stats import _calendar_day_msk_period_bounds
from utils.telegram_reactions import mark_message_processed_ok

logger = logging.getLogger(__name__)

LIVE_CHAT_ID = int(config('TELEGRAM_LIVE_FLIGHT_CHAT_ID', default=-1003960872491))
REPORTS_TOPIC_ID = int(config('TELEGRAM_REPORTS_TOPIC_ID', default=2406))
CACHE_MAX_MSG_ID = 'rubicon_tg_max_message_id'


def _storage_chat_id() -> int | None:
    """
    Приватный канал/группа, куда бот временно пересылает сообщения для чтения.
    Бот не может «написать сам себе» в личку — нужен отдельный служебный чат.
    """
    for key in ('TELEGRAM_BACKFILL_CHAT_ID', 'TELEGRAM_SYNC_CHANNEL_ID'):
        raw = (config(key, default='') or '').strip()
        if not raw:
            continue
        try:
            return int(raw)
        except ValueError:
            logger.warning('%s=%s не число', key, raw)
    return None


def is_sent_at_today_msk(sent_at) -> bool:
    if not sent_at:
        return False
    when = normalize_sent_at(sent_at)
    if when is None:
        return False
    when_msk = when.astimezone(ZoneInfo('Europe/Moscow'))
    period_start, _ = _calendar_day_msk_period_bounds()
    period_end_exclusive = period_start + timedelta(days=1)
    return period_start <= when_msk < period_end_exclusive


def track_message_id(message_id: int) -> None:
    if not message_id:
        return
    current = cache.get(CACHE_MAX_MSG_ID) or 0
    if message_id > current:
        cache.set(CACHE_MAX_MSG_ID, message_id, timeout=None)


def resolve_sync_bounds(
    *,
    chat_id: int,
    topic_id: int,
    limit: int,
    from_message_id: int | None,
    to_message_id: int | None,
) -> tuple[int, int]:
    qs = TelegramFlightReport.objects.filter(chat_id=chat_id)
    if topic_id:
        qs = qs.filter(message_thread_id=topic_id)
    agg = qs.aggregate(max_id=Max('telegram_message_id'))
    max_db = int(agg['max_id'] or 0)
    max_cached = int(cache.get(CACHE_MAX_MSG_ID) or 0)
    upper = int(to_message_id) if to_message_id else max(max_db, max_cached, 1)
    if upper <= 1:
        try:
            upper = int(config('TELEGRAM_VIDEO_REPORT_SCAN_TO_ID', default='4400'))
        except ValueError:
            upper = 8500

    if from_message_id is not None:
        lower = int(from_message_id)
    else:
        lower = max(1, upper - limit + 1)

    if upper - lower + 1 > limit:
        lower = upper - limit + 1

    return lower, upper


async def _fetch_via_storage_forward(
    bot: Bot,
    *,
    source_chat_id: int,
    message_id: int,
    storage_chat_id: int,
) -> dict | None:
    """Forward в служебный чат бота → читаем caption → сразу удаляем."""
    for attempt in range(5):
        try:
            fwd = await bot.forward_message(
                chat_id=storage_chat_id,
                from_chat_id=source_chat_id,
                message_id=message_id,
                request_timeout=90,
            )
            break
        except TelegramRetryAfter as exc:
            wait = int(exc.retry_after) + 1
            logger.info('Flood wait %ss (msg=%s), попытка %s', wait, message_id, attempt + 1)
            await asyncio.sleep(wait)
        except (TelegramBadRequest, TelegramForbiddenError):
            return None
        except Exception as exc:
            logger.debug('forward msg=%s: %s', message_id, exc)
            if attempt >= 4:
                return None
            await asyncio.sleep(2)
    else:
        return None

    origin_user_id = 0
    if fwd.forward_from:
        origin_user_id = fwd.forward_from.id
    elif fwd.from_user and not fwd.from_user.is_bot:
        origin_user_id = fwd.from_user.id

    video_payload = None
    if fwd.video:
        video_payload = {
            'file_id': fwd.video.file_id,
            'mime_type': fwd.video.mime_type or 'video/mp4',
            'file_size': fwd.video.file_size,
            'duration': fwd.video.duration,
        }
    elif fwd.document and (fwd.document.mime_type or '').startswith('video/'):
        video_payload = {
            'file_id': fwd.document.file_id,
            'mime_type': fwd.document.mime_type or 'video/mp4',
            'file_size': fwd.document.file_size,
            'duration': None,
        }

    payload = {
        'text': fwd.text,
        'caption': fwd.caption,
        'date': fwd.forward_date or fwd.date,
        'from_user_id': origin_user_id,
        'video_payload': video_payload,
        'message_thread_id': getattr(fwd, 'message_thread_id', None),
    }
    try:
        await bot.delete_message(chat_id=storage_chat_id, message_id=fwd.message_id)
    except TelegramBadRequest:
        pass
    return payload


def _load_processed_ids_for_chat(*, chat_id: int) -> set[int]:
    return set(
        TelegramFlightReport.objects.filter(
            chat_id=chat_id,
        ).values_list('telegram_message_id', flat=True)
    )


def _load_processed_ids(*, chat_id: int, topic_id: int) -> set[int]:
    return set(
        TelegramFlightReport.objects.filter(
            chat_id=chat_id,
            message_thread_id=topic_id,
        ).values_list('telegram_message_id', flat=True)
    )


async def sync_reports_chat_topics(
    bot: Bot,
    *,
    chat_id: int,
    topic_ids: list[int],
    limit: int = 2000,
    react_ok: bool = False,
    all_days: bool = True,
    assign_thread_id: int | None = None,
    from_message_id: int | None = None,
    to_message_id: int | None = None,
) -> dict:
    """Один проход по message_id чата; обрабатывает только указанные топики."""
    storage_id = _storage_chat_id()
    if not storage_id:
        return {
            'ok': False,
            'error': 'Задайте TELEGRAM_BACKFILL_CHAT_ID (служебный чат для forward).',
        }

    allowed = set(int(t) for t in topic_ids)
    anchor_topic = assign_thread_id or (next(iter(allowed)) if allowed else 0)
    lower, upper = await asyncio.to_thread(
        resolve_sync_bounds,
        chat_id=chat_id,
        topic_id=anchor_topic,
        limit=limit,
        from_message_id=from_message_id,
        to_message_id=to_message_id,
    )

    scanned = saved = reacted = skipped = unreadable = not_today = parse_failed = errors = 0
    if assign_thread_id is not None:
        processed_ids = await asyncio.to_thread(
            _load_processed_ids,
            chat_id=chat_id,
            topic_id=assign_thread_id,
        )
    else:
        processed_ids = await asyncio.to_thread(_load_processed_ids_for_chat, chat_id=chat_id)

    logger.info(
        'Backfill chat=%s topics=%s (служ. чат %s): message_id %s–%s all_days=%s',
        chat_id,
        sorted(allowed),
        storage_id,
        lower,
        upper,
        all_days,
    )

    for message_id in range(lower, upper + 1):
        scanned += 1
        if message_id in processed_ids:
            skipped += 1
            continue

        payload = await _fetch_via_storage_forward(
            bot,
            source_chat_id=chat_id,
            message_id=message_id,
            storage_chat_id=storage_id,
        )
        if not payload:
            unreadable += 1
            continue

        sent_at = normalize_sent_at(payload.get('date'))
        if not all_days and not is_sent_at_today_msk(sent_at):
            not_today += 1
            continue

        # Forward в служебный чат не сохраняет topic id исходного форума.
        effective_thread_id = assign_thread_id
        if effective_thread_id is None and len(allowed) == 1:
            effective_thread_id = next(iter(allowed))

        body = extract_message_text(
            text=payload.get('text'),
            caption=payload.get('caption'),
        )
        if not body:
            unreadable += 1
            continue

        from_user_id = payload.get('from_user_id') or 0
        try:
            outcome = await asyncio.to_thread(
                process_report_message,
                text=body,
                chat_id=chat_id,
                message_thread_id=effective_thread_id,
                telegram_message_id=message_id,
                telegram_user_id=from_user_id,
                sent_at=sent_at,
                reports_topic_ids=sorted(allowed) if allowed else [],
                video_payload=payload.get('video_payload'),
                backfill=assign_thread_id is None,
            )
        except Exception as exc:
            errors += 1
            logger.exception('sync msg=%s: %s', message_id, exc)
            continue

        if outcome.get('saved'):
            saved += 1
            processed_ids.add(message_id)
            record = outcome.get('record') or {}
            if record.get('has_video') and record.get('id'):
                from utils.report_video_download import schedule_report_video_download_bot
                schedule_report_video_download_bot(record['id'], bot)
            if react_ok:
                if await mark_message_processed_ok(
                    bot, chat_id=chat_id, message_id=message_id
                ):
                    reacted += 1
        elif outcome.get('reason') == 'parse_failed':
            parse_failed += 1

        if scanned % 10 == 0:
            await asyncio.sleep(0.3)

    return {
        'ok': True,
        'from_message_id': lower,
        'to_message_id': upper,
        'scanned': scanned,
        'saved': saved,
        'reacted': reacted,
        'skipped': skipped,
        'unreadable': unreadable,
        'not_today': not_today,
        'parse_failed': parse_failed,
        'errors': errors,
    }


async def sync_reports_topic_for_source(
    bot: Bot,
    *,
    chat_id: int,
    topic_id: int,
    limit: int = 1500,
    react_ok: bool = True,
    all_days: bool = False,
    from_message_id: int | None = None,
    to_message_id: int | None = None,
) -> dict:
    """Догрузка пропущенных отчётов из одного топика."""
    return await sync_reports_chat_topics(
        bot,
        chat_id=chat_id,
        topic_ids=[topic_id],
        limit=limit,
        react_ok=react_ok,
        all_days=all_days,
        assign_thread_id=topic_id,
        from_message_id=from_message_id,
        to_message_id=to_message_id,
    )


async def sync_reports_topic(
    bot: Bot,
    *,
    hours: int = 48,
    limit: int = 1500,
    react_ok: bool = True,
    from_message_id: int | None = None,
    to_message_id: int | None = None,
) -> dict:
    """Догрузка пропущенных отчётов топика 2406 (оперативная группа)."""
    del hours
    return await sync_reports_topic_for_source(
        bot,
        chat_id=LIVE_CHAT_ID,
        topic_id=REPORTS_TOPIC_ID,
        limit=limit,
        react_ok=react_ok,
        from_message_id=from_message_id,
        to_message_id=to_message_id,
    )
