# Миграция данных из локальной БД в продакшн

## Вариант 1: Использование скриптов (рекомендуется)

### На локальной машине (экспорт):

1. **Экспорт через скрипт:**
```bash
# В директории проекта
./export_db.sh
```

Скрипт создаст 3 файла:
- `db_export_YYYYMMDD_HHMMSS.sql` - полный дамп БД
- `db_export_custom_YYYYMMDD_HHMMSS.sql` - только данные (без структуры)
- `db_export_YYYYMMDD_HHMMSS.json` - JSON формат

2. **Или через Django команду:**
```bash
docker-compose exec api python manage.py export_data --output db_export.json
```

3. **Передача файла на сервер:**
```bash
# Через SCP
scp db_export_custom_*.sql user@46.17.40.216:/opt/rubikon/
# или
scp db_export_*.json user@46.17.40.216:/opt/rubikon/
```

### На сервере (импорт):

1. **Импорт через скрипт:**
```bash
cd /opt/rubikon
chmod +x import_db.sh
./import_db.sh db_export_custom_YYYYMMDD_HHMMSS.sql
```

2. **Или через Django команду:**
```bash
docker-compose -f docker-compose.prod.yaml exec api python manage.py import_data --input db_export.json
```

---

## Вариант 2: Прямой экспорт/импорт через PostgreSQL

### На локальной машине:

```bash
# Экспорт только данных (без структуры)
docker-compose exec database pg_dump -U postgres -d rubicon \
    --data-only \
    --table=public.pilot \
    --table=public.flight \
    --table=public.drone \
    --table=public.explosive_type \
    --table=public.explosive_device \
    --table=public.target_type \
    --table=public.corrective_type \
    --table=public.importprogress \
    > db_export.sql
```

### На сервере:

```bash
# Импорт данных
docker cp db_export.sql rubicon-db-prod:/tmp/
docker-compose -f docker-compose.prod.yaml exec database \
    psql -U postgres -d rubicon -f /tmp/db_export.sql
```

---

## Вариант 3: Через Django dumpdata/loaddata

### На локальной машине:

```bash
# Экспорт
docker-compose exec api python manage.py dumpdata \
    flights.Pilot \
    flights.Flight \
    flights.Drone \
    flights.ExplosiveType \
    flights.ExplosiveDevice \
    flights.TargetType \
    flights.CorrectiveType \
    flights.ImportProgress \
    --indent 2 \
    > db_export.json
```

### На сервере:

```bash
# Импорт
docker cp db_export.json rubicon-api-prod:/tmp/
docker-compose -f docker-compose.prod.yaml exec api \
    python manage.py loaddata /tmp/db_export.json
```

---

## Важные замечания:

1. **Резервная копия:** Перед импортом сделайте резервную копию продакшн БД:
```bash
docker-compose -f docker-compose.prod.yaml exec database \
    pg_dump -U postgres -d rubicon > backup_$(date +%Y%m%d_%H%M%S).sql
```

2. **Очистка данных:** Если нужно очистить данные перед импортом:
```bash
docker-compose -f docker-compose.prod.yaml exec api python manage.py shell -c "
from flights.models import Flight, Pilot
Flight.objects.all().delete()
Pilot.objects.all().delete()
"
```

3. **Проверка данных:** После импорта проверьте количество записей:
```bash
docker-compose -f docker-compose.prod.yaml exec api python manage.py shell -c "
from flights.models import Flight, Pilot
print(f'Пилотов: {Pilot.objects.count()}')
print(f'Полетов: {Flight.objects.count()}')
"
```

4. **Координаты:** После импорта может потребоваться пересчет координат:
```bash
docker-compose -f docker-compose.prod.yaml exec api \
    python manage.py precache_coordinates
```

---

## Рекомендуемый порядок действий:

1. ✅ Сделать резервную копию продакшн БД
2. ✅ Экспортировать данные из локальной БД
3. ✅ Передать файл на сервер
4. ✅ Импортировать данные в продакшн БД
5. ✅ Проверить количество записей
6. ✅ При необходимости пересчитать координаты
7. ✅ Очистить кеш Redis (если используется)









