from __future__ import annotations

from collections import defaultdict
from datetime import datetime, time as dt_time, timezone as dt_timezone
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone

from flights.models import (
    OperatorCommLink,
    OperatorLocation,
    OperatorPlacementZone,
    OperatorPositionLog,
    OperatorProfile,
    User,
)
from flights.utils.live_flight import get_active_pilot_callnames
from flights.utils.telegram_report_stats import _shift_hours

UNASSIGNED_SENIOR_KEY = '__unassigned__'
UNASSIGNED_SENIOR_LABEL = ''
SENIOR_TAIL_CALLSIGN = 'иней'
UNASSIGNED_LOCATION_KEY = '__unassigned__'
UNASSIGNED_LOCATION_LABEL = 'Расположение не задано'
DETACHMENT_LOCATION_LABEL = 'В ОТРЫВЕ'


def comm_link_choices_payload() -> list[dict]:
    return [{'value': choice.value, 'label': choice.label} for choice in OperatorCommLink]


def normalize_comm_links(values) -> list[str]:
    if not values:
        return []
    if isinstance(values, str):
        values = [values]
    allowed = set(OperatorCommLink.values)
    seen: set[str] = set()
    result: list[str] = []
    for raw in values:
        value = (raw or '').strip()
        if value and value in allowed and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def comm_link_label(value: str) -> str:
    if not value:
        return ''
    try:
        return OperatorCommLink(value).label
    except ValueError:
        return value


def comm_link_labels(values) -> list[str]:
    return [comm_link_label(value) for value in normalize_comm_links(values)]


def _format_location_display(name: str, description: str = '') -> str:
    """н.п. Отрадное (поз. Берлога) — как на табло FPV-ТД."""
    name = (name or '').strip() or '—'
    desc = (description or '').strip()
    if desc and name != '—':
        return f'{desc} (поз. {name})'
    if desc:
        return desc
    if name != '—':
        return f'поз. {name}'
    return UNASSIGNED_LOCATION_LABEL


def _split_location_display(display: str) -> tuple[str, str]:
    """Раздельно н.п. и позиция для табло."""
    display = (display or '').strip()
    if not display or display == UNASSIGNED_LOCATION_LABEL:
        return '', ''
    marker = ' (поз. '
    if marker in display and display.endswith(')'):
        idx = display.rfind(marker)
        settlement = display[:idx].strip()
        position = display[idx + len(marker):-1].strip()
        if position and not position.startswith('поз.'):
            position = f'поз. {position}'
        return settlement, position
    if display.startswith('поз.'):
        return '', display
    return display, ''


def _is_assigned_senior_key(senior_key: str | None) -> bool:
    return bool(senior_key) and senior_key != UNASSIGNED_SENIOR_KEY


def _is_assigned_location_key(location_key: str | None) -> bool:
    return bool(location_key) and location_key != UNASSIGNED_LOCATION_KEY


def _msk_now(now=None):
    now = now or timezone.now()
    if timezone.is_naive(now):
        now = timezone.make_aware(now, dt_timezone.utc)
    return now.astimezone(ZoneInfo('Europe/Moscow'))


def _format_time(value: dt_time | None) -> str:
    if not value:
        return '—'
    return value.strftime('%H:%M')


def _schedule_label(profile: OperatorProfile, zone: str) -> str:
    if zone == OperatorPlacementZone.DAY:
        start, end = profile.day_shift_start, profile.day_shift_end
    elif zone == OperatorPlacementZone.NIGHT:
        start, end = profile.night_shift_start, profile.night_shift_end
    else:
        return '—'
    if start and end:
        return f'{_format_time(start)}–{_format_time(end)}'
    return '—'


def _duty_elapsed_seconds(profile: OperatorProfile, now=None) -> int | None:
    if not profile.duty_started_at:
        return None
    now = now or timezone.now()
    started = profile.duty_started_at
    if timezone.is_naive(started):
        started = timezone.make_aware(started, dt_timezone.utc)
    delta = now - started
    if delta.total_seconds() < 0:
        return 0
    return int(delta.total_seconds())


def _format_elapsed(seconds: int | None) -> str:
    if seconds is None:
        return '—'
    hours, remainder = divmod(seconds, 3600)
    minutes = remainder // 60
    if hours:
        return f'{hours} ч {minutes:02d} мин'
    return f'{minutes} мин'


def _serialize_operator(profile: OperatorProfile, now=None) -> dict:
    elapsed = _duty_elapsed_seconds(profile, now=now)
    return {
        'id': str(profile.id),
        'callsign': profile.pilot.callname,
        'drone_type': profile.drone_type_display,
        'placement_zone': profile.placement_zone,
        'schedule': _schedule_label(profile, profile.placement_zone),
        'duty_started_at': profile.duty_started_at.isoformat() if profile.duty_started_at else None,
        'duty_elapsed_seconds': elapsed,
        'duty_elapsed_label': _format_elapsed(elapsed),
        'location_id': str(profile.location_id) if profile.location_id else None,
        'location_label': profile.location_label,
        'location_description': (
            profile.location.description if profile.location_id else ''
        ),
        'location_display': _format_location_display(
            profile.location_label,
            profile.location.description if profile.location_id else '',
        ),
        'location_comm_links': (
            normalize_comm_links(profile.location.comm_links)
            if profile.location_id else []
        ),
        'senior_id': str(profile.senior_id) if profile.senior_id else None,
        'senior_callsign': profile.senior.callname if profile.senior_id else None,
        'notes': profile.notes or '',
    }


def _sort_key_unassigned_last(label: str, unassigned_label: str) -> tuple:
    return (label == unassigned_label, (label or '').lower())


def _normalize_callsign(value: str) -> str:
    return (value or '').strip().casefold().replace('ё', 'е')


def _senior_group_sort_key(group: dict) -> tuple:
    """Порядок секций: Тринадцатый, Урал, …, Иней внизу, без старшего — последним."""
    if not group.get('senior_id'):
        return (3, '')
    callsign = _normalize_callsign(group.get('senior_callsign'))
    if callsign == SENIOR_TAIL_CALLSIGN:
        return (2, '')
    return (0, callsign)


def _senior_section_sort_key(section: dict) -> tuple:
    callsign = (section.get('senior_callsign') or '').strip()
    if not callsign:
        return (3, '')
    normalized = _normalize_callsign(callsign)
    if normalized == SENIOR_TAIL_CALLSIGN:
        return (2, '')
    return (0, normalized)


def _senior_key_sort_key(
    senior_key: str,
    *,
    day_index: dict,
    night_index: dict,
    detachment_index: dict,
) -> tuple:
    if not _is_assigned_senior_key(senior_key):
        return (3, '')
    for index in (day_index, night_index, detachment_index):
        group = index.get(senior_key)
        if group:
            return _senior_group_sort_key(group)
    return (1, senior_key)


def _normalize_location_marker(value: str) -> str:
    return (value or '').strip().casefold().replace('ё', 'е')


def _is_v_otryve_location(loc: dict) -> bool:
    if loc.get('is_detachment_only'):
        return False
    markers = {
        _normalize_location_marker(DETACHMENT_LOCATION_LABEL),
        'в отрыве',
    }
    for field in (
        'location_label',
        'location_display',
        'location_settlement',
        'location_position',
    ):
        normalized = _normalize_location_marker(loc.get(field) or '')
        if not normalized:
            continue
        if normalized in markers:
            return True
        if normalized.startswith('поз. ') and normalized[5:] in markers:
            return True
    return False


def _location_board_sort_key(loc: dict) -> tuple:
    if loc.get('is_detachment_only'):
        return (3, '')
    label = (loc.get('location_display') or loc.get('location_label') or '').strip()
    if _is_v_otryve_location(loc):
        return (2, label.lower())
    is_unassigned = label == UNASSIGNED_LOCATION_LABEL
    return (1 if is_unassigned else 0, label.lower())


def _location_group_sort_key(loc: dict) -> tuple:
    label = (loc.get('location_display') or loc.get('location_label') or '').strip()
    if _is_v_otryve_location(loc):
        return (2, label.lower())
    return _sort_key_unassigned_last(label, UNASSIGNED_LOCATION_LABEL)


def _group_by_senior_and_location(operators: list[dict]) -> list[dict]:
    """Смена → старший → расположение → пилот."""
    senior_buckets: dict[str, dict] = defaultdict(lambda: {
        'senior_id': None,
        'senior_callsign': UNASSIGNED_SENIOR_LABEL,
        'locations': {},
    })

    for item in operators:
        senior_key = item.get('senior_id') or UNASSIGNED_SENIOR_KEY
        senior_group = senior_buckets[senior_key]
        if item.get('senior_id'):
            senior_group['senior_id'] = item['senior_id']
            senior_group['senior_callsign'] = item['senior_callsign']

        location_key = item.get('location_id') or UNASSIGNED_LOCATION_KEY
        location_label = (item.get('location_label') or '').strip() or UNASSIGNED_LOCATION_LABEL
        location_display = item.get('location_display') or _format_location_display(
            location_label,
            item.get('location_description', ''),
        )
        locations = senior_group['locations']
        if location_key not in locations:
            locations[location_key] = {
                'location_id': item.get('location_id'),
                'location_label': location_label,
                'location_display': location_display,
                'comm_links': normalize_comm_links(item.get('location_comm_links')),
                'operators': [],
            }
        locations[location_key]['operators'].append(item)

    groups = []
    for senior_group in senior_buckets.values():
        location_groups = list(senior_group['locations'].values())
        location_groups.sort(key=_location_group_sort_key)
        senior_count = 0
        for location_group in location_groups:
            location_group['operators'].sort(key=lambda op: op['callsign'].lower())
            location_group['count'] = len(location_group['operators'])
            senior_count += location_group['count']
        senior_group['locations'] = location_groups
        senior_group['count'] = senior_count
        groups.append(senior_group)

    groups.sort(key=_senior_group_sort_key)
    return groups


def _zone_payload(operators: list[dict]) -> dict:
    groups = _group_by_senior_and_location(operators)
    return {
        'groups': groups,
        'count': len(operators),
        'group_count': len(groups),
    }


def _index_zone_groups(groups: list[dict]) -> dict[str, dict]:
    index: dict[str, dict] = {}
    for senior_group in groups:
        senior_key = senior_group.get('senior_id') or UNASSIGNED_SENIOR_KEY
        index[senior_key] = senior_group
    return index


def _locations_map(senior_group: dict) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for loc in senior_group.get('locations', []):
        key = loc.get('location_id') or UNASSIGNED_LOCATION_KEY
        result[key] = loc
    return result


def build_operator_board(
    *,
    day_groups: list[dict],
    night_groups: list[dict],
    detachment_groups: list[dict],
) -> dict:
    """
    Единая таблица: ДЕНЬ | ОТРЫВ | НОЧЬ.
    Синие строки — старший, зелёные — расположение, ниже — пилоты.
    """
    day_index = _index_zone_groups(day_groups)
    night_index = _index_zone_groups(night_groups)
    detachment_index = _index_zone_groups(detachment_groups)

    senior_keys: list[str] = []
    seen: set[str] = set()
    for groups in (day_groups, night_groups, detachment_groups):
        for senior_group in groups:
            key = senior_group.get('senior_id') or UNASSIGNED_SENIOR_KEY
            if not _is_assigned_senior_key(key) or key in seen:
                continue
            seen.add(key)
            senior_keys.append(key)

    unassigned_det = detachment_index.get(UNASSIGNED_SENIOR_KEY, {})
    has_unassigned_detachment = any(
        loc.get('operators')
        for loc in unassigned_det.get('locations', [])
    )
    if has_unassigned_detachment and UNASSIGNED_SENIOR_KEY not in seen:
        senior_keys.append(UNASSIGNED_SENIOR_KEY)

    senior_keys.sort(
        key=lambda key: _senior_key_sort_key(
            key,
            day_index=day_index,
            night_index=night_index,
            detachment_index=detachment_index,
        ),
    )

    sections = []
    for senior_key in senior_keys:
        day_senior = day_index.get(senior_key, {})
        night_senior = night_index.get(senior_key, {})
        detachment_senior = detachment_index.get(senior_key, {})
        senior_callsign = (
            day_senior.get('senior_callsign')
            or night_senior.get('senior_callsign')
            or detachment_senior.get('senior_callsign')
            or ''
        ).strip()

        day_locs = _locations_map(day_senior)
        night_locs = _locations_map(night_senior)
        detachment_locs = _locations_map(detachment_senior)
        location_keys = {
            key for key in (set(day_locs) | set(night_locs) | set(detachment_locs))
            if _is_assigned_location_key(key)
        }

        location_entries = []
        for location_key in location_keys:
            day_loc = day_locs.get(location_key)
            night_loc = night_locs.get(location_key)
            detachment_loc = detachment_locs.get(location_key)
            display = (
                (day_loc or {}).get('location_display')
                or (night_loc or {}).get('location_display')
                or (detachment_loc or {}).get('location_display')
                or ''
            )
            settlement, position = _split_location_display(display)
            day_ops = (day_loc or {}).get('operators', [])
            night_ops = (night_loc or {}).get('operators', [])
            if not (day_ops or night_ops):
                continue
            row_count = max(len(day_ops), len(night_ops), 1)
            rows = []
            for row_idx in range(row_count):
                rows.append({
                    'day': day_ops[row_idx] if row_idx < len(day_ops) else None,
                    'night': night_ops[row_idx] if row_idx < len(night_ops) else None,
                    'detachment': None,
                })
            comm_links = normalize_comm_links(
                (day_loc or {}).get('comm_links')
                or (night_loc or {}).get('comm_links')
                or (detachment_loc or {}).get('comm_links')
            )
            location_entries.append({
                'location_id': location_key,
                'location_display': display,
                'location_label': (
                    (day_loc or {}).get('location_label')
                    or (night_loc or {}).get('location_label')
                    or (detachment_loc or {}).get('location_label')
                    or ''
                ),
                'location_settlement': settlement,
                'location_position': position,
                'comm_links': comm_links,
                'comm_link_labels': comm_link_labels(comm_links),
                'rows': rows,
            })

        section_detachment_ops: list[dict] = []
        for loc in detachment_locs.values():
            section_detachment_ops.extend(loc.get('operators', []))
        section_detachment_ops.sort(key=lambda op: (op.get('callsign') or '').lower())
        if section_detachment_ops:
            location_entries.append({
                'location_id': None,
                'location_display': '',
                'location_settlement': '',
                'location_position': '',
                'comm_links': [],
                'comm_link_labels': [],
                'is_detachment_only': True,
                'rows': [{
                    'day': None,
                    'night': None,
                    'detachment': None,
                    'detachment_group': section_detachment_ops,
                }],
            })

        if not location_entries:
            continue
        location_entries.sort(key=_location_board_sort_key)
        sections.append({
            'senior_callsign': senior_callsign,
            'locations': location_entries,
        })

    sections.sort(key=_senior_section_sort_key)

    return {
        'sections': sections,
    }


def get_operator_dashboard_payload(now=None) -> dict:
    now_msk = _msk_now(now)
    day_start_hour, night_start_hour = _shift_hours()
    profiles = (
        OperatorProfile.objects.filter(is_active=True)
        .select_related('pilot', 'senior', 'location')
        .order_by('senior__callname', 'location__name', 'pilot__callname')
    )

    zones = {
        OperatorPlacementZone.DAY: [],
        OperatorPlacementZone.NIGHT: [],
        OperatorPlacementZone.DETACHMENT: [],
    }

    for profile in profiles:
        item = _serialize_operator(profile, now=now)
        zones.setdefault(profile.placement_zone, []).append(item)

    day_ops = zones.get(OperatorPlacementZone.DAY, [])
    night_ops = zones.get(OperatorPlacementZone.NIGHT, [])
    detachment_ops = zones.get(OperatorPlacementZone.DETACHMENT, [])

    day_payload = _zone_payload(day_ops)
    night_payload = _zone_payload(night_ops)
    detachment_payload = _zone_payload(detachment_ops)

    return {
        'now_msk': now_msk.isoformat(),
        'shift_labels': {
            'day': f'день ({day_start_hour:02d}:00–{night_start_hour:02d}:00 МСК)',
            'night': f'ночь ({night_start_hour:02d}:00–{day_start_hour:02d}:00 МСК)',
            'detachment': 'отрыв',
        },
        'zones': {
            'day': day_payload,
            'night': night_payload,
            'detachment': detachment_payload,
        },
        'counts': {
            'day': len(day_ops),
            'night': len(night_ops),
            'detachment': len(detachment_ops),
        },
        'board': build_operator_board(
            day_groups=day_payload['groups'],
            night_groups=night_payload['groups'],
            detachment_groups=detachment_payload['groups'],
        ),
        'active_pilots': sorted(get_active_pilot_callnames()),
        'updated_at': timezone.localtime(timezone.now()).isoformat(),
    }


@transaction.atomic
def log_operator_position_change(
    *,
    profile: OperatorProfile,
    old_location_id,
    old_placement_zone: str | None,
    new_location: OperatorLocation | None,
    recorded_by: User | None = None,
    comment: str = '',
) -> None:
    new_location_id = new_location.id if new_location else None
    location_changed = old_location_id != new_location_id
    zone_changed = (
        old_placement_zone is not None
        and old_placement_zone != profile.placement_zone
    )
    moved_to_detachment = (
        zone_changed
        and profile.placement_zone == OperatorPlacementZone.DETACHMENT
    )
    if not (location_changed or moved_to_detachment):
        return

    log_comment = (comment or '').strip()
    if moved_to_detachment:
        log_comment = (profile.notes or '').strip() or log_comment
    if not log_comment:
        log_comment = 'Изменение расположения'

    OperatorPositionLog.objects.create(
        profile=profile,
        placement_zone=profile.placement_zone,
        location=new_location,
        location_label=new_location.name if new_location else '',
        recorded_by=recorded_by,
        comment=log_comment,
    )


@transaction.atomic
def update_operator_location(
    *,
    profile: OperatorProfile,
    location: OperatorLocation | None,
    placement_zone: str | None = None,
    duty_started_at: datetime | None = None,
    comment: str = '',
    detachment_destination: str = '',
    recorded_by: User | None = None,
) -> OperatorProfile:
    old_location_id = profile.location_id
    old_placement_zone = profile.placement_zone

    if placement_zone and placement_zone in OperatorPlacementZone.values:
        profile.placement_zone = placement_zone

    destination = (detachment_destination or comment or '').strip()
    if profile.placement_zone == OperatorPlacementZone.DETACHMENT:
        if profile.placement_zone != old_placement_zone and not destination:
            raise ValueError('Укажите, куда перемещаем.')
        if destination:
            profile.notes = destination
            comment = destination

    profile.location = location

    if duty_started_at is not None:
        profile.duty_started_at = duty_started_at

    profile.save()

    log_operator_position_change(
        profile=profile,
        old_location_id=old_location_id,
        old_placement_zone=old_placement_zone,
        new_location=profile.location,
        recorded_by=recorded_by,
        comment=comment,
    )
    return profile


def get_position_history(profile_id, *, limit: int = 100) -> list[dict]:
    logs = (
        OperatorPositionLog.objects.filter(profile_id=profile_id)
        .select_related('profile__pilot', 'recorded_by', 'location')
        .order_by('-recorded_at')[:limit]
    )
    return [
        {
            'id': str(log.id),
            'recorded_at': log.recorded_at.isoformat(),
            'placement_zone': log.placement_zone,
            'location_id': str(log.location_id) if log.location_id else None,
            'location_label': log.location.name if log.location_id else (log.location_label or ''),
            'comment': log.comment,
            'recorded_by': log.recorded_by.username if log.recorded_by else '',
        }
        for log in logs
    ]
