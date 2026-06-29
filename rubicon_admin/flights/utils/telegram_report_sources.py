"""Источники TG-отчётов с видео (Отчетный квартал ТД и др.)."""
from __future__ import annotations

from django.conf import settings


def _parse_topic_ids(raw: str) -> list[int]:
    result = []
    for part in (raw or '').split(','):
        part = part.strip()
        if not part:
            continue
        try:
            result.append(int(part))
        except ValueError:
            continue
    return result


def get_video_reports_chat_id() -> int | None:
    for key in (
        'TELEGRAM_VIDEO_REPORTS_CHAT_ID',
        'TELEGRAM_TD_REPORTS_CHAT_ID',
    ):
        raw = getattr(settings, key, None)
        if raw in (None, ''):
            continue
        try:
            return int(raw)
        except (TypeError, ValueError):
            continue
    return None


def get_video_reports_topic_ids() -> list[int]:
    for key in (
        'TELEGRAM_VIDEO_REPORT_TOPIC_IDS',
        'TELEGRAM_TD_REPORT_TOPIC_IDS',
    ):
        raw = getattr(settings, key, None)
        if raw:
            ids = _parse_topic_ids(str(raw))
            if ids:
                return ids
    return []


def get_map_report_sources() -> list[tuple[int, list[int]]]:
    """
    Источники точек на карте: [(chat_id, [topic_id, ...]), ...].
    Приоритет — Отчетный квартал ТД (видео-отчёты).
    """
    video_chat = get_video_reports_chat_id()
    video_topics = get_video_reports_topic_ids()
    if video_chat and video_topics:
        return [(video_chat, video_topics)]

    legacy_chat = getattr(settings, 'TELEGRAM_REPORTS_CHAT_ID', None)
    legacy_topic = getattr(settings, 'TELEGRAM_REPORTS_TOPIC_ID', None)
    if legacy_chat and legacy_topic:
        return [(int(legacy_chat), [int(legacy_topic)])]
    return []


def is_video_report_topic(*, chat_id: int, message_thread_id: int | None) -> bool:
    if message_thread_id is None:
        return False
    for source_chat, topic_ids in get_map_report_sources():
        if int(chat_id) == int(source_chat) and int(message_thread_id) in topic_ids:
            return True
    return False
