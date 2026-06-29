"""Погода для оперативного дашборда (Open-Meteo, без API-ключа)."""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

WEATHER_CACHE_SECONDS = 20 * 60

# Направления погоды на дашборде (ДНР / ЛНР / Запорожье + приграничье).
# Переопределение: DASHBOARD_WEATHER_REGIONS — JSON-массив [{id, name, lat, lon}, ...] в .env
DEFAULT_WEATHER_REGIONS = [
    {'id': 'pokrovsk', 'name': 'Покровск', 'lat': 48.281, 'lon': 37.179},
    {'id': 'myrnohrad', 'name': 'Мирноград', 'lat': 48.291, 'lon': 37.268},
    {'id': 'huliaipole', 'name': 'Гуляйполе', 'lat': 47.664, 'lon': 36.256},
    {'id': 'selydove', 'name': 'Селидово', 'lat': 48.147, 'lon': 37.300},
    {'id': 'dobropillia', 'name': 'Доброполье', 'lat': 48.467, 'lon': 37.084},
    {'id': 'slavyanka', 'name': 'Славянка', 'lat': 48.069, 'lon': 37.134},
    {'id': 'pokrovske', 'name': 'Покровское', 'lat': 48.635, 'lon': 38.131},
    {'id': 'vozdvyzhenka', 'name': 'Воздвижевка', 'lat': 48.304, 'lon': 37.516},
    {'id': 'belgorod', 'name': 'Белгород', 'lat': 50.596, 'lon': 36.587},
    {'id': 'shebekino', 'name': 'Шебекино', 'lat': 50.410, 'lon': 36.914},
    {'id': 'kozacha_lopan', 'name': 'Козачья Лопань', 'lat': 50.282, 'lon': 36.734},
    {'id': 'niu_york', 'name': 'Нью-Йорк', 'lat': 48.318, 'lon': 37.845},
    {'id': 'polohy', 'name': 'Пологи', 'lat': 47.484, 'lon': 36.254},
]

WMO_DESCRIPTIONS = {
    0: 'Ясно',
    1: 'Преимущественно ясно',
    2: 'Переменная облачность',
    3: 'Пасмурно',
    45: 'Туман',
    48: 'Изморозь',
    51: 'Морось',
    53: 'Морось',
    55: 'Морось',
    61: 'Дождь',
    63: 'Дождь',
    65: 'Ливень',
    71: 'Снег',
    73: 'Снег',
    75: 'Снегопад',
    77: 'Снег',
    80: 'Ливень',
    81: 'Ливень',
    82: 'Ливень',
    85: 'Снег',
    86: 'Снегопад',
    95: 'Гроза',
    96: 'Гроза с градом',
    99: 'Гроза с градом',
}


def get_weather_regions():
    raw = getattr(settings, 'DASHBOARD_WEATHER_REGIONS', None)
    if not raw:
        return list(DEFAULT_WEATHER_REGIONS)
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning('Некорректный DASHBOARD_WEATHER_REGIONS, используем значения по умолчанию')
            return list(DEFAULT_WEATHER_REGIONS)
    return list(raw)


def _region_by_id(region_id):
    regions = get_weather_regions()
    if not region_id:
        return regions[0] if regions else None
    for region in regions:
        if region.get('id') == region_id:
            return region
    return regions[0] if regions else None


def _wmo_label(code):
    try:
        return WMO_DESCRIPTIONS.get(int(code), '—')
    except (TypeError, ValueError):
        return '—'


def _wind_direction_label(degrees):
    if degrees is None:
        return '—'
    try:
        deg = float(degrees) % 360
    except (TypeError, ValueError):
        return '—'
    directions = ['С', 'СВ', 'В', 'ЮВ', 'Ю', 'ЮЗ', 'З', 'СЗ']
    index = int((deg + 22.5) // 45) % 8
    return directions[index]


def fetch_weather_for_region(region):
    params = urllib.parse.urlencode({
        'latitude': region['lat'],
        'longitude': region['lon'],
        'current': 'temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m,wind_direction_10m',
        'wind_speed_unit': 'ms',
        'timezone': 'Europe/Moscow',
    })
    url = f'https://api.open-meteo.com/v1/forecast?{params}'
    with urllib.request.urlopen(url, timeout=10) as response:
        payload = json.loads(response.read().decode('utf-8'))
    current = payload.get('current') or {}
    return {
        'region_id': region['id'],
        'region_name': region['name'],
        'temperature': current.get('temperature_2m'),
        'humidity': current.get('relative_humidity_2m'),
        'wind_speed': current.get('wind_speed_10m'),
        'wind_direction': current.get('wind_direction_10m'),
        'wind_direction_label': _wind_direction_label(current.get('wind_direction_10m')),
        'weather_code': current.get('weather_code'),
        'description': _wmo_label(current.get('weather_code')),
        'observed_at': current.get('time'),
        'fetched_at': timezone.localtime(timezone.now()).isoformat(),
    }


def get_dashboard_weather(region_id=None, *, force_refresh=False):
    region = _region_by_id(region_id)
    if not region:
        return None

    cache_key = f'dashboard_weather:{region["id"]}'
    if not force_refresh:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

    try:
        weather = fetch_weather_for_region(region)
        cache.set(cache_key, weather, WEATHER_CACHE_SECONDS)
        return weather
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError) as exc:
        logger.warning('Погода для %s: %s', region.get('id'), exc)
        return {
            'region_id': region['id'],
            'region_name': region['name'],
            'error': 'unavailable',
            'description': 'Нет данных',
            'fetched_at': timezone.localtime(timezone.now()).isoformat(),
        }
