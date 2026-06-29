# Инструкция по запуску nginx контейнера

## Проблема

Конфигурация не монтируется автоматически из-за проблем с путями в Windows.

## Решение

### Вариант 1: Запустить через bat файл

Откройте Command Prompt (cmd) в директории проекта и выполните:

```cmd
start-nginx.bat
```

### Вариант 2: Запустить вручную через PowerShell

Откройте PowerShell в директории проекта и выполните:

```powershell
cd "C:\Users\reshe\Downloads\Telegram Desktop\rubicon_bot_docker — export"

docker stop rubicon-gateway
docker rm rubicon-gateway

docker run -d --name rubicon-gateway --restart always `
  -p 80:80 -p 443:443 `
  -v "${PWD}/certbot/conf:/etc/letsencrypt:ro" `
  -v "${PWD}/certbot/www:/var/www/certbot:ro" `
  -v "${PWD}/nginx/conf.d:/etc/nginx/conf.d:ro" `
  -v static_volume:/code/static:rw `
  --network app_network `
  nginx:1.25
```

### Вариант 3: Использовать docker-compose (если работает)

```powershell
cd "C:\Users\reshe\Downloads\Telegram Desktop\rubicon_bot_docker — export"
docker-compose build webserver
docker-compose up -d webserver
```

## После запуска проверьте:

```bash
# Проверка конфигурации
docker exec rubicon-gateway nginx -t

# Проверка наличия конфигурации
docker exec rubicon-gateway ls -la /etc/nginx/conf.d/

# Проверка HTTPS
curl -I https://aeroflot-pvz.ru
```

## Важно:

1. **Порт 443 для HTTPS, не HTTP!**
   - ❌ НЕ используйте: `http://localhost:443/`
   - ✅ Используйте: `https://localhost/` (если настроен) или `https://aeroflot-pvz.ru/`

2. **Для локального доступа используйте HTTP на порту 80:**
   - ✅ `http://localhost/`

3. **Для домена используйте HTTPS:**
   - ✅ `https://aeroflot-pvz.ru/`

## Текущая конфигурация:

- ✅ HTTP (порт 80) для localhost → работает без редиректа
- ✅ HTTP (порт 80) для домена → редирект на HTTPS
- ✅ HTTPS (порт 443) для домена → работает с SSL сертификатами
