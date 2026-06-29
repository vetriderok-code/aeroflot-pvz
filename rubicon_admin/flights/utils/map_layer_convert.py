"""Конвертация файлов слоёв карты (LDK/KML/KMZ/GPX/GeoJSON) в GeoJSON."""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)

APQ2GPX = Path(__file__).resolve().parent / 'apq2gpx.pl'

_APQ_NAMED_COLORS = {
    'black': '#000000',
    'blue': '#0000FF',
    'cyan': '#00FFFF',
    'green': '#00AA00',
    'grey': '#808080',
    'gray': '#808080',
    'magenta': '#FF00FF',
    'orange': '#FF9900',
    'red': '#FF0000',
    'white': '#FFFFFF',
    'yellow': '#FFFF00',
}

_FEATURE_PALETTE = [
    '#E6194B', '#3CB44B', '#4363D8', '#F58231', '#911EB4',
    '#42D4F4', '#F032E6', '#BFEF45', '#469990', '#9A6324',
    '#800000', '#FFD700', '#DCBEFF', '#FABED4', '#AAFFC3',
]

SUPPORTED_EXTENSIONS = {'.ldk', '.kml', '.kmz', '.gpx', '.geojson', '.json'}


def detect_format(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext == '.json':
        return 'geojson'
    return ext.lstrip('.') or 'unknown'


def convert_layer_file(path: Path, file_format: str | None = None) -> dict:
    """Возвращает GeoJSON FeatureCollection."""
    fmt = file_format or detect_format(path.name)
    fmt = fmt.lower()
    if fmt == 'ldk':
        return _convert_ldk(path)
    if fmt == 'kml':
        return _convert_kml(path.read_bytes())
    if fmt == 'kmz':
        return _convert_kmz(path)
    if fmt == 'gpx':
        return _convert_gpx(path.read_bytes())
    if fmt in ('geojson', 'json'):
        return _normalize_geojson(json.loads(path.read_text(encoding='utf-8')))
    raise ValueError(f'Неподдерживаемый формат: {fmt}')


def _normalize_geojson(data: dict) -> dict:
    if data.get('type') == 'FeatureCollection':
        features = data.get('features') or []
    elif data.get('type') == 'Feature':
        features = [data]
    elif data.get('type') in ('Point', 'LineString', 'Polygon', 'MultiLineString', 'MultiPolygon'):
        features = [{'type': 'Feature', 'geometry': data, 'properties': {}}]
    else:
        raise ValueError('Неизвестная структура GeoJSON')
    cleaned = []
    for feature in features:
        geom = feature.get('geometry')
        if not geom or not geom.get('coordinates'):
            continue
        cleaned.append({
            'type': 'Feature',
            'geometry': geom,
            'properties': feature.get('properties') or {},
        })
    if not cleaned:
        raise ValueError('В GeoJSON нет объектов с координатами')
    return {'type': 'FeatureCollection', 'features': cleaned}


def _convert_kmz(path: Path) -> dict:
    with zipfile.ZipFile(path, 'r') as zf:
        kml_names = [n for n in zf.namelist() if n.lower().endswith('.kml')]
        if not kml_names:
            raise ValueError('В KMZ не найден KML')
        return _convert_kml(zf.read(kml_names[0]))


def _kml_ns(root: ET.Element) -> str:
    m = re.match(r'\{(.*)\}', root.tag)
    return m.group(1) if m else ''


def _kml_find(parent: ET.Element, ns: str, tag: str):
    if ns:
        return parent.findall(f'.//{{{ns}}}{tag}')
    return parent.findall(f'.//{tag}')


def _kml_coords_text(text: str) -> list:
    coords = []
    for chunk in re.split(r'\s+', (text or '').strip()):
        if not chunk:
            continue
        parts = chunk.split(',')
        if len(parts) >= 2:
            lon, lat = float(parts[0]), float(parts[1])
            coords.append([lon, lat])
    return coords


def _convert_kml(data: bytes) -> dict:
    root = ET.fromstring(data)
    ns = _kml_ns(root)
    features = []

    for placemark in _kml_find(root, ns, 'Placemark'):
        name_el = placemark.find(f'{{{ns}}}name') if ns else placemark.find('name')
        name = (name_el.text or '').strip() if name_el is not None else ''
        props = {'name': name}

        point = placemark.find(f'{{{ns}}}Point') if ns else placemark.find('Point')
        if point is not None:
            coord_el = point.find(f'{{{ns}}}coordinates') if ns else point.find('coordinates')
            pts = _kml_coords_text(coord_el.text if coord_el is not None else '')
            if pts:
                features.append({
                    'type': 'Feature',
                    'geometry': {'type': 'Point', 'coordinates': pts[0]},
                    'properties': props,
                })
            continue

        line = placemark.find(f'{{{ns}}}LineString') if ns else placemark.find('LineString')
        if line is not None:
            coord_el = line.find(f'{{{ns}}}coordinates') if ns else line.find('coordinates')
            pts = _kml_coords_text(coord_el.text if coord_el is not None else '')
            if len(pts) >= 2:
                features.append({
                    'type': 'Feature',
                    'geometry': {'type': 'LineString', 'coordinates': pts},
                    'properties': props,
                })
            continue

        polygon = placemark.find(f'{{{ns}}}Polygon') if ns else placemark.find('Polygon')
        if polygon is not None:
            ring = polygon.find(f'.//{{{ns}}}LinearRing') if ns else polygon.find('.//LinearRing')
            if ring is not None:
                coord_el = ring.find(f'{{{ns}}}coordinates') if ns else ring.find('coordinates')
                pts = _kml_coords_text(coord_el.text if coord_el is not None else '')
                if len(pts) >= 3:
                    if pts[0] != pts[-1]:
                        pts.append(pts[0])
                    features.append({
                        'type': 'Feature',
                        'geometry': {'type': 'Polygon', 'coordinates': [pts]},
                        'properties': props,
                    })

    if not features:
        raise ValueError('В KML не найдены объекты')
    return {'type': 'FeatureCollection', 'features': features}


def _convert_gpx(data: bytes) -> dict:
    root = ET.fromstring(data)
    ns = _gpx_ns(root)
    features = []

    for wpt in _gpx_find(root, ns, 'wpt'):
        lat, lon = float(wpt.attrib['lat']), float(wpt.attrib['lon'])
        name = _gpx_text(wpt, ns, 'name')
        features.append({
            'type': 'Feature',
            'geometry': {'type': 'Point', 'coordinates': [lon, lat]},
            'properties': {'name': name},
        })

    for trk in _gpx_find(root, ns, 'trk'):
        name = _gpx_text(trk, ns, 'name')
        for seg in _gpx_find(trk, ns, 'trkseg'):
            pts = []
            for trkpt in _gpx_find(seg, ns, 'trkpt'):
                pts.append([float(trkpt.attrib['lon']), float(trkpt.attrib['lat'])])
            if len(pts) >= 2:
                features.append({
                    'type': 'Feature',
                    'geometry': {'type': 'LineString', 'coordinates': pts},
                    'properties': {'name': name},
                })

    for rte in _gpx_find(root, ns, 'rte'):
        name = _gpx_text(rte, ns, 'name')
        pts = []
        for rtept in _gpx_find(rte, ns, 'rtept'):
            pts.append([float(rtept.attrib['lon']), float(rtept.attrib['lat'])])
        if len(pts) >= 2:
            features.append({
                'type': 'Feature',
                'geometry': {'type': 'LineString', 'coordinates': pts},
                'properties': {'name': name},
            })

    if not features:
        raise ValueError('В GPX не найдены точки или треки')
    return {'type': 'FeatureCollection', 'features': features}


def _gpx_ns(root: ET.Element) -> str:
    m = re.match(r'\{(.*)\}', root.tag)
    return m.group(1) if m else ''


def _gpx_find(parent: ET.Element, ns: str, tag: str):
    if ns:
        return parent.findall(f'.//{{{ns}}}{tag}')
    return parent.findall(f'.//{tag}')


def _gpx_text(parent: ET.Element, ns: str, tag: str) -> str:
    el = parent.find(f'{{{ns}}}{tag}') if ns else parent.find(tag)
    return (el.text or '').strip() if el is not None else ''


_LDK_SUB_EXTENSIONS = {'.trk', '.are', '.wpt', '.rte', '.set'}


def _run_apq2gpx(args: list[str], timeout: int = 120) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            ['perl', str(APQ2GPX), *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise ValueError(
            'Для LDK нужен Perl на сервере (apt install perl)',
        ) from exc


def _convert_ldk(path: Path) -> dict:
    if not APQ2GPX.exists():
        raise ValueError('Конвертер LDK не найден на сервере')

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        extract_prefix = str(tmp_path / 'ext_')
        extract_proc = _run_apq2gpx(['-q', '-b', '-f', '-o', extract_prefix, str(path)])

        if extract_proc.returncode != 0:
            err = (extract_proc.stderr or extract_proc.stdout or '').strip()
            raise ValueError(f'Ошибка извлечения LDK: {err[:500]}')

        subfiles = sorted(
            f for f in tmp_path.iterdir()
            if f.is_file() and f.suffix.lower() in _LDK_SUB_EXTENSIONS
        )
        if not subfiles:
            raise ValueError('LDK не содержит распознанных меток или треков')

        features = []
        convert_errors = 0
        for index, subfile in enumerate(subfiles):
            conv_dir = tmp_path / f'conv_{index}'
            conv_dir.mkdir()
            # apq2gpx строит имя JSON из пути входного файла — укорачиваем.
            short_subfile = conv_dir / f'sub{index}{subfile.suffix.lower()}'
            shutil.copy2(subfile, short_subfile)
            conv_prefix = str(conv_dir / 'out_')
            conv_proc = _run_apq2gpx(['-q', '-j', '-f', '-o', conv_prefix, str(short_subfile)])
            if conv_proc.returncode != 0:
                convert_errors += 1
                logger.warning(
                    'LDK subfile convert failed: %s (%s)',
                    subfile.name,
                    (conv_proc.stderr or conv_proc.stdout or '')[:200],
                )
                continue

            for json_file in conv_dir.glob('*.json'):
                data = json.loads(json_file.read_text(encoding='utf-8'))
                features.extend(_apq_json_to_features(data, source_index=index))

        if not features:
            if convert_errors == len(subfiles):
                raise ValueError('LDK: не удалось конвертировать вложенные файлы')
            raise ValueError('LDK: не удалось извлечь координаты')

    return {'type': 'FeatureCollection', 'features': features}


def normalize_apq_color(
    value: str | None,
    *,
    fallback_index: int | None = None,
) -> str | None:
    """AlpineQuest: #AARRGGBB, #RRGGBB или имя цвета."""
    if not value:
        if fallback_index is not None:
            return _FEATURE_PALETTE[fallback_index % len(_FEATURE_PALETTE)]
        return None

    raw = str(value).strip()
    lowered = raw.lower()
    if lowered in _APQ_NAMED_COLORS:
        return _APQ_NAMED_COLORS[lowered]

    if raw.startswith('#') and len(raw) == 9:
        return f'#{raw[3:].upper()}'
    if raw.startswith('#') and len(raw) == 7:
        return raw.upper()
    return None


def _style_props_from_meta(meta: dict | None, *, fallback_index: int | None = None) -> dict:
    meta = meta or {}
    name = meta.get('name', '')
    desc = meta.get('desc') or meta.get('description') or ''
    color = normalize_apq_color(meta.get('color'), fallback_index=fallback_index)

    props: dict = {}
    if name:
        props['name'] = name
    if desc:
        props['description'] = desc
    if color:
        props['color'] = color

    stroke_width = meta.get('style:line:w')
    if stroke_width is not None:
        try:
            props['stroke_width'] = max(1, min(12, int(float(stroke_width))))
        except (TypeError, ValueError):
            pass
    return props


def _apq_json_to_features(data: dict, *, source_index: int = 0) -> list[dict]:
    features = []
    meta = data.get('meta') or {}
    meta_name = meta.get('name', '')
    base_props = _style_props_from_meta(meta, fallback_index=source_index)

    for wp in data.get('waypoints') or []:
        loc = wp.get('location') or {}
        lat, lon = loc.get('lat'), loc.get('lon')
        if lat is None or lon is None:
            continue
        wp_meta = wp.get('meta') or {}
        name = wp_meta.get('name') or meta_name
        props = {**base_props, **_style_props_from_meta(wp_meta, fallback_index=source_index)}
        props['name'] = name
        features.append({
            'type': 'Feature',
            'geometry': {'type': 'Point', 'coordinates': [float(lon), float(lat)]},
            'properties': props,
        })

    for segment in data.get('segments') or []:
        pts = []
        for p in segment:
            if p.get('lat') is None or p.get('lon') is None:
                continue
            pts.append([float(p['lon']), float(p['lat'])])
        if len(pts) >= 2:
            props = dict(base_props)
            if meta_name:
                props['name'] = meta_name
            features.append({
                'type': 'Feature',
                'geometry': {'type': 'LineString', 'coordinates': pts},
                'properties': props,
            })

    if data.get('type') == 'wpt' and data.get('location'):
        loc = data['location']
        props = _style_props_from_meta(meta)
        features.append({
            'type': 'Feature',
            'geometry': {
                'type': 'Point',
                'coordinates': [float(loc['lon']), float(loc['lat'])],
            },
            'properties': props,
        })

    locations = data.get('locations') or []
    if locations:
        pts = []
        for loc in locations:
            lat, lon = loc.get('lat'), loc.get('lon')
            if lat is None or lon is None:
                continue
            pts.append([float(lon), float(lat)])
        area_name = meta_name or meta.get('name', '')
        props = dict(base_props)
        if area_name:
            props['name'] = area_name
        if len(pts) >= 3:
            if pts[0] != pts[-1]:
                pts.append(pts[0])
            features.append({
                'type': 'Feature',
                'geometry': {'type': 'Polygon', 'coordinates': [pts]},
                'properties': props,
            })
        elif len(pts) == 2:
            features.append({
                'type': 'Feature',
                'geometry': {'type': 'LineString', 'coordinates': pts},
                'properties': props,
            })

    return features
