"""Оперативные вылеты (Старт/Стоп из Telegram)."""
import logging
from datetime import datetime, time as dt_time, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone

from flights.models import (
    Flight,
    FlightResultTypes,
    LiveFlight,
    LiveFlightCloseReason,
    OperatorProfile,
    Pilot,
)

logger = logging.getLogger(__name__)

LIVE_FLIGHT_TIMEOUT = timedelta(minutes=40)
LIVE_FLIGHT_ACTION_START = 'start'
LIVE_FLIGHT_ACTION_STOP = 'stop'


def _calendar_day_msk_start(now=None):
    """Начало текущих операционных суток по МСК (06:00–06:00)."""
    from flights.utils.telegram_report_stats import _calendar_day_msk_period_bounds

    period_start, _ = _calendar_day_msk_period_bounds(now)
    return period_start


def reconcile_duplicate_active_flights():
    """Один active-вылет на пилота: лишние закрываются как new_start."""
    now = timezone.now()
    active = (
        LiveFlight.objects.filter(ended_at__isnull=True)
        .order_by('pilot_id', '-started_at')
    )
    seen_pilots = set()
    updated = 0
    for flight in active.iterator():
        if flight.pilot_id in seen_pilots:
            flight.ended_at = now
            flight.close_reason = LiveFlightCloseReason.NEW_START
            flight.save(update_fields=['ended_at', 'close_reason', 'modified'])
            updated += 1
            continue
        seen_pilots.add(flight.pilot_id)
    return updated


def close_expired_live_flights():
    """Авто-закрытие: ended_at = started_at + 40 мин."""
    reconcile_duplicate_active_flights()
    now = timezone.now()
    updated = 0
    active = LiveFlight.objects.filter(ended_at__isnull=True)
    for flight in active.iterator():
        deadline = flight.started_at + LIVE_FLIGHT_TIMEOUT
        if deadline > now:
            continue
        flight.ended_at = deadline
        flight.close_reason = LiveFlightCloseReason.TIMEOUT
        flight.save(update_fields=['ended_at', 'close_reason', 'modified'])
        _sync_operator_duty(flight.pilot, duty_started_at=None)
        updated += 1
    return updated


def _get_pilot_by_telegram_id(telegram_user_id):
    return Pilot.objects.filter(tg_id=telegram_user_id).first()


def _get_active_flight(telegram_user_id):
    return (
        LiveFlight.objects.filter(
            telegram_user_id=telegram_user_id,
            ended_at__isnull=True,
        )
        .order_by('-started_at')
        .first()
    )


def _normalize_event_at(event_at: datetime | None) -> datetime:
    if event_at is None:
        return timezone.now()
    if timezone.is_naive(event_at):
        return timezone.make_aware(event_at, dt_timezone.utc)
    return event_at


def _sync_operator_duty(pilot: Pilot, *, duty_started_at: datetime | None) -> None:
    """Дашборд размещения: «На дежурстве» по Старт/Стоп."""
    profile = OperatorProfile.objects.filter(pilot=pilot, is_active=True).first()
    if not profile or profile.duty_started_at == duty_started_at:
        return
    profile.duty_started_at = duty_started_at
    profile.save(update_fields=['duty_started_at', 'modified'])


@transaction.atomic
def record_live_flight_start(*, telegram_user_id, chat_id, message_id=None, event_at=None):
    """Старт вылета: закрыть все active у этого tg_id, открыть новый."""
    pilot = _get_pilot_by_telegram_id(telegram_user_id)
    if not pilot:
        logger.warning('Старт без привязанного пилота, tg_id=%s', telegram_user_id)
        return {'ok': False, 'error': 'pilot_not_linked'}

    if message_id is not None:
        existing = (
            LiveFlight.objects.filter(chat_id=chat_id, message_id_start=message_id)
            .select_related('pilot')
            .first()
        )
        if existing:
            return {
                'ok': True,
                'flight_id': str(existing.id),
                'callname': existing.pilot.callname,
                'duplicate': True,
            }

    when = _normalize_event_at(event_at)
    LiveFlight.objects.filter(
        telegram_user_id=telegram_user_id,
        ended_at__isnull=True,
    ).update(
        ended_at=when,
        close_reason=LiveFlightCloseReason.NEW_START,
        modified=when,
    )

    flight = LiveFlight.objects.create(
        pilot=pilot,
        telegram_user_id=telegram_user_id,
        chat_id=chat_id,
        started_at=when,
        message_id_start=message_id,
    )
    reconcile_duplicate_active_flights()
    _sync_operator_duty(pilot, duty_started_at=when)
    logger.info('Старт: %s (tg_id=%s)', pilot.callname, telegram_user_id)
    return {'ok': True, 'flight_id': str(flight.id), 'callname': pilot.callname}


@transaction.atomic
def record_live_flight_stop(*, telegram_user_id, chat_id=None, message_id=None, event_at=None):
    """Стоп вылета."""
    pilot = _get_pilot_by_telegram_id(telegram_user_id)
    if not pilot:
        logger.warning('Стоп без привязанного пилота, tg_id=%s', telegram_user_id)
        return {'ok': False, 'error': 'pilot_not_linked'}

    if message_id is not None:
        existing = LiveFlight.objects.filter(message_id_stop=message_id).select_related('pilot').first()
        if existing:
            return {
                'ok': True,
                'flight_id': str(existing.id),
                'callname': existing.pilot.callname,
                'duplicate': True,
            }

    active = _get_active_flight(telegram_user_id)
    if not active:
        logger.info('Стоп без active-вылета: %s', pilot.callname)
        return {'ok': False, 'error': 'no_active_flight'}

    when = _normalize_event_at(event_at)
    active.ended_at = when
    active.close_reason = LiveFlightCloseReason.STOP
    if message_id is not None:
        active.message_id_stop = message_id
    active.save(update_fields=['ended_at', 'close_reason', 'message_id_stop', 'modified'])
    _sync_operator_duty(pilot, duty_started_at=None)
    logger.info('Стоп: %s (tg_id=%s)', pilot.callname, telegram_user_id)
    return {'ok': True, 'flight_id': str(active.id), 'callname': pilot.callname}


def record_live_flight_event(
    *,
    action,
    telegram_user_id,
    chat_id,
    message_id=None,
    event_at=None,
):
    close_expired_live_flights()
    if action == LIVE_FLIGHT_ACTION_START:
        return record_live_flight_start(
            telegram_user_id=telegram_user_id,
            chat_id=chat_id,
            message_id=message_id,
            event_at=event_at,
        )
    if action == LIVE_FLIGHT_ACTION_STOP:
        return record_live_flight_stop(
            telegram_user_id=telegram_user_id,
            chat_id=chat_id,
            message_id=message_id,
            event_at=event_at,
        )
    return {'ok': False, 'error': 'invalid_action'}


def _format_time_msk(dt):
    if dt is None:
        return ''
    local = timezone.localtime(dt)
    return local.strftime('%H:%M')


def serialize_live_flight(flight, *, active=False):
    pilot_name = flight.pilot.callname
    started = _format_time_msk(flight.started_at)
    payload = {
        'id': str(flight.id),
        'callname': pilot_name,
        'started_at': started,
        'started_at_iso': flight.started_at.isoformat(),
    }
    if active:
        return payload
    ended = _format_time_msk(flight.ended_at)
    payload['time_range'] = f'{started}–{ended}'
    payload['ended_at_iso'] = flight.ended_at.isoformat() if flight.ended_at else None
    payload['is_auto'] = flight.close_reason == LiveFlightCloseReason.TIMEOUT
    payload['close_reason'] = flight.close_reason or ''
    return payload


def _dedupe_active_flights(flights):
    """Один вылет на пилота — самый поздний старт."""
    seen_pilots = set()
    result = []
    for flight in sorted(flights, key=lambda item: item.started_at, reverse=True):
        if flight.pilot_id in seen_pilots:
            continue
        seen_pilots.add(flight.pilot_id)
        result.append(flight)
    return sorted(result, key=lambda item: item.started_at)


def _active_pilot_callnames():
    close_expired_live_flights()
    now = timezone.now()
    timeout_threshold = now - LIVE_FLIGHT_TIMEOUT
    active = list(
        LiveFlight.objects.filter(
            ended_at__isnull=True,
            started_at__gt=timeout_threshold,
        ).select_related('pilot')
    )
    return {flight.pilot.callname for flight in _dedupe_active_flights(active)}


def get_active_pilot_callnames() -> set[str]:
    """Позывные пилотов с открытым live-вылетом (Старт без Стоп / таймаут)."""
    return _active_pilot_callnames()


def get_dashboard_map_points():
    """Координаты вылетов за текущие сутки (МСК) для карты на дашборде."""
    now = timezone.now()
    since = _calendar_day_msk_start(now)
    since_date = since.astimezone(ZoneInfo('Europe/Moscow')).date()
    active_callnames = _active_pilot_callnames()

    flights = (
        Flight.objects.filter(flight_date__gte=since_date)
        .exclude(lat_wgs84__isnull=True)
        .exclude(lon_wgs84__isnull=True)
        .select_related('pilot')
        .only(
            'id', 'number', 'pilot_id', 'drone', 'flight_date', 'flight_time',
            'target', 'result', 'coordinates', 'lat_wgs84', 'lon_wgs84',
            'comment', 'pilot__callname',
        )
    )

    points_by_key = {}
    for flight in flights.iterator(chunk_size=500):
        lat = flight.lat_wgs84
        lon = flight.lon_wgs84
        if lat is None or lon is None or (lat == 90.0 and lon == 0.0):
            continue

        pilot_name = flight.pilot.callname if flight.pilot_id else ''
        point = {
            'id': str(flight.id),
            'lat': lat,
            'lng': lon,
            'number': flight.number,
            'pilot_name': pilot_name,
            'is_active_pilot': pilot_name in active_callnames,
            'drone': flight.drone or '',
            'flight_date': flight.flight_date.isoformat() if flight.flight_date else None,
            'flight_time': flight.flight_time.isoformat() if flight.flight_time else None,
            'target': flight.target or '',
            'result': flight.result,
            'coordinates': flight.coordinates or '',
        }
        dedupe_key = FlightResultTypes.map_dedupe_key(flight)
        existing = points_by_key.get(dedupe_key)
        if existing is None:
            points_by_key[dedupe_key] = point
        elif FlightResultTypes.result_priority(flight.result) > FlightResultTypes.result_priority(
            existing['result']
        ):
            points_by_key[dedupe_key] = point

    return list(points_by_key.values())


def get_dashboard_daily_stats():
    from flights.utils.telegram_report_stats import get_dashboard_shift_stats

    return get_dashboard_shift_stats()


def _get_rolling_24h_stats():
    from flights.utils.telegram_report_stats import get_dashboard_rolling_24h_stats

    return get_dashboard_rolling_24h_stats()


def _sync_duty_from_active_flights() -> int:
    """Сброс duty_started_at у пилотов без открытого live-вылета."""
    active_pilot_ids = set(
        LiveFlight.objects.filter(ended_at__isnull=True).values_list('pilot_id', flat=True)
    )
    stale = OperatorProfile.objects.filter(
        is_active=True,
        duty_started_at__isnull=False,
    ).exclude(pilot_id__in=active_pilot_ids)
    return stale.update(duty_started_at=None, modified=timezone.now())


def get_dashboard_live_flights(*, weather_region_id=None):
    close_expired_live_flights()
    _sync_duty_from_active_flights()
    now = timezone.now()
    timeout_threshold = now - LIVE_FLIGHT_TIMEOUT

    active_flights = _dedupe_active_flights(list(
        LiveFlight.objects.filter(
            ended_at__isnull=True,
            started_at__gt=timeout_threshold,
        ).select_related('pilot')
    ))

    since = _calendar_day_msk_start(now)
    completed_qs = (
        LiveFlight.objects.filter(
            ended_at__isnull=False,
            started_at__gte=since,
        )
        .exclude(close_reason=LiveFlightCloseReason.NEW_START)
        .select_related('pilot')
        .order_by('-ended_at')
    )

    from flights.utils.dashboard_alerts import get_dashboard_alerts
    from flights.utils.dashboard_weather import get_dashboard_weather, get_weather_regions

    return {
        'active': [serialize_live_flight(f, active=True) for f in active_flights],
        'completed': [serialize_live_flight(f) for f in completed_qs],
        'map_points': get_dashboard_map_points(),
        'weather_regions': get_weather_regions(),
        'weather': get_dashboard_weather(weather_region_id),
        'shift_stats': get_dashboard_daily_stats(),
        'rolling_24h_stats': _get_rolling_24h_stats(),
        'daily_stats': get_dashboard_daily_stats(),
        'alerts': get_dashboard_alerts(),
        'updated_at': timezone.localtime(now).isoformat(),
    }
