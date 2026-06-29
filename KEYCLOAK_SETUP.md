# Настройка Keycloak для аутентификации

## Переменные окружения

Добавьте следующие переменные в файл `.env`:

```env
# Keycloak настройки
KEYCLOAK_SERVER_URL=https://static.88.68.91.77.ip.webhost1.net
KEYCLOAK_REALM_NAME=Rubik
KEYCLOAK_CLIENT_ID=rubicon-app
KEYCLOAK_CLIENT_SECRET=  # Оставьте пустым для public клиента, или укажите секрет для confidential
KEYCLOAK_VERIFY_SSL=False  # Отключить проверку SSL для самоподписанных сертификатов
```

## Настройка Keycloak

### Шаг 1: Создание клиента

1. Войдите в Keycloak Admin Console: https://static.88.68.91.77.ip.webhost1.net/admin/master/console/#/Rubik
2. Перейдите в realm "Rubik"
3. В меню слева выберите **Clients** → **Create client**

### Шаг 2: Настройка клиента "rubicon-app"

**Рекомендуемый вариант (Public клиент - без секрета):**

1. **General Settings:**
   - Client ID: `rubicon-app`
   - Client authentication: **OFF** (это делает клиент public)
   - Authorization: OFF
   - Authentication flow: Standard flow

2. **Login settings:**
   - Root URL: `http://localhost:8888` (или ваш URL)
   - Home URL: `http://localhost:8888`
   - Valid redirect URIs: `http://localhost:8888/*` (или `*` для тестирования)
   - Web origins: `http://localhost:8888` (или `*` для тестирования)

3. Сохраните клиент

**Альтернативный вариант (Confidential клиент - с секретом):**

1. **General Settings:**
   - Client ID: `rubicon-app`
   - Client authentication: **ON** (это делает клиент confidential)
   - Authorization: OFF
   - Authentication flow: Standard flow

2. **Login settings:**
   - Root URL: `http://localhost:8888`
   - Home URL: `http://localhost:8888`
   - Valid redirect URIs: `http://localhost:8888/*`
   - Web origins: `http://localhost:8888`

3. Сохраните клиент

4. Перейдите на вкладку **Credentials**
5. Скопируйте значение **Client secret**
6. Добавьте его в `.env`: `KEYCLOAK_CLIENT_SECRET=скопированный_секрет`

### Шаг 3: Создание пользователя (если еще не создан)

1. В меню слева выберите **Users** → **Create new user**
2. Заполните:
   - Username: ваш логин
   - Email: ваш email
   - First name, Last name (опционально)
3. Сохраните пользователя
4. Перейдите на вкладку **Credentials**
5. Установите пароль для пользователя
6. Отключите "Temporary" (чтобы пароль не требовал смены при первом входе)

## Как это работает

1. Пользователь вводит логин и пароль на странице входа
2. Django пытается аутентифицировать через Keycloak (приоритет)
3. Если Keycloak успешно аутентифицирует, создается или обновляется пользователь в Django
4. Если Keycloak не доступен или не находит пользователя, используется fallback на локальную БД

## Установка зависимостей

После добавления `python-keycloak` в `requirements.txt`, выполните:

```bash
docker-compose build api
docker-compose restart api
```

## Проверка работы

1. Откройте страницу входа
2. Введите учетные данные из Keycloak
3. Если все настроено правильно, вы должны быть аутентифицированы через Keycloak

