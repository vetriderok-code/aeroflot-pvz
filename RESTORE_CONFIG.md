# Конфигурация восстановлена!

## Что было сделано:

1. ✅ Восстановлена оригинальная структура конфигурации из backup
2. ✅ Добавлен HTTPS блок с новыми SSL сертификатами
3. ✅ Сохранена поддержка localhost через HTTP

## Запуск контейнера:

### Вариант 1: Через docker-compose (если работает)

```powershell
cd "C:\Users\reshe\Downloads\Telegram Desktop\rubicon_bot_docker — export"
docker-compose build webserver
docker-compose up -d webserver
```

### Вариант 2: Напрямую через docker run

```powershell
cd "C:\Users\reshe\Downloads\Telegram Desktop\rubicon_bot_docker — export"

docker run -d --name rubicon-gateway --restart always `
  -p 80:80 -p 443:443 `
  -v "${PWD}/certbot/conf:/etc/letsencrypt:ro" `
  -v "${PWD}/certbot/www:/var/www/certbot:ro" `
  -v "${PWD}/nginx/conf.d:/etc/nginx/conf.d:ro" `
  -v static_volume:/code/static:rw `
  --network app_network `
  nginx:1.25
```

## Проверка:

```bash
# Проверка конфигурации
docker exec rubicon-gateway nginx -t

# Проверка HTTPS
curl -I https://aeroflot-pvz.ru

# Проверка HTTP редиректа
curl -I http://aeroflot-pvz.ru
```

## Текущая конфигурация:

- ✅ HTTP для домена → редирект на HTTPS
- ✅ HTTP для localhost → работает без редиректа
- ✅ HTTPS для домена → работает с новыми сертификатами
- ✅ SSL сертификаты: `/etc/letsencrypt/live/aeroflot-pvz.ru/`

## Важно:

Конфигурация восстановлена на основе оригинальной структуры, только обновлены пути к SSL сертификатам.
