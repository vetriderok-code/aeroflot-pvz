import logging

from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from flights.utils.live_flight import (
    LIVE_FLIGHT_ACTION_START,
    LIVE_FLIGHT_ACTION_STOP,
    record_live_flight_event,
)

logger = logging.getLogger(__name__)


class LiveFlightEventAPIView(APIView):
    """
    События Старт/Стоп от Telegram-бота.
    Авторизация: заголовок X-Live-Flight-Secret.
    """

    authentication_classes = []
    permission_classes = []

    def post(self, request):
        secret = request.headers.get('X-Live-Flight-Secret', '')
        expected = getattr(settings, 'LIVE_FLIGHT_BOT_SECRET', '') or ''
        if not expected or secret != expected:
            return Response({'error': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

        action = (request.data.get('action') or '').strip().lower()
        if action not in (LIVE_FLIGHT_ACTION_START, LIVE_FLIGHT_ACTION_STOP):
            return Response({'error': 'invalid_action'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            telegram_user_id = int(request.data['telegram_user_id'])
            chat_id = int(request.data['chat_id'])
        except (KeyError, TypeError, ValueError):
            return Response({'error': 'invalid_payload'}, status=status.HTTP_400_BAD_REQUEST)

        message_id = request.data.get('message_id')
        if message_id is not None:
            try:
                message_id = int(message_id)
            except (TypeError, ValueError):
                return Response({'error': 'invalid_message_id'}, status=status.HTTP_400_BAD_REQUEST)

        result = record_live_flight_event(
            action=action,
            telegram_user_id=telegram_user_id,
            chat_id=chat_id,
            message_id=message_id,
        )
        if not result.get('ok'):
            code = result.get('error', 'unknown')
            if code == 'pilot_not_linked':
                return Response(result, status=status.HTTP_404_NOT_FOUND)
            if code == 'no_active_flight':
                return Response(result, status=status.HTTP_409_CONFLICT)
            return Response(result, status=status.HTTP_400_BAD_REQUEST)

        return Response(result)
