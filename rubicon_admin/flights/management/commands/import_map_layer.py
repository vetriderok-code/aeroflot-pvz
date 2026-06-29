"""Импорт слоя карты из LDK/KML/KMZ/GPX/GeoJSON на сервере."""

from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError

from flights.models import MapLayer


class Command(BaseCommand):
    help = 'Импортировать слой карты из файла (LDK, KML, KMZ, GPX, GeoJSON)'

    def add_arguments(self, parser):
        parser.add_argument('path', type=str, help='Путь к файлу слоя')
        parser.add_argument('--name', type=str, required=True, help='Название слоя на карте')
        parser.add_argument('--description', type=str, default='', help='Описание')
        parser.add_argument('--sort-order', type=int, default=0, help='Порядок в списке слоёв')
        parser.add_argument('--color', type=str, default='#00BFFF', help='Цвет по умолчанию (#RRGGBB)')
        parser.add_argument('--inactive', action='store_true', help='Создать слой выключенным')

    def handle(self, *args, **options):
        source = Path(options['path']).expanduser().resolve()
        if not source.is_file():
            raise CommandError(f'Файл не найден: {source}')

        layer = MapLayer(
            name=options['name'],
            description=options['description'],
            sort_order=options['sort_order'],
            color=options['color'],
            is_active=not options['inactive'],
        )

        with source.open('rb') as handle:
            layer.source_file.save(source.name, File(handle), save=False)

        try:
            layer.process_source_file()
        except Exception as exc:
            layer.conversion_error = str(exc)
            layer.geojson = None
            layer.feature_count = 0
            layer.save()
            raise CommandError(f'Ошибка конвертации: {exc}') from exc

        self.stdout.write(
            self.style.SUCCESS(
                f'Слой «{layer.name}» импортирован: {layer.feature_count} объектов, id={layer.id}'
            )
        )
