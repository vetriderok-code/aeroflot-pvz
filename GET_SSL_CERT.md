# Получение SSL сертификатов для aeroflot-pvz.ru

## Шаг 1: Получение сертификатов через DNS challenge

Выполните команду:

```powershell
docker run -it --rm -v "${PWD}/certbot/conf:/etc/letsencrypt" certbot/certbot certonly --manual --preferred-challenges dns --email adminsito@mail.ru --agree-tos --no-eff-email -d aeroflot-pvz.ru -d www.aeroflot-pvz.ru
```

## Шаг 2: Добавление TXT записи в DNS

Certbot попросит вас добавить TXT запись в DNS. Пример:

```
_acme-challenge.aeroflot-pvz.ru TXT "ваш-токен-от-certbot"
```

После добавления записи нажмите Enter в терминале.

## Шаг 3: Проверка сертификатов

После успешного получения сертификатов проверьте:

```powershell
Test-Path "certbot\conf\live\aeroflot-pvz.ru\fullchain.pem"
```

## Шаг 4: Включение HTTPS

После получения сертификатов раскомментируйте HTTPS блок в `nginx/conf.d/default.conf` и перезапустите nginx.
