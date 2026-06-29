# Инструкция по получению SSL сертификатов

## Быстрый старт

### На Windows (PowerShell):

```powershell
.\get-ssl-cert.ps1 -Email "your-email@example.com"
```

### На Linux/Mac (Bash):

```bash
chmod +x get-ssl-cert.sh
./get-ssl-cert.sh your-email@example.com
```

## Важные требования

Перед получением сертификатов убедитесь что:

1. ✅ **Домен указывает на сервер**: `aeroflot-pvz.ru` должен указывать на IP `5.104.51.225`
   ```bash
   nslookup aeroflot-pvz.ru
   # или
   dig aeroflot-pvz.ru
   ```

2. ✅ **Порт 80 открыт**: Должен быть доступен из интернета
   ```bash
   curl -I http://aeroflot-pvz.ru
   ```

3. ✅ **Контейнеры запущены**: 
   ```bash
   docker-compose ps
   ```

4. ✅ **Nginx настроен**: Должен быть настроен location `/.well-known/acme-challenge/`

## Что происходит при получении сертификатов

1. Certbot отправляет запрос в Let's Encrypt
2. Let's Encrypt проверяет доступность домена через HTTP на порту 80
3. Certbot создает временный файл в `certbot/www/.well-known/acme-challenge/`
4. Let's Encrypt запрашивает этот файл через ваш домен
5. После успешной проверки сертификаты сохраняются в `certbot/conf/live/aeroflot-pvz.ru/`

## После получения сертификатов

1. **Включите HTTPS редирект** в `nginx/conf.d/default.conf`:
   - Найдите блок с комментарием `# ВРЕМЕННО: Работа через HTTP`
   - Закомментируйте блок проксирования
   - Раскомментируйте редирект:
   ```nginx
   location / {
       return 301 https://$host$request_uri;
   }
   ```

2. **Перезапустите контейнеры**:
   ```bash
   docker-compose restart webserver
   ```

3. **Проверьте работу HTTPS**:
   ```bash
   curl -I https://aeroflot-pvz.ru
   ```

## Альтернативный метод: DNS Challenge

Если порт 80 недоступен из интернета, можно использовать DNS challenge:

```bash
docker run -it --rm \
  -v "./certbot/conf:/etc/letsencrypt" \
  certbot/certbot certonly \
  --manual \
  --preferred-challenges dns \
  --email your-email@example.com \
  --agree-tos \
  --no-eff-email \
  -d aeroflot-pvz.ru \
  -d www.aeroflot-pvz.ru
```

Certbot попросит добавить TXT запись в DNS. После добавления записи нажмите Enter.

## Автоматическое обновление

Сертификаты Let's Encrypt действительны 90 дней. Для автоматического обновления добавьте в crontab:

```bash
0 0 1 * * docker run --rm -v "./certbot/conf:/etc/letsencrypt" -v "./certbot/www:/var/www/certbot" certbot/certbot renew && docker-compose restart webserver
```

## Диагностика проблем

### Ошибка: "Failed to connect to aeroflot-pvz.ru"

**Причина**: Домен не указывает на сервер или порт 80 закрыт

**Решение**: 
- Проверьте DNS записи
- Убедитесь что порт 80 открыт в firewall
- Проверьте что nginx контейнер запущен

### Ошибка: "Connection refused"

**Причина**: Nginx не слушает на порту 80 или контейнер не запущен

**Решение**:
```bash
docker-compose ps
docker-compose logs webserver
```

### Ошибка: "Invalid response from http://aeroflot-pvz.ru/.well-known/acme-challenge/..."

**Причина**: Nginx не настроен для обслуживания файлов certbot

**Решение**: Убедитесь что в `nginx/conf.d/default.conf` есть:
```nginx
location /.well-known/acme-challenge/ {
    root /var/www/certbot;
    try_files $uri =404;
}
```

## Проверка сертификатов

После получения сертификатов проверьте их наличие:

```bash
ls -la certbot/conf/live/aeroflot-pvz.ru/
```

Должны быть файлы:
- `fullchain.pem` - полная цепочка сертификатов
- `privkey.pem` - приватный ключ
- `chain.pem` - цепочка промежуточных сертификатов
- `cert.pem` - сертификат домена
