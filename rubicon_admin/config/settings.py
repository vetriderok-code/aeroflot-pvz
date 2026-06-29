import os
from pathlib import Path

from dotenv import load_dotenv
from split_settings.tools import include

load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/3.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY', 'secret_key')
YANDEX_API_KEY = os.getenv('YANDEX_API_KEY', 'yandex_secret_key')
YANDEX_API_KEY_EXTRA = os.getenv('YANDEX_API_KEY_EXTRA', '')
MAP_GSH_ENABLED = os.getenv('MAP_GSH_ENABLED', 'True').lower() in ('true', '1', 'yes')
# Upstream-шаблон(ы) для серверного прокси (| — fallback). Пусто = авто по масштабу ГГЦ.
MAP_GSH_TILE_URL = os.getenv('MAP_GSH_TILE_URL', '')
MAP_GSH_UPSTREAM_URLS = os.getenv('MAP_GSH_UPSTREAM_URLS', '')
# URL для браузера — всегда same-origin прокси (куки + локальный кэш SAS).
MAP_GSH_BROWSER_TILE_URL = os.getenv(
    'MAP_GSH_BROWSER_TILE_URL',
    '/api/map-tiles/gsh/{z}/{x}/{y}.png',
)
MAP_GSH_SERVER_NAMES = os.getenv('MAP_GSH_SERVER_NAMES', 'a,b,c')
MAP_GSH_CACHE_DIR = os.getenv('MAP_GSH_CACHE_DIR', '')
MAP_GSH_REFERER = os.getenv('MAP_GSH_REFERER', 'https://nakarte.me/')
MAP_GSH_ZOOM_MIN = int(os.getenv('MAP_GSH_ZOOM_MIN', '6'))
MAP_GSH_ZOOM_MAX = int(os.getenv('MAP_GSH_ZOOM_MAX', '15'))
TOKEN = os.getenv('TOKEN', 'token')
LIVE_FLIGHT_BOT_SECRET = os.getenv('LIVE_FLIGHT_BOT_SECRET', '')
TELEGRAM_ALERTS_CHAT_ID = int(
    os.getenv('TELEGRAM_ALERTS_CHAT_ID')
    or os.getenv('TELEGRAM_LIVE_FLIGHT_CHAT_ID', '-1003960872491')
)
TELEGRAM_ALERTS_TOPIC_ID = int(os.getenv('TELEGRAM_ALERTS_TOPIC_ID', '2408'))
TELEGRAM_REPORTS_CHAT_ID = int(
    os.getenv('TELEGRAM_REPORTS_CHAT_ID')
    or os.getenv('TELEGRAM_LIVE_FLIGHT_CHAT_ID', '-1003960872491')
)
TELEGRAM_REPORTS_TOPIC_ID = int(os.getenv('TELEGRAM_REPORTS_TOPIC_ID', '2406'))
# Отчетный квартал ТД — видео-отчёты (топики 1 ИГ / 2 ИГ / 3 ИГ)
TELEGRAM_VIDEO_REPORTS_CHAT_ID = os.getenv(
    'TELEGRAM_VIDEO_REPORTS_CHAT_ID',
    os.getenv('TELEGRAM_TD_REPORTS_CHAT_ID', ''),
)
TELEGRAM_VIDEO_REPORT_TOPIC_IDS = os.getenv(
    'TELEGRAM_VIDEO_REPORT_TOPIC_IDS',
    os.getenv('TELEGRAM_TD_REPORT_TOPIC_IDS', ''),
)
DASHBOARD_SHIFT_DAY_START_HOUR = int(os.getenv('DASHBOARD_SHIFT_DAY_START_HOUR', '6'))
DASHBOARD_SHIFT_NIGHT_START_HOUR = int(os.getenv('DASHBOARD_SHIFT_NIGHT_START_HOUR', '18'))
DASHBOARD_WEATHER_REGIONS = os.getenv('DASHBOARD_WEATHER_REGIONS', '')
PORTAL_SITE_NAME = os.getenv('PORTAL_SITE_NAME', 'Тяжелые Дроны')
DASHBOARD_ENABLED = os.getenv('DASHBOARD_ENABLED', 'True').lower() in ('true', '1', 'yes')
EXCEL_IMPORT_ASYNC = os.getenv('EXCEL_IMPORT_ASYNC', 'False').lower() in ('true', '1', 'yes')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG', False) == 'True'

# CSRF настройки
CSRF_COOKIE_SECURE = os.getenv('CSRF_COOKIE_SECURE', 'True').lower() in ('true', '1', 'yes')
CSRF_TRUSTED_ORIGINS = os.getenv(
    'CSRF_TRUSTED_ORIGINS',
    'https://himchistkacovrov.ru,https://aeroflot-pvz.ru,https://www.aeroflot-pvz.ru',
).split(',')

CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'", "'unsafe-inline'")

# HTTPS
SECURE_SSL_REDIRECT = False
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Cookies
SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'True').lower() in ('true', '1', 'yes')
SESSION_COOKIE_HTTPONLY = True

# HSTS
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# XSS защита
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True

# Referrer Policy
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'


# ALLOWED_HOSTS: если установлена переменная окружения, используем её, иначе используем значения по умолчанию
_default_allowed_hosts = [
    'localhost', '127.0.0.1',
    'aeroflot-pvz.ru', 'www.aeroflot-pvz.ru',
    'airlineportal.ru', 'www.airlineportal.ru',
    'himchistkacovrov.ru',
]
_allowed_hosts_from_env = [
    h.strip() for h in os.getenv('DJANGO_ALLOWED_HOSTS', '').replace(',', ' ').split() if h.strip()
]
if _allowed_hosts_from_env and _allowed_hosts_from_env != ['']:
    # Если переменная окружения установлена, используем её и добавляем обязательные домены
    ALLOWED_HOSTS = list(set(_allowed_hosts_from_env + [
        'aeroflot-pvz.ru', 'www.aeroflot-pvz.ru',
        'airlineportal.ru', 'www.airlineportal.ru',
        'rubicon-api',
    ]))
else:
    # Иначе используем значения по умолчанию
    ALLOWED_HOSTS = _default_allowed_hosts
INTERNAL_IPS = ['127.0.0.1']


# Application definition

INSTALLED_APPS = [
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'flights.apps.FlightConfig',
    'debug_toolbar',
    'axes',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'debug_toolbar.middleware.DebugToolbarMiddleware',
    'flights.middlewares.axes_middlewares.RealIPMiddleware',
    'flights.middlewares.commander_middleware.CommanderAccessMiddleware',
    # 'axes.middleware.AxesMiddleware',  # Отключен - блокировка по ошибкам входа отключена
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR / 'templates',
            BASE_DIR / 'flights' / 'templates',
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'flights.context_processors.portal_branding',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


include(
    'components/database.py',
    'components/jazzmin_panel.py',
    'components/rest_fw.py',
    'components/axes_fw.py',
)


# Password validation
# https://docs.djangoproject.com/en/3.2/ref/settings/#auth-password-validators

AUTHENTICATION_BACKENDS = [
    # 'axes.backends.AxesBackend',  # Отключен - блокировка по ошибкам входа отключена
    'flights.backends.auth_backend.KeycloakAuthBackend',  # Сначала пробуем Keycloak
    'flights.backends.auth_backend.MixedAuthBackend',  # Затем локальная БД (fallback)
    'flights.backends.auth_backend.TelegramAuthBackend',
    'django.contrib.auth.backends.ModelBackend',
]

AUTH_USER_MODEL = 'flights.User'

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

DATA_UPLOAD_MAX_NUMBER_FIELDS = 10000
DATA_UPLOAD_MAX_MEMORY_SIZE = 52428800

# Internationalization
#   https://docs.djangoproject.com/en/3.2/topics/i18n/

LANGUAGE_CODE = 'ru'

TIME_ZONE = 'Europe/Moscow'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.2/howto/static-files/

STATIC_URL = '/static/'

STATIC_ROOT = os.path.join(BASE_DIR, 'static')

STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'staticfiles'),
]

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
TELEGRAM_REPORT_VIDEO_DIR = os.getenv(
    'TELEGRAM_REPORT_VIDEO_DIR',
    os.path.join(BASE_DIR, 'static', 'video', 'telegram_reports'),
)
TELEGRAM_REPORT_VIDEO_RETENTION_DAYS = int(
    os.getenv('TELEGRAM_REPORT_VIDEO_RETENTION_DAYS', '365')
)
TELEGRAM_BOT_API_URL = os.getenv('TELEGRAM_BOT_API_URL', '').strip()

# Автоимпорт Excel вылетов с NAS-шары (cron import_flights_from_share)
FLIGHTS_EXCEL_IMPORT_DIR = os.getenv(
    'FLIGHTS_EXCEL_IMPORT_DIR',
    '/data/Gerasimenko/ГБУ',
)
FLIGHTS_EXCEL_IMPORT_FILENAME = os.getenv(
    'FLIGHTS_EXCEL_IMPORT_FILENAME',
    'ТАБ_ПИСЬМЕННОГО_ДОКЛАДА_ПИЛОТОВ_НОВАЯ2.xlsm',
)

# Default primary key field type
# https://docs.djangoproject.com/en/3.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOCALE_PATHS = ['flights/locale']

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}
'''
LOGGING = {
    'version': 1,
    'core.handlers': {
        'level': 'INFO',
        'handlers': ['console']
    },
    'filters': {
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        }
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'filters': ['require_debug_true'],
            'class': 'logging.StreamHandler',
        }
    },
    'loggers': {
        'django.db.backends': {
            'level': 'DEBUG',
            'handlers': ['console'],
        }
    },
}'''

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'

SESSION_COOKIE_AGE = 86400  # 1 сутки
SESSION_SAVE_EVERY_REQUEST = True