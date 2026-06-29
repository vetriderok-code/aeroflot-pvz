from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from flights.utils.nearest_settlement import resolve_settlements_batch


class SettlementGeocodeBatchView(APIView):
    """Пакетное определение ближайшего НП для экспорта карты."""

    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        points = request.data.get('points') or []
        if not isinstance(points, list):
            return Response({'error': 'points must be a list'}, status=400)
        if len(points) > 2000:
            return Response({'error': 'max 2000 points per request'}, status=400)

        normalized = []
        for item in points:
            try:
                normalized.append({
                    'lat': float(item['lat']),
                    'lon': float(item['lon']),
                })
            except (KeyError, TypeError, ValueError):
                normalized.append({'lat': None, 'lon': None})

        names = resolve_settlements_batch(normalized)
        return Response({'settlements': names})
