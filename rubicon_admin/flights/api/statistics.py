from django.db.models import Count, Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from datetime import datetime, timedelta
from flights.models import Flight, FlightResultTypes
from flights.utils.success_stats import (
    aggregate_daily_success_stats,
    aggregate_drone_success_stats,
    aggregate_pilot_success_stats,
    aggregate_pilot_target_success_stats,
    aggregate_success_counts,
    aggregate_target_success_stats,
    empty_success_counts,
    success_total,
)
from django.utils import timezone
from collections import defaultdict
import logging
import re

logger = logging.getLogger(__name__)

def normalize_drone_for_display(drone_name):
    """Нормализует название дрона для отображения в статистике.
    Преобразует все варианты КВН в два: КВН или КВН-Т"""
    if not drone_name:
        return drone_name
    drone_str = str(drone_name).strip()
    if not drone_str:
        return drone_name
    
    # Приводим к нижнему регистру для проверки
    drone_lower = drone_str.lower()
    
    # КВН - преобразуем все варианты в два: КВН или КВН-Т
    # Проверяем наличие "квн" в строке (без учета регистра)
    if 'квн' in drone_lower:
        # Находим позицию "квн" в строке
        kvn_pos = drone_lower.find('квн')
        if kvn_pos != -1:
            # Берем все после "квн" (3 символа: к, в, н)
            substring_after_kvn = drone_lower[kvn_pos + 3:]
            # Убираем все символы кроме букв и цифр для проверки наличия "т"
            # Это покроет все варианты: квн-т, квн-16т, квн-16-т, квн-23т, квн-23-т, квн 16 т, квнт и т.д.
            cleaned = re.sub(r'[^а-яё0-9]', '', substring_after_kvn)
            if 'т' in cleaned:
                return 'КВН-Т'
        return 'КВН'
    
    # Для остальных дронов возвращаем как есть
    return drone_name

class StatisticsView(APIView):
    def get(self, request, format=None):
        logger.debug("=== НАЧАЛО StatisticsView ===")
        date_from_str = request.query_params.get('date_from')
        date_to_str = request.query_params.get('date_to')
        pilot_callname = request.query_params.get('pilot_callname')
        drone_type = request.query_params.get('drone_type')
        logger.debug(
            f"Параметры запроса: date_from={date_from_str}, date_to={date_to_str}, pilot_callname={pilot_callname}, drone_type={drone_type}")

        flights = Flight.objects.select_related('pilot')

        if date_from_str:
            try:
                date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date()
                flights = flights.filter(flight_date__gte=date_from)
                logger.debug(f"Фильтр по дате с: {date_from}")
            except ValueError:
                logger.warning(f"Неверный формат date_from: {date_from_str}")
                pass # Или return Response(..., status=status.HTTP_400_BAD_REQUEST)

        if date_to_str:
            try:
                date_to = datetime.strptime(date_to_str, '%Y-%m-%d').date()
                flights = flights.filter(flight_date__lte=date_to)
                logger.debug(f"Фильтр по дате по: {date_to}")
            except ValueError:
                logger.warning(f"Неверный формат date_to: {date_to_str}")
                pass # Или return Response(..., status=status.HTTP_400_BAD_REQUEST)

        # --- ИЗМЕНЕНО: Фильтруем по callname ---
        if pilot_callname:
            # Используем icontains для нечеткого поиска (без учета регистра и частичное совпадение)
            # или __iexact для точного совпадения без учета регистра
            # flights = flights.filter(pilot__callname__iexact=pilot_callname)
            flights = flights.filter(pilot__callname__icontains=pilot_callname)
            logger.debug(f"Фильтр по позывному пилота: {pilot_callname}")

        if drone_type:
            # Нормализуем значение фильтра
            normalized_filter_drone = normalize_drone_for_display(drone_type)
            # Находим все варианты дронов в текущем queryset, которые нормализуются в выбранное значение
            all_drones_in_queryset = flights.values_list('drone', flat=True).distinct()
            matching_drones = [
                d for d in all_drones_in_queryset
                if normalize_drone_for_display(d) == normalized_filter_drone
            ]
            if matching_drones:
                flights = flights.filter(drone__in=matching_drones)
                logger.debug(f"Фильтр по типу дрона: {drone_type} (нормализовано: {normalized_filter_drone}, найдено вариантов: {len(matching_drones)})")
            else:
                # Если не найдено совпадений, фильтруем по точному значению (на случай, если это не КВН)
                flights = flights.filter(drone=drone_type)
                logger.debug(f"Фильтр по типу дрона (точное совпадение): {drone_type}")

        # --- Остальная логика остается без изменений ---
        total_flights = flights.count()
        logger.debug(f"Всего полетов после фильтрации: {total_flights}")
        stats_data = {}

        destroyed_count = flights.filter(result=FlightResultTypes.DESTROYED).count()
        defeated_count = flights.filter(result=FlightResultTypes.DEFEATED).count()
        not_defeated_count = flights.filter(result=FlightResultTypes.NOT_DEFEATED).count()
        success_counts = aggregate_success_counts(flights)
        success_flights_count = success_total(success_counts)
        success_rate = (success_flights_count / total_flights * 100) if total_flights > 0 else 0

        stats_data['kpi'] = {
            'total_flights': total_flights,
            'destroyed_flights': destroyed_count,
            'porazheno_flights': defeated_count,
            'defeated_flights': defeated_count,
            'not_defeated_flights': not_defeated_count,
            'success_total': success_flights_count,
            'success_rate_percent': round(success_rate, 2),
        }

        stats_data['pilots'] = aggregate_pilot_success_stats(flights)
        stats_data['drones'] = aggregate_drone_success_stats(flights, normalize_drone_for_display)

        success_breakdown = {
            'destroyed': destroyed_count,
            'porazheno': defeated_count,
            'defeated': defeated_count,
            'not_defeated': not_defeated_count,
        }
        stats_data['results_breakdown'] = success_breakdown
        stats_data['targets'] = aggregate_target_success_stats(flights)

        if pilot_callname:
            stats_data['pilot_targets'] = aggregate_pilot_target_success_stats(flights, pilot_callname)
        else:
            stats_data['pilot_targets'] = []

        stats_data['daily_trend'] = aggregate_daily_success_stats(flights)

        flights_with_coords = flights.exclude(
            Q(lat_wgs84__isnull=True) |
            Q(lon_wgs84__isnull=True)
        ).values(
            'lat_wgs84',
            'lon_wgs84',
            'result',
        )
        heatmap_points = []
        category_weights = {
            FlightResultTypes.DESTROYED: 2.0,
            FlightResultTypes.DEFEATED: 1.5,
        }
        for flight in flights_with_coords:
            lat = flight['lat_wgs84']
            lon = flight['lon_wgs84']
            if lat == 90.0 and lon == 0.0:
                continue
            result = flight.get('result')
            if result not in category_weights:
                continue
            heatmap_points.append({
                'lat': lat,
                'lng': lon,
                'weight': category_weights[result],
            })
        stats_data['heatmap_points'] = heatmap_points

        pilots_list = stats_data['pilots']
        drones_list = stats_data['drones']
        most_active_pilot = None
        if pilots_list:
            most_active_pilot = max(
                pilots_list, key=lambda pilot: pilot['total_flights']
            )['pilot__callname']
        most_popular_drone = None
        if drones_list:
            most_popular_drone = drones_list[0]['drone']
        stats_data['summary'] = {
            'most_active_pilot': most_active_pilot,
            'most_popular_drone': most_popular_drone,
        }

        latest_flights = flights.order_by('-flight_date', '-flight_time')[:50]
        flights_table_data = []
        for flight in latest_flights:
            flights_table_data.append({
                'id': str(flight.id),
                'number': flight.number,
                'pilot_name': flight.pilot.callname if flight.pilot else 'N/A',
                'drone': normalize_drone_for_display(flight.drone),
                'flight_date': flight.flight_date.isoformat() if flight.flight_date else None,
                'flight_time': flight.flight_time.isoformat() if flight.flight_time else None,
                'target': flight.target,
                'result': flight.result,
                'comment': flight.comment,
            })
        stats_data['flights_table'] = flights_table_data

        logger.debug("=== КОНЕЦ StatisticsView УСПЕШНО ===")
        return Response(stats_data, status=status.HTTP_200_OK)
