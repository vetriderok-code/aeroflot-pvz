# flights/backends.py
from django.contrib.auth.backends import BaseBackend
from django.contrib.auth import get_user_model
from flights.models import Pilot
import asyncio
from telegram import Bot
from flights.utils.axes_logger import log_telegram_code_attempt
import logging

logger = logging.getLogger(__name__)

User = get_user_model()


class TelegramAuthBackend(BaseBackend):
    def authenticate(self, request, username=None, code=None):
        if not username or not code:
            return None

        try:
            # Находим пользователя по username
            user = User.objects.get(username=username)

            # Если у пользователя нет пилота, это обычный пользователь
            # и аутентификация через Telegram для него не подходит
            if not user.pilot:
                log_telegram_code_attempt(request, username, code, successful=False)
                return None

            # Проверяем код из сессии только для пользователей с пилотом
            session_code = request.session.get('auth_code')
            if session_code and session_code == code:
                return user
        except User.DoesNotExist:
            logger.info('log code attempt dont exist')
            log_telegram_code_attempt(request, username, code, successful=False)
            return None
        log_telegram_code_attempt(request, username, code, successful=False)
        return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None


# Бэкенд для аутентификации через Keycloak
class KeycloakAuthBackend(BaseBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            logger.debug("KeycloakAuthBackend: username или password не указаны")
            return None

        try:
            from flights.utils.keycloak_auth import keycloak_auth
            
            logger.info(f"KeycloakAuthBackend: попытка аутентификации для {username}")
            
            # Пытаемся аутентифицироваться через Keycloak
            keycloak_user_info = keycloak_auth.authenticate(username, password)
            
            if keycloak_user_info:
                logger.info(f"KeycloakAuthBackend: успешная аутентификация через Keycloak для {username}")
                # Получаем или создаем пользователя Django
                user = keycloak_auth.get_or_create_user(keycloak_user_info)
                if user:
                    logger.info(f"KeycloakAuthBackend: пользователь {username} получен/создан в Django")
                else:
                    logger.error(f"KeycloakAuthBackend: не удалось получить/создать пользователя {username} в Django")
                return user
            else:
                logger.warning(f"KeycloakAuthBackend: аутентификация через Keycloak не удалась для {username}")
        except Exception as e:
            logger.error(f"Ошибка аутентификации через Keycloak: {e}", exc_info=True)
        
        return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None


# Добавим также бэкенд для обычной аутентификации по username/password (fallback)
# Этот бэкенд используется только если Keycloak не сработал
class MixedAuthBackend(BaseBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            logger.debug("MixedAuthBackend: username или password не указаны")
            return None

        try:
            logger.info(f"MixedAuthBackend: попытка аутентификации для {username} (fallback после Keycloak)")
            user = User.objects.get(username=username)
            logger.debug(f"MixedAuthBackend: пользователь {username} найден в БД")
            
            # Проверяем, есть ли у пользователя установленный пароль в Django
            # Если пароля нет - значит пользователь должен аутентифицироваться через Keycloak
            if not user.has_usable_password():
                logger.info(f"MixedAuthBackend: у пользователя {username} нет локального пароля, пропускаем (должен использоваться Keycloak)")
                return None
            
            if user.check_password(password):
                logger.info(f"MixedAuthBackend: успешная аутентификация для {username} через локальную БД")
                return user
            else:
                logger.warning(f"MixedAuthBackend: неверный пароль для {username}")
        except User.DoesNotExist:
            logger.warning(f"MixedAuthBackend: пользователь {username} не найден в БД")
            return None
        return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None