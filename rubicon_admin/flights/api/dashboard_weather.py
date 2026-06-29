from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from flights.utils.dashboard_weather import get_dashboard_weather, get_weather_regions
from flights.utils.portal_features import dashboard_enabled


class DashboardWeatherAPIView(APIView):
    """Погода для дашборда (отдельно от live_dashboard)."""

    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not dashboard_enabled():
            return Response(status=status.HTTP_404_NOT_FOUND)
        region_id = request.query_params.get('region') or request.query_params.get('weather_region')
        force = str(request.query_params.get('refresh', '')).lower() in ('1', 'true', 'yes')
        return Response({
            'weather_regions': get_weather_regions(),
            'weather': get_dashboard_weather(region_id, force_refresh=force),
        })
