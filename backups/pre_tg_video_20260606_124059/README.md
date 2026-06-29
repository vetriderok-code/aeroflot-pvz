# Бэкап перед TG-видео на карте

Дата: 2026-06-06

Скопированы файлы до внедрения гибридного хранения видео отчётов Telegram:

- `models.py`
- `telegram_report_stats.py`
- `telegram_report_ingest.py`
- `urls.py`
- `map.html`
- `group_monitor.py`
- `topic_backfill.py`

Восстановление (при необходимости):

```bash
cp BACKUP_FILE /opt/rubicon/rubicon_admin/flights/...
docker compose restart api rubicon_tg_bot
```
