# views.py (или где у вас находится FlightsListView)
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q
import logging
from datetime import date, timedelta
from flights.models import Flight

logger = logging.getLogger(__name__)


class FlightsListViewWithForcedCache(APIView):

    def is_default_coordinates(self, coord_info):
        if not coord_info:
            return True
        if (coord_info.get('lat_wgs84') == 90.0 and coord_info.get('lon_wgs84') == 0.0 and
                coord_info.get('lat_sk42') == 90.0 and coord_info.get('lon_sk42') == 0.0):
            return True
        if (coord_info.get('lat_wgs84') == 0.0 and coord_info.get('lon_wgs84') == 0.0 and
                coord_info.get('lat_sk42') == 0.0 and coord_info.get('lon_sk42') == 0.0):
            return True
        if (coord_info.get('lat_wgs84') is None or coord_info.get('lon_wgs84') is None or
                coord_info.get('lat_sk42') is None or coord_info.get('lon_sk42') is None):
            return True
        return False

    def get(self, request, *args, **kwargs):
        try:
            date_from = request.GET.get('date_from')
            date_to = request.GET.get('date_to')
            pilot_name = request.GET.get('pilot')
            result = request.GET.get('result')
            target = request.GET.get('target')

            logger.info("Начало загрузки полетов с принудительным пересчетом координат при необходимости")

            flights = Flight.objects.select_related('pilot').all()

            # Применяем фильтр по дате только если он явно указан
            # Если фильтры не установлены - показываем все записи
            if date_from:
                flights = flights.filter(flight_date__gte=date_from)
            if date_to:
                flights = flights.filter(flight_date__lte=date_to)
            if pilot_name:
                flights = flights.filter(pilot__callname__icontains=pilot_name)
            if result:
                flights = flights.filter(result=result)
            if target:
                flights = flights.filter(target__icontains=target)

            logger.info(f"Найдено {flights.count()} полетов до обработки координат")

            flights_data = []
            valid_count = 0
            skipped_count = 0
            recalculated_count = 0

            # Явно получаем все записи без ограничений
            flights_list = list(flights)
            logger.info(f"Загружено {len(flights_list)} полетов для обработки")

            for flight in flights_list:
                try:
                    has_valid_cache = (
                            flight.lat_wgs84 is not None and flight.lon_wgs84 is not None and
                            flight.lat_sk42 is not None and flight.lon_sk42 is not None and
                            not (flight.lat_wgs84 == 90.0 and flight.lon_wgs84 == 0.0 and
                                 flight.lat_sk42 == 90.0 and flight.lon_sk42 == 0.0) and
                            not (flight.lat_wgs84 == 0.0 and flight.lon_wgs84 == 0.0 and
                                 flight.lat_sk42 == 0.0 and flight.lon_sk42 == 0.0)
                    )

                    if has_valid_cache:
                        coord_info = {
                            'lat_sk42': flight.lat_sk42,
                            'lon_sk42': flight.lon_sk42,
                            'lat_wgs84': flight.lat_wgs84,
                            'lon_wgs84': flight.lon_wgs84
                        }
                        logger.debug(f"Использованы закэшированные координаты для полета {flight.id}")
                    else:
                        logger.info(f"Принудительный пересчет координат для полета {flight.id}")
                        coord_info = flight.get_coordinates_info_cached()
                        recalculated_count += 1
                        logger.debug(f"Координаты пересчитаны для полета {flight.id}")

                    if not coord_info:
                        logger.warning(f"Координаты не получены для полета {flight.id}")
                        skipped_count += 1
                        continue

                    if self.is_default_coordinates(coord_info):
                        logger.warning(f"Координаты по умолчанию для полета {flight.id}")
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
                    flights_data.append(flight_data)
                    valid_count += 1

                except Exception as flight_error:
                    logger.error(f"Ошибка обработки полета {flight.id}: {flight_error}", exc_info=True)
                    skipped_count += 1
                    continue

            logger.info(
                f"Обработано: валидных={valid_count}, пропущенных={skipped_count}, пересчитанных={recalculated_count}")
            return Response(flights_data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"КРИТИЧЕСКАЯ ОШИБКА в FlightsListViewWithForcedCache: {e}", exc_info=True)
            return Response(
                {'error': 'Internal Server Error', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
