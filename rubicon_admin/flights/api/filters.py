from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from flights.models import Flight, Pilot, FlightResultTypes
import logging

logger = logging.getLogger(__name__)


def normalize_result(result_value):
    """Нормализует значение результата к стандартным значениям"""
    if not result_value:
        return None
    
    result_str = str(result_value).strip().lower()
    
    # Сопоставляем с известными вариантами
    if 'destroyed' in result_str or 'уничтожен' in result_str:
        return FlightResultTypes.DESTROYED
    elif 'defeated' in result_str or 'поражен' in result_str:
        return FlightResultTypes.DEFEATED
    elif 'not defeated' in result_str or 'not_defeated' in result_str or 'не поражен' in result_str or 'промах' in result_str:
        return FlightResultTypes.NOT_DEFEATED
    
    # Если не найдено соответствие, пытаемся найти по точному совпадению
    if result_str == FlightResultTypes.DESTROYED:
        return FlightResultTypes.DESTROYED
    elif result_str == FlightResultTypes.DEFEATED:
        return FlightResultTypes.DEFEATED
    elif result_str == FlightResultTypes.NOT_DEFEATED:
        return FlightResultTypes.NOT_DEFEATED
    
    return None


class FiltersDataView(APIView):
    """API для получения доступных фильтров с учетом выбранных пилотов, целей и дронов"""
    
    def get(self, request, format=None):
        try:
            pilot_ids = request.query_params.getlist('pilot_id')
            target_types = request.query_params.getlist('target_type')
            drone_types = request.query_params.getlist('drone_type')
            
            # Базовый QuerySet полетов
            flights = Flight.objects.select_related('pilot').all()
            
            # Исключаем "Неизвестных" пилотов из списка всех пилотов
            all_pilots = Pilot.objects.exclude(callname__istartswith='Неизвестный_').values('id', 'callname')
            
            # Если выбраны пилоты, фильтруем только их полеты
            if pilot_ids:
                flights = flights.filter(pilot__id__in=pilot_ids)
            
            # Получаем уникальные цели из отфильтрованных полетов (для выбранных пилотов)
            available_targets = flights.exclude(
                target__isnull=True
            ).exclude(
                target=''
            ).values_list('target', flat=True).distinct()
            
            # Если выбраны цели, фильтруем дальше
            if target_types:
                flights = flights.filter(target__in=target_types)
            
            # Получаем уникальные дроны из отфильтрованных полетов
            available_drones = flights.exclude(
                drone__isnull=True
            ).exclude(
                drone=''
            ).values_list('drone', flat=True).distinct()
            
            # Если выбраны дроны, фильтруем дальше
            if drone_types:
                flights = flights.filter(drone__in=drone_types)
            
            # Получаем уникальные результаты из отфильтрованных полетов и нормализуем их
            raw_results = flights.values_list('result', flat=True).distinct()
            
            # Нормализуем и группируем результаты
            normalized_results = set()
            for result in raw_results:
                normalized = normalize_result(result)
                if normalized:
                    normalized_results.add(normalized)
            
            # Возвращаем стандартные результаты в определенном порядке
            available_results = []
            for standard_result in [FlightResultTypes.DESTROYED, FlightResultTypes.DEFEATED, FlightResultTypes.NOT_DEFEATED]:
                if standard_result in normalized_results:
                    available_results.append(standard_result)
            
            response_data = {
                'pilots': [{'id': str(p['id']), 'callname': p['callname']} for p in all_pilots],
                'targets': list(available_targets),
                'drones': list(available_drones),
                'results': available_results,
            }
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Ошибка при получении данных фильтров: {e}", exc_info=True)
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

