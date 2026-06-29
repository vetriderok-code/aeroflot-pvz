import logging

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from flights.models import TelegramFlightReport
from flights.utils.telegram_report_video import build_report_video_response

logger = logging.getLogger(__name__)


@login_required(login_url='login')
@require_GET
def telegram_report_video_stream(request, report_id):
    report = get_object_or_404(TelegramFlightReport, pk=report_id)
    return build_report_video_response(report, request)
