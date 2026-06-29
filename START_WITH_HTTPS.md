# Запуск nginx с HTTPS

## HTTPS блок включен в конфигурации!

Конфигурация готова, но нужно правильно запустить контейнер с монтированием сертификатов.

## Проверьте наличие сертификатов:

```powershell
Test-Path "certbot\conf\live\aeroflot-pvz.ru\fullchain.pem"
Test-Path "certbot\conf\live\aeroflot-pvz.ru\privkey.pem"
```

Если сертификатов нет, получите их заново:
```powershell
docker run -it --rm -v "${PWD}/certbot/conf:/etc/letsencrypt" certbot/certbot certonly --manual --preferred-challenges dns --email adminsito@mail.ru --agree-tos --no-eff-email -d aeroflot-pvz.ru -d www.aeroflot-pvz.ru
```

## Запуск контейнера:

### Вариант 1: Используя docker-compose (если работает)

```powershell
cd "C:\Users\reshe\Downloads\Telegram Desktop\rubicon_bot_docker — export"
docker-compose build webserver
docker-compose up -d webserver
```

### Вариант 2: Напрямую через docker

```powershell
cd "C:\Users\reshe\Downloads\Telegram Desktop\rubicon_bot_docker — export"

# Остановите старый контейнер
docker stop rubicon-gateway
docker rm rubicon-gateway

# Пересоберите образ
docker build -t rubicon-nginx:latest -f nginx/Dockerfile nginx/

# Запустите контейнер с правильными путями
docker run -d --name rubicon-gateway --restart always `
  -p 80:80 -p 443:443 `
  -v "${PWD}/certbot/conf:/etc/letsencrypt:ro" `
  -v "${PWD}/certbot/www:/var/www/certbot:ro" `
  -v static_volume:/code/static:rw `
  --network app_network `
  rubicon-nginx:latest
```

## Проверка:

```powershell
# Проверка конфигурации
docker exec rubicon-gateway nginx -t

# Проверка сертификатов
docker exec rubicon-gateway sh -c "ls -la /etc/letsencrypt/live/aeroflot-pvz.ru/"

# Проверка HTTPS
curl -I https://aeroflot-pvz.ru
```

## Текущая конфигурация:

- ✅ HTTP (порт 80) для домена → редирект на HTTPS
- ✅ HTTP (порт 80) для localhost → работает без редиректа
- ✅ HTTPS (порт 443) для домена → включен с SSL сертификатами
