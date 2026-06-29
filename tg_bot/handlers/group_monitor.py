"""Оперативная группа: Старт/Стоп, отчёты (топик 2406), оповещения (топик 2408)."""
import asyncio
import logging
from datetime import timezone as dt_timezone

from aiogram import F, Router
from aiogram.types import Message
from decouple import config

from flights.utils.telegram_report_ingest import ingest_group_message, normalize_sent_at
from bridge.hooks import bridge_tg_message
from utils.telegram_reactions import mark_message_processed_ok
from utils.topic_backfill import track_message_id

logger = logging.getLogger(__name__)

group_router = Router()

LIVE_CHAT_ID = int(config('TELEGRAM_LIVE_FLIGHT_CHAT_ID', default=-1003960872491))
REPORTS_TOPIC_ID = int(config('TELEGRAM_REPORTS_TOPIC_ID', default=2406))
ALERTS_TOPIC_ID = int(config('TELEGRAM_ALERTS_TOPIC_ID', default=2408))


def _message_thread_id(message: Message):
    return getattr(message, 'message_thread_id', None)


def _message_sent_at(message: Message):
    return normalize_sent_at(message.date)


def _extract_video_payload(message: Message) -> dict | None:
    if message.video:
        video = message.video
        return {
            'file_id': video.file_id,
            'mime_type': video.mime_type or 'video/mp4',
            'file_size': video.file_size,
            'duration': video.duration,
        }
    if message.document and (message.document.mime_type or '').startswith('video/'):
        doc = message.document
        return {
            'file_id': doc.file_id,
            'mime_type': doc.mime_type or 'video/mp4',
            'file_size': doc.file_size,
            'duration': None,
        }
    return None


def process_group_message(message: Message) -> dict:
    if not message.from_user:
        return {'kind': 'ignored'}

    track_message_id(message.message_id)

    outcome = ingest_group_message(
        text=message.text,
        caption=message.caption,
        chat_id=message.chat.id,
        message_thread_id=_message_thread_id(message),
        telegram_message_id=message.message_id,
        telegram_user_id=message.from_user.id,
        sent_at=_message_sent_at(message),
        reports_topic_id=REPORTS_TOPIC_ID,
        alerts_topic_id=ALERTS_TOPIC_ID,
        video_payload=_extract_video_payload(message),
    )

    kind = outcome.get('kind')
    if kind == 'start_stop' and outcome.get('ok'):
        logger.info(
            '%s: %s (tg_id=%s)',
            outcome.get('command'),
            outcome.get('callname'),
            message.from_user.id,
        )
    elif kind == 'start_stop' and outcome.get('error') == 'pilot_not_linked':
        logger.warning(
            '%s: tg_id=%s не привязан к пилоту',
            outcome.get('command'),
            message.from_user.id,
        )
    elif kind == 'report' and outcome.get('saved'):
        logger.info(
            'Отчёт №%s сохранён (tg_id=%s, msg=%s)',
            outcome.get('flight_number'),
            message.from_user.id,
            message.message_id,
        )
    elif kind == 'alert' and outcome.get('saved'):
        logger.info('Оповещение сохранено (msg=%s)', message.message_id)

    return outcome


async def _after_message_processed(message: Message, outcome: dict, bot):
    if outcome.get('kind') != 'report' or not outcome.get('saved'):
        return
    await mark_message_processed_ok(bot, chat_id=message.chat.id, message_id=message.message_id)


@group_router.message(F.chat.id == LIVE_CHAT_ID)
async def on_group_message(message: Message):
    outcome = await asyncio.to_thread(process_group_message, message)
    await _after_message_processed(message, outcome, message.bot)
    await bridge_tg_message(message, message.bot)


@group_router.edited_message(F.chat.id == LIVE_CHAT_ID)
async def on_group_message_edited(message: Message):
    """Правки подписи к видео/текста отчёта."""
    outcome = await asyncio.to_thread(process_group_message, message)
    await _after_message_processed(message, outcome, message.bot)
    await bridge_tg_message(message, message.bot)
