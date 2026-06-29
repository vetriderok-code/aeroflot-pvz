# Исправление конфигурации nginx для HTTPS

## Проблема

Конфигурация nginx не монтируется правильно в контейнер, поэтому HTTPS не работает.

## Решение

### Вариант 1: Использовать docker-compose (рекомендуется)

1. Убедитесь что в `docker-compose.yaml` есть volume для конфигурации:
```yaml
volumes:
  - ./nginx/conf.d:/etc/nginx/conf.d:ro
```

2. Пересоздайте контейнер:
```bash
docker-compose stop webserver
docker-compose rm -f webserver
docker-compose up -d webserver
```

### Вариант 2: Пересобрать образ nginx

1. Пересоберите образ с новой конфигурацией:
```bash
docker-compose build webserver
docker-compose up -d webserver
```

### Вариант 3: Использовать docker run напрямую

Остановите текущий контейнер и создайте новый с правильным монтированием:

```bash
docker stop rubicon-gateway
docker rm rubicon-gateway

# Замените путь на ваш реальный путь к проекту
docker run -d --name rubicon-gateway --restart always \
  -p 80:80 -p 443:443 \
  -v "C:/Users/reshe/Downloads/Telegram Desktop/rubicon_bot_docker — export/certbot/conf:/etc/letsencrypt:ro" \
  -v "C:/Users/reshe/Downloads/Telegram Desktop/rubicon_bot_docker — export/certbot/www:/var/www/certbot:ro" \
  -v "C:/Users/reshe/Downloads/Telegram Desktop/rubicon_bot_docker — export/nginx/conf.d:/etc/nginx/conf.d:ro" \
  -v static_volume:/code/static:rw \
  --network app_network \
  nginx:1.25
```

## Проверка

После применения одного из решений проверьте:

```bash
# Проверка конфигурации
docker exec rubicon-gateway nginx -t

# Проверка наличия конфигурации
docker exec rubicon-gateway ls -la /etc/nginx/conf.d/

# Проверка HTTPS
curl -I https://aeroflot-pvz.ru
```

## Важно

Убедитесь что:
- ✅ Сертификаты доступны: `docker exec rubicon-gateway ls -la /etc/letsencrypt/live/aeroflot-pvz.ru/`
- ✅ Конфигурация содержит правильный блок HTTPS (listen 443 ssl)
- ✅ Порт 443 открыт на сервере
