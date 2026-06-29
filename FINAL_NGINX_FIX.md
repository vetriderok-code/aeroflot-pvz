# ФИНАЛЬНОЕ ИСПРАВЛЕНИЕ - Проблема в Dockerfile

## Проблема:
В `nginx/Dockerfile` копируется **вся** директория `conf.d`, включая `init.conf`, поэтому он попадает в образ Docker.

## Решение:

### На сервере выполните:

```bash
# 1. Остановите webserver
docker-compose -f docker-compose.prod.yaml stop webserver

# 2. Убедитесь, что default.conf существует
cp nginx/conf.d/prod.conf nginx/conf.d/default.conf

# 3. Удалите все лишние файлы
rm -f nginx/conf.d/init.conf nginx/conf.d/init.conf.bak

# 4. Обновите nginx/Dockerfile (если еще не обновлен)
# Или вручную отредактируйте:
nano nginx/Dockerfile
```

**Замените:**
```dockerfile
COPY ./conf.d /etc/nginx/conf.d
```

**На:**
```dockerfile
COPY ./conf.d/default.conf /etc/nginx/conf.d/default.conf
```

**Сохраните:** Ctrl+O, Enter, Ctrl+X

```bash
# 5. Пересоберите образ nginx
docker-compose -f docker-compose.prod.yaml build webserver

# 6. Запустите webserver
docker-compose -f docker-compose.prod.yaml up -d webserver

# 7. Проверьте логи (не должно быть ошибок!)
sleep 5
docker-compose -f docker-compose.prod.yaml logs --tail=20 webserver

# 8. Проверьте конфигурацию
docker-compose -f docker-compose.prod.yaml exec webserver nginx -t

# 9. Проверьте доступность
curl -I http://localhost
curl -I https://localhost
```

## Альтернативное решение (быстрее):

Если не хотите пересобирать образ, можно просто удалить init.conf из образа:

```bash
# 1. Остановите webserver
docker-compose -f docker-compose.prod.yaml stop webserver

# 2. Убедитесь, что docker-compose.prod.yaml монтирует только default.conf
grep "nginx/conf.d" docker-compose.prod.yaml
# Должно быть: - ./nginx/conf.d/default.conf:/etc/nginx/conf.d/default.conf:ro

# 3. Если нет - исправьте:
sed -i 's|- ./nginx/conf.d:/etc/nginx/conf.d:ro|- ./nginx/conf.d/default.conf:/etc/nginx/conf.d/default.conf:ro|' docker-compose.prod.yaml

# 4. Убедитесь, что default.conf существует
cp nginx/conf.d/prod.conf nginx/conf.d/default.conf

# 5. Пересоздайте контейнер (монтирование перезапишет файлы из образа)
docker-compose -f docker-compose.prod.yaml up -d --force-recreate webserver

# 6. Проверьте логи
sleep 5
docker-compose -f docker-compose.prod.yaml logs --tail=20 webserver
```

## Проверка что все правильно:

```bash
# Проверьте файлы в контейнере
docker-compose -f docker-compose.prod.yaml exec webserver ls -la /etc/nginx/conf.d/

# Должен быть только default.conf, init.conf НЕ должно быть!
```











