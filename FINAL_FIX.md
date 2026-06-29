# Финальное исправление проблемы с Nginx

## Проблема:
Nginx загружает **оба** файла: `default.conf` и `prod.conf`, оба содержат `upstream my_unicorn_server`.

## Решение:

### Вариант 1: Монтировать только default.conf (рекомендуется)

Измените `docker-compose.prod.yaml` на сервере:

```bash
nano docker-compose.prod.yaml
```

Найдите секцию `webserver` -> `volumes` и замените:
```yaml
- ./nginx/conf.d:/etc/nginx/conf.d:ro
```

На:
```yaml
- ./nginx/conf.d/default.conf:/etc/nginx/conf.d/default.conf:ro
```

Затем:
```bash
# Пересоздайте контейнер
docker-compose -f docker-compose.prod.yaml up -d --force-recreate webserver

# Проверьте логи
docker-compose -f docker-compose.prod.yaml logs --tail=20 webserver
```

### Вариант 2: Удалить prod.conf из директории

```bash
# Остановите webserver
docker-compose -f docker-compose.prod.yaml stop webserver

# Удалите или переименуйте prod.conf
mv nginx/conf.d/prod.conf nginx/conf.d/prod.conf.bak

# Запустите webserver
docker-compose -f docker-compose.prod.yaml up -d webserver
```

### Вариант 3: Использовать только prod.conf

```bash
# Остановите webserver
docker-compose -f docker-compose.prod.yaml stop webserver

# Удалите default.conf
rm nginx/conf.d/default.conf

# Переименуйте prod.conf в default.conf
mv nginx/conf.d/prod.conf nginx/conf.d/default.conf

# Запустите webserver
docker-compose -f docker-compose.prod.yaml up -d webserver
```

## После исправления проверьте:

```bash
# 1. Проверьте логи (не должно быть ошибок)
docker-compose -f docker-compose.prod.yaml logs --tail=20 webserver

# 2. Проверьте конфигурацию
docker-compose -f docker-compose.prod.yaml exec webserver nginx -t

# 3. Проверьте доступность
curl -I http://localhost
curl -I https://localhost

# 4. Проверьте с внешнего IP
curl -I http://aeroflot-pvz.ru
curl -I https://aeroflot-pvz.ru
```
