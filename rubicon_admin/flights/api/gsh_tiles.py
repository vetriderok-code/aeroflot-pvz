from pathlib import Path
from typing import Iterable, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseNotFound
from django.views.decorators.http import require_GET


def _gsh_server_name(x: int, y: int) -> str:
    names = [
        item.strip()
        for item in getattr(settings, 'MAP_GSH_SERVER_NAMES', 'a,b,c').split(',')
        if item.strip()
    ]
    if not names:
        return 'a'
    return names[(x + y) % len(names)]


def _apply_tile_template(template: str, z: int, x: int, y: int) -> str:
    tms_y = (2 ** z) - y - 1
    replacements = {
        '{s}': _gsh_server_name(x, y),
        '{z}': str(z),
        '{x}': str(x),
        '{y}': str(y),
        '{-y}': str(tms_y),
        '{z+1}': str(z + 1),
        '{x/1024}': str(x // 1024),
        '{y/1024}': str(y // 1024),
    }
    url = template
    for placeholder, value in replacements.items():
        url = url.replace(placeholder, value)
    return url


def _configured_upstream_templates() -> list[str]:
    raw = getattr(settings, 'MAP_GSH_UPSTREAM_URLS', '') or ''
    if raw.strip():
        return [item.strip() for item in raw.split('|') if item.strip()]

    primary = getattr(settings, 'MAP_GSH_TILE_URL', '') or ''
    if primary and not primary.startswith('/'):
        return [primary]
    return []


def _auto_scale_upstream_urls(z: int, x: int, y: int) -> list[str]:
    """Combo_Best_GGC: от мелкого масштаба к крупному, пока не найдётся тайл."""
    scales = [
        (15, 'Locals_Ggc_00250', 'ggc250'),
        (14, 'Locals_Ggc_00500', 'ggc500'),
        (13, 'Locals_Ggc_01000', 'ggc1000'),
        (12, 'Locals_Ggc_02000', 'ggc2000'),
    ]
    urls: list[str] = []
    subdomain = _gsh_server_name(x, y)
    for max_zoom, anygis_name, nakarte_name in scales:
        if z > max_zoom:
            continue
        urls.append(
            f'https://anygis.ru/api/v1/{anygis_name}/{x}/{y}/{z}'
        )
        urls.append(
            f'https://{subdomain}.tiles.nakarte.me/{nakarte_name}/{z}/{x}/{y}'
        )
    return urls


def build_gsh_tile_url(z: int, x: int, y: int) -> Optional[str]:
    templates = _configured_upstream_templates()
    if not templates:
        auto = _auto_scale_upstream_urls(z, x, y)
        if auto:
            return auto[0]
        return None
    return _apply_tile_template(templates[0], z, x, y)


def iter_gsh_tile_urls(z: int, x: int, y: int) -> Iterable[str]:
    seen: set[str] = set()
    for template in _configured_upstream_templates():
        url = _apply_tile_template(template, z, x, y)
        if url not in seen:
            seen.add(url)
            yield url
    for url in _auto_scale_upstream_urls(z, x, y):
        if url not in seen:
            seen.add(url)
            yield url


def _local_sas_tile_path(cache_dir: str, z: int, x: int, y: int) -> Optional[Path]:
    base = Path(cache_dir)
    if not base.is_dir():
        return None

    z_levels = [z, z + 1]
    extensions = ('.jpg', '.jpeg', '.png', '.webp')
    path_patterns = []

    for z_level in z_levels:
        path_patterns.extend([
            base / f'z{z_level}' / str(x // 1024) / f'x{x}' / str(y // 1024) / f'y{y}{ext}'
            for ext in extensions
        ])
        path_patterns.extend([
            base / f'z{z_level}' / f'{x}_{y}{ext}'
            for ext in extensions
        ])
        path_patterns.extend([
            base / str(z_level) / str(x) / f'{y}{ext}'
            for ext in extensions
        ])

    for path in path_patterns:
        if path.is_file():
            return path
    return None


def _guess_content_type(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in ('.jpg', '.jpeg'):
        return 'image/jpeg'
    if ext == '.png':
        return 'image/png'
    if ext == '.webp':
        return 'image/webp'
    return 'application/octet-stream'


def _fetch_remote_tile(tile_url: str) -> Optional[tuple[bytes, str]]:
    headers = {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
        ),
        'Referer': getattr(settings, 'MAP_GSH_REFERER', 'https://nakarte.me/'),
        'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8',
    }
    try:
        req = Request(tile_url, headers=headers)
        with urlopen(req, timeout=12) as resp:
            data = resp.read()
            if len(data) < 128:
                return None
            content_type = resp.headers.get('Content-Type', 'image/png')
            if 'text' in content_type or 'html' in content_type:
                return None
            return data, content_type
    except HTTPError as exc:
        if exc.code == 404:
            return None
        return None
    except (URLError, OSError, ValueError):
        return None


@login_required(login_url='login')
@require_GET
def gsh_tile_proxy(request, z: int, x: int, y: int):
    if not getattr(settings, 'MAP_GSH_ENABLED', True):
        return HttpResponseNotFound()

    zoom_min = getattr(settings, 'MAP_GSH_ZOOM_MIN', 6)
    zoom_max = getattr(settings, 'MAP_GSH_ZOOM_MAX', 15)
    if z < zoom_min or z > zoom_max:
        return HttpResponseNotFound()

    cache_dir = getattr(settings, 'MAP_GSH_CACHE_DIR', '') or ''
    if cache_dir:
        local_path = _local_sas_tile_path(cache_dir, z, x, y)
        if local_path:
            data = local_path.read_bytes()
            return HttpResponse(data, content_type=_guess_content_type(local_path))

    for tile_url in iter_gsh_tile_urls(z, x, y):
        if tile_url.startswith('/') or tile_url.startswith('file://'):
            file_path = Path(tile_url.removeprefix('file://'))
            if file_path.is_file():
                data = file_path.read_bytes()
                return HttpResponse(data, content_type=_guess_content_type(file_path))
            continue

        fetched = _fetch_remote_tile(tile_url)
        if fetched:
            data, content_type = fetched
            return HttpResponse(data, content_type=content_type)

    return HttpResponseNotFound()
