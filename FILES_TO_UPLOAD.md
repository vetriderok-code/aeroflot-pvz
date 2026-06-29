# Файлы для загрузки на продакшн-сервер

## Текущий путь к проекту (локально):
```
C:\Users\reshe\Downloads\Telegram Desktop\rubicon_bot_docker — export
```

## Путь на сервере (куда загружать):
```
/opt/rubicon
```

## Структура проекта и файлы для загрузки:

### Обязательные файлы и директории:

```
rubicon_bot_docker — export/
├── docker-compose.prod.yaml          # ✅ ОБЯЗАТЕЛЬНО - конфигурация для продакшна
├── env.prod.example                  # ✅ ОБЯЗАТЕЛЬНО - пример переменных окружения
├── get-ssl-cert.sh                   # ✅ ОБЯЗАТЕЛЬНО - скрипт получения SSL
├── deploy.sh                         # ✅ ОБЯЗАТЕЛЬНО - скрипт развертывания
│
├── api/                              # ✅ ОБЯЗАТЕЛЬНО - директория API
│   ├── Dockerfile
│   ├── requirements.txt
│   └── entrypoint.sh
│
├── nginx/                            # ✅ ОБЯЗАТЕЛЬНО - конфигурация Nginx
│   ├── Dockerfile
│   └── conf.d/
│       ├── prod.conf                 # ✅ ОБЯЗАТЕЛЬНО - конфигурация для продакшна
│       └── init.conf                 # ✅ ОБЯЗАТЕЛЬНО - временная конфигурация
│
├── rubicon_admin/                    # ✅ ОБЯЗАТЕЛЬНО - Django приложение
│   ├── config/
│   ├── flights/
│   ├── manage.py
│   └── ... (вся директория)
│
├── video_files/                      # ⚠️ Опционально - если есть видео файлы
│
└── certbot/                          # ⚠️ Создается автоматически, но можно создать пустые директории
    ├── conf/
    └── www/
```

### Файлы, которые НЕ нужно загружать:

```
❌ .env                    # Локальные переменные окружения
❌ .env.prod               # Создается на сервере из env.prod.example
❌ docker-compose.yaml     # Локальная версия (используем .prod.yaml)
❌ .git/                   # Если используете git на сервере
❌ __pycache__/            # Кеш Python
❌ *.pyc                   # Скомпилированные файлы Python
❌ .redis_data/            # Данные Redis (создаются на сервере)
❌ node_modules/           # Если есть
❌ .vscode/                # Настройки IDE
❌ *.log                   # Логи
```

## Команды для загрузки на сервер:

### Вариант 1: Через SCP (с локальной Windows машины)

```powershell
# Из PowerShell на Windows
cd "C:\Users\reshe\Downloads\Telegram Desktop\rubicon_bot_docker — export"

# Загрузка всех необходимых файлов
scp -r api root@46.17.40.216:/opt/rubicon/
scp -r nginx root@46.17.40.216:/opt/rubicon/
scp -r rubicon_admin root@46.17.40.216:/opt/rubicon/
scp docker-compose.prod.yaml root@46.17.40.216:/opt/rubicon/
scp env.prod.example root@46.17.40.216:/opt/rubicon/
scp get-ssl-cert.sh root@46.17.40.216:/opt/rubicon/
scp deploy.sh root@46.17.40.216:/opt/rubicon/

# Если есть video_files
scp -r video_files root@46.17.40.216:/opt/rubicon/
```

### Вариант 2: Через Git (рекомендуется)

```bash
# На сервере
cd /opt/rubicon
git clone your_repository_url .
# или
git pull origin main
```

### Вариант 3: Через архив (tar/zip)

```powershell
# На локальной машине (Windows)
# Создайте архив с нужными файлами
# Используйте 7-Zip или WinRAR для создания .tar.gz или .zip

# Затем загрузите на сервер
scp project.tar.gz root@46.17.40.216:/opt/rubicon/

# На сервере распакуйте
ssh root@46.17.40.216
cd /opt/rubicon
tar -xzf project.tar.gz
```

### Вариант 4: Через rsync (если установлен на Windows)

```powershell
# Установите rsync для Windows или используйте WSL
wsl rsync -avz --exclude='.env' --exclude='.git' --exclude='__pycache__' \
  --exclude='*.pyc' --exclude='.redis_data' \
  ./ root@46.17.40.216:/opt/rubicon/
```

## Минимальный набор файлов (если загружаете вручную):

Если загружаете файлы по одному, обязательно нужны:

1. `docker-compose.prod.yaml`
2. `env.prod.example`
3. `get-ssl-cert.sh`
4. `deploy.sh`
5. `api/` (вся директория)
6. `nginx/` (вся директория)
7. `rubicon_admin/` (вся директория)

## Проверка после загрузки:

```bash
# На сервере проверьте наличие файлов
ssh root@46.17.40.216
cd /opt/rubicon
ls -la

# Должны быть:
# - docker-compose.prod.yaml
# - env.prod.example
# - api/
# - nginx/
# - rubicon_admin/
# - get-ssl-cert.sh
# - deploy.sh
```

## Создание .env.prod на сервере:

```bash
# На сервере
cd /opt/rubicon
cp env.prod.example .env.prod
nano .env.prod  # Заполните все значения
```

## Создание директорий для Certbot:

```bash
# На сервере
cd /opt/rubicon
mkdir -p certbot/conf certbot/www
```











