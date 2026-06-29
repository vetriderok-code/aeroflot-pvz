"""Импорт из Расчёты.xlsx: расположения (I/J) и/или пилоты с дежурствами."""
from __future__ import annotations

import os

from django.core.management.base import BaseCommand, CommandError

from flights.utils.raschety_pilot_import import (
    SHEET_NAME,
    assign_pilot_groups_from_raschety,
    assign_pilot_locations_from_raschety,
    import_pilots_from_raschety,
    read_raschety_rows,
    replace_locations_from_raschety,
    update_locations_comm_links_from_raschety,
)
from flights.utils.operator_dashboard import comm_link_labels


class Command(BaseCommand):
    help = (
        'Импорт из Excel (лист «Расчёты»). '
        'По умолчанию — синхронизация дежурства: снять всех, поставить пилотов из A '
        '(сапёр C, смена E, дрон G если есть в базе). '
        'С --locations-only / --comm-links-only — только расположения.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            default='/data/Обмен/Расчёты.xlsx',
            help='Путь к файлу Расчёты.xlsx.',
        )
        parser.add_argument(
            '--sheet',
            type=str,
            default=SHEET_NAME,
            help=f'Имя листа (по умолчанию «{SHEET_NAME}»).',
        )
        parser.add_argument(
            '--locations-only',
            action='store_true',
            help='Только расположения: удалить все и загрузить из столбцов J + I.',
        )
        parser.add_argument(
            '--comm-links-only',
            action='store_true',
            help='Только связь (столбец H) для существующих расположений из столбца J.',
        )
        parser.add_argument(
            '--groups-only',
            action='store_true',
            help='Распределить пользователей по Django-группам из столбца L.',
        )
        parser.add_argument(
            '--assign-locations-only',
            action='store_true',
            help='Назначить пилотам расположения из столбца J (без смены старшего).',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Только показать, без записи в БД.',
        )

    def handle(self, *args, **options):
        file_path = os.path.abspath(options['file'])
        if not os.path.isfile(file_path):
            raise CommandError(f'Файл не найден: {file_path}')

        self.stdout.write(f'Файл: {file_path}, лист: {options["sheet"]}')

        if options['assign_locations_only']:
            rows, stats = assign_pilot_locations_from_raschety(
                file_path,
                sheet_name=options['sheet'],
                dry_run=options['dry_run'],
            )
            prefix = 'dry-run: ' if options['dry_run'] else ''
            self.stdout.write(self.style.SUCCESS(
                f'{prefix}Расположения пилотов: сброшено {stats.pilot_locations_cleared}, '
                f'назначено {stats.pilot_locations_assigned}, пропущено {stats.skipped}'
            ))
            from collections import defaultdict
            by_loc: dict[str, list[str]] = defaultdict(list)
            for row in rows:
                if row.location_name:
                    by_loc[row.location_name].append(row.callname)
            for loc_name in sorted(by_loc):
                pilots = ', '.join(by_loc[loc_name])
                self.stdout.write(f'  {loc_name} ({len(by_loc[loc_name])}): {pilots}')
            return

        if options['groups_only']:
            try:
                rows, stats = assign_pilot_groups_from_raschety(
                    file_path,
                    sheet_name=options['sheet'],
                    dry_run=options['dry_run'],
                )
            except ValueError as exc:
                raise CommandError(str(exc)) from exc
            prefix = 'dry-run: ' if options['dry_run'] else ''
            self.stdout.write(self.style.SUCCESS(
                f'{prefix}Группы: назначено {stats.groups_assigned}, '
                f'пользователей в группах {stats.users_in_groups}, '
                f'пропущено {stats.skipped}'
            ))
            from collections import defaultdict
            by_group: dict[str, list[str]] = defaultdict(list)
            for row in rows:
                if row.group_name:
                    by_group[row.group_name].append(row.callname)
            for group_name in sorted(by_group):
                pilots = ', '.join(by_group[group_name])
                self.stdout.write(f'  {group_name} ({len(by_group[group_name])}): {pilots}')
            return

        if options['comm_links_only']:
            locations, stats = update_locations_comm_links_from_raschety(
                file_path,
                sheet_name=options['sheet'],
                dry_run=options['dry_run'],
            )
            prefix = 'dry-run: ' if options['dry_run'] else ''
            self.stdout.write(self.style.SUCCESS(
                f'{prefix}Связь обновлена у {stats.locations_updated} расположений '
                f'(не найдено: {stats.skipped})'
            ))
            for item in locations:
                if not item.comm_links:
                    continue
                labels = ', '.join(comm_link_labels(item.comm_links)) or '—'
                self.stdout.write(f'  {item.name} | связь: {labels}')
            return

        if options['locations_only']:
            locations, stats = replace_locations_from_raschety(
                file_path,
                sheet_name=options['sheet'],
                dry_run=options['dry_run'],
            )
            if options['dry_run']:
                self.stdout.write(self.style.WARNING(
                    f'dry-run: удалено было бы {stats.locations_deleted}, '
                    f'создано {len(locations)} расположений:'
                ))
                for item in locations:
                    np = item.settlement or '—'
                    links = ', '.join(comm_link_labels(item.comm_links)) or '—'
                    self.stdout.write(f'  {item.name} | н.п.: {np} | связь: {links}')
                return

            self.stdout.write(self.style.SUCCESS(
                f'Расположения: удалено {stats.locations_deleted}, создано {stats.locations_created}'
            ))
            for item in locations:
                np = item.settlement or '—'
                links = ', '.join(comm_link_labels(item.comm_links)) or '—'
                self.stdout.write(f'  {item.name} | н.п.: {np} | связь: {links}')
            return

        if options['dry_run']:
            rows = read_raschety_rows(file_path, sheet_name=options['sheet'])
            self.stdout.write(self.style.WARNING(f'dry-run: строк с пилотами: {len(rows)}'))
            for row in rows:
                if row.placement_zone == 'day':
                    duty = '06:00–18:00'
                elif row.placement_zone == 'night':
                    duty = '18:00–06:00'
                else:
                    duty = '—'
                self.stdout.write(
                    f'  {row.callname} | сапёр: {row.engineer_callname or "—"} | '
                    f'смена: {row.placement_zone or "—"} | время: {duty} | '
                    f'дрон: {row.drone_raw or "—"}'
                )
            return

        rows, stats = import_pilots_from_raschety(
            file_path,
            sheet_name=options['sheet'],
            dry_run=False,
        )
        self.stdout.write(self.style.SUCCESS(
            f'Дежурство: снято {stats.profiles_deactivated}, '
            f'на дежурстве {stats.rows_read} пилотов из файла; '
            f'пилотов +{stats.pilots_created}/~{stats.pilots_updated}, '
            f'дежурств +{stats.profiles_created}/~{stats.profiles_updated}; '
            f'дронов найдено {stats.drones_matched}, не в базе {stats.drones_skipped}'
        ))
