from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from flights.models import MapLayer


class MapLayersAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        layers = MapLayer.objects.filter(is_active=True).order_by('sort_order', 'name')
        payload = []
        for layer in layers:
            if not layer.geojson:
                continue
            payload.append({
                'id': str(layer.id),
                'name': layer.name,
                'description': layer.description,
                'file_format': layer.file_format,
                'color': layer.color,
                'stroke_width': layer.stroke_width,
                'opacity': layer.opacity,
                'feature_count': layer.feature_count,
                'geojson': layer.geojson,
            })
        return Response(payload)
