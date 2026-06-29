# Исправление ошибки 400 Bad Request

## Проблемы и решения

### 1. Локальная разработка

**Проблема:** Использование `http://localhost:443/` вызывает ошибку 400.

**Решение:** 
- Порт 443 используется для HTTPS, а не HTTP
- Для локальной разработки используйте: `http://localhost/` или `http://localhost:80/`

### 2. Настройки Django для локальной разработки

Исправлены настройки безопасности Django:
- `SESSION_COOKIE_SECURE` и `CSRF_COOKIE_SECURE` теперь отключаются автоматически для HTTP
- Добавлен `localhost` и `127.0.0.1` в `CSRF_TRUSTED_ORIGINS`
- HSTS отключается для локальной разработки

**Важно:** Для продакшена установите переменную окружения `USE_HTTPS=True` в `.env` файле.

### 3. Порт 443 для HTTPS

Добавлен порт 443 в `docker-compose.yaml` для работы HTTPS на продакшене.

## Что нужно сделать

### Для локальной разработки:

1. Убедитесь, что в `.env` файле установлено:
   ```
   USE_HTTPS=False
   ```

2. Перезапустите контейнеры:
   ```bash
   docker-compose down
   docker-compose up -d
   ```

3. Откройте в браузере: `http://localhost/` (не `http://localhost:443/`)

### Для продакшена:

1. Убедитесь, что в `.env` файле установлено:
   ```
   USE_HTTPS=True
   ```

2. Убедитесь, что SSL сертификаты настроены правильно (путь: `/etc/letsencrypt/live/aeroflot-pvz.ru/`)

3. Перезапустите контейнеры:
   ```bash
   docker-compose down
   docker-compose up -d
   ```

4. Проверьте доступность: `https://aeroflot-pvz.ru/`

## Проверка работы

### Локально:
```bash
curl http://localhost/
```

Должен вернуть HTML страницу без ошибок.

### На продакшене:
```bash
curl https://aeroflot-pvz.ru/
```

Должен вернуть HTML страницу без ошибок.

## Дополнительная диагностика

Если ошибка 400 все еще возникает:

1. Проверьте логи Django:
   ```bash
   docker-compose logs api
   ```

2. Проверьте логи nginx:
   ```bash
   docker-compose logs webserver
   ```

3. Проверьте, что переменная `USE_HTTPS` установлена правильно:
   ```bash
   docker-compose exec api env | grep USE_HTTPS
   ```

4. Проверьте `ALLOWED_HOSTS`:
   ```bash
   docker-compose exec api python manage.py shell -c "from django.conf import settings; print(settings.ALLOWED_HOSTS)"
   ```
