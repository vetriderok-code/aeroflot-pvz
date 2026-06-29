# Решение проблемы получения SSL сертификата

## Проблема
Certbot не может получить доступ к файлам проверки `.well-known/acme-challenge/`, потому что веб-сервер не запущен.

## Решение 1: Standalone режим (самый простой)

**Важно:** Порт 80 должен быть свободен!

```bash
# Остановите все контейнеры, если они запущены
docker-compose -f docker-compose.prod.yaml down

# Запустите получение сертификата
./get-ssl-cert.sh
```

Этот скрипт использует `--standalone` режим, который временно запускает веб-сервер на порту 80.

## Решение 2: С предварительным запуском nginx

Если порт 80 занят или нужно сохранить работу приложения:

```bash
# Используйте скрипт, который сначала запустит nginx
chmod +x get-ssl-cert-with-nginx.sh
./get-ssl-cert-with-nginx.sh
```

Этот скрипт:
1. Использует временную конфигурацию nginx (init.conf)
2. Запускает контейнеры
3. Получает сертификат через webroot
4. После получения можно обновить конфигурацию на prod.conf

## Решение 3: DNS Challenge (если порт 80 недоступен)

Если порт 80 заблокирован или есть другие проблемы:

```bash
chmod +x get-ssl-cert-dns.sh
./get-ssl-cert-dns.sh
```

Этот метод требует ручного добавления TXT записи в DNS (Certbot покажет инструкции).

## Рекомендуемая последовательность действий:

### Вариант A: Standalone (рекомендуется для первого раза)

```bash
# 1. Убедитесь, что порт 80 свободен
sudo lsof -i :80
# Если что-то запущено, остановите:
# sudo systemctl stop nginx
# или
# docker-compose -f docker-compose.prod.yaml down

# 2. Получите сертификат
./get-ssl-cert.sh

# 3. После получения сертификата запустите приложение
./deploy.sh
```

### Вариант B: С запущенным nginx

```bash
# 1. Используйте временную конфигурацию
cp nginx/conf.d/init.conf nginx/conf.d/default.conf

# 2. Запустите приложение
docker-compose -f docker-compose.prod.yaml up -d

# 3. Подождите запуска (30 секунд)
sleep 30

# 4. Получите сертификат
./get-ssl-cert-with-nginx.sh

# 5. Обновите конфигурацию на продакшн
cp nginx/conf.d/prod.conf nginx/conf.d/default.conf

# 6. Перезапустите webserver
docker-compose -f docker-compose.prod.yaml restart webserver
```

## Проверка после получения сертификата:

```bash
# Проверьте наличие сертификатов
ls -la certbot/conf/live/aeroflot-pvz.ru/

# Должны быть файлы:
# - fullchain.pem
# - privkey.pem
```

## Если все еще не работает:

1. **Проверьте DNS:**
   ```bash
   dig aeroflot-pvz.ru +short
   # Должен вернуть: 46.17.40.216
   ```

2. **Проверьте порты:**
   ```bash
   sudo ufw status
   sudo netstat -tulpn | grep :80
   ```

3. **Проверьте логи:**
   ```bash
   docker-compose -f docker-compose.prod.yaml logs webserver
   ```

4. **Попробуйте вручную:**
   ```bash
   # Остановите все
   docker-compose -f docker-compose.prod.yaml down
   
   # Получите сертификат вручную
   docker run -it --rm \
     -p 80:80 \
     -v $(pwd)/certbot/conf:/etc/letsencrypt \
     certbot/certbot certonly \
     --standalone \
     --email admin@aeroflot-pvz.ru \
     --agree-tos \
     --no-eff-email \
     -d aeroflot-pvz.ru \
     -d www.aeroflot-pvz.ru
   ```











