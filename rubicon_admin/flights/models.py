from __future__ import annotations

import re
import uuid
from pathlib import Path

from django.core.validators import MaxValueValidator, MinValueValidator
from django.utils import timezone
from pyproj import Transformer
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.db import models
from django.utils.translation import gettext_lazy as _
import logging
from functools import lru_cache


logger = logging.getLogger(__name__)

# Кеш для Transformer объектов - создаем один раз и переиспользуем
_TRANSFORMER_CACHE = {}

def get_transformer(source_crs, target_crs):
    """Получить кешированный Transformer объект"""
    cache_key = f"{source_crs}_{target_crs}"
    if cache_key not in _TRANSFORMER_CACHE:
        _TRANSFORMER_CACHE[cache_key] = Transformer.from_crs(source_crs, target_crs, always_xy=True)
    return _TRANSFORMER_CACHE[cache_key]


class TimeStampedMixin(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UUIDMixin(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True

class Pilot(TimeStampedMixin, UUIDMixin, models.Model):
    callname = models.CharField(_("Callname"), max_length=255)
    tg_id = models.PositiveBigIntegerField(_("TG ID"), unique=True, null=True, blank=True)
    driver_callname = models.CharField(_("Driver Callname"), max_length=255, null=True, blank=True)
    engineer_callname = models.CharField(_("Engineer Callname"), max_length=255, null=True, blank=True)
    drone_type = models.CharField(_("Drone Type"), max_length=127, null=True, blank=True)
    video_type = models.CharField(_("Video Type"), max_length=255, null=True, blank=True)
    manual_type = models.CharField(_("Manual Type"), max_length=255, null=True, blank=True)

    def __str__(self):
        return self.callname

    class Meta:
        db_table = 'public"."pilot'
        verbose_name = _('pilot')
        verbose_name_plural = _('pilots')
        ordering = ('callname',)

    @property
    def user_username(self):
        if hasattr(self, 'user') and self.user:
            return self.user.username
        return ""

class User(AbstractUser):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    # Опциональная связь с пилотом
    pilot = models.OneToOneField(
        'Pilot',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='user'
    )

    phone = models.CharField(max_length=20, blank=True, null=True)

    # Явно переопределяем поля с уникальными related_name
    groups = models.ManyToManyField(
        Group,
        verbose_name='groups',
        blank=True,
        help_text=(
            'The groups this user belongs to. A user will get all permissions '
            'granted to each of their groups.'
        ),
        related_name='flights_users',  # Уникальное имя вместо 'user_set'
        related_query_name='flights_user',
    )

    user_permissions = models.ManyToManyField(
        Permission,
        verbose_name='user permissions',
        blank=True,
        help_text='Specific permissions for this user.',
        related_name='flights_users',  # Уникальное имя вместо 'user_set'
        related_query_name='flights_user',
    )

    class Meta:
        db_table = 'users'
        verbose_name = _('user')
        verbose_name_plural = _('users')


class DroneTypes(models.TextChoices):
    KT = 'kt', _('kt')
    ST = 'st', _('st')


class Drone(UUIDMixin, TimeStampedMixin):
    name = models.CharField(_('dronetype'), max_length=255)
    description = models.TextField(_('description'), blank=True)
    drone_type = models.CharField(
        _('drone_type'),
        max_length=31,
        choices=DroneTypes.choices
    )

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'public"."drone'
        verbose_name = _('drone')
        verbose_name_plural = _('drones')
        ordering = ('name',)


class ExplosiveType(UUIDMixin, TimeStampedMixin):
    name = models.CharField(_('explosive_type'), max_length=255)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'public"."explosive_type'
        verbose_name = _('explosive type')
        verbose_name_plural = _('explosive types')

class ExplosiveDevice(UUIDMixin, TimeStampedMixin):
    name = models.CharField(_('explosive_device'), max_length=255)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'public"."explosive_device'
        verbose_name = _('explosive device')
        verbose_name_plural = _('explosive devices')

class DirectionType(UUIDMixin, TimeStampedMixin):
    name = models.CharField(_('direction_type'), max_length=255)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'public"."direction_type'
        verbose_name = _('direction type')
        verbose_name_plural = _('direction types')

class TargetType(UUIDMixin, TimeStampedMixin):
    name = models.CharField(_('target_type'), max_length=255)
    weight = models.IntegerField(_('target_value'), default=1, validators=[MinValueValidator(1), MaxValueValidator(10)])

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'public"."target_type'
        verbose_name = _('target type')
        verbose_name_plural = _('target types')

class CorrectiveType(UUIDMixin, TimeStampedMixin):
    name = models.CharField(_('corrective_type'), max_length=255)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'public"."corrective_type'
        verbose_name = _('corrective type')
        verbose_name_plural = _('corrective types')

class FlightResultTypes(models.TextChoices):
    DEFEATED = 'defeated', _('defeated')
    NOT_DEFEATED = 'not defeated', _('not defeated')
    DESTROYED = 'destroyed', _('destroyed')

    @classmethod
    def map_success_values(cls):
        """Результаты, отображаемые на карте по умолчанию (успешные вылеты)."""
        return (cls.DESTROYED, cls.DEFEATED)

    @classmethod
    def result_priority(cls, result):
        """Приоритет результата при дедупликации точек на карте."""
        return {
            cls.DESTROYED: 3,
            cls.DEFEATED: 2,
            cls.NOT_DEFEATED: 1,
        }.get(result, 0)

    @staticmethod
    def map_dedupe_key(flight):
        """Ключ уникальности вылета на карте (повторный импорт Excel)."""
        return (
            str(flight.pilot_id),
            flight.number,
            str(flight.flight_date),
            flight.coordinates or '',
        )

    @classmethod
    def from_excel_text(cls, result_raw):
        """Нормализация значения «Результат применения» из сводной Excel."""
        if not result_raw:
            return cls.NOT_DEFEATED
        result_str = str(result_raw).lower().strip()
        if 'уничтож' in result_str:
            return cls.DESTROYED
        if 'не п' in result_str:
            return cls.NOT_DEFEATED
        if 'не усп' in result_str:
            return cls.NOT_DEFEATED
        if any(
            marker in result_str
            for marker in ('подавл', 'успеш', 'успех', 'пораж', 'доставк')
        ):
            return cls.DEFEATED
        return cls.NOT_DEFEATED

    @classmethod
    def success_category_from_raw(cls, result_raw, result_enum=None, comment=None):
        """Категория KPI только по колонке «Результат применения» (result_raw)."""
        if not result_raw:
            return None
        result_str = str(result_raw).lower().strip()
        if 'уничтож' in result_str or 'не п' in result_str:
            return None
        if 'доставк' in result_str:
            return None
        # KPI «Поражено» — только явное поражение/подавление; «Успешно» не учитываем.
        if 'пораж' in result_str or 'подавл' in result_str:
            return 'porazheno'
        return None


class FlightObjectiveTypes(models.TextChoices):
    EXISTS = 'exists', _('exists')
    NOT_EXISTS = 'not exists', _('not exists')

class Flight(UUIDMixin, TimeStampedMixin):
    number = models.IntegerField(_('flight_number'), validators=[MinValueValidator(0)])
    pilot = models.ForeignKey(Pilot, verbose_name=_('pilot'), on_delete=models.CASCADE, related_name='flights')
    engineer = models.CharField(_('engineer_callname'), max_length=127, null=True, blank=True)
    driver = models.CharField(_('driver_callname'), max_length=127, null=True, blank=True)
    drone = models.CharField(_('drone_type'), max_length=127, null=True, blank=True)
    video = models.CharField(_('video_type'), max_length=63, null=True, blank=True)
    manage = models.CharField(_('manage_type'), max_length=63, null=True, blank=True)
    explosive_type = models.CharField(_('explosive_type'), max_length=127, null=True, blank=True)
    explosive_device = models.CharField(_('explosive_device'), max_length=127, null=True, blank=True)
    flight_date = models.DateField(_('flight_date'))
    flight_time = models.TimeField(_('flight_time'))
    distance = models.CharField(_('distance'), max_length=127, blank=True, null=True)
    video_length = models.CharField(_('video_length'), max_length=127, blank=True, null=True)
    target = models.CharField(_('target_type'), max_length=127, blank=True, null=True)
    application_purpose = models.CharField(
        _('application purpose'),
        max_length=127,
        blank=True,
        null=True,
        help_text=_('Исходный текст «Цель применения» из сводной Excel (колонка N)'),
    )
    corrective = models.CharField(_('corrective_type'), max_length=127, blank=True, null=True)
    result = models.CharField(
        _('result'),
        max_length=31,
        choices=FlightResultTypes.choices,
        default=FlightResultTypes.NOT_DEFEATED,
    )
    result_raw = models.CharField(
        _('result raw'),
        max_length=127,
        blank=True,
        null=True,
        help_text=_('Исходный текст результата из сводной Excel'),
    )
    coordinates = models.CharField(_('coordinates'), max_length=127, null=True, blank=True)
    direction = models.CharField(_('direction'), max_length=255, null=True, blank=True)
    comment = models.CharField(_('comment'), max_length=255, null=True, blank=True)
    drone_remains = models.CharField(_('drone_remains'), max_length=255, null=True, blank=True)
    objective = models.CharField(
        _('objective'),
        max_length=31,
        choices=FlightObjectiveTypes.choices,
        default=FlightObjectiveTypes.NOT_EXISTS
    )

    lat_sk42 = models.FloatField(null=True, blank=True)
    lon_sk42 = models.FloatField(null=True, blank=True)
    lat_wgs84 = models.FloatField(null=True, blank=True)
    lon_wgs84 = models.FloatField(null=True, blank=True)

    @staticmethod
    def _extract_sk42_numbers(coords_raw: str) -> list[float]:
        """Числа из строки координат (игнорируем #VALUE! и прочий мусор из Excel)."""
        cleaned = (
            coords_raw.lower()
            .replace('x', '')
            .replace('y', '')
            .replace('=', '')
            .replace(',', '.')
        )
        return [float(token) for token in re.findall(r'\d+(?:\.\d+)?', cleaned)]

    @staticmethod
    def _normalize_sk42_meters(y_meters: float, x_meters: float) -> tuple[float, float]:
        """Y X в метрах СК-42; восстанавливаем типичные ошибки сводной Excel."""
        # Восток 67xxxxx при севере 52xxxxx — в сводной перепутана «6»/«7» (уезжает к Кишинёву).
        if (5200000 <= y_meters <= 5400000) and (6700000 <= x_meters < 6800000):
            x_corrected = 7270000 + (x_meters - 6700000)
            if 2000000 <= x_corrected <= 9000000:
                logger.info(
                    'Нормализация СК-42: X %s → %s (исправление 67→72)',
                    x_meters,
                    x_corrected,
                )
                x_meters = x_corrected

        if (2000000 <= x_meters <= 9000000) and (4000000 <= y_meters <= 13000000):
            return y_meters, x_meters
        # обрезанный Y (6 цифр): 5361598 736525 → 7365250
        if (2000000 <= x_meters <= 9000000) and (100000 <= y_meters < 1_000_000):
            y_padded = y_meters * 10
            if 4000000 <= y_padded <= 13000000:
                logger.info('Нормализация СК-42: Y %s → %s', y_meters, y_padded)
                return y_padded, x_meters
        # обрезанный X
        if (4000000 <= y_meters <= 13000000) and (100000 <= x_meters < 1_000_000):
            x_padded = x_meters * 10
            if 2000000 <= x_padded <= 9000000:
                logger.info('Нормализация СК-42: X %s → %s', x_meters, x_padded)
                return y_meters, x_padded
        return y_meters, x_meters

    @classmethod
    def normalize_coordinates_field(cls, coords_raw: str) -> str | None:
        """Нормализованная строка «Y X» или None, если восстановить нельзя."""
        numbers = cls._extract_sk42_numbers(coords_raw or '')
        if len(numbers) < 2:
            return None
        y_meters, x_meters = cls._normalize_sk42_meters(numbers[0], numbers[1])
        if not (
            (2000000 <= x_meters <= 9000000)
            and (4000000 <= y_meters <= 13000000)
        ):
            return None
        return f'{int(round(y_meters))} {int(round(x_meters))}'

    def parse_coordinates_sk42(self):
        try:
            if not self.coordinates:
                logger.warning(f"Пустые координаты для полета {self.id}")
                return None, None

            numbers = self._extract_sk42_numbers(self.coordinates)
            if len(numbers) < 2:
                logger.error(
                    f"Недостаточно координат для полета {self.id}: {self.coordinates}",
                )
                return None, None

            # В БД и сводной Excel: «Y X» — сначала север (E), затем восток (F), в метрах СК-42.
            y_meters, x_meters = self._normalize_sk42_meters(numbers[0], numbers[1])

            logger.debug(
                f"Координаты СК-42 (метры): Y(север)={y_meters}, X(восток)={x_meters}",
            )

            if (2000000 <= x_meters <= 9000000) and (4000000 <= y_meters <= 13000000):
                return self.meters_to_degrees_sk42(x_meters, y_meters)

            logger.error(
                f"Невалидные координаты в метрах СК-42: X={x_meters}, Y={y_meters}",
            )
            logger.error('Ожидаемые диапазоны: X(2000000-9000000), Y(4000000-13000000)')
            return None, None

        except (ValueError, AttributeError, IndexError) as e:
            logger.error(f"Ошибка парсинга координат для полета {self.id}: {e}")
            logger.error(f"Координаты: {self.coordinates}")
            return None, None

    def meters_to_degrees_sk42(self, x_meters, y_meters):
        try:
            zone = round(x_meters / 1000000)

            if zone < 1:
                zone = 1
            elif zone > 60:
                zone = 60

            logger.debug(f"Определена зона Гаусса-Крюгера: {zone}")

            # Пробуем преобразование через разные зоны
            priority_zones = [zone, 9, 10, 8, 11, 7, 12, 5, 6, 4]

            for test_zone in priority_zones:
                if test_zone < 1 or test_zone > 60:
                    continue

                try:
                    source_crs = f"EPSG:284{test_zone:02d}"
                    logger.debug(f"Пробуем зону {test_zone} ({source_crs})")

                    transformer = get_transformer(source_crs, "EPSG:4179")
                    lon_deg, lat_deg = transformer.transform(x_meters, y_meters)

                    if (-90 <= lat_deg <= 90) and (-180 <= lon_deg <= 180):
                        logger.debug(
                            f"Успешное преобразование через зону {test_zone}: широта={lat_deg}, долгота={lon_deg}")
                        return lat_deg, lon_deg

                except Exception as zone_error:
                    logger.debug(f"Зона {test_zone} не подошла: {zone_error}")
                    continue

            try:
                transformer = get_transformer("EPSG:28400", "EPSG:4179")
                lon_deg, lat_deg = transformer.transform(x_meters, y_meters)
                if (-90 <= lat_deg <= 90) and (-180 <= lon_deg <= 180):
                    logger.debug(f"Успешное преобразование через общую зону: широта={lat_deg}, долгота={lon_deg}")
                    return lat_deg, lon_deg
            except Exception as general_error:
                logger.error(f"Ошибка преобразования через общую зону: {general_error}")

            logger.error(f"Не удалось преобразовать координаты ни через одну зону")
            return None, None

        except Exception as e:
            logger.error(f"Ошибка преобразования метров в градусы для полета {self.id}: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None, None

    def sk42_to_wgs84(self, lat_sk42, lon_sk42):
        try:
            transformer = get_transformer("EPSG:4179", "EPSG:4326")

            lon_wgs84, lat_wgs84 = transformer.transform(lon_sk42, lat_sk42)

            logger.debug(f"Преобразование: СК-42({lat_sk42}, {lon_sk42}) -> WGS-84({lat_wgs84}, {lon_wgs84})")

            return round(lat_wgs84, 8), round(lon_wgs84, 8)
        except Exception as e:
            logger.error(f"Ошибка преобразования координат для полета {self.id}: {e}")
            return lat_sk42, lon_sk42

    def get_coordinates_info_cached(self):
        if (self.lat_wgs84 is not None and self.lon_wgs84 is not None and
                self.lat_sk42 is not None and self.lon_sk42 is not None):
            if not (self.lat_wgs84 == 90.0 and self.lon_wgs84 == 0.0 and
                    self.lat_sk42 == 90.0 and self.lon_sk42 == 0.0):
                return {
                    'lat_sk42': self.lat_sk42,
                    'lon_sk42': self.lon_sk42,
                    'lat_wgs84': self.lat_wgs84,
                    'lon_wgs84': self.lon_wgs84
                }

        try:
            lat_sk42, lon_sk42 = self.parse_coordinates_sk42()

            if lat_sk42 is not None and lon_sk42 is not None:
                lat_wgs84, lon_wgs84 = self.sk42_to_wgs84(lat_sk42, lon_sk42)

                if lat_wgs84 is not None and lon_wgs84 is not None:
                    self.lat_sk42 = lat_sk42
                    self.lon_sk42 = lon_sk42
                    self.lat_wgs84 = lat_wgs84
                    self.lon_wgs84 = lon_wgs84
                    self.__class__.objects.filter(id=self.id).update(
                        lat_sk42=lat_sk42,
                        lon_sk42=lon_sk42,
                        lat_wgs84=lat_wgs84,
                        lon_wgs84=lon_wgs84
                    )
                else:
                    raise Exception("Ошибка преобразования координат")
            else:
                raise Exception("Ошибка парсинга координат")

        except Exception as e:
            logger.error(f"Ошибка при вычислении координат для полета {self.id}: {e}")
            self.lat_sk42 = 90.0
            self.lon_sk42 = 0.0
            self.lat_wgs84 = 90.0
            self.lon_wgs84 = 0.0
            self.__class__.objects.filter(id=self.id).update(
                lat_sk42=90.0,
                lon_sk42=0.0,
                lat_wgs84=90.0,
                lon_wgs84=0.0
            )

        return {
            'lat_sk42': self.lat_sk42,
            'lon_sk42': self.lon_sk42,
            'lat_wgs84': self.lat_wgs84,
            'lon_wgs84': self.lon_wgs84
        }

    def wgs84_to_sk42(self, lat_wgs84, lon_wgs84):
        try:
            transformer = get_transformer("EPSG:4326", "EPSG:4179")
            lon_sk42, lat_sk42 = transformer.transform(lon_wgs84, lat_wgs84)

            logger.debug(f"WGS-84({lat_wgs84}, {lon_wgs84}) -> СК-42 градусы({lat_sk42}, {lon_sk42})")
            return lat_sk42, lon_sk42
        except Exception as e:
            logger.error(f"Ошибка преобразования WGS-84 в СК-42: {e}")
            return None, None

    def update_coordinates_from_cache(self):
        try:
            if (self.lat_wgs84 is None or self.lon_wgs84 is None or
                    self.lat_wgs84 == 90.0 and self.lon_wgs84 == 0.0):
                logger.warning(f"Нет валидных WGS-84 координат для обновления кэша полета {self.id}")
                return False
            lat_sk42_deg, lon_sk42_deg = self.wgs84_to_sk42(self.lat_wgs84, self.lon_wgs84)

            if lat_sk42_deg is None or lon_sk42_deg is None:
                logger.error(f"Не удалось преобразовать WGS-84 в СК-42 градусы для полета {self.id}")
                return False

            x_meters, y_meters = self.degrees_to_meters_sk42(lon_sk42_deg, lat_sk42_deg)

            if x_meters is None or y_meters is None:
                logger.error(f"Не удалось преобразовать СК-42 градусы в метры для полета {self.id}")
                return False

            self.lat_sk42 = lat_sk42_deg
            self.lon_sk42 = lon_sk42_deg

            self.coordinates = f"{x_meters:.0f} {y_meters:.0f}"

            self.__class__.objects.filter(id=self.id).update(
                lat_sk42=lat_sk42_deg,
                lon_sk42=lon_sk42_deg,
                coordinates=self.coordinates
            )

            logger.debug(f"Координаты успешно обновлены для полета {self.id}: "
                         f"WGS-84({self.lat_wgs84}, {self.lon_wgs84}) → "
                         f"СК-42 градусы({lat_sk42_deg}, {lon_sk42_deg}) → "
                         f"СК-42 метры({x_meters:.0f}, {y_meters:.0f})")

            return True

        except Exception as e:
            logger.error(f"Ошибка при обновлении координат из кэша для полета {self.id}: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False

    def degrees_to_meters_sk42(self, lon_deg, lat_deg):
        try:
            zone = int((lon_deg + 180) / 6) + 1
            if zone < 1:
                zone = 1
            elif zone > 60:
                zone = 60

            logger.debug(f"Определена зона Гаусса-Крюгера для обратного преобразования: {zone}")

            priority_zones = [zone, 7, 6, 5, 4, 9, 10, 8, 11, 7, 12]

            for test_zone in priority_zones:
                if test_zone < 1 or test_zone > 60:
                    continue

                try:
                    target_crs = f"EPSG:284{test_zone:02d}"
                    logger.debug(f"Пробуем зону {test_zone} ({target_crs}) для обратного преобразования")

                    transformer = get_transformer("EPSG:4179", target_crs)

                    x_meters, y_meters = transformer.transform(lon_deg, lat_deg)

                    if (2000000 <= x_meters <= 9000000) and (4000000 <= y_meters <= 13000000):
                        logger.debug(f"Успешное обратное преобразование через зону {test_zone}: "
                                     f"X(восток)={x_meters}, Y(север)={y_meters}")
                        return y_meters, x_meters

                except Exception as zone_error:
                    logger.debug(f"Зона {test_zone} не подошла для обратного преобразования: {zone_error}")
                    continue

            try:
                transformer = get_transformer("EPSG:4179", "EPSG:28400")
                x_meters, y_meters = transformer.transform(lon_deg, lat_deg)

                if (2000000 <= x_meters <= 9000000) and (4000000 <= y_meters <= 13000000):
                    logger.debug(f"Успешное обратное преобразование через общую зону: "
                                 f"X(восток)={x_meters}, Y(север)={y_meters}")
                    return x_meters, y_meters
            except Exception as general_error:
                logger.error(f"Ошибка обратного преобразования через общую зону: {general_error}")

            logger.error(f"Не удалось выполнить обратное преобразование координат")
            return None, None

        except Exception as e:
            logger.error(f"Ошибка преобразования градусов в метры для полета {self.id}: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None, None

    @staticmethod
    def calculate_coordinates_info(flight_instance):
        """Вычисляет координаты для экземпляра полета без обновления БД"""
        try:
            lat_sk42, lon_sk42 = flight_instance.parse_coordinates_sk42()
            if lat_sk42 is not None and lon_sk42 is not None:
                lat_wgs84, lon_wgs84 = flight_instance.sk42_to_wgs84(lat_sk42, lon_sk42)
                if lat_wgs84 is not None and lon_wgs84 is not None:
                    return {
                        'lat_sk42': lat_sk42,
                        'lon_sk42': lon_sk42,
                        'lat_wgs84': lat_wgs84,
                        'lon_wgs84': lon_wgs84
                    }
        except Exception as e:
            logger.error(f"Ошибка при вычислении координат для полета {flight_instance.id}: {e}")
        
        return {
            'lat_sk42': 90.0,
            'lon_sk42': 0.0,
            'lat_wgs84': 90.0,
            'lon_wgs84': 0.0
        }
    
    @classmethod
    def batch_process_coordinates(cls, queryset=None, batch_size=500, update_callback=None):
        """
        Пакетная обработка координат с использованием bulk_update.
        
        Args:
            queryset: QuerySet полетов для обработки (если None, обрабатываются все с координатами)
            batch_size: Размер пакета для bulk_update
            update_callback: Функция обратного вызова для отслеживания прогресса (callback(processed, total))
        
        Returns:
            tuple: (success_count, error_count)
        """
        if queryset is None:
            queryset = cls.objects.filter(
                coordinates__isnull=False
            ).exclude(
                coordinates=''
            ).filter(
                lat_wgs84__isnull=True
            )
        
        total = queryset.count()
        if total == 0:
            return 0, 0
        
        success_count = 0
        error_count = 0
        
        # Обрабатываем батчами
        for offset in range(0, total, batch_size):
            batch_queryset = queryset[offset:offset + batch_size]
            batch_flights = list(batch_queryset)
            
            flights_to_update = []
            
            for flight in batch_flights:
                try:
                    coord_info = cls.calculate_coordinates_info(flight)
                    
                    # Пропускаем дефолтные координаты (90.0, 0.0)
                    if not (coord_info['lat_wgs84'] == 90.0 and coord_info['lon_wgs84'] == 0.0):
                        flight.lat_sk42 = coord_info['lat_sk42']
                        flight.lon_sk42 = coord_info['lon_sk42']
                        flight.lat_wgs84 = coord_info['lat_wgs84']
                        flight.lon_wgs84 = coord_info['lon_wgs84']
                        flights_to_update.append(flight)
                        success_count += 1
                    else:
                        error_count += 1
                except Exception as e:
                    logger.error(f"Ошибка обработки координат для полета {flight.id}: {e}")
                    error_count += 1
                    continue
            
            # Обновляем батч через bulk_update
            if flights_to_update:
                try:
                    cls.objects.bulk_update(
                        flights_to_update,
                        ['lat_sk42', 'lon_sk42', 'lat_wgs84', 'lon_wgs84'],
                        batch_size=batch_size
                    )
                    logger.info(f"Обновлено координат: {len(flights_to_update)} полетов (батч {offset//batch_size + 1})")
                except Exception as bulk_error:
                    logger.error(f"Ошибка bulk_update координат: {bulk_error}", exc_info=True)
                    error_count += len(flights_to_update)
                    success_count -= len(flights_to_update)
            
            # Вызываем callback для отслеживания прогресса
            if update_callback:
                update_callback(offset + len(batch_flights), total)
        
        return success_count, error_count

    class Meta:
        db_table = 'public"."flight'
        verbose_name = _('flight')
        verbose_name_plural = _('flights')
        ordering = ['-created']


def map_layer_upload_to(instance, filename: str) -> str:
    return f'map_layers/{instance.id or "new"}/{filename}'


class MapLayer(TimeStampedMixin, UUIDMixin, models.Model):
    """Пользовательский слой карты (LDK/KML/KMZ/GPX/GeoJSON)."""

    name = models.CharField(_('name'), max_length=255)
    description = models.TextField(_('description'), blank=True)
    source_file = models.FileField(
        _('source file'),
        upload_to=map_layer_upload_to,
        help_text=_('LDK, KML, KMZ, GPX или GeoJSON'),
    )
    file_format = models.CharField(_('file format'), max_length=16, blank=True)
    geojson = models.JSONField(_('geojson'), null=True, blank=True)
    feature_count = models.PositiveIntegerField(_('feature count'), default=0)
    conversion_error = models.TextField(_('conversion error'), blank=True)
    converted_at = models.DateTimeField(_('converted at'), null=True, blank=True)
    is_active = models.BooleanField(_('is active'), default=True, db_index=True)
    sort_order = models.IntegerField(_('sort order'), default=0, db_index=True)
    color = models.CharField(_('color'), max_length=7, default='#00BFFF')
    stroke_width = models.PositiveSmallIntegerField(
        _('stroke width'),
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(12)],
    )
    opacity = models.FloatField(
        _('opacity'),
        default=0.85,
        validators=[MinValueValidator(0.1), MaxValueValidator(1.0)],
    )

    class Meta:
        db_table = 'map_layer'
        verbose_name = _('map layer')
        verbose_name_plural = _('map layers')
        ordering = ('sort_order', 'name')

    def __str__(self):
        return self.name

    def process_source_file(self, save: bool = True) -> None:
        from flights.utils.map_layer_convert import convert_layer_file, detect_format

        if not self.source_file:
            raise ValueError('Файл слоя не загружен')

        path = Path(self.source_file.path)
        self.file_format = detect_format(path.name)
        geojson = convert_layer_file(path, self.file_format)
        self.geojson = geojson
        self.feature_count = len(geojson.get('features') or [])
        self.conversion_error = ''
        self.converted_at = timezone.now()
        if save:
            self.save(
                update_fields=[
                    'file_format', 'geojson', 'feature_count',
                    'conversion_error', 'converted_at', 'modified',
                ],
            )


class ImportProgress(TimeStampedMixin, UUIDMixin, models.Model):
    """Модель для хранения прогресса импорта Excel файлов"""
    file_name = models.CharField(_('file_name'), max_length=255, db_index=True)
    file_size = models.BigIntegerField(_('file_size'), help_text=_('Размер файла в байтах'))
    file_hash = models.CharField(_('file_hash'), max_length=64, db_index=True, help_text=_('MD5 hash файла для идентификации'))
    last_processed_row = models.IntegerField(_('last_processed_row'), default=0, help_text=_('Последняя обработанная строка'))
    total_rows = models.IntegerField(_('total_rows'), default=0, help_text=_('Общее количество строк в файле'))
    total_created = models.IntegerField(_('total_created'), default=0, help_text=_('Всего создано записей'))
    is_completed = models.BooleanField(_('is_completed'), default=False, help_text=_('Импорт завершен'))
    last_import_date = models.DateTimeField(_('last_import_date'), auto_now=True, help_text=_('Дата последнего импорта'))
    
    class Meta:
        db_table = 'import_progress'
        verbose_name = _('import_progress')
        verbose_name_plural = _('import_progresses')
        ordering = ['-last_import_date']
        unique_together = [['file_name', 'file_hash']]
    
    def __str__(self):
        status = "✓" if self.is_completed else "⏳"
        return f"{status} {self.file_name} (строка {self.last_processed_row}/{self.total_rows})"


class LiveFlightCloseReason(models.TextChoices):
    STOP = 'stop', _('Stop')
    NEW_START = 'new_start', _('New start')
    TIMEOUT = 'timeout', _('Timeout')


class LiveFlight(UUIDMixin, TimeStampedMixin):
    """Оперативный вылет из Telegram (Старт/Стоп)."""
    pilot = models.ForeignKey(
        Pilot,
        verbose_name=_('pilot'),
        on_delete=models.CASCADE,
        related_name='live_flights',
    )
    telegram_user_id = models.PositiveBigIntegerField(_('telegram user id'), db_index=True)
    chat_id = models.BigIntegerField(_('chat id'))
    started_at = models.DateTimeField(_('started at'), db_index=True)
    ended_at = models.DateTimeField(_('ended at'), null=True, blank=True, db_index=True)
    close_reason = models.CharField(
        _('close reason'),
        max_length=16,
        choices=LiveFlightCloseReason.choices,
        null=True,
        blank=True,
    )
    message_id_start = models.BigIntegerField(null=True, blank=True)
    message_id_stop = models.BigIntegerField(null=True, blank=True)

    class Meta:
        db_table = 'public"."live_flight'
        verbose_name = _('live flight')
        verbose_name_plural = _('live flights')
        ordering = ('-started_at',)

    def __str__(self):
        return f'{self.pilot.callname} {self.started_at}'


class DashboardAlert(UUIDMixin, TimeStampedMixin):
    """Оповещение из топика Telegram (дашборд)."""
    chat_id = models.BigIntegerField(_('chat id'))
    message_thread_id = models.BigIntegerField(_('topic id'), null=True, blank=True)
    telegram_message_id = models.BigIntegerField(_('telegram message id'))
    text = models.TextField(_('text'))
    posted_at = models.DateTimeField(_('posted at'), db_index=True)

    class Meta:
        db_table = 'public"."dashboard_alert'
        verbose_name = _('dashboard alert')
        verbose_name_plural = _('dashboard alerts')
        ordering = ('-posted_at',)
        constraints = [
            models.UniqueConstraint(
                fields=['chat_id', 'telegram_message_id'],
                name='dashboard_alert_chat_message_uniq',
            ),
        ]

    def __str__(self):
        preview = (self.text or '')[:60]
        return f'{self.posted_at} {preview}'


class TelegramFlightReport(UUIDMixin, TimeStampedMixin):
    """Вылет из Telegram-отчёта (топик 2406 — короткий формат)."""
    chat_id = models.BigIntegerField(_('chat id'), db_index=True)
    message_thread_id = models.BigIntegerField(_('topic id'), null=True, blank=True, db_index=True)
    telegram_message_id = models.BigIntegerField(_('telegram message id'))
    flight_number = models.IntegerField(_('flight number'), default=0)
    work_date = models.CharField(_('work date'), max_length=32, blank=True)
    result = models.CharField(_('result'), max_length=512, blank=True)
    pilot_callsign = models.CharField(_('pilot callsign'), max_length=255, blank=True)
    is_successful = models.BooleanField(_('is successful'), default=False, db_index=True)
    parse_ok = models.BooleanField(_('parse ok'), default=True)
    sent_at = models.DateTimeField(_('sent at'), db_index=True)
    raw_text = models.TextField(_('raw text'), blank=True)
    coordinates_sk42 = models.CharField(_('coordinates sk42'), max_length=64, blank=True)
    lat_wgs84 = models.FloatField(_('latitude wgs84'), null=True, blank=True, db_index=True)
    lon_wgs84 = models.FloatField(_('longitude wgs84'), null=True, blank=True, db_index=True)
    target_type = models.CharField(_('target type'), max_length=255, blank=True)
    telegram_file_id = models.CharField(_('telegram file id'), max_length=255, blank=True)
    video_mime = models.CharField(_('video mime'), max_length=127, blank=True)
    video_size = models.PositiveBigIntegerField(_('video size'), null=True, blank=True)
    video_duration = models.PositiveIntegerField(_('video duration sec'), null=True, blank=True)
    local_video_path = models.CharField(_('local video path'), max_length=512, blank=True)
    video_downloaded_at = models.DateTimeField(_('video downloaded at'), null=True, blank=True)

    class Meta:
        db_table = 'public"."telegram_flight_report'
        verbose_name = _('telegram flight report')
        verbose_name_plural = _('telegram flight reports')
        ordering = ('-sent_at',)
        constraints = [
            models.UniqueConstraint(
                fields=['chat_id', 'telegram_message_id'],
                name='telegram_flight_report_chat_msg_uniq',
            ),
        ]

    def __str__(self):
        return f'№{self.flight_number} {self.work_date} {self.result[:40]}'


class OperatorPlacementZone(models.TextChoices):
    DAY = 'day', _('Дневная смена')
    NIGHT = 'night', _('Ночная смена')
    DETACHMENT = 'detachment', _('Отрыв')


class OperatorCommLink(models.TextChoices):
    STARLINK = 'starlink', 'StarLink'
    BSHPD = 'bshpd', 'БШПД'
    OPTICS = 'optics', 'Оптика'
    LTE = 'lte', 'LTE'
    SKS = 'sks', 'СКС'
    RJ45 = 'rj45', 'RJ45'
    P274M = 'p274m', 'П-274М'


class OperatorLocation(UUIDMixin, TimeStampedMixin):
    """Справочник точек размещения операторов."""
    name = models.CharField(_('Название'), max_length=255, unique=True)
    description = models.TextField(_('Описание'), blank=True)
    senior = models.ForeignKey(
        Pilot,
        verbose_name=_('Старший (ответственный)'),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='operator_locations_led',
    )
    sort_order = models.IntegerField(_('Порядок сортировки'), default=0, db_index=True)
    is_active = models.BooleanField(_('Активна'), default=True, db_index=True)
    comm_links = models.JSONField(_('Связь'), default=list, blank=True)

    class Meta:
        db_table = 'public"."operator_location'
        verbose_name = _('Расположение')
        verbose_name_plural = _('Расположения')
        ordering = ('sort_order', 'name')

    def __str__(self):
        return self.name


class OperatorProfile(UUIDMixin, TimeStampedMixin):
    """Оператор на дашборде размещения (пилот из общей базы)."""
    pilot = models.OneToOneField(
        Pilot,
        verbose_name=_('Пилот'),
        on_delete=models.CASCADE,
        related_name='operator_profile',
    )
    senior = models.ForeignKey(
        Pilot,
        verbose_name=_('Старший (ответственный)'),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='operator_team_members',
    )
    location = models.ForeignKey(
        OperatorLocation,
        verbose_name=_('Расположение'),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='operators',
    )
    is_active = models.BooleanField(_('Активен'), default=True, db_index=True)
    placement_zone = models.CharField(
        _('Зона размещения'),
        max_length=16,
        choices=OperatorPlacementZone.choices,
        default=OperatorPlacementZone.DAY,
        db_index=True,
    )
    day_shift_start = models.TimeField(_('Начало дневной смены'), null=True, blank=True)
    day_shift_end = models.TimeField(_('Конец дневной смены'), null=True, blank=True)
    night_shift_start = models.TimeField(_('Начало ночной смены'), null=True, blank=True)
    night_shift_end = models.TimeField(_('Конец ночной смены'), null=True, blank=True)
    duty_started_at = models.DateTimeField(_('Начало дежурства'), null=True, blank=True)
    notes = models.TextField(_('Примечания'), blank=True)

    class Meta:
        db_table = 'public"."operator_profile'
        verbose_name = _('Дежурство пилота')
        verbose_name_plural = _('Пилоты на дежурстве')
        ordering = ('senior__callname', 'pilot__callname')

    def __str__(self):
        if self.pilot_id:
            try:
                return self.pilot.callname
            except self.pilot.RelatedObjectDoesNotExist:
                pass
        return str(self.pk)

    @property
    def drone_type_display(self):
        return self.pilot.drone_type or '—'

    @property
    def location_label(self):
        return self.location.name if self.location_id else '—'


class OperatorPositionLog(UUIDMixin, models.Model):
    """История перемещений оператора."""
    profile = models.ForeignKey(
        OperatorProfile,
        verbose_name=_('Оператор'),
        on_delete=models.CASCADE,
        related_name='position_logs',
    )
    placement_zone = models.CharField(
        _('Зона размещения'),
        max_length=16,
        choices=OperatorPlacementZone.choices,
    )
    location = models.ForeignKey(
        OperatorLocation,
        verbose_name=_('Расположение'),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='position_logs',
    )
    location_label = models.CharField(_('Расположение (текст)'), max_length=255, blank=True)
    recorded_at = models.DateTimeField(_('Время записи'), default=timezone.now, db_index=True)
    recorded_by = models.ForeignKey(
        User,
        verbose_name=_('Кто изменил'),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='operator_position_logs',
    )
    comment = models.CharField(_('Комментарий'), max_length=512, blank=True)

    class Meta:
        db_table = 'public"."operator_position_log'
        verbose_name = _('история перемещения')
        verbose_name_plural = _('история перемещений')
        ordering = ('-recorded_at',)

    def __str__(self):
        return f'{self.profile} {self.recorded_at:%d.%m.%Y %H:%M}'

