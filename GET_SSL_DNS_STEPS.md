# Пошаговая инструкция получения SSL через DNS Challenge

## Шаг 1: Запустите команду в PowerShell

Откройте PowerShell в директории проекта и выполните:

```powershell
docker run -it --rm -v "$(pwd)/certbot/conf:/etc/letsencrypt" certbot/certbot certonly --manual --preferred-challenges dns --email adminsito@mail.ru --agree-tos --no-eff-email -d aeroflot-pvz.ru -d www.aeroflot-pvz.ru
```

## Шаг 2: Certbot покажет инструкции

Certbot выведет что-то вроде:

```
Please deploy a DNS TXT record under the name
_acme-challenge.aeroflot-pvz.ru with the following value:

abc123xyz789... (длинная строка)

Before continuing, verify the record is deployed.
```

## Шаг 3: Добавьте TXT запись в DNS

1. Войдите в панель управления вашего DNS провайдера (где настроен домен aeroflot-pvz.ru)
2. Добавьте новую TXT запись:
   - **Имя/Хост**: `_acme-challenge` (или `_acme-challenge.aeroflot-pvz.ru`)
   - **Тип**: `TXT`
   - **Значение**: Скопируйте значение, которое показал certbot
   - **TTL**: Оставьте по умолчанию (обычно 3600)

3. Для www поддомена добавьте еще одну запись:
   - **Имя/Хост**: `_acme-challenge.www` (или `_acme-challenge.www.aeroflot-pvz.ru`)
   - **Тип**: `TXT`
   - **Значение**: Второе значение от certbot
   - **TTL**: Оставьте по умолчанию

## Шаг 4: Проверьте распространение DNS

Подождите несколько минут (обычно 1-5 минут) и проверьте:

```powershell
# Проверка первой записи
nslookup -type=TXT _acme-challenge.aeroflot-pvz.ru

# Проверка второй записи
nslookup -type=TXT _acme-challenge.www.aeroflot-pvz.ru
```

Или используйте онлайн сервисы:
- https://mxtoolbox.com/TXTLookup.aspx
- https://www.whatsmydns.net/#TXT/_acme-challenge.aeroflot-pvz.ru

## Шаг 5: Вернитесь в терминал и нажмите Enter

После того как TXT записи добавлены и проверены, вернитесь в терминал где запущен certbot и нажмите **Enter**.

Certbot проверит записи и выдаст сертификаты.

## Шаг 6: После успешного получения

После успешного получения сертификатов:

1. **Включите HTTPS редирект** в `nginx/conf.d/default.conf`
2. **Перезапустите контейнеры**: `docker-compose restart webserver`
3. **Проверьте работу**: `curl -I https://aeroflot-pvz.ru`

## Альтернатива: Автоматический скрипт

Если у вас есть API доступ к DNS провайдеру, можно использовать автоматические плагины certbot для вашего провайдера.

## Примечания

- DNS записи могут распространяться до 48 часов, но обычно это занимает несколько минут
- Убедитесь что вы добавили обе записи (для основного домена и www)
- После получения сертификатов TXT записи можно удалить
