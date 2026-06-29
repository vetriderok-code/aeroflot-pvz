# Диагностика проблемы с HTTPS

## Что проверить:

### 1. Проверка доступности домена извне:

```bash
# Проверка HTTP редиректа
curl -I http://aeroflot-pvz.ru

# Должен вернуть: HTTP/1.1 301 Moved Permanently
# Location: https://aeroflot-pvz.ru/
```

### 2. Проверка HTTPS:

```bash
# Проверка HTTPS
curl -I https://aeroflot-pvz.ru

# Должен вернуть: HTTP/2 200 или другой успешный статус
```

### 3. Проверка сертификатов в контейнере:

```bash
docker exec rubicon-gateway ls -la /etc/letsencrypt/live/aeroflot-pvz.ru/
```

### 4. Проверка конфигурации nginx:

```bash
docker exec rubicon-gateway nginx -t
```

### 5. Проверка логов:

```bash
docker logs rubicon-gateway --tail 50
```

## Возможные проблемы:

### Проблема 1: Конфигурация не обновилась

**Решение**: Пересоздать контейнер:
```bash
docker-compose stop webserver
docker-compose rm -f webserver
docker-compose up -d webserver
```

### Проблема 2: Сертификаты не найдены

**Решение**: Проверить монтирование volume:
```bash
docker exec rubicon-gateway ls -la /etc/letsencrypt/live/aeroflot-pvz.ru/
```

Если файлов нет, проверьте что volume правильно смонтирован в docker-compose.yaml

### Проблема 3: Порт 443 не открыт

**Решение**: Открыть порт 443 в firewall на сервере

### Проблема 4: Ошибка 400 Bad Request

**Причина**: Django требует HTTPS, но получает HTTP запросы

**Решение**: Убедитесь что:
- X-Forwarded-Proto установлен в https для HTTPS запросов
- USE_HTTPS=True в .env файле (если DEBUG=False)

## Важно:

- **НЕ используйте** `http://localhost:443/` - порт 443 для HTTPS, не HTTP
- Используйте: `https://aeroflot-pvz.ru/` или `http://localhost/` для локального доступа
- Для локального доступа используйте HTTP на порту 80, не HTTPS на порту 443
