from rest_framework import serializers
from .models import Flight


class FlightSerializer(serializers.ModelSerializer):
    pilot_name = serializers.CharField(source='pilot.name', read_only=True)
    coordinates_info = serializers.SerializerMethodField()

    class Meta:
        model = Flight
        fields = [
            'id',
            'number',
            'pilot_name',
            'drone',
            'flight_date',
            'flight_time',
            'target',
            'corrective',
            'result',
            'coordinates',
            'coordinates_info',
            'comment',
            'objective'
        ]

    def get_coordinates_info(self, obj):
        return obj.get_coordinates_info()