# Мост Telegram ↔ MAX

Двусторонняя синхронизация **без сторонних сервисов** — свой модуль в `tg_bot/bridge/`.

## Какие группы

| ID в mapping | Telegram | MAX |
|--------------|----------|-----|
| `dirty` | **Грязная группа** (`TELEGRAM_LIVE_FLIGHT_CHAT_ID`, все топики) | `MAX_BRIDGE_CHAT_DIRTY` |
| `td_quarter` | **Отчётный квартал ТД** (`TELEGRAM_VIDEO_REPORTS_CHAT_ID`, все топики) | `MAX_BRIDGE_CHAT_TD` |

Топики в Telegram помечаются префиксом в тексте: `[1 ИГ]`, `[Отчёты]`, `[Оповещения]` и т.д.  
При ответе из MAX тот же префикс в начале сообщения направляет его в нужный топик TG.

## Быстрый старт

1. Создайте бота в MAX ([@MasterBot](https://max.ru/MasterBot)) → токен.
2. Добавьте MAX-бота **админом** в две MAX-группы (зеркала «Грязной» и «ТД»).
3. В `.env` на NAS:

```env
MAX_BRIDGE_ENABLED=true
MAX_BOT_TOKEN=ваш_токен
MAX_BRIDGE_CHAT_DIRTY=123456789
MAX_BRIDGE_CHAT_TD=987654321
```

`chat_id` MAX можно взять из логов `rubicon_tg_bot` после добавления бота:
`MAX bot_added chat_id=...`

4. Перезапуск:

```bash
docker compose -f docker-compose.yaml -f docker-compose.airlineportal.yaml up -d tg-bot
```

5. Проверка: сообщение в TG → появляется в MAX и наоборот.

## Как работает

- **TG → MAX:** после обработки отчётов/оповещений handlers вызывают `bridge_tg_message`.
- **MAX → TG:** фоновый long poll `GET /updates` на [platform-api.max.ru](https://platform-api.max.ru).
- **Анти-петля:** SQLite (`bridge.db`) хранит пары `tg_msg_id ↔ max_msg_id`.

Бизнес-логика Rubicon (дашборд, видео на карте, реакции 👌) **не меняется**.

## Медиа

- **TG → MAX:** фото, видео, документы — загрузка через MAX `/uploads`.
- **MAX → TG:** MVP — по URL вложения; если URL недоступен, только текст.

Видео-отчёты ТД в TG → MAX должны проходить (лимит MAX на видео — 250 МБ).

## Файлы

```
tg_bot/bridge/
  mapping.yaml      # TG chat_id + подписи топиков
  config.py
  store.py          # SQLite
  max_client.py     # HTTP API MAX
  mirror.py         # TG ↔ MAX
  poll.py           # long poll MAX
  hooks.py          # вызов из handlers
```

## Ограничения v1

- Long poll MAX (для prod позже — webhook через nginx).
- Редактирования не синхронизируются (только новые сообщения).
- Сообщения от TG-бота не зеркалятся обратно.

Документация MAX: [dev.max.ru/docs-api](https://dev.max.ru/docs-api)
