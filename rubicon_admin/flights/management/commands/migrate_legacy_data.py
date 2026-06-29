from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.dateparse import parse_date, parse_time
from django.utils.translation import gettext_lazy as _
import csv
import uuid
from flights.models import Flight, Pilot, FlightResultTypes, FlightObjectiveTypes, Drone, ExplosiveType, \
    ExplosiveDevice, TargetType, CorrectiveType, DroneTypes


class Command(BaseCommand):
    help = 'Миграция данных из старой базы CSV файлов'

    def add_arguments(self, parser):
        parser.add_argument('--pilots_file', type=str, default='pilots.csv',
                            help='Путь к CSV файлу пилотов')
        parser.add_argument('--flights_file', type=str, default='flights.csv',
                            help='Путь к CSV файлу полетов')
        parser.add_argument('--drones_file', type=str, default='drones.csv',
                            help='Путь к CSV файлу типов дронов')
        parser.add_argument('--explosives_types_file', type=str, default='explosives_types.csv',
                            help='Путь к CSV файлу типов взрывчатых веществ')
        parser.add_argument('--explosives_devices_file', type=str, default='explosives_devices.csv',
                            help='Путь к CSV файлу взрывных устройств')
        parser.add_argument('--targets_file', type=str, default='targets.csv',
                            help='Путь к CSV файлу типов целей')
        parser.add_argument('--correctives_file', type=str, default='correctives.csv',
                            help='Путь к CSV файлу типов корректировок')

    def handle(self, *args, **options):
        self.stdout.write('Начало миграции данных из CSV файлов...')

        try:
            with transaction.atomic():
                # Мигрируем справочники первыми
                self.migrate_drones(options['drones_file'])
                self.migrate_explosive_types(options['explosives_types_file'])
                self.migrate_explosive_devices(options['explosives_devices_file'])
                self.migrate_target_types(options['targets_file'])
                self.migrate_corrective_types(options['correctives_file'])

                # Мигрируем основные данные
                pilot_mapping = self.migrate_pilots(options['pilots_file'])
                flights_count = self.migrate_flights(options['flights_file'], pilot_mapping)

            self.stdout.write(
                self.style.SUCCESS(
                    f'Миграция успешно завершена! Мигрировано: {len(pilot_mapping)} пилотов, {flights_count} полетов')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Ошибка миграции: {str(e)}')
            )
            import traceback
            self.stdout.write(self.style.ERROR(traceback.format_exc()))
            raise

    def migrate_drones(self, drones_file):
        """Миграция типов дронов из CSV файла"""
        drones_count = 0

        try:
            with open(drones_file, 'r', encoding='utf-8') as file:
                sample = file.read(1024)
                file.seek(0)
                delimiter = ',' if ',' in sample else ';'

                reader = csv.DictReader(file, delimiter=delimiter)

                for row in reader:
                    try:
                        drone_name = row['name'].strip()
                        if drone_name:
                            drone, created = Drone.objects.get_or_create(
                                name=drone_name,
                                defaults={
                                    'id': uuid.uuid4(),
                                    'description': f"Импортированный тип дрона: {drone_name}",
                                    'drone_type': DroneTypes.KT  # Всегда KT
                                }
                            )

                            # Если уже существует, проверяем и обновляем тип если нужно
                            if not created and drone.drone_type != DroneTypes.KT:
                                drone.drone_type = DroneTypes.KT
                                drone.save()
                                self.stdout.write(f'Обновлен тип дрона: {drone.name} (Тип: {drone.drone_type})')
                            elif created:
                                drones_count += 1
                                self.stdout.write(f'Создан тип дрона: {drone.name} (Тип: {drone.drone_type})')

                    except Exception as e:
                        self.stdout.write(
                            self.style.WARNING(f'Ошибка обработки типа дрона {row.get("name", "unknown")}: {e}')
                        )
                        continue

        except FileNotFoundError:
            self.stdout.write(
                self.style.WARNING(f'Файл типов дронов не найден: {drones_file}')
            )
            return 0
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Ошибка при чтении файла типов дронов: {e}')
            )
            return 0

        self.stdout.write(f'Обработано типов дронов: {drones_count}')
        return drones_count

    def migrate_explosive_types(self, explosives_types_file):
        """Миграция типов взрывчатых веществ из CSV файла"""
        et_count = 0

        try:
            with open(explosives_types_file, 'r', encoding='utf-8') as file:
                sample = file.read(1024)
                file.seek(0)
                delimiter = ',' if ',' in sample else ';'

                reader = csv.DictReader(file, delimiter=delimiter)

                for row in reader:
                    try:
                        et_name = row['name'].strip()
                        if et_name:
                            explosive_type, created = ExplosiveType.objects.get_or_create(
                                name=et_name,
                                defaults={
                                    'id': uuid.uuid4()
                                }
                            )

                            if created:
                                et_count += 1
                                self.stdout.write(f'Создан тип ВВ: {explosive_type.name}')

                    except Exception as e:
                        self.stdout.write(
                            self.style.WARNING(f'Ошибка обработки типа ВВ {row.get("name", "unknown")}: {e}')
                        )
                        continue

        except FileNotFoundError:
            self.stdout.write(
                self.style.WARNING(f'Файл типов ВВ не найден: {explosives_types_file}')
            )
            return 0
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Ошибка при чтении файла типов ВВ: {e}')
            )
            return 0

        self.stdout.write(f'Обработано типов ВВ: {et_count}')
        return et_count

    def migrate_explosive_devices(self, explosives_devices_file):
        """Миграция взрывных устройств из CSV файла"""
        ed_count = 0

        try:
            with open(explosives_devices_file, 'r', encoding='utf-8') as file:
                sample = file.read(1024)
                file.seek(0)
                delimiter = ',' if ',' in sample else ';'

                reader = csv.DictReader(file, delimiter=delimiter)

                for row in reader:
                    try:
                        ed_name = row['name'].strip()
                        if ed_name:
                            explosive_device, created = ExplosiveDevice.objects.get_or_create(
                                name=ed_name,
                                defaults={
                                    'id': uuid.uuid4()
                                }
                            )

                            if created:
                                ed_count += 1
                                self.stdout.write(f'Создано ВУ: {explosive_device.name}')

                    except Exception as e:
                        self.stdout.write(
                            self.style.WARNING(f'Ошибка обработки ВУ {row.get("name", "unknown")}: {e}')
                        )
                        continue

        except FileNotFoundError:
            self.stdout.write(
                self.style.WARNING(f'Файл ВУ не найден: {explosives_devices_file}')
            )
            return 0
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Ошибка при чтении файла ВУ: {e}')
            )
            return 0

        self.stdout.write(f'Обработано ВУ: {ed_count}')
        return ed_count

    def migrate_target_types(self, targets_file):
        """Миграция типов целей из CSV файла"""
        tt_count = 0

        try:
            with open(targets_file, 'r', encoding='utf-8') as file:
                sample = file.read(1024)
                file.seek(0)
                delimiter = ',' if ',' in sample else ';'

                reader = csv.DictReader(file, delimiter=delimiter)

                for row in reader:
                    try:
                        tt_name = row['name'].strip()
                        if tt_name:
                            target_type, created = TargetType.objects.get_or_create(
                                name=tt_name,
                                defaults={
                                    'id': uuid.uuid4()
                                }
                            )

                            if created:
                                tt_count += 1
                                self.stdout.write(f'Создан тип цели: {target_type.name}')

                    except Exception as e:
                        self.stdout.write(
                            self.style.WARNING(f'Ошибка обработки типа цели {row.get("name", "unknown")}: {e}')
                        )
                        continue

        except FileNotFoundError:
            self.stdout.write(
                self.style.WARNING(f'Файл типов целей не найден: {targets_file}')
            )
            return 0
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Ошибка при чтении файла типов целей: {e}')
            )
            return 0

        self.stdout.write(f'Обработано типов целей: {tt_count}')
        return tt_count

    def migrate_corrective_types(self, correctives_file):
        """Миграция типов корректировок из CSV файла"""
        ct_count = 0

        try:
            with open(correctives_file, 'r', encoding='utf-8') as file:
                sample = file.read(1024)
                file.seek(0)
                delimiter = ',' if ',' in sample else ';'

                reader = csv.DictReader(file, delimiter=delimiter)

                for row in reader:
                    try:
                        ct_name = row['name'].strip()
                        if ct_name:
                            corrective_type, created = CorrectiveType.objects.get_or_create(
                                name=ct_name,
                                defaults={
                                    'id': uuid.uuid4()
                                }
                            )

                            if created:
                                ct_count += 1
                                self.stdout.write(f'Создан тип корректировки: {corrective_type.name}')

                    except Exception as e:
                        self.stdout.write(
                            self.style.WARNING(f'Ошибка обработки типа корректировки {row.get("name", "unknown")}: {e}')
                        )
                        continue

        except FileNotFoundError:
            self.stdout.write(
                self.style.WARNING(f'Файл типов корректировок не найден: {correctives_file}')
            )
            return 0
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Ошибка при чтении файла типов корректировок: {e}')
            )
            return 0

        self.stdout.write(f'Обработано типов корректировок: {ct_count}')
        return ct_count

    def migrate_pilots(self, pilots_file):
        """Миграция пилотов из CSV файла"""
        pilot_mapping = {}
        pilots_created = 0

        try:
            with open(pilots_file, 'r', encoding='utf-8') as file:
                sample = file.read(1024)
                file.seek(0)
                delimiter = ',' if ',' in sample else ';'

                reader = csv.DictReader(file, delimiter=delimiter)

                for row in reader:
                    try:
                        tg_id = None
                        if row['tg_id'] and row['tg_id'].isdigit():
                            tg_id = int(row['tg_id'])

                        pilot_defaults = {
                            'id': uuid.uuid4(),
                            'callname': row['callname'] or '',
                            'driver_callname': row['driver_callname'] or '',
                            'engineer_callname': row['engineer_callname'] or '',
                            'drone_type': row['dronetype'] or '',
                            'video_type': row['video'] or '',
                            'manual_type': row['manage'] or '',
                        }

                        if tg_id:
                            pilot, created = Pilot.objects.get_or_create(
                                tg_id=tg_id,
                                defaults=pilot_defaults
                            )
                        else:
                            pilot, created = Pilot.objects.get_or_create(
                                callname=row['callname'],
                                defaults=pilot_defaults
                            )

                        pilot_mapping[row['idx']] = pilot.id

                        if created:
                            pilots_created += 1
                            self.stdout.write(f'Создан пилот: {pilot.callname}')
                        else:
                            self.stdout.write(f'Найден существующий пилот: {pilot.callname}')

                    except Exception as e:
                        self.stdout.write(
                            self.style.WARNING(f'Ошибка обработки пилота {row.get("callname", "unknown")}: {e}')
                        )
                        continue

        except FileNotFoundError:
            self.stdout.write(
                self.style.ERROR(f'Файл пилотов не найден: {pilots_file}')
            )
            return {}
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Ошибка при чтении файла пилотов: {e}')
            )
            return {}

        self.stdout.write(
            f'Обработано пилотов: {pilots_created} новых, {len(pilot_mapping) - pilots_created} существующих')
        return pilot_mapping

    def migrate_flights(self, flights_file, pilot_mapping):
        """Миграция полетов из CSV файла"""
        flights_count = 0

        try:
            with open(flights_file, 'r', encoding='utf-8') as file:
                sample = file.read(1024)
                file.seek(0)
                delimiter = ',' if ',' in sample else ';'

                reader = csv.DictReader(file, delimiter=delimiter)

                for row in reader:
                    try:
                        old_pilot_id = row['flyer_id']
                        pilot_uuid = pilot_mapping.get(old_pilot_id)

                        if not pilot_uuid:
                            self.stdout.write(
                                self.style.WARNING(f'Пропущен полет {row["idx"]}: пилот с ID {old_pilot_id} не найден')
                            )
                            continue

                        flight_date = None
                        if row['fly_date']:
                            try:
                                flight_date = parse_date(row['fly_date'])
                            except (ValueError, TypeError):
                                self.stdout.write(
                                    self.style.WARNING(
                                        f'Неверный формат даты для полета {row["idx"]}: {row["fly_date"]}')
                                )
                                flight_date = '2024-01-01'

                        flight_time = None
                        if row['fly_time']:
                            try:
                                flight_time = parse_time(row['fly_time'])
                            except (ValueError, TypeError):
                                self.stdout.write(
                                    self.style.WARNING(
                                        f'Неверный формат времени для полета {row["idx"]}: {row["fly_time"]}')
                                )

                        coordinates = self.format_coordinates(row['coordinates'], row['coordinatesY'])
                        result = self.map_result(row['correction'], row['result'])
                        objective = self.map_objective(row['objective_control'])
                        drone_remains = self.map_remains(row['remains'])

                        flight = Flight.objects.create(
                            id=uuid.uuid4(),
                            pilot_id=pilot_uuid,
                            number=int(row['fly_number']) if row['fly_number'] and row['fly_number'].isdigit() else 0,
                            engineer=row['engineer_callname'] or '',
                            driver=row['driver_callname'] or '',
                            drone=row['dron_model'] or '',
                            video=row['video'] or '',
                            manage=row['manage'] or '',
                            explosive_type=row['explosives_type'] or '',
                            explosive_device=row['explosives_device'] or '',
                            flight_date=flight_date or '2024-01-01',
                            flight_time=flight_time,
                            distance=row['distance'] or '',
                            target=row['target'] or '',
                            corrective=row['correction'] or '',
                            result=result,
                            coordinates=coordinates,
                            direction=row['direction'] or '',
                            comment=row['comment'] or '',
                            drone_remains=drone_remains,
                            objective=objective,
                        )

                        flights_count += 1

                        if flights_count % 100 == 0:
                            self.stdout.write(f'Обработано полетов: {flights_count}')

                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(f'Ошибка миграции полета {row["idx"]}: {str(e)}')
                        )
                        import traceback
                        self.stdout.write(self.style.ERROR(traceback.format_exc()))
                        continue

        except FileNotFoundError:
            self.stdout.write(
                self.style.ERROR(f'Файл полетов не найден: {flights_file}')
            )
            return 0
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Ошибка при чтении файла полетов: {e}')
            )
            return 0

        self.stdout.write(f'Всего мигрировано полетов: {flights_count}')
        return flights_count

    def format_coordinates(self, coord_x, coord_y):
        """Форматирование координат в формат Y, X"""
        if coord_y and coord_x:
            x_parts = coord_x.strip().split()
            y_parts = coord_y.strip().split()

            if len(x_parts) >= 2 and len(y_parts) >= 2:
                x_coord = x_parts[0]
                y_coord = y_parts[0]
                return f"{y_coord}, {x_coord}"
            else:
                return f"{coord_y.strip()}, {coord_x.strip()}"
        elif coord_y:
            return coord_y.strip()
        elif coord_x:
            return coord_x.strip()
        return ""

    def map_result(self, correction, result_field):
        """Преобразование результата из старой системы в новую"""
        if correction:
            if 'попадание' in correction.lower():
                return FlightResultTypes.DEFEATED
            elif 'промах' in correction.lower():
                return FlightResultTypes.NOT_DEFEATED
            else:
                return FlightResultTypes.NOT_DEFEATED
        elif result_field and result_field.lower() == 'true':
            return FlightResultTypes.DEFEATED
        else:
            return FlightResultTypes.NOT_DEFEATED

    def map_objective(self, objective_control):
        """Преобразование objective из старой системы в новую"""
        if objective_control and objective_control.lower() == 'f':
            return FlightObjectiveTypes.NOT_EXISTS
        elif objective_control and objective_control.lower() in ['t', 'true']:
            return FlightObjectiveTypes.EXISTS
        else:
            return FlightObjectiveTypes.NOT_EXISTS

    def map_remains(self, remains_field):
        """Преобразование remains из старой системы в новую"""
        if remains_field and remains_field.lower() == 'true':
            return "Да"
        elif remains_field and remains_field.lower() == 'false':
            return "Нет"
        else:
            return remains_field or "Не указано"