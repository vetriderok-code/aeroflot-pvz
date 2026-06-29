# Инструкция по локальному запуску проекта Rubicon Bot

## Шаг 1: Установка Docker Desktop

**ВАЖНО:** Для работы проекта необходимо установить Docker Desktop для Windows. WSL2 с Docker внутри WSL не работает для доступа с Windows.

1. Скачайте Docker Desktop для Windows: https://www.docker.com/products/docker-desktop/
2. Установите Docker Desktop (при установке автоматически установятся WSL компоненты)
3. Запустите Docker Desktop и дождитесь полной загрузки
4. Убедитесь, что Docker Desktop запущен (иконка в системном трее)

## Шаг 2: Настройка .env файла

Файл `.env` уже создан на основе `.env_example`. 

**ВАЖНО: Перед запуском необходимо заполнить следующие значения:**

1. **TOKEN** - токен Telegram бота (получить у @BotFather)
2. **YANDEX_API_KEY** - ключ API Яндекс карт (https://developer.tech.yandex.ru/services)
3. **TG_ADMIN** - ваш Telegram ID (можно узнать у @userinfobot)
4. **TG_GROUP_ID** - ID группового чата для отчетов (начинается с -100)
5. **TG_TOPIC_KT** и **TG_TOPIC_ST** - ID сообщений топиков (опционально)

Остальные значения уже настроены для локальной разработки:
- База данных: `rubicon_user` / `rubicon_pass` / `rubicon_db`
- Redis пароль: `dev_redis_password`
- Django суперпользователь: `admin` / `admin123`

## Шаг 3: Запуск проекта

### Вариант 1: Использование скриптов (рекомендуется)

Просто запустите файл `start.bat` двойным кликом или из командной строки:
```bash
start.bat
```

Для остановки:
```bash
stop.bat
```

### Вариант 2: Ручной запуск через командную строку

После установки Docker Desktop выполните в корневой папке проекта:

```bash
# Сборка образов
docker compose build

# Запуск контейнеров
docker compose up -d

# Просмотр логов
docker compose logs -f
```

## Шаг 4: Доступ к приложению

После запуска контейнеров:

- **Веб-интерфейс**: http://localhost:8888/admin
  - Логин: `admin`
  - Пароль: `admin123`

- **Страница входа**: http://localhost:8888/login/standard/

- **API**: http://localhost:8888/api/flights/

- **Дашборд (Старт/Стоп)**: http://localhost:8888/dashboard/

- **Telegram-бот**: поднимается вместе со стеком (`rubicon_tg_bot`, `python manage.py run_telegram_bot`).  
  Один `.env`, одна БД с Django. Не запускайте второй экземпляр бота с тем же `TOKEN`.

  В `.env` для группы Старт/Стоп: `TELEGRAM_LIVE_FLIGHT_CHAT_ID=-1003960872491`

## Шаг 5: Первоначальная настройка

1. Войдите в админ-панель Django
2. Заполните справочники (минимум по одной записи в каждом):
   - Дроны
   - Направления
   - Типы ВВ
   - Типы взрывателей
   - Типы коррективов
   - Типы целей

## Полезные команды

```bash
# Остановка контейнеров
docker compose down

# Перезапуск контейнеров
docker compose restart

# Просмотр статуса
docker compose ps

# Просмотр логов конкретного сервиса
docker compose logs api
docker compose logs tg-bot

# Выполнение команд в контейнере
docker compose exec api python manage.py migrate
docker compose exec api python manage.py createsuperuser
```

## Устранение проблем

### Порт 8888 занят
Если порт 8888 занят, измените в `docker-compose.yaml` порт для `webserver`:
```yaml
ports:
  - "8080:80"  # Используйте другой порт вместо 8888
```

**Примечание:** После изменения порта также обновите `CSRF_TRUSTED_ORIGINS` в `.env` файле или `config/settings.py`.

### Ошибки при сборке
```bash
# Очистка и пересборка
docker compose down
docker compose build --no-cache
docker compose up -d
```

### Проблемы с базой данных
```bash
# Пересоздание базы данных
docker compose down -v
docker compose up -d
```

