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
    limit: int,
    from_message_id: int | None,
    to_message_id: int | None,
) -> tuple[int, int]:
    agg = TelegramFlightReport.objects.filter(
        chat_id=LIVE_CHAT_ID,
        message_thread_id=REPORTS_TOPIC_ID,
    ).aggregate(max_id=Max('telegram_message_id'))
    max_db = int(agg['max_id'] or 0)
    max_cached = int(cache.get(CACHE_MAX_MSG_ID) or 0)
    upper = int(to_message_id) if to_message_id else max(max_db, max_cached, 1)

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
                request_timeout=45,
            )
            break
        except TelegramRetryAfter as exc:
            wait = int(exc.retry_after) + 1
            logger.info('Flood wait %ss (msg=%s), попытка %s', wait, message_id, attempt + 1)
            await asyncio.sleep(wait)
        except (TelegramBadRequest, TelegramForbiddenError):
            return None
    else:
        return None

    origin_user_id = 0
    if fwd.forward_from:
        origin_user_id = fwd.forward_from.id
    elif fwd.from_user and not fwd.from_user.is_bot:
        origin_user_id = fwd.from_user.id

    payload = {
        'text': fwd.text,
        'caption': fwd.caption,
        'date': fwd.forward_date or fwd.date,
        'from_user_id': origin_user_id,
    }
    try:
        await bot.delete_message(chat_id=storage_chat_id, message_id=fwd.message_id)
    except TelegramBadRequest:
        pass
    return payload


def _load_processed_ids() -> set[int]:
    return set(
        TelegramFlightReport.objects.filter(
            chat_id=LIVE_CHAT_ID,
            message_thread_id=REPORTS_TOPIC_ID,
        ).values_list('telegram_message_id', flat=True)
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
    """
    Догрузка пропущенных отчётов топика 2406.
    Forward только в TELEGRAM_BACKFILL_CHAT_ID; рабочая группа не затрагивается.
    Сохраняются только отчёты с sent_at за текущие сутки (06:00–06:00 МСК).
    """
    del hours
    storage_id = _storage_chat_id()
    if not storage_id:
        return {
            'ok': False,
            'error': (
                'Задайте TELEGRAM_BACKFILL_CHAT_ID — приватный канал/группа, '
                'куда добавлен бот как админ (служебный чат, не рабочая группа). '
                'Один раз: создайте канал → добавьте бота админом → узнайте chat_id.'
            ),
        }

    lower, upper = await asyncio.to_thread(
        resolve_sync_bounds,
        limit=limit,
        from_message_id=from_message_id,
        to_message_id=to_message_id,
    )

    scanned = saved = reacted = skipped = unreadable = not_today = parse_failed = errors = 0
    processed_ids = await asyncio.to_thread(_load_processed_ids)

    logger.info(
        'Backfill (служ. чат %s, группа не трогается): message_id %s–%s',
        storage_id,
        lower,
        upper,
    )

    for message_id in range(lower, upper + 1):
        scanned += 1
        if message_id in processed_ids:
            skipped += 1
            continue

        payload = await _fetch_via_storage_forward(
            bot,
            source_chat_id=LIVE_CHAT_ID,
            message_id=message_id,
            storage_chat_id=storage_id,
        )
        if not payload:
            unreadable += 1
            continue

        sent_at = normalize_sent_at(payload.get('date'))
        if not is_sent_at_today_msk(sent_at):
            not_today += 1
            continue

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
                chat_id=LIVE_CHAT_ID,
                message_thread_id=REPORTS_TOPIC_ID,
                telegram_message_id=message_id,
                telegram_user_id=from_user_id,
                sent_at=sent_at,
                reports_topic_id=REPORTS_TOPIC_ID,
            )
        except Exception as exc:
            errors += 1
            logger.exception('sync msg=%s: %s', message_id, exc)
            continue

        if outcome.get('saved'):
            saved += 1
            processed_ids.add(message_id)
            if react_ok:
                if await mark_message_processed_ok(
                    bot, chat_id=LIVE_CHAT_ID, message_id=message_id
                ):
                    reacted += 1
        elif outcome.get('reason') == 'parse_failed':
            parse_failed += 1

        if scanned % 5 == 0:
            await asyncio.sleep(0.2)

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
