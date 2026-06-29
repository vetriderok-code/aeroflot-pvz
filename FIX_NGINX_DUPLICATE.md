# Исправление проблемы с дублированием upstream в Nginx

## Проблема:
```
duplicate upstream "my_unicorn_server" in /etc/nginx/conf.d/init.conf:5
```

Nginx загружает **оба** файла: `default.conf` и `init.conf`, и оба содержат `upstream my_unicorn_server`.

## Решение на сервере:

```bash
# 1. Остановите webserver
docker-compose -f docker-compose.prod.yaml stop webserver

# 2. Удалите или переименуйте init.conf
mv nginx/conf.d/init.conf nginx/conf.d/init.conf.bak
# или
rm nginx/conf.d/init.conf

# 3. Убедитесь, что default.conf содержит prod.conf
cp nginx/conf.d/prod.conf nginx/conf.d/default.conf

# 4. Проверьте, что в директории conf.d только default.conf (и возможно .bak файлы)
ls -la nginx/conf.d/

# 5. Запустите webserver
docker-compose -f docker-compose.prod.yaml up -d webserver

# 6. Проверьте логи
docker-compose -f docker-compose.prod.yaml logs --tail=20 webserver

# 7. Проверьте конфигурацию
docker-compose -f docker-compose.prod.yaml exec webserver nginx -t

# 8. Проверьте доступность
curl -I http://localhost
curl -I https://localhost
```

## Альтернативное решение (монтировать только default.conf):

Если проблема сохраняется, можно изменить `docker-compose.prod.yaml`:

```yaml
volumes:
  - static_volume:/code/static:rw
  - ./nginx/conf.d/default.conf:/etc/nginx/conf.d/default.conf:ro  # Только default.conf
  - ./certbot/conf:/etc/letsencrypt:ro
  - ./certbot/www:/var/www/certbot:ro
```

Тогда Nginx будет загружать только `default.conf`.











