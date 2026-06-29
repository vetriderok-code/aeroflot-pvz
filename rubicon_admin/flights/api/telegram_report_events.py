import logging

from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from flights.utils.telegram_report_stats import record_telegram_flight_report

logger = logging.getLogger(__name__)


class TelegramReportEventAPIView(APIView):
    """Приём вылетов из Telegram-отчётов (топик 2406)."""

    authentication_classes = []
    permission_classes = []

    def post(self, request):
        secret = request.headers.get('X-Live-Flight-Secret', '')
        expected = getattr(settings, 'LIVE_FLIGHT_BOT_SECRET', '') or ''
        if not expected or secret != expected:
            return Response({'error': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

        try:
            chat_id = int(request.data['chat_id'])
            telegram_message_id = int(request.data['message_id'])
            flight_number = int(request.data.get('flight_number') or 0)
        except (KeyError, TypeError, ValueError):
            return Response({'error': 'invalid_payload'}, status=status.HTTP_400_BAD_REQUEST)

        message_thread_id = request.data.get('message_thread_id')
        if message_thread_id is not None:
            try:
                message_thread_id = int(message_thread_id)
            except (TypeError, ValueError):
                return Response({'error': 'invalid_thread'}, status=status.HTTP_400_BAD_REQUEST)

        result = record_telegram_flight_report(
            chat_id=chat_id,
            message_thread_id=message_thread_id,
            telegram_message_id=telegram_message_id,
            flight_number=flight_number,
            work_date=request.data.get('work_date', ''),
            result=request.data.get('result', ''),
            sent_at=request.data.get('sent_at'),
            parse_ok=bool(request.data.get('parse_ok', True)),
            pilot_callsign=request.data.get('pilot_callsign', ''),
            raw_text=request.data.get('raw_text', ''),
        )
        if not result.get('ok'):
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
        return Response(result)
