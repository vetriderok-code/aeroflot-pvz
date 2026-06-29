from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from flights.utils.live_flight import get_dashboard_live_flights
from flights.utils.portal_features import dashboard_enabled


class LiveDashboardAPIView(APIView):
    """Оперативные вылеты для дашборда (в работе + за 24 ч, МСК)."""

    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not dashboard_enabled():
            return Response(status=status.HTTP_404_NOT_FOUND)
        region_id = request.query_params.get('region') or request.query_params.get('weather_region')
        return Response(get_dashboard_live_flights(weather_region_id=region_id))
