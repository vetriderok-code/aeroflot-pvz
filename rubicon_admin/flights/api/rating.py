# old_api_updated.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta, date
from flights.models import Pilot, Flight, FlightResultTypes, TargetType
import logging
import math

logger = logging.getLogger(__name__)


class PilotRatingView(APIView):
    def get(self, request):
        try:
            # Используем простую дату без часового пояса для сравнения с DateField
            today = date.today()
            
            # Проверяем, есть ли вообще полеты в БД и их даты
            sample_flights = Flight.objects.order_by('-flight_date')[:5]
            if sample_flights.exists():
                latest_date = sample_flights[0].flight_date
                oldest_date = Flight.objects.order_by('flight_date').first().flight_date
                logger.info(f"Диапазон дат в БД: с {oldest_date} по {latest_date}, сегодня={today}")
                
                # ВСЕГДА используем последние 7/30 дней от последней даты в БД
                # Это гарантирует, что будут показаны данные, даже если они старые
                start_of_week = latest_date - timedelta(days=6)  # Последние 7 дней
                start_of_month = latest_date - timedelta(days=29)  # Последние 30 дней
                
                logger.info(f"Используем относительные даты от последней даты в БД ({latest_date}): "
                           f"начало недели={start_of_week} (последние 7 дней), "
                           f"начало месяца={start_of_month} (последние 30 дней)")
            else:
                logger.warning("В БД нет полетов!")
                # Используем стандартные даты
                days_since_monday = today.weekday()
                start_of_week = today - timedelta(days=days_since_monday)
                start_of_month = today.replace(day=1)

            # Исключаем пилотов с именем, начинающимся с "Неизвестный_"
            pilots = Pilot.objects.exclude(callname__istartswith='Неизвестный_')
            result = []
            first_pilot_id = None
            if pilots.exists():
                first_pilot_id = pilots.first().id
            
            for pilot in pilots:
                try:
                    all_flights = pilot.flights.all()
                    weekly_flights = all_flights.filter(flight_date__gte=start_of_week)
                    monthly_flights = all_flights.filter(flight_date__gte=start_of_month)
                    
                    # Логируем для отладки (только для первого пилота с полетами)
                    should_log = all_flights.exists() and (
                        (first_pilot_id and pilot.id == first_pilot_id) or 
                        weekly_flights.count() > 0 or 
                        monthly_flights.count() > 0
                    )
                    if should_log:
                        logger.info(f"Пилот {pilot.callname}: всего полетов={all_flights.count()}, "
                                   f"за неделю (с {start_of_week})={weekly_flights.count()}, "
                                   f"за месяц (с {start_of_month})={monthly_flights.count()}")
                        if all_flights.exists():
                            sample_dates = list(all_flights.order_by('-flight_date').values_list('flight_date', flat=True)[:3])
                            logger.info(f"  Примеры дат всех полетов: {sample_dates}")
                        if weekly_flights.count() > 0:
                            logger.info(f"  Примеры дат полетов за неделю: {list(weekly_flights.values_list('flight_date', flat=True)[:3])}")
                        if monthly_flights.count() > 0:
                            logger.info(f"  Примеры дат полетов за месяц: {list(monthly_flights.values_list('flight_date', flat=True)[:3])}")

                    week_data = self.calculate_rating_details_new(weekly_flights)
                    month_data = self.calculate_rating_details_new(monthly_flights)
                    total_data = self.calculate_rating_details_new(all_flights)

                    result.append({
                        "pilot_id": str(pilot.id),
                        "callname": pilot.callname,
                        "drone_type": pilot.drone_type or "Не указан",
                        "rating": {
                            "week": week_data["rating"],
                            "month": month_data["rating"],
                            "total": total_data["rating"],
                        },
                        "details": {
                            "week": {
                                "destroys": week_data["K"],
                                "defeated": week_data.get("L", 0),
                                "flights_count": week_data["N"],
                                "total_weight": week_data["W_total"],
                                "accuracy": round(week_data["A"], 2) if week_data["A"] is not None else 0.0,
                                "success_rate": week_data.get("success_rate", 0.0)
                            },
                            "month": {
                                "destroys": month_data["K"],
                                "defeated": month_data.get("L", 0),
                                "flights_count": month_data["N"],
                                "total_weight": month_data["W_total"],
                                "accuracy": round(month_data["A"], 2) if month_data["A"] is not None else 0.0,
                                "success_rate": month_data.get("success_rate", 0.0)
                            },
                            "total": {
                                "destroys": total_data["K"],
                                "defeated": total_data.get("L", 0),
                                "flights_count": total_data["N"],
                                "total_weight": total_data["W_total"],
                                "accuracy": round(total_data["A"], 2) if total_data["A"] is not None else 0.0,
                                "success_rate": total_data.get("success_rate", 0.0)
                            }
                        }
                    })
                except Exception as e:
                    logger.error(f"Ошибка при расчете рейтинга для пилота {pilot.callname}: {e}", exc_info=True)
                    # Добавляем пилота с нулевым рейтингом в случае ошибки
                    result.append({
                        "pilot_id": str(pilot.id),
                        "callname": pilot.callname,
                        "drone_type": pilot.drone_type or "Не указан",
                        "rating": {
                            "week": 0.0,
                            "month": 0.0,
                            "total": 0.0,
                        },
                        "details": {
                            "week": {"destroys": 0, "flights_count": 0, "total_weight": 0, "accuracy": 0.0},
                            "month": {"destroys": 0, "flights_count": 0, "total_weight": 0, "accuracy": 0.0},
                            "total": {"destroys": 0, "flights_count": 0, "total_weight": 0, "accuracy": 0.0}
                        }
                    })
                    continue
            
            return Response(result, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Критическая ошибка в PilotRatingView: {e}", exc_info=True)
            return Response({'error': f'Internal server error: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def calculate_rating_details_new(self, flights):
        K = 0
        L = 0
        N = 0
        A = 0
        success_rate = 0
        try:
            destroyed_flights = flights.filter(result=FlightResultTypes.DESTROYED)
            defeated_flights = flights.filter(result=FlightResultTypes.DEFEATED)

            K = destroyed_flights.count()  # Уничтожения
            L = defeated_flights.count()  # Поражения
            N = flights.count()  # Общее количество вылетов

            A = (K + L) / N if N > 0 else 0
            success_rate = (K + L) / N * 100 if N > 0 else 0  # Процент успеха
        except Exception as e:
            logger.error(f"Ошибка при подсчете статистики полетов: {e}", exc_info=True)
            return {
                "rating": 0.0,
                "K": 0,
                "L": 0,
                "W_total": 0,
                "N": 0,
                "A": 0,
                "success_rate": 0
            }

        W_total = 0
        try:
            for flight in destroyed_flights:
                if flight.target:
                    try:
                        # Используем filter().first() вместо get(), так как могут быть дубликаты
                        target_type = TargetType.objects.filter(name__iexact=flight.target).first()
                        if target_type and target_type.weight:
                            W_total += target_type.weight
                        else:
                            W_total += 1  # Вес по умолчанию, если не найдено
                    except Exception as e:
                        logger.warning(f"Ошибка при получении TargetType для '{flight.target}': {e}")
                        W_total += 1  # Вес по умолчанию при ошибке
                else:
                    W_total += 1  # Вес по умолчанию, если цель не указана
        except Exception as e:
            logger.error(f"Ошибка при расчете веса целей: {e}", exc_info=True)
            W_total = K  # Используем количество уничтожений как минимальный вес

        epsilon = 0.1

        if A >= 1.0:
            A_adj = 0.99
        else:
            A_adj = A

        if N > 0:
            # Упрощенная и более стабильная формула расчета рейтинга
            # Компонент веса целей (W_total)
            if W_total > 0:
                try:
                    # Используем более простую формулу для веса
                    weight_component = math.log(W_total + 1, 10) * 10  # Масштабируем для больших значений
                except (OverflowError, ValueError):
                    weight_component = math.log(W_total + 1, 10) * 10
            else:
                # Если нет уничтожений, используем минимальный вес
                weight_component = 1.0

            # Компонент точности (A)
            if A > 0:
                # Формула: (A + 0.1) / (1 - A + 0.1) для нормализации
                accuracy_component = (A_adj + 0.1) / max((1 - A_adj + 0.1), 0.01)
            else:
                # Если нет успешных вылетов, используем минимальную точность
                accuracy_component = 0.1

            # Компонент количества полетов (N)
            flight_count_component = math.log(N + 1, 10) * 2  # Масштабируем для больших значений

            # Итоговый рейтинг
            R = weight_component * accuracy_component * flight_count_component
            
            # Убеждаемся, что рейтинг не равен нулю, если есть полеты
            if R <= 0.0 and N > 0:
                R = 0.01  # Минимальный рейтинг для пилотов с полетами
            
            # Логируем для отладки (только для первых нескольких пилотов)
            if N > 0 and K > 0:
                logger.debug(f"Рейтинг: K={K}, L={L}, N={N}, A={A:.2f}, W_total={W_total}, "
                           f"weight={weight_component:.2f}, accuracy={accuracy_component:.2f}, "
                           f"count={flight_count_component:.2f}, R={R:.2f}")
        else:
            R = 0.0

        return {
            "rating": round(R, 2),
            "K": K,
            "L": L,
            "W_total": W_total,
            "N": N,
            "A": A,
            "success_rate": round(success_rate, 1)
        }
