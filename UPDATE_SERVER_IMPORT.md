# Файлы для обновления на сервере - Логика импорта

## Файлы, которые нужно заменить:

### 1. **`rubicon_admin/flights/admin.py`**
   - Добавлена проверка дубликатов при импорте
   - Добавлена переменная `skipped_duplicates` для подсчета пропущенных дубликатов
   - Добавлена проверка существующих полетов перед созданием новых
   - Добавлено фоновое преобразование координат

### 2. **`rubicon_admin/flights/models.py`**
   - Добавлено кеширование Transformer объектов для снижения CPU нагрузки
   - Добавлена функция `get_transformer()` для переиспользования Transformer

### 3. **`docker-compose.prod.yaml`**
   - Добавлены лимиты CPU: `cpus: '2.0'` (максимум), `cpus: '0.5'` (минимум)

## Команды для обновления на сервере:

```bash
# 1. Перейти в директорию проекта
cd /opt/rubikon

# 2. Сделать резервную копию (опционально)
cp rubicon_admin/flights/admin.py rubicon_admin/flights/admin.py.backup
cp rubicon_admin/flights/models.py rubicon_admin/flights/models.py.backup
cp docker-compose.prod.yaml docker-compose.prod.yaml.backup

# 3. Обновить файлы (скопировать с локальной машины через SCP)
# На локальной машине:
scp rubicon_admin/flights/admin.py user@46.17.40.216:/opt/rubikon/rubicon_admin/flights/
scp rubicon_admin/flights/models.py user@46.17.40.216:/opt/rubikon/rubicon_admin/flights/
scp docker-compose.prod.yaml user@46.17.40.216:/opt/rubikon/

# 4. На сервере - перезапустить контейнер API
docker-compose -f docker-compose.prod.yaml restart api

# 5. Проверить логи
docker-compose -f docker-compose.prod.yaml logs --tail=50 api
```

## Альтернативный способ (через git, если используется):

```bash
# На сервере
cd /opt/rubikon
git pull  # если изменения закоммичены
docker-compose -f docker-compose.prod.yaml restart api
```

## Что изменилось:

### В `admin.py`:
- ✅ Проверка существующих полетов перед созданием (по ключу: number, pilot_id, flight_date, flight_time)
- ✅ Пропуск дубликатов вместо создания новых записей
- ✅ Фоновое преобразование координат после каждого батча
- ✅ Счетчик пропущенных дубликатов в итоговом сообщении

### В `models.py`:
- ✅ Кеширование Transformer объектов (снижает CPU нагрузку)
- ✅ Функция `get_transformer()` для переиспользования

### В `docker-compose.prod.yaml`:
- ✅ Лимиты CPU для контейнера API

## Проверка после обновления:

```bash
# Проверить, что контейнер запущен
docker-compose -f docker-compose.prod.yaml ps

# Проверить логи на ошибки
docker-compose -f docker-compose.prod.yaml logs api | grep -i error

# Проверить использование CPU
docker stats rubicon-api-prod
```

## Важно:

1. **Резервная копия**: Рекомендуется сделать резервную копию перед обновлением
2. **Миграции**: Если были изменения в моделях, выполните миграции:
   ```bash
   docker-compose -f docker-compose.prod.yaml exec api python manage.py migrate
   ```
3. **Кеш**: После обновления может потребоваться очистить кеш:
   ```bash
   docker-compose -f docker-compose.prod.yaml exec api python manage.py shell -c "from django.core.cache import cache; cache.clear()"
   ```









