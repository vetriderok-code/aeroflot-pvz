from django.core.management.base import BaseCommand
from django.db import transaction
from flights.models import Flight
import re


class Command(BaseCommand):
    help = 'Нормализация данных целей и дронов в существующих полетах'

    def normalize_target_name(self, target_name):
        """Нормализует название цели для объединения дубликатов"""
        if not target_name:
            return None
        target_str = str(target_name).strip()
        if not target_str:
            return None
        
        target_lower = target_str.lower()
        # Удаляем лишние пробелы, дефисы, точки, запятые
        target_normalized = re.sub(r'[-\s\.\,]+', ' ', target_lower).strip()
        
        # Объединяем похожие варианты
        # Автомобильная техника
        if any(word in target_normalized for word in ['автомобильн', 'автотехник', 'авто техник', 'авто-техник']):
            return 'Автомобильная техника'
        # ПВХ
        if 'пвх' in target_normalized:
            match = re.search(r'пвх\s*[-\s]*(\d+[и]?)', target_normalized, re.IGNORECASE)
            if match:
                return f"ПВХ-{match.group(1).upper()}"
            return 'ПВХ'
        
        # Общая нормализация
        normalized = re.sub(r'[^\w\s]', '', target_str)
        normalized = ' '.join(normalized.split())
        if normalized:
            normalized = normalized[0].upper() + normalized[1:].lower() if len(normalized) > 1 else normalized.upper()
        return normalized if normalized else None

    def normalize_drone_name(self, drone_name):
        """Нормализует название дрона для объединения дубликатов"""
        if not drone_name:
            return None
        drone_str = str(drone_name).strip()
        if not drone_str:
            return None
        
        drone_lower = drone_str.lower()
        # Удаляем лишние пробелы, дефисы, точки, запятые
        drone_normalized = re.sub(r'[-\s\.\,]+', ' ', drone_lower).strip()
        
        # Объединяем похожие варианты
        # ПВХ
        if 'пвх' in drone_normalized:
            match = re.search(r'пвх\s*[-\s]*(\d+[и]?)', drone_normalized, re.IGNORECASE)
            if match:
                return f"ПВХ-{match.group(1).upper()}"
            return 'ПВХ'
        # Молния
        if 'молния' in drone_normalized:
            match = re.search(r'молния\s*[-\s]*(\d+[дт]?)', drone_normalized, re.IGNORECASE)
            if match:
                return f"Молния-{match.group(1).upper()}"
            return 'Молния'
        # КВН - преобразуем все варианты в два: КВН или КВН-Т
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
        
        # Общая нормализация для остальных дронов
        normalized = re.sub(r'[^\w\s]', '', drone_str)
        normalized = ' '.join(normalized.split())
        if normalized:
            normalized = normalized[0].upper() + normalized[1:].lower() if len(normalized) > 1 else normalized.upper()
        return normalized if normalized else None

    def handle(self, *args, **options):
        self.stdout.write('Начало нормализации данных целей и дронов...')
        
        flights = Flight.objects.all()
        total = flights.count()
        self.stdout.write(f'Найдено полетов: {total}')
        
        updated_targets = 0
        updated_drones = 0
        batch_size = 500
        
        for i in range(0, total, batch_size):
            batch = flights[i:i + batch_size]
            
            with transaction.atomic():
                for flight in batch:
                    updated = False
                    
                    # Нормализуем цель
                    if flight.target:
                        normalized_target = self.normalize_target_name(flight.target)
                        if normalized_target and normalized_target != flight.target:
                            flight.target = normalized_target
                            updated = True
                            updated_targets += 1
                    
                    # Нормализуем дрон
                    if flight.drone:
                        normalized_drone = self.normalize_drone_name(flight.drone)
                        if normalized_drone and normalized_drone != flight.drone:
                            flight.drone = normalized_drone
                            updated = True
                            updated_drones += 1
                    
                    if updated:
                        flight.save(update_fields=['target', 'drone'])
            
            if (i + batch_size) % 1000 == 0:
                self.stdout.write(f'Обработано: {min(i + batch_size, total)}/{total}')
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Нормализация завершена! Обновлено целей: {updated_targets}, дронов: {updated_drones}'
            )
        )











