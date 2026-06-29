from django.db.models import Count, Q, Case, When, IntegerField, Sum
from django.db.models.functions import TruncDate
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from datetime import datetime, timedelta
from flights.models import Flight, FlightResultTypes, Pilot, TargetType, Drone
from django.utils import timezone
import logging
import re

logger = logging.getLogger(__name__)


def normalize_target_name(target_name):
    """Нормализует название цели ТОЛЬКО для сравнения (ключ группировки), не меняет название"""
    if not target_name:
        return 'не указана'
    target_str = str(target_name).strip()
    if not target_str:
        return 'не указана'
    
    # Простая нормализация для сравнения: нижний регистр, нормализация пробелов
    target_normalized = re.sub(r'\s+', ' ', target_str.lower()).strip()
    
    # Объединяем "Не указано", "Не указана" и т.д.
    if target_normalized in ['не указано', 'не указана', 'неуказано', 'неуказана', 'none', 'null', '']:
        return 'не указана'
    
    # Объединяем похожие варианты (только для ключа группировки)
    # Автомобильная техника
    if any(word in target_normalized for word in ['автомобильн', 'автотехник', 'авто техник', 'авто-техник']):
        return 'автомобильная техника'
    # ПВХ - ищем ПВХ с номером
    if 'пвх' in target_normalized:
        match = re.search(r'пвх\s*[-]?\s*(\d+[и]?)', target_normalized, re.IGNORECASE)
        if match:
            return f"пвх-{match.group(1).lower()}"
        return 'пвх'
    
    # Для остальных - просто нормализуем пробелы и регистр для сравнения
    return target_normalized


def normalize_drone_name(drone_name):
    """Нормализует название дрона ТОЛЬКО для сравнения (ключ группировки), не меняет название.
    Дефисы сохраняются для правильного объединения вариантов типа X-51 и X51"""
    if not drone_name:
        return 'не указан'
    drone_str = str(drone_name).strip()
    if not drone_str:
        return 'не указан'
    
    # Простая нормализация для сравнения: нижний регистр, нормализация пробелов
    # ВАЖНО: НЕ удаляем дефисы, чтобы X-51 и X51 считались одним дроном
    drone_normalized = re.sub(r'\s+', ' ', drone_str.lower()).strip()
    
    # Объединяем "Не указано", "Не указан" и т.д.
    if drone_normalized in ['не указано', 'не указан', 'неуказано', 'неуказан', 'none', 'null', '']:
        return 'не указан'
    
    # Объединяем похожие варианты (только для ключа группировки)
    # ПВХ - ищем ПВХ с номером
    if 'пвх' in drone_normalized:
        match = re.search(r'пвх\s*[-]?\s*(\d+[и]?)', drone_normalized, re.IGNORECASE)
        if match:
            return f"пвх-{match.group(1).lower()}"
        return 'пвх'
    # Молния - ищем Молния с номером
    if 'молния' in drone_normalized:
        match = re.search(r'молния\s*[-]?\s*(\d+[дт]?)', drone_normalized, re.IGNORECASE)
        if match:
            return f"молния-{match.group(1).lower()}"
        return 'молния'
    # КВН - преобразуем все варианты в два: квн или квн-т
    if 'квн' in drone_normalized:
        # Находим позицию "квн" в строке
        kvn_pos = drone_normalized.find('квн')
        if kvn_pos != -1:
            # Берем все после "квн" (3 символа: к, в, н)
            substring_after_kvn = drone_normalized[kvn_pos + 3:]
            # Убираем все символы кроме букв и цифр для проверки наличия "т"
            # Это покроет все варианты: квн-т, квн-16т, квн-16-т, квн-23т, квн-23-т, квн 16 т, квнт и т.д.
            cleaned = re.sub(r'[^а-яё0-9]', '', substring_after_kvn)
            if 'т' in cleaned:
                return 'квн-т'
        return 'квн'
    
    # Для остальных - удаляем ВСЕ дефисы для сравнения, чтобы X-51 и X51 считались одним
    # Но в отображении будем использовать версию с дефисом (если она есть)
    drone_without_dash = re.sub(r'[-]', '', drone_normalized)
    return drone_without_dash


class ReportsDataView(APIView):
    """API для получения данных для отчетов"""
    
    def get(self, request, format=None):
        try:
            # Получаем параметры фильтрации
            # Поддерживаем как DRF request (query_params), так и обычный Django request (GET)
            if hasattr(request, 'query_params'):
                # DRF APIView
                date_from_str = request.query_params.get('date_from')
                date_to_str = request.query_params.get('date_to')
                pilot_ids = request.query_params.getlist('pilot_id')  # Может быть несколько
                target_types = request.query_params.getlist('target_type')
                drone_types = request.query_params.getlist('drone_type')
                results = request.query_params.getlist('result')
            else:
                # Обычный Django request
                date_from_str = request.GET.get('date_from')
                date_to_str = request.GET.get('date_to')
                pilot_ids = request.GET.getlist('pilot_id')  # Может быть несколько
                target_types = request.GET.getlist('target_type')
                drone_types = request.GET.getlist('drone_type')
                results = request.GET.getlist('result')
            
            # Начинаем с базового QuerySet
            flights = Flight.objects.select_related('pilot').all()
            
            # Применяем фильтры
            if date_from_str:
                try:
                    date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date()
                    flights = flights.filter(flight_date__gte=date_from)
                except ValueError:
                    pass
            
            if date_to_str:
                try:
                    date_to = datetime.strptime(date_to_str, '%Y-%m-%d').date()
                    flights = flights.filter(flight_date__lte=date_to)
                except ValueError:
                    pass
            
            if pilot_ids:
                flights = flights.filter(pilot__id__in=pilot_ids)
            
            if target_types:
                flights = flights.filter(target__in=target_types)
            
            if drone_types:
                flights = flights.filter(drone__in=drone_types)
            
            if results:
                flights = flights.filter(result__in=results)
            
            # Общая статистика
            total_flights = flights.count()
            destroyed_flights = flights.filter(result=FlightResultTypes.DESTROYED).count()
            defeated_flights = flights.filter(result=FlightResultTypes.DEFEATED).count()
            not_defeated_flights = flights.filter(result=FlightResultTypes.NOT_DEFEATED).count()
            
            destruction_rate = (destroyed_flights / total_flights * 100) if total_flights > 0 else 0
            success_rate = ((destroyed_flights + defeated_flights) / total_flights * 100) if total_flights > 0 else 0
            
            # Статистика по пилотам
            pilot_stats = flights.values('pilot__id', 'pilot__callname').annotate(
                total_flights=Count('id'),
                destroyed_flights=Sum(Case(
                    When(result=FlightResultTypes.DESTROYED, then=1),
                    output_field=IntegerField()
                )),
                defeated_flights=Sum(Case(
                    When(result=FlightResultTypes.DEFEATED, then=1),
                    output_field=IntegerField()
                )),
                not_defeated_flights=Sum(Case(
                    When(result=FlightResultTypes.NOT_DEFEATED, then=1),
                    output_field=IntegerField()
                )),
            ).order_by('-total_flights')
            
            pilot_stats_list = []
            for stat in pilot_stats:
                destroyed = stat['destroyed_flights'] or 0
                defeated = stat['defeated_flights'] or 0
                not_defeated = stat['not_defeated_flights'] or 0
                total = stat['total_flights']
                pilot_destruction_rate = (destroyed / total * 100) if total > 0 else 0
                pilot_success_rate = ((destroyed + defeated) / total * 100) if total > 0 else 0
                
                pilot_stats_list.append({
                    'pilot_id': str(stat['pilot__id']),
                    'pilot_name': stat['pilot__callname'],
                    'total_flights': total,
                    'destroyed_flights': destroyed,
                    'defeated_flights': defeated,
                    'not_defeated_flights': not_defeated,
                    'destruction_rate_percent': round(pilot_destruction_rate, 2),
                    'success_rate_percent': round(pilot_success_rate, 2),
                })
            
            # Статистика по целям (данные уже нормализованы при импорте, просто группируем)
            target_stats = flights.values('target').annotate(
                total_flights=Count('id'),
                destroyed_flights=Sum(Case(
                    When(result=FlightResultTypes.DESTROYED, then=1),
                    output_field=IntegerField()
                )),
                defeated_flights=Sum(Case(
                    When(result=FlightResultTypes.DEFEATED, then=1),
                    output_field=IntegerField()
                )),
                not_defeated_flights=Sum(Case(
                    When(result=FlightResultTypes.NOT_DEFEATED, then=1),
                    output_field=IntegerField()
                )),
            ).order_by('-total_flights')
            
            # Группируем цели: просто используем оригинальные значения (как для пилотов)
            # Нормализация только для объединения похожих вариантов (регистр, пробелы)
            target_stats_dict = {}
            
            for stat in target_stats:
                original_target = stat['target'] or 'Не указана'
                # Используем нормализацию только для создания ключа группировки
                # Но сохраняем оригинальное название
                normalized_key = normalize_target_name(original_target).lower().strip()
                
                destroyed = stat['destroyed_flights'] or 0
                defeated = stat['defeated_flights'] or 0
                not_defeated = stat['not_defeated_flights'] or 0
                total = stat['total_flights']
                
                # Группируем по нормализованному ключу
                if normalized_key in target_stats_dict:
                    # Объединяем статистику
                    target_stats_dict[normalized_key]['total_flights'] += total
                    target_stats_dict[normalized_key]['destroyed_flights'] += destroyed
                    target_stats_dict[normalized_key]['defeated_flights'] += defeated
                    target_stats_dict[normalized_key]['not_defeated_flights'] += not_defeated
                else:
                    # Первое вхождение - сохраняем оригинальное название из базы
                    target_stats_dict[normalized_key] = {
                        'target': original_target,  # Оригинальное название из БД
                        'total_flights': total,
                        'destroyed_flights': destroyed,
                        'defeated_flights': defeated,
                        'not_defeated_flights': not_defeated,
                    }
            
            target_stats_list = sorted(target_stats_dict.values(), key=lambda x: x['total_flights'], reverse=True)
            logger.info(f"Цели: было {len(target_stats)} уникальных в БД, стало {len(target_stats_list)} после объединения")
            
            # Статистика по дронам (данные уже нормализованы при импорте, просто группируем)
            drone_stats = flights.values('drone').annotate(
                total_flights=Count('id'),
                destroyed_flights=Sum(Case(
                    When(result=FlightResultTypes.DESTROYED, then=1),
                    output_field=IntegerField()
                )),
                defeated_flights=Sum(Case(
                    When(result=FlightResultTypes.DEFEATED, then=1),
                    output_field=IntegerField()
                )),
                not_defeated_flights=Sum(Case(
                    When(result=FlightResultTypes.NOT_DEFEATED, then=1),
                    output_field=IntegerField()
                )),
            ).order_by('-total_flights')
            
            # Группируем дроны: просто используем оригинальные значения (как для пилотов)
            # Нормализация только для объединения похожих вариантов (регистр, пробелы)
            drone_stats_dict = {}
            
            for stat in drone_stats:
                original_drone = stat['drone'] or 'Не указан'
                # Используем нормализацию только для создания ключа группировки
                # Но сохраняем оригинальное название
                normalized_key = normalize_drone_name(original_drone).lower().strip()
                
                destroyed = stat['destroyed_flights'] or 0
                defeated = stat['defeated_flights'] or 0
                not_defeated = stat['not_defeated_flights'] or 0
                total = stat['total_flights']
                
                # Группируем по нормализованному ключу
                if normalized_key in drone_stats_dict:
                    # Объединяем статистику
                    drone_stats_dict[normalized_key]['total_flights'] += total
                    drone_stats_dict[normalized_key]['destroyed_flights'] += destroyed
                    drone_stats_dict[normalized_key]['defeated_flights'] += defeated
                    drone_stats_dict[normalized_key]['not_defeated_flights'] += not_defeated
                    # Если новое название содержит дефис, а сохраненное - нет, заменяем на версию с дефисом
                    if '-' in original_drone and '-' not in drone_stats_dict[normalized_key]['drone']:
                        drone_stats_dict[normalized_key]['drone'] = original_drone
                else:
                    # Первое вхождение - сохраняем оригинальное название из базы
                    drone_stats_dict[normalized_key] = {
                        'drone': original_drone,  # Оригинальное название из БД
                        'total_flights': total,
                        'destroyed_flights': destroyed,
                        'defeated_flights': defeated,
                        'not_defeated_flights': not_defeated,
                    }
            
            drone_stats_list = sorted(drone_stats_dict.values(), key=lambda x: x['total_flights'], reverse=True)
            logger.info(f"Дроны: было {len(drone_stats)} уникальных в БД, стало {len(drone_stats_list)} после объединения")
            logger.info(f"Всего пилотов в отчете: {len(pilot_stats_list)}, целей: {len(target_stats_list)}, дронов: {len(drone_stats_list)}")
            
            # Динамика по датам
            daily_stats = flights.annotate(flight_day=TruncDate('flight_date')).values('flight_day').annotate(
                total_flights=Count('id'),
                destroyed_flights=Sum(Case(
                    When(result=FlightResultTypes.DESTROYED, then=1),
                    output_field=IntegerField()
                )),
                defeated_flights=Sum(Case(
                    When(result=FlightResultTypes.DEFEATED, then=1),
                    output_field=IntegerField()
                )),
                not_defeated_flights=Sum(Case(
                    When(result=FlightResultTypes.NOT_DEFEATED, then=1),
                    output_field=IntegerField()
                )),
            ).order_by('flight_day')
            
            daily_stats_list = []
            for stat in daily_stats:
                destroyed = stat['destroyed_flights'] or 0
                defeated = stat['defeated_flights'] or 0
                not_defeated = stat['not_defeated_flights'] or 0
                total = stat['total_flights']
                
                daily_stats_list.append({
                    'date': stat['flight_day'].isoformat() if stat['flight_day'] else None,
                    'total_flights': total,
                    'destroyed_flights': destroyed,
                    'defeated_flights': defeated,
                    'not_defeated_flights': not_defeated,
                })
            
            # Список доступных фильтров (используем все полеты, а не отфильтрованные)
            # Исключаем пилотов с именем, начинающимся с "Неизвестный_"
            all_pilots = Pilot.objects.exclude(callname__istartswith='Неизвестный_').values('id', 'callname')
            all_targets = Flight.objects.values_list('target', flat=True).distinct().exclude(target__isnull=True).exclude(target='')
            all_drones = Flight.objects.values_list('drone', flat=True).distinct().exclude(drone__isnull=True).exclude(drone='')
            
            response_data = {
                'summary': {
                    'total_flights': total_flights,
                    'destroyed_flights': destroyed_flights,
                    'defeated_flights': defeated_flights,
                    'not_defeated_flights': not_defeated_flights,
                    'destruction_rate_percent': round(destruction_rate, 2),
                    'success_rate_percent': round(success_rate, 2),
                },
                'pilots': pilot_stats_list,
                'targets': target_stats_list,
                'drones': drone_stats_list,
                'daily_trend': daily_stats_list,
                'filters': {
                    'pilots': [{'id': str(p['id']), 'callname': p['callname']} for p in all_pilots],
                    'targets': list(all_targets),
                    'drones': list(all_drones),
                }
            }
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Ошибка при генерации данных отчета: {e}", exc_info=True)
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

