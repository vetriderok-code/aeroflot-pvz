"""Приём отчётов и команд из оперативной Telegram-группы (общая логика для бота и sync)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone as dt_timezone
from typing import Any

from flights.models import Pilot
from flights.utils.dashboard_alerts import record_dashboard_alert
from flights.utils.live_flight import (
    LIVE_FLIGHT_ACTION_START,
    LIVE_FLIGHT_ACTION_STOP,
    record_live_flight_event,
)
from flights.utils.telegram_report_stats import (
    parse_telegram_report_message,
    record_telegram_flight_report,
)

logger = logging.getLogger(__name__)

CMD_START = 'Старт'
CMD_STOP = 'Стоп'


def _normalize_start_stop_command(text: str) -> str | None:
    """«Старт» / «Стоп» без учёта регистра (старт, СТАРТ, …)."""
    normalized = (text or '').strip().casefold()
    if normalized == CMD_START.casefold():
        return CMD_START
    if normalized == CMD_STOP.casefold():
        return CMD_STOP
    return None


def extract_message_text(*, text: str | None = None, caption: str | None = None) -> str:
    """Текст сообщения: подпись к видео/фото или обычный text."""
    return (text or caption or '').strip()


def normalize_sent_at(sent_at: datetime | None) -> datetime | None:
    if sent_at is None:
        return None
    if sent_at.tzinfo is None:
        return sent_at.replace(tzinfo=dt_timezone.utc)
    return sent_at


def process_start_stop_message(
    *,
    text: str,
    telegram_user_id: int,
    chat_id: int,
    message_id: int | None = None,
    sent_at: datetime | None = None,
) -> dict[str, Any]:
    stripped = (text or '').strip()
    command = _normalize_start_stop_command(stripped)
    if command == CMD_START:
        action = LIVE_FLIGHT_ACTION_START
    elif command == CMD_STOP:
        action = LIVE_FLIGHT_ACTION_STOP
    else:
        return {'handled': False}

    result = record_live_flight_event(
        action=action,
        telegram_user_id=telegram_user_id,
        chat_id=chat_id,
        message_id=message_id,
        event_at=normalize_sent_at(sent_at),
    )
    result['handled'] = True
    result['command'] = command
    return result


def normalize_video_payload(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not payload or not payload.get('file_id'):
        return None
    return {
        'telegram_file_id': str(payload['file_id']),
        'video_mime': (payload.get('mime_type') or payload.get('video_mime') or 'video/mp4')[:127],
        'video_size': payload.get('file_size') or payload.get('video_size'),
        'video_duration': payload.get('duration') or payload.get('video_duration'),
    }


def process_report_message(
    *,
    text: str,
    chat_id: int,
    message_thread_id: int | None,
    telegram_message_id: int,
    telegram_user_id: int,
    sent_at: datetime | None = None,
    reports_topic_id: int | None = None,
    reports_topic_ids: list[int] | None = None,
    video_payload: dict[str, Any] | None = None,
    backfill: bool = False,
) -> dict[str, Any]:
    allowed_topics = list(reports_topic_ids or [])
    if reports_topic_id is not None and reports_topic_id not in allowed_topics:
        allowed_topics.append(int(reports_topic_id))
    if (
        not backfill
        and allowed_topics
        and message_thread_id not in allowed_topics
    ):
        return {'handled': False, 'reason': 'wrong_topic'}

    body = extract_message_text(text=text)
    if not body:
        return {'handled': True, 'reason': 'empty_text', 'saved': False}

    pilot = Pilot.objects.filter(tg_id=telegram_user_id).first()
    pilot_callsign = pilot.callname if pilot else ''
    parsed = parse_telegram_report_message(body, pilot_callsign=pilot_callsign)
    if not parsed.get('parse_ok'):
        logger.debug(
            'Отчёт не распознан (msg=%s): %s',
            telegram_message_id,
            body[:120],
        )
        return {'handled': True, 'reason': 'parse_failed', 'saved': False}

    video = normalize_video_payload(video_payload)
    result = record_telegram_flight_report(
        chat_id=int(chat_id),
        message_thread_id=int(message_thread_id) if message_thread_id is not None else None,
        telegram_message_id=int(telegram_message_id),
        flight_number=parsed['flight_number'],
        work_date=parsed.get('work_date', ''),
        result=parsed.get('result', ''),
        pilot_callsign=parsed.get('pilot_callsign') or pilot_callsign,
        sent_at=normalize_sent_at(sent_at),
        raw_text=body,
        parse_ok=True,
        coordinates_sk42=parsed.get('coordinates_sk42', ''),
        lat_wgs84=parsed.get('lat_wgs84'),
        lon_wgs84=parsed.get('lon_wgs84'),
        telegram_file_id=(video or {}).get('telegram_file_id', ''),
        video_mime=(video or {}).get('video_mime', ''),
        video_size=(video or {}).get('video_size'),
        video_duration=(video or {}).get('video_duration'),
    )
    return {
        'handled': True,
        'saved': bool(result.get('ok')),
        'created': result.get('created'),
        'flight_number': parsed['flight_number'],
        'record': result,
    }


def process_alert_message(
    *,
    text: str,
    chat_id: int,
    message_thread_id: int | None,
    telegram_message_id: int,
    sent_at: datetime | None = None,
    alerts_topic_id: int | None,
) -> dict[str, Any]:
    if alerts_topic_id is None or message_thread_id != alerts_topic_id:
        return {'handled': False, 'reason': 'wrong_topic'}

    body = extract_message_text(text=text)
    if not body:
        return {'handled': True, 'reason': 'empty_text', 'saved': False}

    result = record_dashboard_alert(
        chat_id=int(chat_id),
        message_thread_id=int(message_thread_id) if message_thread_id is not None else None,
        telegram_message_id=int(telegram_message_id),
        text=body,
        posted_at=normalize_sent_at(sent_at),
    )
    return {
        'handled': True,
        'saved': bool(result.get('ok')),
        'record': result,
    }


def ingest_group_message(
    *,
    text: str | None,
    caption: str | None,
    chat_id: int,
    message_thread_id: int | None,
    telegram_message_id: int,
    telegram_user_id: int,
    sent_at: datetime | None,
    reports_topic_id: int | None = None,
    reports_topic_ids: list[int] | None = None,
    alerts_topic_id: int = -1,
    video_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Обработка одного сообщения группы.
    Сначала Старт/Стоп (только чистый text), затем отчёт, затем оповещение.
    """
    plain_text = extract_message_text(text=text, caption=caption)

    # Старт/Стоп — только отдельное текстовое сообщение (не подпись к видео).
    start_stop = process_start_stop_message(
        text=(text or '').strip(),
        telegram_user_id=telegram_user_id,
        chat_id=chat_id,
        message_id=telegram_message_id,
        sent_at=sent_at,
    )
    if start_stop.get('handled'):
        return {'kind': 'start_stop', **start_stop}

    report = process_report_message(
        text=plain_text,
        chat_id=chat_id,
        message_thread_id=message_thread_id,
        telegram_message_id=telegram_message_id,
        telegram_user_id=telegram_user_id,
        sent_at=sent_at,
        reports_topic_id=reports_topic_id,
        reports_topic_ids=reports_topic_ids,
        video_payload=video_payload,
    )
    if report.get('handled'):
        return {'kind': 'report', **report}

    if alerts_topic_id < 0:
        return {'kind': 'ignored', 'handled': False}

    alert = process_alert_message(
        text=plain_text,
        chat_id=chat_id,
        message_thread_id=message_thread_id,
        telegram_message_id=telegram_message_id,
        sent_at=sent_at,
        alerts_topic_id=alerts_topic_id,
    )
    if alert.get('handled'):
        return {'kind': 'alert', **alert}

    return {'kind': 'ignored', 'handled': False}
