"""Запуск Telegram-бота в составе проекта Rubicon (общая БД и .env с Django)."""
import asyncio
import os
import sys
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand


def _resolve_tg_bot_dir() -> Path:
    candidates = (
        Path(settings.BASE_DIR).parent / 'tg_bot',
        Path(settings.BASE_DIR) / 'tg_bot',
    )
    for path in candidates:
        if path.is_dir():
            return path.resolve()
    raise FileNotFoundError(
        'Каталог tg_bot не найден. Ожидается ../tg_bot или ./tg_bot от rubicon_admin.'
    )


class Command(BaseCommand):
    help = 'Запускает Telegram-бота (aiogram) с доступом к Django ORM и общей PostgreSQL'

    def handle(self, *args, **options):
        tg_bot_dir = _resolve_tg_bot_dir()
        os.chdir(tg_bot_dir)
        tg_path = str(tg_bot_dir)
        if tg_path not in sys.path:
            sys.path.insert(0, tg_path)

        self.stdout.write(self.style.SUCCESS(f'Запуск бота из {tg_bot_dir}'))

        from aiogram_run import main

        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            self.stdout.write('Остановка бота')
