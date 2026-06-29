from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.views import APIView
import logging
from datetime import timedelta, time, date
from flights.models import Flight, Pilot, Drone, DroneTypes
from flights.utils.live_flight import get_active_pilot_callnames

logger = logging.getLogger(__name__)


class ScheduleAPIView(APIView):

    def get(self, request):
        try:
            logger.info("=== НАЧАЛО ScheduleAPIView ===")

            date_from_str = request.query_params.get('date_from')
            date_to_str = request.query_params.get('date_to')
            pilot_name = request.query_params.get('pilot')

            logger.debug(f"Параметры запроса: date_from={date_from_str}, date_to={date_to_str}, pilot={pilot_name}")

            flights = Flight.objects.select_related('pilot').all()

            if date_from_str:
                try:
                    from_date = parse_date(date_from_str)
                    flights = flights.filter(flight_date__gte=from_date)
                    logger.debug(f"Фильтр по дате с: {from_date}")
                except ValueError:
                    logger.warning(f"Неверный формат date_from: {date_from_str}")
            else:
                flights = flights.filter(flight_date__gte=date.today() - timedelta(days=7))
                logger.debug(f"Фильтр по дате с: {date.today() - timedelta(days=7)}")

            if date_to_str:
                try:
                    to_date = parse_date(date_to_str)
                    flights = flights.filter(flight_date__lte=to_date)
                    logger.debug(f"Фильтр по дате по: {to_date}")
                except ValueError:
                    logger.warning(f"Неверный формат date_to: {date_to_str}")

            if pilot_name:
                try:
                    # Используем icontains для нечеткого поиска (без учета регистра и частичное совпадение)
                    flights = flights.filter(pilot__callname__icontains=pilot_name)
                    logger.debug(f"Фильтр по пилоту: {pilot_name}")
                except Exception as e:
                    logger.warning(f"Ошибка при фильтрации по пилоту {pilot_name}: {e}")

            dates = flights.values_list('flight_date', flat=True).distinct().order_by('flight_date')
            logger.debug(f"Уникальные даты: {list(dates)}")

            kt_pilots = []
            st_pilots = []

            # Получаем только пилотов, у которых есть полеты в выбранном периоде
            # Сначала получаем уникальных пилотов из отфильтрованных полетов
            pilots_with_flights = flights.exclude(
                pilot__callname__istartswith='Неизвестный_'
            ).exclude(
                pilot__isnull=True
            ).values_list('pilot__id', 'pilot__callname').distinct()
            
            # Если применен фильтр по пилоту, дополнительно фильтруем
            if pilot_name:
                pilots_with_flights = pilots_with_flights.filter(pilot__callname__icontains=pilot_name)
            
            # Получаем ID пилотов, которые летали в выбранном периоде
            pilot_ids_in_period = [pilot_id for pilot_id, _ in pilots_with_flights]
            
            # Получаем объекты пилотов, которые летали в выбранном периоде
            all_pilots = Pilot.objects.filter(
                id__in=pilot_ids_in_period
            ).exclude(
                callname__istartswith='Неизвестный_'
            ).distinct()
            
            logger.debug(f"Пилоты с полетами в выбранном периоде: {all_pilots.count()}")
            logger.debug(f"Список пилотов: {[p.callname for p in all_pilots]}")

            for pilot in all_pilots:
                # Определяем тип дрона по полетам пилота, а не по полю pilot.drone_type
                pilot_flights = flights.filter(pilot=pilot)
                
                # Получаем уникальные названия дронов из полетов пилота
                pilot_drone_names = pilot_flights.exclude(
                    drone__isnull=True
                ).exclude(
                    drone=''
                ).values_list('drone', flat=True).distinct()
                
                is_st_pilot = False
                is_kt_pilot = False
                
                # Проверяем каждый дрон из полетов пилота
                for drone_name in pilot_drone_names:
                    if not drone_name:
                        continue
                    
                    try:
                        # Ищем дрон в таблице Drone по имени (без учета регистра)
                        drone = Drone.objects.filter(name__iexact=drone_name).first()
                        
                        if drone:
                            if drone.drone_type == DroneTypes.ST:
                                is_st_pilot = True
                            elif drone.drone_type == DroneTypes.KT:
                                is_kt_pilot = True
                        else:
                            # Если дрон не найден в таблице, определяем по названию
                            drone_name_lower = str(drone_name).lower()
                            if 'ст' in drone_name_lower or 'st' in drone_name_lower:
                                is_st_pilot = True
                            elif 'кт' in drone_name_lower or 'kt' in drone_name_lower:
                                is_kt_pilot = True
                    except Exception as e:
                        logger.warning(f"Ошибка определения типа дрона '{drone_name}' для пилота {pilot.callname}: {e}")
                
                # Если пилот использует СТ дроны, добавляем в ST
                if is_st_pilot:
                    st_pilots.append(pilot.callname)
                # Иначе добавляем в KT (по умолчанию)
                else:
                    kt_pilots.append(pilot.callname)

            logger.debug(f"Пилоты KT: {kt_pilots}")
            logger.debug(f"Пилоты ST: {st_pilots}")

            kt_schedule_data = self.build_schedule_for_pilots(flights, kt_pilots, dates)

            st_schedule_data = self.build_schedule_for_pilots(flights, st_pilots, dates)

            logger.info("=== КОНЕЦ ScheduleAPIView УСПЕШНО ===")

            return JsonResponse({
                'kt_schedule': kt_schedule_data,
                'st_schedule': st_schedule_data,
                'kt_pilots': kt_pilots,
                'st_pilots': st_pilots,
                'dates': [date.isoformat() for date in dates] if dates else [],
                'active_pilots': sorted(get_active_pilot_callnames()),
                'updated_at': timezone.localtime(timezone.now()).isoformat(),
                'summary': {
                    'total_kt_pilots': len(kt_pilots),
                    'total_st_pilots': len(st_pilots),
                    'total_dates': dates.count() if hasattr(dates, 'count') else len(list(dates))
                }
            }, safe=False, json_dumps_params={'ensure_ascii': False})

        except Exception as e:
            logger.error(f"КРИТИЧЕСКАЯ ОШИБКА в ScheduleAPIView: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return JsonResponse({'error': 'Internal Server Error'}, status=500)

    def build_schedule_for_pilots(self, all_flights, pilot_names, dates):
        schedule_data = []

        for pilot_name in pilot_names:
            pilot_flights = all_flights.filter(pilot__callname=pilot_name)

            if not pilot_flights.exists():
                pilot_schedule = {
                    'pilot_name': pilot_name,
                    'dates': []
                }

                for flight_date in dates:
                    pilot_schedule['dates'].append({
                        'date': flight_date.isoformat() if flight_date else None,
                        'day_flights': 0,
                        'night_flights': 0,
                    })

                schedule_data.append(pilot_schedule)
                continue

            pilot_schedule = {
                'pilot_name': pilot_name,
                'dates': []
            }

            for flight_date in dates:
                current_date_flights = pilot_flights.filter(flight_date=flight_date)
                previous_date_flights = pilot_flights.filter(flight_date=flight_date - timedelta(days=1))

                shift_info = self.determine_shift_for_date(current_date_flights, previous_date_flights, flight_date)

                pilot_schedule['dates'].append({
                    'date': flight_date.isoformat() if flight_date else None,
                    'day_flights': shift_info['day'],
                    'night_flights': shift_info['night'],
                })

            schedule_data.append(pilot_schedule)

        return schedule_data

    def determine_shift_for_date(self, current_flights, previous_flights, target_date):
        try:
            day_count = 0
            night_count = 0

            for flight in previous_flights:
                if flight.flight_time:
                    try:
                        if flight.flight_time >= time(20, 0):
                            night_count += 1
                    except Exception as time_error:
                        logger.error(f"Ошибка обработки времени полета {flight.id}: {time_error}")
                        continue

            for flight in current_flights:
                if flight.flight_time:
                    try:
                        if time(8, 0) <= flight.flight_time < time(20, 0):
                            day_count += 1
                        else:
                            night_count += 1
                    except Exception as time_error:
                        logger.error(f"Ошибка обработки времени полета {flight.id}: {time_error}")
                        continue

            logger.debug(f"Дата {target_date}: дневных полетов: {day_count}, ночных полетов: {night_count}")

            return {'day': day_count, 'night': night_count}

        except Exception as e:
            logger.error(f"Ошибка определения смены для даты {target_date}: {e}")
            return {'day': 0, 'night': 0}