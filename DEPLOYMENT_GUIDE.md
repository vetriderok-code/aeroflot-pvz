# Руководство по развертыванию на продакшн-сервере

## Сервер и домен
- **IP сервера**: 45.155.52.249
- **Домен**: aeroflot-pvz.ru
- **WWW домен**: www.aeroflot-pvz.ru

## Предварительные требования

1. **Установка Docker и Docker Compose на сервере:**
```bash
# Обновление системы
sudo apt update && sudo apt upgrade -y

# Установка Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Установка Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Добавление пользователя в группу docker
sudo usermod -aG docker $USER
```

2. **Настройка DNS:**
   - Настройте A-записи для домена:
     - `aeroflot-pvz.ru` → `45.155.52.249`
     - `www.aeroflot-pvz.ru` → `45.155.52.249`
   - Дождитесь распространения DNS (может занять до 24 часов, обычно 1-2 часа)

3. **Открытие портов в firewall:**
```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 22/tcp  # SSH
sudo ufw enable
```

## Шаг 1: Подготовка сервера

1. **Подключитесь к серверу:**
```bash
ssh root@46.17.40.216
# или
ssh your_user@46.17.40.216
```

2. **Создайте директорию для проекта:**
```bash
mkdir -p /opt/rubicon
cd /opt/rubicon
```

3. **Загрузите проект на сервер:**
   - Вариант 1: Через Git (если проект в репозитории)
   ```bash
   git clone your_repo_url .
   ```
   
   - Вариант 2: Через SCP (с локальной машины)
   ```bash
   scp -r /path/to/project/* root@46.17.40.216:/opt/rubicon/
   ```

## Шаг 2: Настройка переменных окружения

1. **Создайте файл `.env.prod`:**
```bash
cd /opt/rubicon
cp .env.prod.example .env.prod
nano .env.prod
```

2. **Заполните все необходимые значения:**
   - `SECRET_KEY` - сгенерируйте новый секретный ключ (минимум 50 символов)
   - `POSTGRES_PASSWORD` - сильный пароль для БД
   - `REDIS_PASSWORD` - сильный пароль для Redis
   - `DJANGO_SUPERUSER_PASSWORD` - пароль для администратора Django
   - `DJANGO_ALLOWED_HOSTS` - `aeroflot-pvz.ru www.aeroflot-pvz.ru 45.155.52.249`
   - `CSRF_TRUSTED_ORIGINS` - `https://aeroflot-pvz.ru,https://www.aeroflot-pvz.ru`
   - Обновите остальные значения (TOKEN, YANDEX_API_KEY и т.д.)

3. **Сгенерируйте SECRET_KEY:**
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
```

## Шаг 3: Получение SSL сертификата

1. **Создайте директории для Certbot:**
```bash
mkdir -p certbot/conf certbot/www
```

2. **Временно запустите контейнеры без SSL (только HTTP):**
```bash
# Сначала используйте временную конфигурацию nginx без SSL
# Или используйте docker-compose.yaml (локальная версия) для получения сертификата
```

3. **Получите SSL сертификат через Certbot:**
```bash
# Вариант 1: Через Docker
docker run -it --rm \
  -v $(pwd)/certbot/conf:/etc/letsencrypt \
  -v $(pwd)/certbot/www:/var/www/certbot \
  certbot/certbot certonly \
  --webroot \
  --webroot-path=/var/www/certbot \
  --email your-email@example.com \
  --agree-tos \
  --no-eff-email \
  -d aeroflot-pvz.ru \
  -d www.aeroflot-pvz.ru

# Вариант 2: Установка Certbot на сервер
sudo apt install certbot
sudo certbot certonly --standalone -d aeroflot-pvz.ru -d www.aeroflot-pvz.ru
# Затем скопируйте сертификаты:
# sudo cp -r /etc/letsencrypt/* $(pwd)/certbot/conf/
```

4. **Проверьте наличие сертификатов:**
```bash
ls -la certbot/conf/live/aeroflot-pvz.ru/
# Должны быть файлы: fullchain.pem, privkey.pem
```

## Шаг 4: Запуск приложения

1. **Соберите и запустите контейнеры:**
```bash
cd /opt/rubicon
docker-compose -f docker-compose.prod.yaml build
docker-compose -f docker-compose.prod.yaml up -d
```

2. **Проверьте логи:**
```bash
docker-compose -f docker-compose.prod.yaml logs -f
```

3. **Проверьте статус контейнеров:**
```bash
docker-compose -f docker-compose.prod.yaml ps
```

## Шаг 5: Настройка автообновления SSL сертификата

Certbot контейнер автоматически обновляет сертификаты каждые 12 часов. После обновления нужно перезагрузить Nginx:

```bash
# Добавьте в cron или systemd timer задачу для перезагрузки nginx после обновления
# Или используйте webhook от Certbot
```

## Шаг 6: Настройка Keycloak

1. **Обновите настройки клиента в Keycloak:**
   - Откройте Keycloak Admin Console
   - Найдите клиент `rubicon-app`
   - Обновите **Valid redirect URIs**: `https://aeroflot-pvz.ru/*`
   - Обновите **Web origins**: `https://aeroflot-pvz.ru`

2. **Проверьте настройки в `.env.prod`:**
   - `KEYCLOAK_SERVER_URL` - должен быть правильным
   - `KEYCLOAK_CLIENT_ID` - должен быть `rubicon-app`

## Шаг 7: Проверка работы

1. **Проверьте доступность сайта:**
   - Откройте в браузере: `https://aeroflot-pvz.ru`
   - Проверьте SSL сертификат (должен быть валидным)
   - Попробуйте войти в систему

2. **Проверьте логи:**
```bash
docker-compose -f docker-compose.prod.yaml logs api
docker-compose -f docker-compose.prod.yaml logs webserver
```

## Полезные команды

```bash
# Остановка контейнеров
docker-compose -f docker-compose.prod.yaml down

# Перезапуск контейнеров
docker-compose -f docker-compose.prod.yaml restart

# Просмотр логов
docker-compose -f docker-compose.prod.yaml logs -f api

# Обновление кода (после git pull)
docker-compose -f docker-compose.prod.yaml build api
docker-compose -f docker-compose.prod.yaml up -d api

# Бэкап базы данных
docker exec rubicon-db-prod pg_dump -U rubicon_user rubicon_db > backup_$(date +%Y%m%d).sql

# Восстановление базы данных
docker exec -i rubicon-db-prod psql -U rubicon_user rubicon_db < backup.sql
```

## Решение проблем

### Проблема: SSL сертификат не работает
- Проверьте, что DNS записи настроены правильно
- Убедитесь, что порты 80 и 443 открыты
- Проверьте права доступа к файлам сертификатов

### Проблема: 502 Bad Gateway
- Проверьте, что контейнер `api` запущен: `docker ps`
- Проверьте логи: `docker-compose -f docker-compose.prod.yaml logs api`

### Проблема: CSRF ошибки
- Проверьте `CSRF_TRUSTED_ORIGINS` в `.env.prod`
- Убедитесь, что используется HTTPS

## Безопасность

1. **Регулярно обновляйте систему:**
```bash
sudo apt update && sudo apt upgrade -y
```

2. **Настройте firewall:**
```bash
sudo ufw status
```

3. **Регулярно делайте бэкапы базы данных**

4. **Используйте сильные пароли для всех сервисов**

5. **Ограничьте доступ к портам (кроме 80, 443, 22)**











