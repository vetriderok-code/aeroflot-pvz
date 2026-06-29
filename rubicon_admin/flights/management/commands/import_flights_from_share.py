"""Ежедневный импорт вылетов из Excel на файловой шаре."""
from __future__ import annotations

import logging
import os

from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.db import SessionStore
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError
from django.test import RequestFactory

from flights.admin import FlightAdmin
from flights.models import Flight, ImportProgress
from flights.utils.excel_import_share import (
    default_import_dir,
    default_import_filename,
    resolve_import_file,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        'Импорт вылетов из Excel на шаре. '
        'По умолчанию: /data/Gerasimenko/ГБУ/ТАБ_ПИСЬМЕННОГО_ДОКЛАДА_ПИЛОТОВ_НОВАЯ2.xlsm'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dir',
            type=str,
            default='',
            help='Каталог шары (по умолчанию FLIGHTS_EXCEL_IMPORT_DIR).',
        )
        parser.add_argument(
            '--file',
            type=str,
            default='',
            help='Полный путь к файлу вместо автопоиска.',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Сбросить прогресс и начать импорт с начала (вылеты не удаляются).',
        )
        parser.add_argument(
            '--full-reset',
            action='store_true',
            help='Полный сброс: удалить все вылеты и прогресс, импорт с нуля.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Только показать, какой файл будет импортирован.',
        )

    def handle(self, *args, **options):
        if options['file']:
            file_path = os.path.abspath(options['file'])
            if not os.path.isfile(file_path):
                raise CommandError(f'Файл не найден: {file_path}')
        else:
            root = options['dir'] or str(default_import_dir())
            try:
                file_path = str(resolve_import_file(root))
            except (FileNotFoundError, ValueError) as exc:
                raise CommandError(str(exc)) from exc

        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        self.stdout.write(
            f'Файл: {file_path} ({file_size / 1024 / 1024:.2f} МБ, '
            f'ожидается: {default_import_filename()})'
        )

        if options['dry_run']:
            self.stdout.write(self.style.SUCCESS('dry-run: импорт не запускался'))
            return

        if options['full_reset']:
            flights_deleted, _ = Flight.objects.all().delete()
            progress_deleted, _ = ImportProgress.objects.filter(file_name=file_name).delete()
            self.stdout.write(
                f'Полный сброс: удалено вылетов {flights_deleted}, записей прогресса {progress_deleted}'
            )
        elif options['force']:
            deleted, _ = ImportProgress.objects.filter(file_name=file_name).delete()
            if deleted:
                self.stdout.write(f'Сброшен прогресс импорта: {deleted} записей (вылеты сохранены)')

        User = get_user_model()
        user = User.objects.filter(is_superuser=True, is_active=True).order_by('id').first()
        if user is None:
            raise CommandError('Нет активного суперпользователя для импорта')

        content_type = (
            'application/vnd.ms-excel.sheet.macroEnabled.12'
            if file_name.lower().endswith('.xlsm')
            else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        with open(file_path, 'rb') as handle:
            payload = handle.read()

        upload = SimpleUploadedFile(
            name=file_name,
            content=payload,
            content_type=content_type,
        )

        request = RequestFactory().post(
            '/admin/flights/flight/import-xlsx/',
            data={},
        )
        request.FILES.setlist('xlsx_files', [upload])
        request.user = user
        request.session = SessionStore()
        request._messages = FallbackStorage(request)
        request.incremental_import = not options['full_reset']

        flights_before = Flight.objects.count()
        self.stdout.write(f'Вылетов в БД до импорта: {flights_before}')

        flight_admin = FlightAdmin(Flight, admin.site)
        try:
            response = flight_admin.import_xlsx_view(request)
        except Exception as exc:
            logger.exception('Импорт из шары завершился с ошибкой')
            raise CommandError(f'Импорт прерван: {exc}') from exc

        flights_after = Flight.objects.count()
        self.stdout.write(f'Вылетов в БД после импорта: {flights_after}')
        self.stdout.write(self.style.SUCCESS(
            f'Импорт завершён (HTTP {getattr(response, "status_code", "?")})'
        ))
