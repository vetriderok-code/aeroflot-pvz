"""Оповещения из Telegram-топика на дашборд."""
from __future__ import annotations

import logging
from datetime import datetime

from django.utils import timezone

from flights.models import DashboardAlert
from flights.utils.live_flight import _calendar_day_msk_start

logger = logging.getLogger(__name__)

ALERTS_LIMIT = 80


def _parse_posted_at(value):
    if not value:
        return timezone.now()
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).replace('Z', '+00:00')
        dt = datetime.fromisoformat(text)
    if timezone.is_naive(dt):
        return timezone.make_aware(dt, timezone.utc)
    return dt


def record_dashboard_alert(
    *,
    chat_id,
    message_thread_id,
    telegram_message_id,
    text,
    posted_at=None,
):
    body = (text or '').strip()
    if not body:
        return {'ok': False, 'error': 'empty_text'}

    when = _parse_posted_at(posted_at)
    alert, created = DashboardAlert.objects.update_or_create(
        chat_id=int(chat_id),
        telegram_message_id=int(telegram_message_id),
        defaults={
            'message_thread_id': int(message_thread_id) if message_thread_id is not None else None,
            'text': body,
            'posted_at': when,
        },
    )
    logger.info(
        'Оповещение %s chat=%s msg=%s',
        'создано' if created else 'обновлено',
        chat_id,
        telegram_message_id,
    )
    return {'ok': True, 'id': str(alert.id), 'created': created}


def serialize_dashboard_alert(alert):
    local = timezone.localtime(alert.posted_at)
    return {
        'id': str(alert.id),
        'text': alert.text,
        'posted_at': local.strftime('%H:%M'),
        'posted_at_iso': alert.posted_at.isoformat(),
        'message_id': alert.telegram_message_id,
    }


def get_dashboard_alerts():
    since = _calendar_day_msk_start()
    qs = DashboardAlert.objects.filter(posted_at__gte=since).order_by('-posted_at')[:ALERTS_LIMIT]
    return [serialize_dashboard_alert(item) for item in qs]
