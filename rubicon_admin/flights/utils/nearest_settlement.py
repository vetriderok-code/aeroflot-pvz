"""Ближайший населённый пункт по координатам WGS84 (обратное геокодирование)."""
from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

CACHE_SECONDS = 60 * 60 * 24 * 30  # 30 дней — координаты не «ездят»
NOMINATIM_MIN_INTERVAL = 1.05
NOMINATIM_RATE_LIMIT_COOLDOWN = 60 * 10  # после 429 не дергаем OSM 10 мин
_last_nominatim_at = 0.0
_nominatim_blocked_until = 0.0

# Приоритет типов НП в ответе Nominatim (addressdetails)
_PLACE_KEYS = (
    'city',
    'town',
    'village',
    'hamlet',
    'suburb',
    'municipality',
    'county',
    'state',
)


def _cache_key(lat: float, lon: float) -> str:
    return f'settlement:{round(float(lat), 4)}:{round(float(lon), 4)}'


def _pick_place_from_nominatim_address(address: dict) -> str:
    if not address:
        return ''
    for key in _PLACE_KEYS:
        value = address.get(key)
        if value:
            return str(value).strip()
    return ''


def _fetch_nominatim(lat: float, lon: float) -> str:
    global _last_nominatim_at, _nominatim_blocked_until
    if time.monotonic() < _nominatim_blocked_until:
        return ''

    elapsed = time.monotonic() - _last_nominatim_at
    if elapsed < NOMINATIM_MIN_INTERVAL:
        time.sleep(NOMINATIM_MIN_INTERVAL - elapsed)

    params = urllib.parse.urlencode({
        'lat': lat,
        'lon': lon,
        'format': 'json',
        'accept-language': 'ru',
        'zoom': 12,
        'addressdetails': 1,
    })
    url = f'https://nominatim.openstreetmap.org/reverse?{params}'
    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'RubiconPortal/1.0 (flight map export)'},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            payload = json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        _last_nominatim_at = time.monotonic()
        if exc.code == 429:
            _nominatim_blocked_until = time.monotonic() + NOMINATIM_RATE_LIMIT_COOLDOWN
            logger.warning('Nominatim rate limit (429), пауза %s сек', NOMINATIM_RATE_LIMIT_COOLDOWN)
        raise
    _last_nominatim_at = time.monotonic()

    address = payload.get('address') or {}
    place = _pick_place_from_nominatim_address(address)
    if place:
        return place

    # fallback: первая часть display_name
    display = (payload.get('display_name') or '').strip()
    if display:
        return display.split(',')[0].strip()
    return ''


def _fetch_photon(lat: float, lon: float) -> str:
    """Photon (OSM) — без жёсткого rate limit, подходит для пакетных отчётов."""
    params = urllib.parse.urlencode({'lat': lat, 'lon': lon})
    url = f'https://photon.komoot.io/reverse?{params}'
    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'RubiconPortal/1.0 (flight map export)'},
    )
    with urllib.request.urlopen(req, timeout=10) as response:
        payload = json.loads(response.read().decode('utf-8'))

    features = payload.get('features') or []
    if not features:
        return ''

    props = features[0].get('properties') or {}
    for key in ('city', 'town', 'village', 'hamlet', 'name'):
        value = props.get(key)
        if value:
            return str(value).strip()
    return ''


def _parse_yandex_payload(payload: dict) -> str:
    members = (
        payload.get('response', {})
        .get('GeoObjectCollection', {})
        .get('featureMember', [])
    )
    if not members:
        return ''

    geo = members[0].get('GeoObject', {})
    meta = geo.get('metaDataProperty', {}).get('GeocoderMetaData', {})
    address = meta.get('Address', {})
    components = address.get('Components') or []
    for preferred in ('locality', 'village', 'district', 'area'):
        for component in components:
            if component.get('kind') == preferred and component.get('name'):
                return str(component['name']).strip()

    name = geo.get('name') or address.get('formatted') or ''
    return str(name).strip()


_INVALID_YANDEX_KEYS = frozenset({'', 'yandex_secret_key', 'None'})


def _yandex_geocoder_api_keys() -> list[str]:
    """HTTP Geocoder: доп. ключ(и) первыми, основной YANDEX_API_KEY — fallback."""
    keys: list[str] = []
    for raw in (
        getattr(settings, 'YANDEX_API_KEY_EXTRA', ''),
        getattr(settings, 'YANDEX_API_KEY', ''),
    ):
        for part in str(raw or '').split(','):
            key = part.strip()
            if key not in _INVALID_YANDEX_KEYS and key not in keys:
                keys.append(key)
    return keys


def _fetch_yandex_with_key(lat: float, lon: float, api_key: str) -> str:
    params = urllib.parse.urlencode({
        'apikey': api_key,
        'format': 'json',
        'geocode': f'{lon},{lat}',
        'lang': 'ru_RU',
        'results': 1,
        'kind': 'locality',
    })
    for base_url in (
        'https://geocode-maps.yandex.ru/v1/',
        'https://geocode-maps.yandex.ru/1.x/',
    ):
        url = f'{base_url}?{params}'
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=10) as response:
                payload = json.loads(response.read().decode('utf-8'))
            place = _parse_yandex_payload(payload)
            if place:
                return place
        except urllib.error.HTTPError as exc:
            logger.debug(
                'Yandex geocode %s,%s key …%s via %s: HTTP %s',
                lat, lon, api_key[-6:], base_url, exc.code,
            )
            if exc.code in (403, 429):
                break
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError) as exc:
            logger.debug('Yandex geocode %s,%s via %s: %s', lat, lon, base_url, exc)
    return ''


def _fetch_yandex(lat: float, lon: float) -> str:
    for api_key in _yandex_geocoder_api_keys():
        place = _fetch_yandex_with_key(lat, lon, api_key)
        if place:
            return place
    return ''


def get_nearest_settlement_name(lat: float, lon: float, *, allow_nominatim: bool = True) -> str:
    """
    Имя ближайшего населённого пункта по WGS84.
    Сначала Yandex (лучше для РФ/Украины), затем Nominatim (OSM).
    """
    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except (TypeError, ValueError):
        return ''

    if lat_f == 90.0 and lon_f == 0.0:
        return ''

    key = _cache_key(lat_f, lon_f)
    cached = cache.get(key)
    if cached and cached != '—':
        return cached

    place = ''
    try:
        place = _fetch_yandex(lat_f, lon_f)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError) as exc:
        logger.debug('Yandex geocode %s,%s: %s', lat_f, lon_f, exc)

    if not place:
        try:
            place = _fetch_photon(lat_f, lon_f)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError) as exc:
            logger.debug('Photon geocode %s,%s: %s', lat_f, lon_f, exc)

    if not place and allow_nominatim:
        try:
            place = _fetch_nominatim(lat_f, lon_f)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError) as exc:
            logger.warning('Nominatim geocode %s,%s: %s', lat_f, lon_f, exc)
            place = ''

    if not place:
        return '—'

    cache.set(key, place, CACHE_SECONDS)
    return place


def resolve_settlements_batch(
    points: list[dict],
    *,
    allow_nominatim: bool = True,
) -> list[str]:
    """points: [{'lat': .., 'lon': ..}, ...] → список названий той же длины."""
    if not points:
        return []

    key_by_index: list[str | None] = []
    coord_by_key: dict[str, tuple[float, float]] = {}

    for point in points:
        try:
            lat_f = float(point.get('lat'))
            lon_f = float(point.get('lon'))
        except (TypeError, ValueError):
            key_by_index.append(None)
            continue

        if lat_f == 90.0 and lon_f == 0.0:
            key_by_index.append(None)
            continue

        key = _cache_key(lat_f, lon_f)
        key_by_index.append(key)
        coord_by_key.setdefault(key, (lat_f, lon_f))

    cached = cache.get_many(list(coord_by_key.keys())) if coord_by_key else {}

    for key, (lat_f, lon_f) in coord_by_key.items():
        cached_value = cached.get(key)
        if cached_value and cached_value != '—':
            continue
        cached[key] = get_nearest_settlement_name(lat_f, lon_f, allow_nominatim=allow_nominatim)

    names: list[str] = []
    for key in key_by_index:
        if key is None:
            names.append('—')
        else:
            names.append(cached.get(key) or '—')
    return names
