# Инструкция по импорту данных на сервере

## Проблемы:
1. Команда `import_data` не найдена (файл не скопирован на сервер)
2. JSON файл в неправильном формате для стандартного `loaddata`
3. SQL дамп с ошибкой кодировки

## Решение:

### Вариант 1: Использовать Python скрипт (рекомендуется)

1. **Скопируйте скрипт на сервер:**
```bash
# На локальной машине
scp import_json_server.py user@46.17.40.216:/opt/rubikon/
```

2. **На сервере выполните:**
```bash
cd /opt/rubikon
docker cp import_json_server.py rubicon-api-prod:/tmp/
docker-compose -f docker-compose.prod.yaml exec api python /tmp/import_json_server.py /tmp/db_export.json
```

### Вариант 2: Использовать Python команду напрямую

```bash
docker-compose -f docker-compose.prod.yaml exec api python -c "
import json
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from django.core import serializers

with open('/tmp/db_export.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Наш формат с вложенными данными
if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict) and 'data' in data[0]:
    total = 0
    for item in data:
        model_name = item.get('model', '')
        model_data = item.get('data', [])
        print(f'Импорт {model_name}: {len(model_data)} записей...')
        imported = 0
        for obj_data in model_data:
            try:
                for obj in serializers.deserialize('json', json.dumps([obj_data])):
                    obj.save()
                    imported += 1
            except Exception as e:
                print(f'  Ошибка: {e}')
        total += imported
        print(f'  Импортировано: {imported}')
    print(f'Всего импортировано: {total}')
else:
    # Стандартный формат
    imported = 0
    for obj in serializers.deserialize('json', json.dumps(data)):
        try:
            obj.save()
            imported += 1
            if imported % 1000 == 0:
                print(f'Импортировано: {imported}...')
        except Exception as e:
            print(f'Ошибка: {e}')
    print(f'Всего импортировано: {imported}')
"
```

### Вариант 3: Исправить SQL дамп

Если хотите использовать SQL дамп, нужно пересоздать его с правильной кодировкой:

**На локальной машине:**
```bash
docker-compose exec -T database pg_dump -U rubicon_user -d rubicon_db \
    --data-only \
    --encoding=UTF8 \
    --table=public.pilot \
    --table=public.flight \
    --table=public.drone \
    --table=public.explosive_type \
    --table=public.explosive_device \
    --table=public.target_type \
    --table=public.corrective_type \
    --table=public.importprogress \
    > db_export_custom_fixed.sql
```

Затем передать на сервер и импортировать:
```bash
docker cp db_export_custom_fixed.sql rubicon-db-prod:/tmp/
docker-compose -f docker-compose.prod.yaml exec database \
    psql -U rubicon_user -d rubicon_db -f /tmp/db_export_custom_fixed.sql
```









