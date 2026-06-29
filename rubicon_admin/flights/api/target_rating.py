# API для рейтинга по целям
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q, Count, Sum
from django.utils import timezone
from datetime import timedelta, date
from flights.models import Flight, FlightResultTypes, TargetType
import logging
import math
from collections import defaultdict

logger = logging.getLogger(__name__)


class TargetRatingView(APIView):
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

            # Получаем только УНИЧТОЖЕННЫЕ цели (destroyed) с пилотами
            logger.info("Начинаем агрегацию данных по целям и пилотам...")
            
            # Получаем все полеты с уничтоженными целями
            all_destroyed_flights = Flight.objects.filter(
                result=FlightResultTypes.DESTROYED
            ).exclude(
                target__isnull=True
            ).exclude(
                target=''
            ).exclude(
                pilot__callname__istartswith='Неизвестный_'
            ).select_related('pilot')
            
            # Структура: target_name -> period -> pilot_callname -> count
            # periods: 'all', 'week', 'month'
            targets_pilots_stats = defaultdict(lambda: {
                'all': defaultdict(int),
                'week': defaultdict(int),
                'month': defaultdict(int),
            })
            
            # Обрабатываем все полеты одним проходом
            logger.info("Обрабатываем полеты для агрегации...")
            batch_size = 1000
            total_processed = 0
            total_count = all_destroyed_flights.count()
            
            for i in range(0, total_count, batch_size):
                batch = all_destroyed_flights[i:i+batch_size]
                for flight in batch:
                    target_name = flight.target
                    if not target_name:
                        continue
                    
                    pilot_callname = flight.pilot.callname if flight.pilot else None
                    if not pilot_callname or pilot_callname.startswith('Неизвестный_'):
                        continue
                    
                    # Все время
                    targets_pilots_stats[target_name]['all'][pilot_callname] += 1
                    
                    # Неделя
                    if flight.flight_date >= start_of_week:
                        targets_pilots_stats[target_name]['week'][pilot_callname] += 1
                    
                    # Месяц
                    if flight.flight_date >= start_of_month:
                        targets_pilots_stats[target_name]['month'][pilot_callname] += 1
                
                total_processed += len(batch)
                if total_processed % 5000 == 0:
                    logger.info(f"Обработано полетов: {total_processed}/{total_count}")
            
            logger.info(f"Всего обработано полетов: {total_processed}, уникальных целей: {len(targets_pilots_stats)}")
            
            result = []
            
            # Формируем результат: для каждой цели список пилотов с количеством уничтожений
            for target_name, periods_data in targets_pilots_stats.items():
                try:
                    # Для каждого периода создаем список пилотов, отсортированный по количеству уничтожений
                    week_pilots = []
                    for pilot_callname, count in sorted(periods_data['week'].items(), key=lambda x: x[1], reverse=True):
                        week_pilots.append({
                            "pilot_callname": pilot_callname,
                            "destroyed_count": count
                        })
                    
                    month_pilots = []
                    for pilot_callname, count in sorted(periods_data['month'].items(), key=lambda x: x[1], reverse=True):
                        month_pilots.append({
                            "pilot_callname": pilot_callname,
                            "destroyed_count": count
                        })
                    
                    total_pilots = []
                    for pilot_callname, count in sorted(periods_data['all'].items(), key=lambda x: x[1], reverse=True):
                        total_pilots.append({
                            "pilot_callname": pilot_callname,
                            "destroyed_count": count
                        })
                    
                    # Считаем общее количество уничтожений для каждого периода
                    week_total = sum(periods_data['week'].values())
                    month_total = sum(periods_data['month'].values())
                    all_total = sum(periods_data['all'].values())
                    
                    result.append({
                        "target_name": target_name,
                        "pilots": {
                            "week": week_pilots,
                            "month": month_pilots,
                            "total": total_pilots,
                        },
                        "totals": {
                            "week": week_total,
                            "month": month_total,
                            "total": all_total,
                        }
                    })
                except Exception as e:
                    logger.error(f"Ошибка при обработке цели {target_name}: {e}", exc_info=True)
                    continue
            
            # Сортируем цели по общему количеству уничтожений
            result.sort(key=lambda x: x['totals']['total'], reverse=True)
            
            logger.info(f"Успешно обработано целей: {len(result)}")
            return Response(result, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Критическая ошибка в TargetRatingView: {e}", exc_info=True)
            return Response({'error': f'Internal server error: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def calculate_target_rating_from_stats(self, K, L, N, target_name):
        """
        Рассчитывает рейтинг цели на основе уже посчитанной статистики
        K - количество уничтоженных
        L - количество пораженных  
        N - общее количество полетов
        """
        try:
            A = (K + L) / N if N > 0 else 0
        except Exception as e:
            logger.error(f"Ошибка при расчете точности для цели {target_name}: {e}", exc_info=True)
            return {
                "rating": 0.0, "K": 0, "L": 0, "W_total": 0, "N": 0, "A": 0
            }

        W_total = 0
        try:
            target_type = TargetType.objects.filter(name__iexact=target_name).first()
            if target_type and target_type.weight:
                W_total = target_type.weight * K
            else:
                W_total = K
        except Exception as e:
            logger.error(f"Ошибка при расчете веса цели {target_name}: {e}", exc_info=True)
            W_total = K

        epsilon = 0.1
        
        if A >= 1.0:
            A_adj = 0.99
        else:
            A_adj = A

        if N > 0:
            # Упрощенная формула расчета рейтинга для целей
            # Компонент веса целей (W_total)
            if W_total > 0:
                try:
                    weight_component = math.log(W_total + 1, 10) * 10
                except (OverflowError, ValueError):
                    weight_component = math.log(W_total + 1, 10) * 10
            else:
                weight_component = 1.0

            # Компонент точности (A)
            if A > 0:
                accuracy_component = (A_adj + 0.1) / max((1 - A_adj + 0.1), 0.01)
            else:
                accuracy_component = 0.1

            # Компонент количества полетов (N)
            flight_count_component = math.log(N + 1, 10) * 2

            # Итоговый рейтинг
            R = weight_component * accuracy_component * flight_count_component
            
            if R <= 0.0 and N > 0:
                R = 0.01
        else:
            R = 0.0

        return {
            "rating": round(R, 2), "K": K, "L": L, "W_total": W_total, "N": N, "A": A
        }
    
    def calculate_target_rating_details(self, flights, target_name):
        try:
            destroyed_flights = flights.filter(result=FlightResultTypes.DESTROYED)
            defeated_flights = flights.filter(result=FlightResultTypes.DEFEATED)

            K = destroyed_flights.count()  # Уничтожения
            L = defeated_flights.count()  # Поражения
            N = flights.count()  # Общее количество вылетов

            A = (K + L) / N if N > 0 else 0
        except Exception as e:
            logger.error(f"Ошибка при подсчете статистики полетов для цели {target_name}: {e}", exc_info=True)
            return {
                "rating": 0.0,
                "K": 0,
                "L": 0,
                "W_total": 0,
                "N": 0,
                "A": 0
            }

        W_total = 0
        try:
            # Получаем вес цели
            target_type = TargetType.objects.filter(name__iexact=target_name).first()
            if target_type and target_type.weight:
                # Общий вес = вес цели * количество уничтожений
                W_total = target_type.weight * K
            else:
                # Если вес не найден, используем количество уничтожений как вес
                W_total = K
        except Exception as e:
            logger.error(f"Ошибка при расчете веса цели {target_name}: {e}", exc_info=True)
            W_total = K  # Используем количество уничтожений как минимальный вес

        epsilon = 0.1

        if A >= 1.0:
            A_adj = 0.99
        else:
            A_adj = A

        if N > 0:
            # Упрощенная формула расчета рейтинга для целей
            # Компонент веса целей (W_total)
            if W_total > 0:
                try:
                    weight_component = math.log(W_total + 1, 10) * 10
                except (OverflowError, ValueError):
                    weight_component = math.log(W_total + 1, 10) * 10
            else:
                weight_component = 1.0

            # Компонент точности (A)
            if A > 0:
                accuracy_component = (A_adj + 0.1) / max((1 - A_adj + 0.1), 0.01)
            else:
                accuracy_component = 0.1

            # Компонент количества полетов (N)
            flight_count_component = math.log(N + 1, 10) * 2

            # Итоговый рейтинг
            R = weight_component * accuracy_component * flight_count_component
            
            if R <= 0.0 and N > 0:
                R = 0.01
        else:
            R = 0.0

        return {
            "rating": round(R, 2),
            "K": K,
            "L": L,
            "W_total": W_total,
            "N": N,
            "A": A
        }

