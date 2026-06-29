"""Агрегация результатов вылетов для статистики (по полю result)."""

from collections import defaultdict

from flights.models import FlightResultTypes


def empty_success_counts():
    return {'destroyed': 0, 'porazheno': 0}


def empty_result_counts():
    return {
        'total_flights': 0,
        'destroyed': 0,
        'porazheno': 0,
        'not_defeated': 0,
    }


def _apply_result_to_counts(entry, result):
    entry['total_flights'] += 1
    if result == FlightResultTypes.DESTROYED:
        entry['destroyed'] += 1
    elif result == FlightResultTypes.DEFEATED:
        entry['porazheno'] += 1
    elif result == FlightResultTypes.NOT_DEFEATED:
        entry['not_defeated'] += 1


def success_total(counts):
    return counts.get('destroyed', 0) + counts.get('porazheno', 0)


def aggregate_success_counts(flights_qs):
    counts = empty_success_counts()
    for result in flights_qs.values_list('result', flat=True).iterator():
        if result == FlightResultTypes.DESTROYED:
            counts['destroyed'] += 1
        elif result == FlightResultTypes.DEFEATED:
            counts['porazheno'] += 1
    return counts


def aggregate_pilot_success_stats(flights_qs):
    stats = {}
    rows = flights_qs.exclude(
        pilot__callname__istartswith='Неизвестный_',
    ).values('pilot__id', 'pilot__callname', 'result')

    for row in rows.iterator():
        pilot_id = row['pilot__id']
        if pilot_id not in stats:
            stats[pilot_id] = {
                'pilot__id': pilot_id,
                'pilot__callname': row['pilot__callname'],
                **empty_result_counts(),
            }
        _apply_result_to_counts(stats[pilot_id], row['result'])

    result = []
    for entry in stats.values():
        total = entry['total_flights']
        success = success_total(entry)
        entry['success_total'] = success
        entry['success_rate_percent'] = round((success / total * 100), 2) if total else 0
        result.append(entry)

    result.sort(key=lambda item: item['success_total'], reverse=True)
    return result


def aggregate_drone_success_stats(flights_qs, normalize_drone):
    stats = {}
    rows = flights_qs.values('drone', 'pilot', 'result')

    for row in rows.iterator():
        normalized_drone = normalize_drone(row['drone'])
        if normalized_drone not in stats:
            stats[normalized_drone] = {
                'drone': normalized_drone,
                'pilots_involved': set(),
                **empty_result_counts(),
            }
        entry = stats[normalized_drone]
        _apply_result_to_counts(entry, row['result'])
        if row['pilot']:
            entry['pilots_involved'].add(row['pilot'])

    result = []
    for entry in stats.values():
        total = entry['total_flights']
        success = success_total(entry)
        pilots_involved = entry.pop('pilots_involved')
        entry['pilots_involved'] = len(pilots_involved)
        entry['success_total'] = success
        entry['success_rate_percent'] = round((success / total * 100), 2) if total else 0
        result.append(entry)

    result.sort(key=lambda item: item['total_flights'], reverse=True)
    return result


def aggregate_daily_success_stats(flights_qs):
    daily = defaultdict(empty_result_counts)

    for row in flights_qs.values('flight_date', 'result').iterator():
        day = row['flight_date']
        if not day:
            continue
        _apply_result_to_counts(daily[day], row['result'])

    result = []
    for day in sorted(daily.keys()):
        entry = daily[day]
        success = success_total(entry)
        total = entry['total_flights']
        result.append({
            'date': day.isoformat(),
            'total_flights': total,
            'destroyed_flights': entry['destroyed'],
            'porazheno_flights': entry['porazheno'],
            'defeated_flights': entry['porazheno'],
            'not_defeated_flights': entry['not_defeated'],
            'success_total': success,
            'success_rate_percent': round((success / total * 100), 2) if total else 0,
        })
    return result


def aggregate_target_success_stats(flights_qs, limit=20):
    target_counts = defaultdict(int)
    rows = flights_qs.exclude(target__isnull=True).exclude(target='').filter(
        result__in=(FlightResultTypes.DESTROYED, FlightResultTypes.DEFEATED),
    ).values('target')

    for row in rows.iterator():
        target_counts[row['target']] += 1

    return [
        {'target': target, 'success_count': count}
        for target, count in sorted(target_counts.items(), key=lambda item: item[1], reverse=True)[:limit]
    ]


def aggregate_pilot_target_success_stats(flights_qs, pilot_callname):
    rows = flights_qs.exclude(
        pilot__callname__istartswith='Неизвестный_',
    ).exclude(target__isnull=True).exclude(target='').filter(
        pilot__callname__icontains=pilot_callname,
        result__in=(FlightResultTypes.DESTROYED, FlightResultTypes.DEFEATED),
    ).values('pilot__id', 'pilot__callname', 'target')

    target_counts = defaultdict(lambda: defaultdict(int))
    pilot_ids = {}

    for row in rows.iterator():
        pilot_name = row['pilot__callname']
        pilot_ids[pilot_name] = row['pilot__id']
        target_counts[pilot_name][row['target']] += 1

    result = []
    for pilot_name, targets in target_counts.items():
        target_list = [
            {'target': target, 'success_count': count}
            for target, count in sorted(targets.items(), key=lambda item: item[1], reverse=True)
        ]
        total_success = sum(item['success_count'] for item in target_list)
        result.append({
            'pilot_name': pilot_name,
            'pilot_id': pilot_ids[pilot_name],
            'targets': target_list,
            'total_success': total_success,
        })

    result.sort(key=lambda item: item['total_success'], reverse=True)
    return result
