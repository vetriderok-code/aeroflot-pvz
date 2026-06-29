"""Отчетный квартал ТД: видео-отчёты из топиков 1 ИГ / 2 ИГ / 3 ИГ."""
import asyncio
import logging

from aiogram import F, Router
from aiogram.types import Message
from decouple import config

from flights.utils.telegram_report_ingest import ingest_group_message, normalize_sent_at
from handlers.group_monitor import _extract_video_payload
from bridge.hooks import bridge_tg_message
from utils.report_video_download import schedule_report_video_download_bot
from utils.telegram_reactions import mark_message_processed_ok

logger = logging.getLogger(__name__)

td_reports_router = Router()


def _video_reports_chat_id() -> int | None:
    raw = (
        config('TELEGRAM_VIDEO_REPORTS_CHAT_ID', default='')
        or config('TELEGRAM_TD_REPORTS_CHAT_ID', default='')
    ).strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        logger.warning('TELEGRAM_VIDEO_REPORTS_CHAT_ID не число: %s', raw)
        return None


def _video_reports_topic_ids() -> set[int]:
    raw = (
        config('TELEGRAM_VIDEO_REPORT_TOPIC_IDS', default='')
        or config('TELEGRAM_TD_REPORT_TOPIC_IDS', default='')
    ).strip()
    result = set()
    for part in raw.split(','):
        part = part.strip()
        if not part:
            continue
        try:
            result.add(int(part))
        except ValueError:
            logger.warning('Некорректный topic id в TELEGRAM_VIDEO_REPORT_TOPIC_IDS: %s', part)
    return result


def _message_thread_id(message: Message):
    return getattr(message, 'message_thread_id', None)


def _message_sent_at(message: Message):
    return normalize_sent_at(message.date)


def process_td_report_message(message: Message) -> dict:
    if not message.from_user:
        return {'kind': 'ignored'}

    topic_ids = _video_reports_topic_ids()
    thread_id = _message_thread_id(message)
    if topic_ids and thread_id not in topic_ids:
        return {'kind': 'ignored', 'reason': 'wrong_topic'}

    outcome = ingest_group_message(
        text=message.text,
        caption=message.caption,
        chat_id=message.chat.id,
        message_thread_id=thread_id,
        telegram_message_id=message.message_id,
        telegram_user_id=message.from_user.id,
        sent_at=_message_sent_at(message),
        reports_topic_id=None,
        reports_topic_ids=sorted(topic_ids),
        alerts_topic_id=-1,
        video_payload=_extract_video_payload(message),
    )
    outcome['kind'] = outcome.get('kind', 'report')
    return outcome


async def _after_message_processed(message: Message, outcome: dict, bot):
    if outcome.get('kind') != 'report' or not outcome.get('saved'):
        return
    record = outcome.get('record') or {}
    if record.get('has_video') and record.get('id'):
        schedule_report_video_download_bot(record['id'], bot)
    await mark_message_processed_ok(bot, chat_id=message.chat.id, message_id=message.message_id)


def _register_td_handlers(router: Router, chat_id: int) -> None:
    @router.message(F.chat.id == chat_id)
    async def on_td_group_message(message: Message):
        outcome = await asyncio.to_thread(process_td_report_message, message)
        await _after_message_processed(message, outcome, message.bot)
        await bridge_tg_message(message, message.bot)

    @router.edited_message(F.chat.id == chat_id)
    async def on_td_group_message_edited(message: Message):
        outcome = await asyncio.to_thread(process_td_report_message, message)
        await _after_message_processed(message, outcome, message.bot)
        await bridge_tg_message(message, message.bot)


TD_CHAT_ID = _video_reports_chat_id()
if TD_CHAT_ID:
    _register_td_handlers(td_reports_router, TD_CHAT_ID)
