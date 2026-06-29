"""Узнать chat_id служебного канала и проверить доступ бота."""
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
    raise FileNotFoundError('Каталог tg_bot не найден')


class Command(BaseCommand):
    help = (
        'Проверить TELEGRAM_BACKFILL_CHAT_ID: бот отправит тест и удалит его '
        '(рабочая группа не используется)'
    )

    def add_arguments(self, parser):
        parser.add_argument('chat_id', type=int, help='ID приватного канала/группы служебного чата')

    def handle(self, *args, **options):
        tg_bot_dir = _resolve_tg_bot_dir()
        os.chdir(tg_bot_dir)
        tg_path = str(tg_bot_dir)
        if tg_path not in sys.path:
            sys.path.insert(0, tg_path)

        from create_bot import bot

        chat_id = options['chat_id']

        async def run():
            me = await bot.get_me()
            msg = await bot.send_message(
                chat_id=chat_id,
                text=f'Rubicon sync OK · @{me.username}',
            )
            await bot.delete_message(chat_id=chat_id, message_id=msg.message_id)
            return me.username

        try:
            username = asyncio.run(run())
        except Exception as exc:
            self.stderr.write(
                self.style.ERROR(
                    f'Не удалось: {exc}\n'
                    'Создайте приватный канал, добавьте бота админом '
                    'с правом публикации и удаления, затем повторите команду.'
                )
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f'Чат {chat_id} доступен боту @{username}. '
                f'Добавьте в .env:\nTELEGRAM_BACKFILL_CHAT_ID={chat_id}'
            )
        )
