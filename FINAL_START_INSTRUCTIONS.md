# Финальная инструкция по запуску nginx с HTTPS

## Проблема

Контейнер не запускается из-за проблем с монтированием volumes в Windows.

## Решение

### Шаг 1: Убедитесь что init.conf удален или переименован

```powershell
cd "C:\Users\reshe\Downloads\Telegram Desktop\rubicon_bot_docker — export"
Remove-Item "nginx\conf.d\init.conf" -ErrorAction SilentlyContinue
```

### Шаг 2: Пересоберите образ nginx

```powershell
cd "C:\Users\reshe\Downloads\Telegram Desktop\rubicon_bot_docker — export"
docker build -t rubicon-nginx:latest -f nginx/Dockerfile nginx/
```

### Шаг 3: Запустите контейнер

```powershell
# Остановите старый контейнер если есть
docker stop rubicon-gateway
docker rm rubicon-gateway

# Запустите новый контейнер
docker run -d --name rubicon-gateway --restart always `
  -p 80:80 -p 443:443 `
  -v "C:/Users/reshe/Downloads/Telegram Desktop/rubicon_bot_docker — export/certbot/conf:/etc/letsencrypt:ro" `
  -v "C:/Users/reshe/Downloads/Telegram Desktop/rubicon_bot_docker — export/certbot/www:/var/www/certbot:ro" `
  -v static_volume:/code/static:rw `
  --network app_network `
  rubicon-nginx:latest
```

### Шаг 4: Проверьте работу

```powershell
# Проверка конфигурации
docker exec rubicon-gateway nginx -t

# Проверка HTTPS
docker exec rubicon-gateway sh -c "openssl s_client -connect localhost:443 -servername aeroflot-pvz.ru </dev/null 2>&1 | grep -E 'CONNECTED|Verify return code'"

# Проверка в браузере
# Откройте: https://aeroflot-pvz.ru
```

## Альтернатива: Использовать docker-compose

Если docker-compose работает:

```powershell
cd "C:\Users\reshe\Downloads\Telegram Desktop\rubicon_bot_docker — export"
docker-compose build webserver
docker-compose up -d webserver
```

## Важно:

1. **Порт 443 для HTTPS, не HTTP!**
   - ❌ НЕ используйте: `http://localhost:443/`
   - ✅ Используйте: `https://aeroflot-pvz.ru/`

2. **Для локального доступа:**
   - ✅ `http://localhost/` (порт 80)

3. **Убедитесь что:**
   - ✅ Файл `nginx/conf.d/init.conf` удален или переименован
   - ✅ SSL сертификаты находятся в `certbot/conf/live/aeroflot-pvz.ru/`
   - ✅ Конфигурация `nginx/conf.d/default.conf` содержит HTTPS блок

## Текущая конфигурация:

- ✅ HTTP (порт 80) для localhost → работает без редиректа
- ✅ HTTP (порт 80) для домена → редирект на HTTPS  
- ✅ HTTPS (порт 443) для домена → работает с SSL сертификатами
