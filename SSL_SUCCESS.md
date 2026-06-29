# SSL сертификаты успешно настроены!

## Что было сделано:

1. ✅ SSL сертификаты получены через DNS challenge
2. ✅ HTTPS редирект включен в nginx
3. ✅ Контейнер nginx перезапущен

## Сертификаты:

- **Расположение**: `/etc/letsencrypt/live/aeroflot-pvz.ru/`
- **Срок действия**: до 2026-04-22
- **Домены**: aeroflot-pvz.ru, www.aeroflot-pvz.ru

## Проверка работы:

### Проверка HTTP редиректа:
```bash
curl -I http://aeroflot-pvz.ru
# Должен вернуть: HTTP/1.1 301 Moved Permanently
# Location: https://aeroflot-pvz.ru/
```

### Проверка HTTPS:
```bash
curl -I https://aeroflot-pvz.ru
# Должен вернуть: HTTP/2 200 или другой успешный статус
```

### Проверка в браузере:
Откройте: https://aeroflot-pvz.ru

Должен отображаться зеленый замочек (SSL активен).

## Важно:

1. **Автоматическое обновление**: DNS challenge сертификаты не обновляются автоматически.
   Для обновления перед истечением срока (2026-04-22) выполните:
   ```bash
   docker run -it --rm -v "%CD%/certbot/conf:/etc/letsencrypt" certbot/certbot certonly --manual --preferred-challenges dns --email adminsito@mail.ru --agree-tos --no-eff-email -d aeroflot-pvz.ru -d www.aeroflot-pvz.ru
   ```

2. **Для автоматического обновления** рекомендуется открыть порт 80 и использовать webroot метод.

3. **Настройки Django**: Убедитесь что в `.env` установлено `USE_HTTPS=True` (если DEBUG=False)

## Текущая конфигурация:

- ✅ HTTP (порт 80) → редирект на HTTPS
- ✅ HTTPS (порт 443) → работает с SSL сертификатами
- ✅ Домены: aeroflot-pvz.ru, www.aeroflot-pvz.ru

## Следующие шаги (опционально):

1. Настроить автоматическое обновление сертификатов
2. Добавить мониторинг истечения сертификатов
3. Настроить HSTS заголовки (уже настроены в nginx)
