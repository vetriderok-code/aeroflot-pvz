import logging

from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from flights.utils.dashboard_alerts import record_dashboard_alert
from flights.utils.portal_features import dashboard_enabled

logger = logging.getLogger(__name__)


class DashboardAlertAPIView(APIView):
    """Приём оповещений из Telegram-бота (топик форума)."""

    authentication_classes = []
    permission_classes = []

    def post(self, request):
        if not dashboard_enabled():
            return Response(status=status.HTTP_404_NOT_FOUND)
        secret = request.headers.get('X-Live-Flight-Secret', '')
        expected = getattr(settings, 'LIVE_FLIGHT_BOT_SECRET', '') or ''
        if not expected or secret != expected:
            return Response({'error': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

        text = request.data.get('text') or ''
        try:
            chat_id = int(request.data['chat_id'])
            telegram_message_id = int(request.data['message_id'])
        except (KeyError, TypeError, ValueError):
            return Response({'error': 'invalid_payload'}, status=status.HTTP_400_BAD_REQUEST)

        message_thread_id = request.data.get('message_thread_id')
        if message_thread_id is not None:
            try:
                message_thread_id = int(message_thread_id)
            except (TypeError, ValueError):
                return Response({'error': 'invalid_thread'}, status=status.HTTP_400_BAD_REQUEST)

        posted_at = request.data.get('posted_at')
        result = record_dashboard_alert(
            chat_id=chat_id,
            message_thread_id=message_thread_id,
            telegram_message_id=telegram_message_id,
            text=text,
            posted_at=posted_at,
        )
        if not result.get('ok'):
            code = result.get('error', 'unknown')
            if code == 'empty_text':
                return Response(result, status=status.HTTP_400_BAD_REQUEST)
            return Response(result, status=status.HTTP_400_BAD_REQUEST)

        return Response(result)
