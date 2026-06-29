"""Видео отчётов Telegram: локальное хранение и отдача с диска (скачивание — через tg_bot)."""
from __future__ import annotations

import logging
import mimetypes
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404, StreamingHttpResponse
from django.utils import timezone

from flights.models import TelegramFlightReport

logger = logging.getLogger(__name__)

CHUNK_SIZE = 256 * 1024
DEFAULT_RETENTION_DAYS = 8
TELEGRAM_BOT_MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024


def video_retention_days() -> int:
    try:
        return int(getattr(settings, 'TELEGRAM_REPORT_VIDEO_RETENTION_DAYS', DEFAULT_RETENTION_DAYS))
    except (TypeError, ValueError):
        return DEFAULT_RETENTION_DAYS


def video_storage_root() -> Path:
    custom = getattr(settings, 'TELEGRAM_REPORT_VIDEO_DIR', '') or ''
    if custom:
        return Path(custom)
    return Path(settings.MEDIA_ROOT) / 'telegram_reports'


def bot_api_supports_large_files() -> bool:
    return bool(getattr(settings, 'TELEGRAM_BOT_API_URL', '') or '')


def report_has_video(report: TelegramFlightReport) -> bool:
    return bool(report.telegram_file_id)


def report_video_cached(report: TelegramFlightReport) -> bool:
    return resolve_local_video_path(report) is not None


def clear_stale_local_video_path(report: TelegramFlightReport) -> bool:
    """Сбросить путь в БД, если файл на диске пропал (пересоздание volume и т.п.)."""
    if not report.local_video_path:
        return False
    if resolve_local_video_path(report):
        return False
    report.local_video_path = ''
    report.save(update_fields=['local_video_path', 'modified'])
    logger.warning('Stale TG video path cleared: report=%s', report.id)
    return True


def report_video_too_large_for_bot(report: TelegramFlightReport) -> bool:
    if bot_api_supports_large_files():
        return False
    size = report.video_size or 0
    return size > TELEGRAM_BOT_MAX_DOWNLOAD_BYTES


def resolve_local_video_path(report: TelegramFlightReport) -> Path | None:
    if not report.local_video_path:
        return None
    root = video_storage_root().resolve()
    path = (root / report.local_video_path).resolve()
    if not str(path).startswith(str(root)):
        return None
    if path.is_file():
        return path
    return None


def _guess_extension(mime_type: str | None) -> str:
    mime = (mime_type or 'video/mp4').split(';', 1)[0].strip()
    ext = mimetypes.guess_extension(mime) or '.mp4'
    if ext == '.jpe':
        ext = '.mp4'
    return ext


def _relative_storage_name(report_id, mime_type: str | None) -> str:
    return f'{report_id}{_guess_extension(mime_type)}'


def schedule_report_video_download(report_id) -> None:
    """Локальное скачивание выполняет tg_bot (у rubicon-api нет доступа к Telegram)."""
    logger.debug('TG video download delegated to tg_bot for report=%s', report_id)


def purge_expired_report_videos(*, older_than_days: int | None = None) -> dict:
    days = older_than_days if older_than_days is not None else video_retention_days()
    if days <= 0:
        return {
            'older_than_days': days,
            'deleted_files': 0,
            'updated_rows': 0,
        }
    cutoff = timezone.now() - timedelta(days=days)
    qs = TelegramFlightReport.objects.filter(
        video_downloaded_at__isnull=False,
        video_downloaded_at__lt=cutoff,
    ).exclude(local_video_path='')

    deleted_files = 0
    updated_rows = 0
    for report in qs.iterator():
        path = resolve_local_video_path(report)
        if path:
            try:
                path.unlink(missing_ok=True)
                deleted_files += 1
            except OSError:
                logger.exception('Cannot delete %s', path)
        report.local_video_path = ''
        report.save(update_fields=['local_video_path', 'modified'])
        updated_rows += 1

    return {
        'older_than_days': days,
        'deleted_files': deleted_files,
        'updated_rows': updated_rows,
    }


def _file_range_response(path: Path, request, content_type: str) -> FileResponse | StreamingHttpResponse:
    file_size = path.stat().st_size
    range_header = request.META.get('HTTP_RANGE', '').strip()
    if range_header.startswith('bytes='):
        range_spec = range_header[6:].split(',')[0].strip()
        if '-' in range_spec:
            start_text, end_text = range_spec.split('-', 1)
            try:
                start = int(start_text) if start_text else 0
                end = int(end_text) if end_text else file_size - 1
            except ValueError:
                start, end = 0, file_size - 1
            start = max(0, start)
            end = min(file_size - 1, end)
            if start <= end:
                length = end - start + 1
                handle = open(path, 'rb')
                handle.seek(start)

                def _gen():
                    remaining = length
                    try:
                        while remaining > 0:
                            data = handle.read(min(CHUNK_SIZE, remaining))
                            if not data:
                                break
                            remaining -= len(data)
                            yield data
                    finally:
                        handle.close()

                response = StreamingHttpResponse(_gen(), status=206, content_type=content_type)
                response['Content-Length'] = str(length)
                response['Content-Range'] = f'bytes {start}-{end}/{file_size}'
                response['Accept-Ranges'] = 'bytes'
                return response

    response = FileResponse(open(path, 'rb'), content_type=content_type)
    response['Content-Length'] = str(file_size)
    response['Accept-Ranges'] = 'bytes'
    return response


def build_report_video_response(report: TelegramFlightReport, request):
    if not report_has_video(report):
        raise Http404('Видео для отчёта недоступно')

    clear_stale_local_video_path(report)
    local_path = resolve_local_video_path(report)
    content_type = report.video_mime or 'video/mp4'

    if local_path:
        return _file_range_response(local_path, request, content_type)

    if report_video_too_large_for_bot(report):
        raise Http404(
            'Видео больше 20 МБ — нужен Local Bot API (TELEGRAM_BOT_API_URL). '
            'Обратитесь к администратору.'
        )

    raise Http404(
        'Видео ещё не загружено на сервер. Подождите несколько минут и обновите страницу.'
    )
