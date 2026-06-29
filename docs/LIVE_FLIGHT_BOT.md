# Telegram-бот (оперативный режим)

Бот слушает **только оперативную группу** `TELEGRAM_LIVE_FLIGHT_CHAT_ID`:

| Топик / сообщение | Действие |
|-------------------|----------|
| любой — «Старт» / «Стоп» | учёт `LiveFlight` → дашборд «В работе» |
| `TELEGRAM_REPORTS_TOPIC_ID` (2406) | парсинг «N вылет» (текст **или подпись к видео**) → счётчики на дашборде; на учтённые отчёты — реакция 👌 |
| `TELEGRAM_ALERTS_TOPIC_ID` (2408) | оповещения → лента на дашборде |

Личные сообщения боту — только справка по `/start`. Формы отчётов, профиль и админ-функции **отключены**.

## Смена для счётчика (МСК)

- **День:** 06:00–18:00
- **Ночь:** 18:00–06:00

Отдельно на дашборде — **календарные сутки 00:00–24:00 МСК** (не скользящие 24 ч).

Переменные: `DASHBOARD_SHIFT_DAY_START_HOUR=6`, `DASHBOARD_SHIFT_NIGHT_START_HOUR=18`.

## Догрузка пропущенных отчётов

Бот **не пишет в рабочую группу**. Для чтения старых сообщений (в т.ч. с видео) он временно пересылает их в **служебный приватный канал** (`TELEGRAM_BACKFILL_CHAT_ID`), читает подпись и сразу удаляет.

> Telegram не даёт боту «написать самому себе» в личку — нужен отдельный канал, куда добавлен только бот.

**Один раз:**
1. Создайте приватный канал (например «Rubicon Sync»).
2. Добавьте бота админом (публикация + удаление).
3. Узнайте `chat_id` канала и проверьте:
   ```bash
   docker exec rubicon-api python manage.py setup_telegram_backfill_chat -100xxxxxxxxxx
   ```
4. В `.env`: `TELEGRAM_BACKFILL_CHAT_ID=-100xxxxxxxxxx`, `TELEGRAM_BACKFILL_ON_START=true`

Ручная догрузка за сегодня (МСК):
```bash
docker exec rubicon-api python manage.py sync_telegram_reports_topic --limit 2000
```

## Запуск

```bash
docker compose -f docker-compose.yaml -f docker-compose.airlineportal.yaml up -d tg-bot
```

или `python manage.py run_telegram_bot`.
