"""Статистика вылетов из Telegram-отчётов (топик 2406 и др.)."""

from __future__ import annotations

import logging
import re
from datetime import datetime, time as dt_time, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone

from flights.models import TelegramFlightReport

logger = logging.getLogger(__name__)

_NOT_DEFEATED_RE = re.compile(r'не\s*пораж', re.IGNORECASE)
_FLIGHT_NUM_RE = re.compile(
    r'(?i)(?:номер\s+вылета\s*[:\s]+)?(\d+)\s*(?:-?\s*(?:й\s*)?)?вылет\b'
)
_DATE_RE = re.compile(r'\b(\d{1,2}\.\d{1,2}(?:\.\d{2,4})?)\b')
_CALLSIGN_RE = re.compile(r'(?i)позывной\s*[:\s]+([^\n\r]+)')
_HTML_TAG_RE = re.compile(r'<[^>]+>')


def normalize_result_text(result: str | None) -> str:
    if not result:
        return ''
    return str(result).casefold().strip()


def is_report_not_defeated(result: str | None) -> bool:
    """Не поражено / промах (как в боте result_filters)."""
    text = normalize_result_text(result)
    if not text:
        return False
    compact = re.sub(r'\s+', '', text)
    if 'непораж' in compact or 'неуспеш' in compact:
        return True
    if _NOT_DEFEATED_RE.search(text):
        return True
    return 'промах' in text


def is_report_defeated(result: str | None) -> bool:
    """Поражено / уничтожено / подавление — без «не поражено» и без «успешно»."""
    text = normalize_result_text(result)
    if not text or is_report_not_defeated(result):
        return False
    if 'успешн' in text:
        return False
    if 'уничтож' in text or 'поражен' in text or 'подавл' in text or 'добиван' in text:
        return True
    return False


def is_report_result_successful(result: str | None) -> bool:
    """Совместимость: «успех» для индекса = поражение цели (не «успешно» из Excel)."""
    return is_report_defeated(result)


def _strip_html(text: str) -> str:
    return _HTML_TAG_RE.sub('', text or '').strip()


def parse_telegram_report_message(text: str, *, pilot_callsign: str = '') -> dict:
    """
    Разбор короткого отчёта из топика (формат «N вылет», дата, результат).
    """
    raw = _strip_html(text).strip()
    if not raw:
        return {'parse_ok': False}

    flight_number = 0
    match = _FLIGHT_NUM_RE.search(raw)
    if match:
        flight_number = int(match.group(1))
    else:
        first_line = raw.splitlines()[0].strip()
        simple = re.match(r'^(\d+)\s*$', first_line)
        if simple:
            flight_number = int(simple.group(1))

    if flight_number <= 0:
        return {'parse_ok': False}

    date_match = _DATE_RE.search(raw)
    work_date = date_match.group(1) if date_match else ''

    callsign_match = _CALLSIGN_RE.search(raw)
    callsign = (callsign_match.group(1).strip() if callsign_match else pilot_callsign)[:255]

    result = ''
    for line in raw.splitlines():
        line_stripped = line.strip()
        if re.search(r'(?i)^результат\s*[:\s]', line_stripped):
            result = re.sub(r'(?i)^результат\s*[:\s]*', '', line_stripped).strip()
            break

    if not result:
        for line in raw.splitlines():
            line_stripped = line.strip()
            if is_report_defeated(line_stripped) or is_report_not_defeated(line_stripped):
                result = line_stripped
                break

    if not result:
        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        if len(lines) >= 2:
            result = lines[-1]

    return {
        'parse_ok': True,
        'flight_number': flight_number,
        'work_date': work_date,
        'result': result,
        'pilot_callsign': callsign,
    }


def record_telegram_flight_report(
    *,
    chat_id,
    message_thread_id,
    telegram_message_id,
    flight_number,
    work_date='',
    result='',
    sent_at=None,
    parse_ok=True,
    pilot_callsign='',
    raw_text='',
):
    if not parse_ok:
        return {'ok': False, 'error': 'parse_failed'}

    when = sent_at or timezone.now()
    if isinstance(when, str):
        when = datetime.fromisoformat(when.replace('Z', '+00:00'))
    if timezone.is_naive(when):
        when = timezone.make_aware(when, dt_timezone.utc)

    defeated = is_report_defeated(result)
    report, created = TelegramFlightReport.objects.update_or_create(
        chat_id=int(chat_id),
        telegram_message_id=int(telegram_message_id),
        defaults={
            'message_thread_id': int(message_thread_id) if message_thread_id is not None else None,
            'flight_number': int(flight_number or 0),
            'work_date': (work_date or '')[:32],
            'result': (result or '')[:512],
            'pilot_callsign': (pilot_callsign or '')[:255],
            'is_successful': defeated,
            'parse_ok': True,
            'sent_at': when,
            'raw_text': raw_text or '',
        },
    )
    logger.info(
        'TG-отчёт %s: вылет №%s (%s)',
        'создан' if created else 'обновлён',
        flight_number,
        'поражено' if defeated else ('не поражено' if is_report_not_defeated(result) else '—'),
    )
    return {'ok': True, 'id': str(report.id), 'created': created, 'is_successful': defeated}


def _msk_now(now=None):
    now = now or timezone.now()
    if timezone.is_naive(now):
        now = timezone.make_aware(now, dt_timezone.utc)
    return now.astimezone(ZoneInfo('Europe/Moscow'))


def _shift_hours():
    day_start = int(getattr(settings, 'DASHBOARD_SHIFT_DAY_START_HOUR', 6))
    night_start = int(getattr(settings, 'DASHBOARD_SHIFT_NIGHT_START_HOUR', 18))
    return day_start, night_start


def _dashboard_shift_period_bounds(now=None):
    """
    Текущая смена по МСК:
    - день: 06:00–18:00
    - ночь: 18:00–06:00 (с предыдущего вечера)
    """
    tz = ZoneInfo('Europe/Moscow')
    day_start_hour, night_start_hour = _shift_hours()
    now_msk = _msk_now(now)
    today = now_msk.date()

    day_start = datetime.combine(today, dt_time(day_start_hour, 0), tzinfo=tz)
    night_start = datetime.combine(today, dt_time(night_start_hour, 0), tzinfo=tz)

    if day_start_hour <= now_msk.hour < night_start_hour:
        period_start = day_start
        shift_kind = 'day'
        shift_label = f'день ({day_start_hour:02d}:00–{night_start_hour:02d}:00 МСК)'
    elif now_msk.hour >= night_start_hour:
        period_start = night_start
        shift_kind = 'night'
        shift_label = f'ночь ({night_start_hour:02d}:00–{day_start_hour:02d}:00 МСК)'
    else:
        period_start = datetime.combine(
            today - timedelta(days=1),
            dt_time(night_start_hour, 0),
            tzinfo=tz,
        )
        shift_kind = 'night'
        shift_label = f'ночь ({night_start_hour:02d}:00–{day_start_hour:02d}:00 МСК)'

    return period_start, now_msk, shift_kind, shift_label


def _calendar_day_msk_period_bounds(now=None):
    """Операционные сутки по МСК: с 06:00 текущего/предыдущего дня до следующих 06:00 (конец — сейчас)."""
    tz = ZoneInfo('Europe/Moscow')
    day_start_hour, _ = _shift_hours()
    now_msk = _msk_now(now)
    today = now_msk.date()
    today_anchor = datetime.combine(today, dt_time(day_start_hour, 0), tzinfo=tz)
    if now_msk < today_anchor:
        period_start = today_anchor - timedelta(days=1)
    else:
        period_start = today_anchor
    return period_start, now_msk


def _rolling_24h_period_bounds(now=None):
    """Совместимость: операционные сутки 06:00–06:00 МСК."""
    return _calendar_day_msk_period_bounds(now)


def _count_results_from_reports(qs) -> dict[str, int]:
    """Подсчёт по полю result (актуально даже для старых записей в БД)."""
    defeated = 0
    not_defeated = 0
    other = 0
    for result in qs.values_list('result', flat=True):
        if is_report_defeated(result):
            defeated += 1
        elif is_report_not_defeated(result):
            not_defeated += 1
        else:
            other += 1
    return {
        'defeated_flights': defeated,
        'not_defeated_flights': not_defeated,
        'other_flights': other,
    }


def _telegram_reports_qs(*, period_start, period_end):
    chat_id = getattr(settings, 'TELEGRAM_REPORTS_CHAT_ID', None)
    topic_id = getattr(settings, 'TELEGRAM_REPORTS_TOPIC_ID', None)

    qs = TelegramFlightReport.objects.filter(
        parse_ok=True,
        flight_number__gt=0,
        sent_at__gte=period_start,
        sent_at__lte=period_end,
    )
    if chat_id:
        qs = qs.filter(chat_id=int(chat_id))
    if topic_id:
        qs = qs.filter(message_thread_id=int(topic_id))
    return qs.distinct()


def get_shift_telegram_reports_qs():
    """Отчёты за текущую смену (06–18 или 18–06 МСК)."""
    period_start, period_end, _, _ = _dashboard_shift_period_bounds()
    return _telegram_reports_qs(period_start=period_start, period_end=period_end)


def get_rolling_24h_telegram_reports_qs():
    """Отчёты за текущие календарные сутки (00:00–24:00 МСК)."""
    period_start, period_end = _calendar_day_msk_period_bounds()
    return _telegram_reports_qs(period_start=period_start, period_end=period_end)


def get_today_telegram_reports_qs():
    """Совместимость: отчёты за текущую смену."""
    return get_shift_telegram_reports_qs()


def _build_stats_payload(*, qs, period_start, period_end, source_suffix: str, shift_label: str = ''):
    from django.db.models import Max

    max_flight = qs.aggregate(m=Max('flight_number'))['m'] or 0
    reports_count = qs.count()
    # KPI = число принятых отчётов (сообщений), не max номер вылета.
    total = reports_count
    counts = _count_results_from_reports(qs)

    payload = {
        'total_flights': total,
        'latest_flight_number': max_flight,
        'reports_count': reports_count,
        'defeated_flights': counts['defeated_flights'],
        'not_defeated_flights': counts['not_defeated_flights'],
        'other_flights': counts['other_flights'],
        'successful_flights': counts['defeated_flights'],
        'success_rate_percent': round((counts['defeated_flights'] / total * 100), 1) if total else 0,
        'defeat_rate_percent': round((counts['defeated_flights'] / total * 100), 1) if total else 0,
        'source': source_suffix,
        'period_start': period_start.isoformat(),
        'period_end': period_end.isoformat(),
    }
    if shift_label:
        payload['shift_label'] = shift_label
    return payload


def get_dashboard_shift_stats():
    """Вылеты за текущую смену: max номер «N вылет» в окне 06–18 / 18–06 МСК."""
    period_start, period_end, shift_kind, shift_label = _dashboard_shift_period_bounds()
    qs = get_shift_telegram_reports_qs()
    payload = _build_stats_payload(
        qs=qs,
        period_start=period_start,
        period_end=period_end,
        source_suffix='telegram_reports_shift',
        shift_label=shift_label,
    )
    payload['shift_kind'] = shift_kind
    return payload


def get_dashboard_rolling_24h_stats():
    """Вылеты за операционные сутки (06:00–06:00 МСК)."""
    period_start, period_end = _calendar_day_msk_period_bounds()
    qs = get_rolling_24h_telegram_reports_qs()
    day_start_hour, _ = _shift_hours()
    period_end_day = period_start + timedelta(days=1)
    day_label = (
        f'{period_start.strftime("%d.%m")} {day_start_hour:02d}:00 – '
        f'{period_end_day.strftime("%d.%m")} {day_start_hour:02d}:00 МСК'
    )
    payload = _build_stats_payload(
        qs=qs,
        period_start=period_start,
        period_end=period_end,
        source_suffix='telegram_reports_day',
        shift_label=f'сутки {day_label}',
    )
    payload['day_label'] = day_label
    return payload


def get_dashboard_daily_stats():
    """Совместимость: KPI за смену."""
    return get_dashboard_shift_stats()


# Старое имя периода — для обратной совместимости тестов/скриптов
def _dashboard_period_bounds():
    period_start, period_end, _, _ = _dashboard_shift_period_bounds()
    return period_start, period_end
