"""Временное хранение результатов обработки Excel (Excel + KML)."""
from __future__ import annotations

import json
import os
import shutil
import time
import uuid

CACHE_ROOT = os.environ.get('TOOLS_REPORT_CACHE_DIR', '/tmp/rubicon_tools_reports')
TTL_SECONDS = 60 * 60  # 1 час


def _report_dir(token: str) -> str:
    safe = token.replace('/', '').replace('..', '')
    return os.path.join(CACHE_ROOT, safe)


def _cleanup_expired() -> None:
    if not os.path.isdir(CACHE_ROOT):
        return
    now = time.time()
    for name in os.listdir(CACHE_ROOT):
        path = os.path.join(CACHE_ROOT, name)
        try:
            if os.path.isdir(path) and now - os.path.getmtime(path) > TTL_SECONDS:
                shutil.rmtree(path, ignore_errors=True)
        except OSError:
            pass


def create_token() -> str:
    return uuid.uuid4().hex


def save_report(
    token: str,
    excel_bytes: bytes,
    excel_filename: str,
    kml_bytes: bytes,
    kml_filename: str,
    meta: dict,
) -> None:
    _cleanup_expired()
    path = _report_dir(token)
    os.makedirs(path, exist_ok=True)
    with open(os.path.join(path, 'report.xlsx'), 'wb') as f:
        f.write(excel_bytes)
    with open(os.path.join(path, 'report.kml'), 'wb') as f:
        f.write(kml_bytes)
    meta_payload = {
        **meta,
        'excel_filename': excel_filename,
        'kml_filename': kml_filename,
        'created_at': time.time(),
    }
    with open(os.path.join(path, 'meta.json'), 'w', encoding='utf-8') as f:
        json.dump(meta_payload, f, ensure_ascii=False)


def get_meta(token: str) -> dict | None:
    path = os.path.join(_report_dir(token), 'meta.json')
    if not os.path.isfile(path):
        return None
    if time.time() - os.path.getmtime(path) > TTL_SECONDS:
        shutil.rmtree(_report_dir(token), ignore_errors=True)
        return None
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def get_excel(token: str) -> tuple[bytes, str] | None:
    meta = get_meta(token)
    if not meta:
        return None
    excel_path = os.path.join(_report_dir(token), 'report.xlsx')
    if not os.path.isfile(excel_path):
        return None
    with open(excel_path, 'rb') as f:
        return f.read(), meta['excel_filename']


def get_kml(token: str) -> tuple[bytes, str] | None:
    meta = get_meta(token)
    if not meta:
        return None
    kml_path = os.path.join(_report_dir(token), 'report.kml')
    if not os.path.isfile(kml_path):
        return None
    with open(kml_path, 'rb') as f:
        return f.read(), meta['kml_filename']
