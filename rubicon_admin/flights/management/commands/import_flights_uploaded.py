"""Фоновый импорт Excel, загруженного через админку (subprocess, не блокирует gunicorn)."""
from __future__ import annotations

import logging
import os
from pathlib import Path

from django.conf import settings
from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.db import SessionStore
from django.core.management.base import BaseCommand, CommandError
from django.test import RequestFactory

from flights.admin import FlightAdmin
from flights.models import Flight
from flights.utils.excel_import_source import PathExcelSource

logger = logging.getLogger(__name__)

LOCK_FILE = Path(settings.BASE_DIR) / 'media' / 'import_queue' / '.running'


class Command(BaseCommand):
    help = 'Импорт Excel из сохранённого на диске файла (запускается из админки в фоне).'

    def add_arguments(self, parser):
        parser.add_argument('--file', action='append', required=True, help='Путь к .xlsx/.xlsm')
        parser.add_argument(
            '--incremental',
            action='store_true',
            help='Не удалять вылеты, продолжить с прогресса.',
        )

    def handle(self, *args, **options):
        paths = [os.path.abspath(p) for p in options['file']]
        for path in paths:
            if not os.path.isfile(path):
                raise CommandError(f'Файл не найден: {path}')

        User = get_user_model()
        user = User.objects.filter(is_superuser=True, is_active=True).order_by('id').first()
        if user is None:
            raise CommandError('Нет активного суперпользователя')

        sources = [PathExcelSource(path) for path in paths]
        request = RequestFactory().post('/admin/flights/flight/import-xlsx/', data={})
        request.user = user
        request.session = SessionStore()
        request._messages = FallbackStorage(request)
        request.incremental_import = bool(options['incremental'])
        request._import_sources = sources

        flights_before = Flight.objects.count()
        self.stdout.write(f'Фоновый импорт: {", ".join(s.name for s in sources)}')
        self.stdout.write(f'Вылетов до: {flights_before}')

        flight_admin = FlightAdmin(Flight, admin.site)
        try:
            response = flight_admin.import_xlsx_view(request)
        except Exception as exc:
            logger.exception('Фоновый импорт Excel завершился с ошибкой')
            raise CommandError(f'Импорт прерван: {exc}') from exc
        finally:
            if LOCK_FILE.exists():
                LOCK_FILE.unlink(missing_ok=True)
            for path in paths:
                try:
                    os.unlink(path)
                except OSError:
                    pass

        flights_after = Flight.objects.count()
        self.stdout.write(f'Вылетов после: {flights_after}')
        self.stdout.write(self.style.SUCCESS(
            f'Импорт завершён (HTTP {getattr(response, "status_code", "?")})'
        ))
