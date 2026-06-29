# Быстрый старт развертывания на продакшн-сервере

## Краткая инструкция

### 1. Подготовка на сервере

```bash
# Подключитесь к серверу
ssh root@46.17.40.216

# Установите Docker и Docker Compose (если еще не установлены)
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Откройте порты
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 22/tcp
sudo ufw enable
```

### 2. Загрузка проекта

```bash
# Создайте директорию
mkdir -p /opt/rubicon
cd /opt/rubicon

# Загрузите проект (через git, scp или другим способом)
# Например, через SCP с локальной машины:
# scp -r /path/to/project/* root@46.17.40.216:/opt/rubicon/
```

### 3. Настройка переменных окружения

```bash
cd /opt/rubicon

# Создайте .env.prod из примера
cp env.prod.example .env.prod
nano .env.prod  # Заполните все значения

# Сгенерируйте SECRET_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
# Скопируйте результат в .env.prod в поле SECRET_KEY
```

**Важно заполнить:**
- `SECRET_KEY` - сгенерированный ключ
- `POSTGRES_PASSWORD` - сильный пароль
- `REDIS_PASSWORD` - сильный пароль
- `DJANGO_SUPERUSER_PASSWORD` - пароль администратора
- `TOKEN` - токен Telegram бота
- `YANDEX_API_KEY` - ключ Яндекс API

### 4. Настройка DNS

Убедитесь, что DNS записи настроены:
- `aeroflot-pvz.ru` → `45.155.52.249`
- `www.aeroflot-pvz.ru` → `45.155.52.249`

Проверьте:
```bash
dig aeroflot-pvz.ru +short
# Должен вернуть: 45.155.52.249
```

### 5. Получение SSL сертификата

```bash
# Сделайте скрипт исполняемым
chmod +x get-ssl-cert.sh

# Запустите получение сертификата
./get-ssl-cert.sh

# Или вручную:
mkdir -p certbot/conf certbot/www
docker run -it --rm \
  -v $(pwd)/certbot/conf:/etc/letsencrypt \
  -v $(pwd)/certbot/www:/var/www/certbot \
  certbot/certbot certonly \
  --webroot \
  --webroot-path=/var/www/certbot \
  --email admin@aeroflot-pvz.ru \
  --agree-tos \
  --no-eff-email \
  -d aeroflot-pvz.ru \
  -d www.aeroflot-pvz.ru
```

### 6. Развертывание

```bash
# Сделайте скрипт исполняемым
chmod +x deploy.sh

# Запустите развертывание
./deploy.sh

# Или вручную:
docker-compose -f docker-compose.prod.yaml build
docker-compose -f docker-compose.prod.yaml up -d
```

### 7. Проверка

```bash
# Проверьте статус контейнеров
docker-compose -f docker-compose.prod.yaml ps

# Проверьте логи
docker-compose -f docker-compose.prod.yaml logs -f

# Откройте в браузере
# https://aeroflot-pvz.ru
```

### 8. Настройка Keycloak

1. Откройте Keycloak Admin Console
2. Найдите клиент `rubicon-app`
3. Обновите:
   - **Valid redirect URIs**: `https://aeroflot-pvz.ru/*`
   - **Web origins**: `https://aeroflot-pvz.ru`

## Полезные команды

```bash
# Остановка
docker-compose -f docker-compose.prod.yaml down

# Перезапуск
docker-compose -f docker-compose.prod.yaml restart

# Просмотр логов
docker-compose -f docker-compose.prod.yaml logs -f api

# Обновление после изменений кода
docker-compose -f docker-compose.prod.yaml build api
docker-compose -f docker-compose.prod.yaml up -d api

# Бэкап БД
docker exec rubicon-db-prod pg_dump -U rubicon_user rubicon_db > backup.sql
```

## Решение проблем

**502 Bad Gateway:**
```bash
docker-compose -f docker-compose.prod.yaml logs api
docker-compose -f docker-compose.prod.yaml restart api
```

**SSL не работает:**
- Проверьте DNS: `dig aeroflot-pvz.ru`
- Проверьте порты: `sudo ufw status`
- Проверьте сертификаты: `ls -la certbot/conf/live/aeroflot-pvz.ru/`

**CSRF ошибки:**
- Проверьте `CSRF_TRUSTED_ORIGINS` в `.env.prod`
- Убедитесь, что используется HTTPS

Подробная инструкция: см. `DEPLOYMENT_GUIDE.md`











