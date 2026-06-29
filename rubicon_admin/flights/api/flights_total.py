from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q
from django.db import connection
from django.core.cache import cache
import hashlib
import logging
import json
from datetime import date, timedelta
from flights.models import Flight, FlightResultTypes

logger = logging.getLogger(__name__)


class FlightsListView(APIView):
    def get(self, request, *args, **kwargs):
        def is_default_coordinates(coord_info):
            if not coord_info:
                return True
            # Проверяем только на дефолтные значения (90.0, 0.0) - это означает, что координаты не были рассчитаны
            if (coord_info.get('lat_wgs84') == 90.0 and coord_info.get('lon_wgs84') == 0.0 and
                    coord_info.get('lat_sk42') == 90.0 and coord_info.get('lon_sk42') == 0.0):
                return True
            # НЕ фильтруем (0.0, 0.0) - это может быть валидная координата
            # НЕ фильтруем None - это уже проверено выше
            return False

        try:
            date_from = request.GET.get('date_from')
            date_to = request.GET.get('date_to')
            pilot_name = request.GET.get('pilot')
            result = request.GET.get('result')
            target = request.GET.get('target')
            
            # По умолчанию на карте — успешные вылеты: уничтожено + поражено (и аналоги из Excel)
            map_success_only = (
                not result and not date_from and not date_to and not pilot_name and not target
            )
            if map_success_only:
                logger.info(
                    "Фильтры не установлены, показываем успешные результаты: "
                    "уничтожено, поражено, доставка, успех"
                )

            # Создаем ключ кэша на основе всех параметров запроса
            cache_key_parts = [
                'flights_total_v3',
                date_from or '',
                date_to or '',
                pilot_name or '',
                result or ('map_success' if map_success_only else ''),
                target or ''
            ]
            cache_key = 'flights_total:' + hashlib.md5('|'.join(cache_key_parts).encode()).hexdigest()
            
            # Проверяем кэш (с обработкой ошибок)
            cached_data = None
            try:
                cached_data = cache.get(cache_key)
                if cached_data is not None:
                    logger.info(f"Возвращаем данные из кэша для ключа: {cache_key}")
                    return Response(cached_data, status=status.HTTP_200_OK)
            except Exception as cache_error:
                logger.warning(f"Ошибка при чтении из кэша: {cache_error}, продолжаем без кэша")
            
            logger.info("Начало загрузки полетов с фильтрацией точек по умолчанию")

            # Проверяем общее количество записей в базе
            total_flights = Flight.objects.count()
            logger.info(f"Всего полетов в базе: {total_flights}")
            
            # ВАЖНО: Строим SQL запрос ВРУЧНУЮ, полностью обходя Django ORM
            # Это гарантирует отсутствие любых ограничений
            logger.info(f"Строим SQL запрос вручную...")
            
            # ВАЖНО: Используем Django ORM, но БЕЗ фильтров по координатам
            # Загружаем все записи с coordinates, координаты будут рассчитываться на лету
            logger.info(f"Загружаем все записи с coordinates через Django ORM...")
            
            # Создаем QuerySet для всех записей с coordinates
            flights_with_coords = Flight.objects.select_related('pilot').exclude(
                coordinates__isnull=True
            ).exclude(
                coordinates=''
            )
            
            # Применяем фильтры
            if date_from:
                flights_with_coords = flights_with_coords.filter(flight_date__gte=date_from)
            if date_to:
                flights_with_coords = flights_with_coords.filter(flight_date__lte=date_to)
            if pilot_name:
                flights_with_coords = flights_with_coords.filter(pilot__callname__icontains=pilot_name)
            if map_success_only:
                flights_with_coords = flights_with_coords.filter(
                    result__in=FlightResultTypes.map_success_values()
                )
            elif result:
                flights_with_coords = flights_with_coords.filter(result=result)
            if target:
                flights_with_coords = flights_with_coords.filter(target__icontains=target)
            
            # Обрабатываем записи напрямую через iterator, без промежуточных преобразований
            logger.info(f"Обрабатываем записи напрямую через iterator...")
            flights_by_key = {}
            valid_count = 0
            skipped_count = 0
            deduped_count = 0
            processed_count = 0
            
            # Ограничиваем количество обрабатываемых записей для производительности
            # Если фильтры не установлены, обрабатываем все записи, но с оптимизацией
            max_records = 100000  # Максимум записей для обработки
            
            for flight in flights_with_coords.iterator(chunk_size=1000):
                processed_count += 1
                
                if processed_count > max_records:
                    logger.warning(f"Достигнут лимит обработки: {max_records} записей")
                    break
                
                if processed_count % 5000 == 0:
                    logger.info(f"Обработано {processed_count} полетов, валидных: {valid_count}...")
                
                try:
                    coord_info = flight.get_coordinates_info_cached()
                    if not coord_info:
                        skipped_count += 1
                        continue
                    
                    # Упрощенная проверка: только дефолтные координаты (90.0, 0.0)
                    if is_default_coordinates(coord_info):
                        skipped_count += 1
                        continue
                    
                    # Проверяем, что координаты валидные (не None)
                    lat_wgs = coord_info.get('lat_wgs84')
                    lon_wgs = coord_info.get('lon_wgs84')
                    if lat_wgs is None or lon_wgs is None:
                        skipped_count += 1
                        continue

                    pilot_name = ''
                    if hasattr(flight, 'pilot') and flight.pilot:
                        pilot_name = getattr(flight.pilot, 'callname', str(flight.pilot))

                    flight_data = {
                        'id': str(flight.id),
                        'number': flight.number,
                        'pilot_name': pilot_name,
                        'drone': flight.drone,
                        'flight_date': flight.flight_date.isoformat() if flight.flight_date else None,
                        'flight_time': flight.flight_time.isoformat() if flight.flight_time else None,
                        'target': flight.target,
                        'corrective': flight.corrective,
                        'result': flight.result,
                        'coordinates': flight.coordinates,
                        'coordinates_info': coord_info,
                        'comment': flight.comment,
                        'objective': flight.objective
                    }
                    dedupe_key = FlightResultTypes.map_dedupe_key(flight)
                    existing = flights_by_key.get(dedupe_key)
                    if existing is None:
                        flights_by_key[dedupe_key] = flight_data
                        valid_count += 1
                    elif FlightResultTypes.result_priority(flight.result) > FlightResultTypes.result_priority(
                        existing['result']
                    ):
                        flights_by_key[dedupe_key] = flight_data
                        deduped_count += 1
                    else:
                        deduped_count += 1
                except Exception as flight_error:
                    logger.error(f"Ошибка обработки полета {flight.id}: {flight_error}")
                    skipped_count += 1
                    continue
            
            flights_data = list(flights_by_key.values())
            logger.info(
                f"Обработано всего: {processed_count} полетов, "
                f"уникальных на карте={valid_count}, дублей отброшено={deduped_count}, "
                f"пропущенных={skipped_count}"
            )
            logger.info(f"Возвращаем {len(flights_data)} записей в ответе API")
            if flights_data:
                logger.info(f"Пример первой записи: id={flights_data[0].get('id')}, coordinates_info={flights_data[0].get('coordinates_info')}")
            
            # Сохраняем в кэш на 1 час (3600 секунд) с обработкой ошибок
            try:
                cache.set(cache_key, flights_data, timeout=3600)
                logger.info(f"Данные сохранены в кэш с ключом: {cache_key}")
            except Exception as cache_error:
                logger.warning(f"Ошибка при сохранении в кэш: {cache_error}, продолжаем без кэша")
            
            return Response(flights_data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"КРИТИЧЕСКАЯ ОШИБКА в flights_list: {e}")
            return Response({'error': 'Internal Server Error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
