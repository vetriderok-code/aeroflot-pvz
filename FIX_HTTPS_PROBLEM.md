# Исправление проблемы с HTTPS для aeroflot-pvz.ru

## Проблема

Сайт `https://aeroflot-pvz.ru/` не работает, потому что отсутствуют SSL сертификаты.

## Текущее состояние

✅ **HTTP работает:** `http://aeroflot-pvz.ru/`  
❌ **HTTPS не работает:** `https://aeroflot-pvz.ru/` (нет SSL сертификатов)

## Что было исправлено

1. ✅ Временно отключен редирект с HTTP на HTTPS
2. ✅ Добавлена поддержка работы через HTTP для домена
3. ✅ Создана инструкция по получению SSL сертификатов (`SSL_SETUP_GUIDE.md`)
4. ✅ Создан скрипт диагностики (`check-ssl.sh`)

## Что нужно сделать сейчас

### Вариант 1: Получить SSL сертификат через Let's Encrypt (рекомендуется)

1. Убедитесь, что домен `aeroflot-pvz.ru` указывает на IP `5.104.51.225`

2. Получите SSL сертификат:
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

3. Проверьте наличие сертификатов:
```bash
ls -la certbot/conf/live/aeroflot-pvz.ru/
```

Должны быть файлы: `fullchain.pem`, `privkey.pem`

4. Включите HTTPS в nginx:
   - Откройте `nginx/conf.d/default.conf`
   - Найдите блок с комментарием `# ВРЕМЕННО: Работа через HTTP`
   - Закомментируйте блок проксирования
   - Раскомментируйте редирект на HTTPS:
   ```nginx
   location / {
       return 301 https://$host$request_uri;
   }
   ```

5. Перезапустите контейнеры:
```bash
docker-compose restart webserver
```

6. Проверьте работу HTTPS:
```bash
curl -I https://aeroflot-pvz.ru
```

### Вариант 2: Временно работать через HTTP

Если SSL сертификаты получить сейчас невозможно, сайт будет работать через HTTP:
- `http://aeroflot-pvz.ru/` ✅ работает
- `https://aeroflot-pvz.ru/` ❌ не работает (пока нет сертификатов)

## Диагностика

Запустите скрипт проверки (на Linux/Mac):
```bash
./check-ssl.sh
```

Или проверьте вручную:

1. Проверка наличия сертификатов:
```bash
ls -la certbot/conf/live/aeroflot-pvz.ru/
```

2. Проверка логов nginx:
```bash
docker-compose logs webserver | grep -i ssl
docker-compose logs webserver | grep -i error
```

3. Проверка конфигурации nginx:
```bash
docker-compose exec webserver nginx -t
```

## Дополнительная информация

Подробная инструкция по настройке SSL: `SSL_SETUP_GUIDE.md`
