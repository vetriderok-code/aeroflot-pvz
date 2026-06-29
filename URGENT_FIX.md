# СРОЧНОЕ ИСПРАВЛЕНИЕ - Nginx все еще видит init.conf

## Проблема:
Nginx загружает `init.conf` из контейнера, потому что монтируется вся директория.

## Решение (выполните на сервере):

```bash
# 1. Остановите webserver
docker-compose -f docker-compose.prod.yaml stop webserver

# 2. Удалите init.conf.bak тоже (на всякий случай)
rm nginx/conf.d/init.conf.bak

# 3. ОБЯЗАТЕЛЬНО измените docker-compose.prod.yaml
nano docker-compose.prod.yaml
```

**Найдите строку (примерно строка 12):**
```yaml
      - ./nginx/conf.d:/etc/nginx/conf.d:ro
```

**Замените на:**
```yaml
      - ./nginx/conf.d/default.conf:/etc/nginx/conf.d/default.conf:ro
```

**Сохраните:** Ctrl+O, Enter, Ctrl+X

```bash
# 4. Пересоздайте контейнер
docker-compose -f docker-compose.prod.yaml up -d --force-recreate webserver

# 5. Проверьте логи (не должно быть ошибок!)
sleep 5
docker-compose -f docker-compose.prod.yaml logs --tail=20 webserver

# 6. Проверьте конфигурацию
docker-compose -f docker-compose.prod.yaml exec webserver nginx -t

# 7. Проверьте доступность
curl -I http://localhost
```

## Если не хотите редактировать файл вручную:

```bash
# Используйте sed для автоматической замены
sed -i 's|- ./nginx/conf.d:/etc/nginx/conf.d:ro|- ./nginx/conf.d/default.conf:/etc/nginx/conf.d/default.conf:ro|' docker-compose.prod.yaml

# Проверьте изменение
grep "nginx/conf.d" docker-compose.prod.yaml

# Пересоздайте контейнер
docker-compose -f docker-compose.prod.yaml up -d --force-recreate webserver
```











