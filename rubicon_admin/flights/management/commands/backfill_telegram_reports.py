"""Импорт отчётов из SQLite бота (data/reports.db) в PostgreSQL для дашборда."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone as dt_timezone
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from flights.utils.telegram_report_stats import record_telegram_flight_report


class Command(BaseCommand):
    help = 'Синхронизировать отчёты из SQLite бота в таблицу telegram_flight_report'

    def add_arguments(self, parser):
        parser.add_argument(
            '--sqlite',
            type=str,
            default='',
            help='Путь к reports.db (по умолчанию — только уже в PostgreSQL)',
        )
        parser.add_argument(
            '--chat-id',
            type=int,
            default=None,
            help='Фильтр chat_id (по умолчанию TELEGRAM_REPORTS_CHAT_ID)',
        )
        parser.add_argument(
            '--topic-id',
            type=int,
            default=None,
            help='message_thread_id для записей без топика (по умолчанию 2406)',
        )
        parser.add_argument(
            '--days',
            type=int,
            default=3,
            help='Сколько последних дней по sent_at/created_at учитывать',
        )

    def handle(self, *args, **options):
        sqlite_path = (options.get('sqlite') or '').strip()
        if not sqlite_path:
            self.stderr.write('Укажите --sqlite /path/to/reports.db')
            self.stderr.write(
                'Пример: docker cp aviasales-telegram-bot:/app/data/reports.db '
                './reports.db && python manage.py backfill_telegram_reports --sqlite ./reports.db'
            )
            return

        path = Path(sqlite_path)
        if not path.is_file():
            self.stderr.write(self.style.ERROR(f'Файл не найден: {path}'))
            return

        chat_id = options['chat_id'] or getattr(settings, 'TELEGRAM_REPORTS_CHAT_ID', None)
        topic_id = options['topic_id'] or getattr(settings, 'TELEGRAM_REPORTS_TOPIC_ID', 2406)
        days = max(1, int(options['days'] or 3))

        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            '''
            SELECT telegram_message_id, chat_id, flight_number, work_date, result,
                   pilot_callsign, raw_text, parse_ok, sent_at, created_at
            FROM reports
            WHERE parse_ok = 1 AND flight_number > 0
            ORDER BY id DESC
            '''
        )
        rows = cur.fetchall()
        conn.close()

        created = updated = skipped = 0
        cutoff = datetime.now(dt_timezone.utc).timestamp() - days * 86400

        for row in rows:
            if chat_id and int(row['chat_id']) != int(chat_id):
                skipped += 1
                continue

            sent_raw = row['sent_at'] or row['created_at']
            if sent_raw:
                try:
                    ts = datetime.fromisoformat(str(sent_raw).replace('Z', '+00:00')).timestamp()
                    if ts < cutoff:
                        skipped += 1
                        continue
                except ValueError:
                    pass

            result = record_telegram_flight_report(
                chat_id=int(row['chat_id']),
                message_thread_id=int(topic_id),
                telegram_message_id=int(row['telegram_message_id']),
                flight_number=int(row['flight_number']),
                work_date=row['work_date'] or '',
                result=row['result'] or '',
                pilot_callsign=row['pilot_callsign'] or '',
                parse_ok=bool(row['parse_ok']),
                sent_at=sent_raw,
                raw_text=row['raw_text'] or '',
            )
            if result.get('created'):
                created += 1
            else:
                updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Готово: создано {created}, обновлено {updated}, пропущено {skipped}'
            )
        )
