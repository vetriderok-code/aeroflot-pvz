# Чеклист после развертывания

## ✅ Шаг 1: Проверка контейнеров

```bash
# Проверьте статус всех контейнеров
docker-compose -f docker-compose.prod.yaml ps

# Все контейнеры должны быть в статусе "Up" или "Healthy"
```

## ✅ Шаг 2: Проверка логов

```bash
# Проверьте логи API
docker-compose -f docker-compose.prod.yaml logs --tail=50 api

# Проверьте логи Nginx
docker-compose -f docker-compose.prod.yaml logs --tail=50 webserver

# Ищите ошибки (ERROR, CRITICAL, failed)
```

## ✅ Шаг 3: Проверка доступности сайта

```bash
# Проверьте доступность через HTTP
curl -I http://localhost
curl -I http://aeroflot-pvz.ru

# Должен вернуть HTTP 200 или 302 (редирект)
```

## ✅ Шаг 4: Получение SSL сертификата

Если SSL сертификат еще не получен:

```bash
# Вариант 1: Standalone (если порт 80 свободен)
# Остановите webserver временно
docker-compose -f docker-compose.prod.yaml stop webserver

# Получите сертификат
./get-ssl-cert.sh

# Запустите webserver обратно
docker-compose -f docker-compose.prod.yaml start webserver

# Обновите конфигурацию nginx на продакшн
cp nginx/conf.d/prod.conf nginx/conf.d/default.conf
docker-compose -f docker-compose.prod.yaml restart webserver
```

## ✅ Шаг 5: Проверка SSL

```bash
# Проверьте наличие сертификатов
ls -la certbot/conf/live/aeroflot-pvz.ru/

# Должны быть:
# - fullchain.pem
# - privkey.pem

# Проверьте доступность через HTTPS
curl -I https://aeroflot-pvz.ru
```

## ✅ Шаг 6: Проверка работы приложения

1. Откройте в браузере: `http://aeroflot-pvz.ru` или `https://aeroflot-pvz.ru`
2. Проверьте, что страница загружается
3. Попробуйте войти в систему

## ✅ Шаг 7: Настройка Keycloak

1. Откройте Keycloak Admin Console
2. Найдите клиент `rubicon-app`
3. Обновите настройки:
   - **Valid redirect URIs**: `https://aeroflot-pvz.ru/*`
   - **Web origins**: `https://aeroflot-pvz.ru`

## ✅ Шаг 8: Финальная проверка

```bash
# Проверьте все сервисы
docker-compose -f docker-compose.prod.yaml ps

# Проверьте логи на ошибки
docker-compose -f docker-compose.prod.yaml logs | grep -i error

# Проверьте доступность через внешний IP
curl -I http://46.17.40.216
```

## 🔧 Решение проблем

### Проблема: 502 Bad Gateway
```bash
# Проверьте, что API контейнер запущен
docker-compose -f docker-compose.prod.yaml ps api

# Проверьте логи API
docker-compose -f docker-compose.prod.yaml logs api

# Перезапустите API
docker-compose -f docker-compose.prod.yaml restart api
```

### Проблема: Сайт не открывается
```bash
# Проверьте порты
sudo netstat -tulpn | grep :80
sudo netstat -tulpn | grep :443

# Проверьте firewall
sudo ufw status

# Проверьте DNS
dig aeroflot-pvz.ru +short
```

### Проблема: SSL не работает
```bash
# Проверьте наличие сертификатов
ls -la certbot/conf/live/aeroflot-pvz.ru/

# Проверьте конфигурацию nginx
docker-compose -f docker-compose.prod.yaml exec webserver nginx -t

# Перезапустите webserver
docker-compose -f docker-compose.prod.yaml restart webserver
```

## 📝 Полезные команды

```bash
# Просмотр всех логов
docker-compose -f docker-compose.prod.yaml logs -f

# Перезапуск всех сервисов
docker-compose -f docker-compose.prod.yaml restart

# Остановка всех сервисов
docker-compose -f docker-compose.prod.yaml down

# Обновление после изменений кода
docker-compose -f docker-compose.prod.yaml build api
docker-compose -f docker-compose.prod.yaml up -d api
```











