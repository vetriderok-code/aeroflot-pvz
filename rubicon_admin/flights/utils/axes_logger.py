# flights/utils/axes_logger.py
from axes.helpers import get_client_ip_address, get_client_user_agent
from axes.signals import user_login_failed, user_logged_in
from django.contrib.auth import get_user_model
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


def log_telegram_auth_attempt(request, username, successful=True, credentials=None):
    """
    Логирование попытки аутентификации через Telegram в Axes
    """
    logger.info('log auth attempt')

    if credentials is None:
        credentials = {}

    credentials['username'] = username
    credentials['auth_method'] = 'telegram'

    if successful:
        # Для успешной аутентификации
        try:
            user = User.objects.get(username=username)
            user_logged_in.send(
                sender=User,
                request=request,
                user=user
            )
        except User.DoesNotExist:
            # Если пользователя нет, логируем как неудачную попытку
            user_login_failed.send(
                sender=User,
                request=request,
                credentials=credentials
            )
    else:
        # Для неудачной попытки
        user_login_failed.send(
            sender=User,
            request=request,
            credentials=credentials
        )


def log_telegram_code_attempt(request, username, code_entered, successful=True):
    """
    Логирование попытки ввода кода через Telegram
    """
    logger.info('log code attempt')

    credentials = {
        'username': username,
        'telegram_code': code_entered,
        'auth_method': 'telegram_code'
    }

    if successful:
        # Для успешного ввода кода
        try:
            user = User.objects.get(username=username)
            user_logged_in.send(
                sender=User,
                request=request,
                user=user
            )
        except User.DoesNotExist:
            # Если пользователя нет, логируем как неудачную попытку
            user_login_failed.send(
                sender=User,
                request=request,
                credentials=credentials
            )
    else:
        # Для неудачного ввода кода
        user_login_failed.send(
            sender=User,
            request=request,
            credentials=credentials
        )