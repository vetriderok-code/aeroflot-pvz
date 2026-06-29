# Руководство по настройке SSL для aeroflot-pvz.ru

## Проблема

Сайт `https://aeroflot-pvz.ru/` не работает, потому что отсутствуют SSL сертификаты.

## Решение

### Вариант 1: Получение SSL сертификата через Let's Encrypt (рекомендуется)

#### Шаг 1: Убедитесь, что домен указывает на ваш сервер

Проверьте DNS записи:
```bash
dig aeroflot-pvz.ru
# или
nslookup aeroflot-pvz.ru
```

Должен возвращаться IP адрес вашего сервера (5.104.51.225).

#### Шаг 2: Убедитесь, что порты 80 и 443 открыты

```bash
# Проверка порта 80
curl -I http://aeroflot-pvz.ru

# Проверка порта 443
curl -I https://aeroflot-pvz.ru
```

#### Шаг 3: Получение SSL сертификата через certbot

**Вариант A: Использование certbot в Docker контейнере**

1. Запустите certbot контейнер:
```bash
docker run -it --rm \
  -v "./certbot/conf:/etc/letsencrypt" \
  -v "./certbot/www:/var/www/certbot" \
  certbot/certbot certonly \
  --webroot \
  --webroot-path=/var/www/certbot \
  --email your-email@example.com \
  --agree-tos \
  --no-eff-email \
  -d aeroflot-pvz.ru \
  -d www.aeroflot-pvz.ru
```

2. После успешного получения сертификатов, проверьте их наличие:
```bash
ls -la certbot/conf/live/aeroflot-pvz.ru/
```

Должны быть файлы:
- `fullchain.pem`
- `privkey.pem`
- `chain.pem`
- `cert.pem`

**Вариант B: Использование certbot на сервере (если установлен)**

```bash
certbot certonly --webroot \
  -w /path/to/certbot/www \
  -d aeroflot-pvz.ru \
  -d www.aeroflot-pvz.ru \
  --email your-email@example.com \
  --agree-tos
```

#### Шаг 4: Включение HTTPS в nginx

После получения сертификатов:

1. Откройте файл `nginx/conf.d/default.conf`

2. Найдите блок с комментарием `# ВРЕМЕННО: Работа через HTTP`

3. Закомментируйте блок проксирования и раскомментируйте редирект:
```nginx
# Редирект всего остального на HTTPS
location / {
    return 301 https://$host$request_uri;
}

# Закомментируйте блок проксирования ниже
```

4. Убедитесь, что HTTPS блок не закомментирован (строки 102-190)

5. Перезапустите nginx:
```bash
docker-compose restart webserver
```

6. Проверьте логи nginx на наличие ошибок:
```bash
docker-compose logs webserver
```

#### Шаг 5: Проверка работы HTTPS

```bash
curl -I https://aeroflot-pvz.ru
```

Должен вернуться статус 200 или 301.

### Вариант 2: Самоподписанный сертификат (только для тестирования)

**ВНИМАНИЕ:** Самоподписанные сертификаты вызывают предупреждения в браузерах и не подходят для продакшена.

1. Создайте директорию для сертификатов:
```bash
mkdir -p nginx/ssl
```

2. Создайте самоподписанный сертификат:
```bash
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout nginx/ssl/aeroflot-pvz.ru.key \
  -out nginx/ssl/aeroflot-pvz.ru.crt \
  -subj "/C=RU/ST=Moscow/L=Moscow/O=Rubicon/CN=aeroflot-pvz.ru" \
  -addext "subjectAltName=DNS:aeroflot-pvz.ru,DNS:www.aeroflot-pvz.ru"
```

3. Обновите docker-compose.yaml, добавив монтирование:
```yaml
volumes:
  - ./nginx/ssl:/etc/nginx/ssl:ro
```

4. Обновите nginx конфигурацию:
```nginx
ssl_certificate /etc/nginx/ssl/aeroflot-pvz.ru.crt;
ssl_certificate_key /etc/nginx/ssl/aeroflot-pvz.ru.key;
```

5. Перезапустите контейнеры:
```bash
docker-compose restart webserver
```

## Автоматическое обновление сертификатов

Let's Encrypt сертификаты действительны 90 дней. Для автоматического обновления:

1. Создайте скрипт обновления: `renew-cert.sh`
```bash
#!/bin/bash
docker run --rm \
  -v "./certbot/conf:/etc/letsencrypt" \
  -v "./certbot/www:/var/www/certbot" \
  certbot/certbot renew

docker-compose restart webserver
```

2. Добавьте в crontab (запуск раз в месяц):
```bash
0 0 1 * * /path/to/renew-cert.sh
```

## Диагностика проблем

### Проверка наличия сертификатов

```bash
docker-compose exec webserver ls -la /etc/letsencrypt/live/aeroflot-pvz.ru/
```

### Проверка логов nginx

```bash
docker-compose logs webserver | grep -i ssl
docker-compose logs webserver | grep -i error
```

### Проверка конфигурации nginx

```bash
docker-compose exec webserver nginx -t
```

### Проверка доступности портов

```bash
# На сервере
netstat -tuln | grep -E ':(80|443)'

# Извне
curl -I http://aeroflot-pvz.ru
curl -I https://aeroflot-pvz.ru
```

## Текущее состояние

- ✅ HTTP работает: `http://aeroflot-pvz.ru/`
- ❌ HTTPS не работает: `https://aeroflot-pvz.ru/` (нет SSL сертификатов)
- ⚠️ Редирект с HTTP на HTTPS временно отключен

## После получения сертификатов

1. Включите редирект в `nginx/conf.d/default.conf`
2. Убедитесь, что `USE_HTTPS=True` в `.env` файле
3. Перезапустите контейнеры
4. Проверьте работу HTTPS
