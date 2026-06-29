import logging

from django.conf import settings
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from flights.models import TelegramFlightReport
from flights.utils.telegram_report_sources import get_map_report_sources
from flights.utils.telegram_report_stats import (
    is_report_defeated,
    is_report_not_defeated,
)
from flights.utils.telegram_report_video import report_has_video, resolve_local_video_path
from django.db.models import Q

logger = logging.getLogger(__name__)


def _report_result_code(result: str) -> str:
    if is_report_defeated(result):
        return 'defeated'
    if is_report_not_defeated(result):
        return 'not defeated'
    return 'other'


def _report_dedupe_key(report: TelegramFlightReport) -> tuple:
    pilot = (report.pilot_callsign or '').strip().casefold()
    work_date = (report.work_date or '').strip()
    return pilot, int(report.flight_number or 0), work_date


def _dedupe_map_points(points: list[dict]) -> list[dict]:
    """Один вылет на карте: приоритет — с видео, затем более свежий."""
    best: dict[tuple, dict] = {}
    for point in points:
        key = (
            (point.get('pilot_name') or '').strip().casefold(),
            int(point.get('flight_number') or 0),
            (point.get('work_date') or '').strip(),
        )
        existing = best.get(key)
        if existing is None:
            best[key] = point
            continue
        if point.get('has_video') and not existing.get('has_video'):
            best[key] = point
            continue
        if point.get('sent_at', '') > existing.get('sent_at', ''):
            best[key] = point
    return list(best.values())


def get_telegram_reports_map_points(*, with_video: bool = False):
    sources = get_map_report_sources()

    qs = TelegramFlightReport.objects.filter(
        parse_ok=True,
        lat_wgs84__isnull=False,
        lon_wgs84__isnull=False,
    )
    if sources:
        source_filter = Q()
        for chat_id, topic_ids in sources:
            source_filter |= Q(
                chat_id=int(chat_id),
            ) & (
                Q(message_thread_id__in=topic_ids)
                | Q(message_thread_id__isnull=True)
            )
        qs = qs.filter(source_filter)
    if with_video:
        qs = qs.filter(telegram_file_id__gt='')

    points = []
    for report in qs.order_by('-sent_at').iterator():
        if report.lat_wgs84 == 90.0 and report.lon_wgs84 == 0.0:
            continue
        local_cached = resolve_local_video_path(report) is not None
        points.append({
            'id': str(report.id),
            'source': 'telegram',
            'flight_number': report.flight_number,
            'pilot_name': report.pilot_callsign,
            'work_date': report.work_date,
            'result': _report_result_code(report.result),
            'result_text': report.result,
            'target': report.target_type,
            'coordinates': report.coordinates_sk42,
            'lat': report.lat_wgs84,
            'lng': report.lon_wgs84,
            'sent_at': report.sent_at.isoformat(),
            'has_video': report_has_video(report),
            'video_cached': local_cached,
            'telegram_message_id': report.telegram_message_id,
        })
    return _dedupe_map_points(points)


class TelegramReportsMapAPIView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        with_video = request.query_params.get('with_video', '').lower() in ('1', 'true', 'yes')
        return Response(get_telegram_reports_map_points(with_video=with_video))
