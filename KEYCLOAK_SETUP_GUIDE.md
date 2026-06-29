# Полная инструкция по настройке Keycloak для Django

## Шаг 1: Создание клиента в Keycloak

1. Войдите в Keycloak Admin Console: https://static.88.68.91.77.ip.webhost1.net/admin/master/console/#/Rubik
2. Перейдите в **Realm "Rubik"** → **Clients** → **Create client**

### Настройки клиента:

**General Settings:**
- **Client ID**: `django-app` (или любое другое имя)
- **Client authentication**: **OFF** (это делает клиент public, client_secret не нужен)
- **Authorization**: OFF
- Нажмите **Next**

**Capability config:**
- **Standard flow**: ON
- **Direct access grants**: **ON** (ОБЯЗАТЕЛЬНО! Без этого не будет работать вход по username/password)
- **Service accounts roles**: OFF (если не нужен)
- Нажмите **Next**

**Login settings:**
- **Root URL**: `http://localhost` (или ваш домен)
- **Home URL**: `http://localhost` (или ваш домен)
- **Valid redirect URIs**: `*` (для теста) или `http://localhost/*` (для продакшена)
- **Web origins**: `*` (для теста) или `http://localhost` (для продакшена)
- Нажмите **Save**

## Шаг 2: Создание пользователей в Keycloak

1. В Keycloak Admin Console перейдите в **Realm "Rubik"** → **Users** → **Create new user**

2. Заполните форму:
   - **Username**: например, `admin` или `rubicon-app` (любое имя)
   - **Email**: email пользователя (опционально)
   - **First name**, **Last name** (опционально)
   - **Email verified**: ON (если указан email)
   - **Enabled**: ON (обязательно!)
   - Нажмите **Create**

3. Установите пароль:
   - Перейдите на вкладку **Credentials**
   - Нажмите **Set password**
   - Введите пароль (например, `gu6qaxlk`)
   - **Temporary**: OFF (чтобы пароль не требовал смены при первом входе)
   - Нажмите **Save**

4. Повторите для всех пользователей, которым нужен доступ к сайту

## Шаг 3: Настройка Django (.env файл)

Добавьте в `.env`:

```env
KEYCLOAK_SERVER_URL=https://static.88.68.91.77.ip.webhost1.net
KEYCLOAK_REALM_NAME=Rubik
KEYCLOAK_CLIENT_ID=django-app  # Имя клиента, созданного в шаге 1
KEYCLOAK_CLIENT_SECRET=  # Оставьте пустым для public клиента
KEYCLOAK_VERIFY_SSL=False
```

## Шаг 4: Как это работает

1. Пользователь вводит **username** и **password** на странице входа Django
2. Django отправляет запрос в Keycloak для проверки учетных данных
3. Если Keycloak подтверждает, Django:
   - Создает пользователя в своей БД (если его еще нет)
   - Или обновляет существующего пользователя
   - Авторизует пользователя в Django

## Важно

- **Пользователи должны быть созданы в Keycloak** - это источник истины для аутентификации
- Django автоматически синхронизирует пользователей при входе
- Если пользователь удален из Keycloak, он не сможет войти в Django
- Пароли хранятся только в Keycloak, не в Django

## Проверка работы

1. Создайте пользователя в Keycloak (шаг 2)
2. Установите пароль для пользователя
3. Войдите на сайт Django с этими учетными данными
4. Если все настроено правильно, вы должны быть авторизованы











