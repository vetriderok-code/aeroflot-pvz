"""
Утилита для аутентификации через Keycloak
"""
import logging
import requests
from keycloak import KeycloakOpenID
from django.conf import settings
from flights.models import User

logger = logging.getLogger(__name__)


class KeycloakAuth:
    """Класс для работы с Keycloak аутентификацией"""
    
    def __init__(self):
        """Инициализация подключения к Keycloak"""
        self.server_url = getattr(settings, 'KEYCLOAK_SERVER_URL', 'https://static.88.68.91.77.ip.webhost1.net')
        self.realm_name = getattr(settings, 'KEYCLOAK_REALM_NAME', 'Rubik')
        # Используем встроенный клиент 'account' - он доступен по умолчанию и поддерживает Direct Access Grants
        self.client_id = getattr(settings, 'KEYCLOAK_CLIENT_ID', 'account')
        self.client_secret = getattr(settings, 'KEYCLOAK_CLIENT_SECRET', None)
        self.verify_ssl = getattr(settings, 'KEYCLOAK_VERIFY_SSL', False)  # Отключаем проверку SSL для самоподписанных сертификатов
        
        logger.info(f"Инициализация Keycloak: server={self.server_url}, realm={self.realm_name}, client={self.client_id}, verify_ssl={self.verify_ssl}")
        
        try:
            self.keycloak_openid = KeycloakOpenID(
                server_url=self.server_url,
                client_id=self.client_id,
                realm_name=self.realm_name,
                client_secret_key=self.client_secret,
                verify=self.verify_ssl
            )
            logger.info(f"Keycloak успешно инициализирован")
        except Exception as e:
            logger.error(f"Ошибка инициализации Keycloak: {e}", exc_info=True)
            self.keycloak_openid = None
    
    def authenticate(self, username, password):
        """
        Аутентификация пользователя через Keycloak
        
        Args:
            username: Имя пользователя
            password: Пароль
            
        Returns:
            dict: Словарь с информацией о пользователе или None при ошибке
        """
        if not self.keycloak_openid:
            logger.error("Keycloak не инициализирован")
            return None
        
        try:
            logger.info(f"Попытка аутентификации через Keycloak для пользователя: {username}")
            
            # Формируем URL для получения токена
            token_url = f"{self.server_url}/realms/{self.realm_name}/protocol/openid-connect/token"
            
            # Пробуем несколько клиентов, если основной не работает
            # Сначала пробуем указанный клиент, затем другие варианты
            client_ids_to_try = [self.client_id]
            if self.client_id != self.realm_name:
                client_ids_to_try.append(self.realm_name)  # Realm-level client
            # Добавляем еще варианты для проверки
            additional_clients = ['rubicon-app', 'test', 'django-app']
            for additional_client in additional_clients:
                if additional_client not in client_ids_to_try:
                    client_ids_to_try.append(additional_client)
            
            response = None
            successful_client = None
            
            for client_id_to_try in client_ids_to_try:
                # Параметры для Resource Owner Password Credentials Grant
                data = {
                    'grant_type': 'password',
                    'client_id': client_id_to_try,
                    'username': username,
                    'password': password
                }
                
                # Если есть client_secret, добавляем его
                if self.client_secret:
                    data['client_secret'] = self.client_secret
                
                logger.info(f"Пробуем клиент: {client_id_to_try}")
            
                logger.debug(f"Полные данные запроса: {dict((k, v if k != 'password' else '***') for k, v in data.items())}")
                
                # Отправляем запрос напрямую
                try:
                    response = requests.post(
                        token_url,
                        data=data,
                        verify=self.verify_ssl,
                        timeout=10
                    )
                except requests.exceptions.RequestException as req_error:
                    logger.error(f"Ошибка сети при запросе к Keycloak: {req_error}")
                    continue  # Пробуем следующий клиент
                
                logger.info(f"Ответ от Keycloak для клиента {client_id_to_try}: status={response.status_code}")
                
                if response.status_code == 200:
                    # Успех! Сохраняем успешный клиент и выходим из цикла
                    successful_client = client_id_to_try
                    logger.info(f"✓ Успешная аутентификация с клиентом: {client_id_to_try}")
                    break
                else:
                    error_text = response.text
                    logger.warning(f"Клиент {client_id_to_try} не подошел: {response.status_code} - {error_text}")
                    # Пробуем следующий клиент
                    continue
            
            # Проверяем результат
            if not successful_client or not response or response.status_code != 200:
                # Если все клиенты не подошли
                if response:
                    error_text = response.text
                    logger.error(f"Все клиенты не подошли. Последняя ошибка: {response.status_code} - {error_text}")
                else:
                    logger.error("Не удалось получить ответ от Keycloak ни для одного клиента")
                return None
            
            # Если дошли сюда, значит получили успешный ответ
            if response.status_code != 200:
                error_text = response.text
                logger.error(f"Ошибка получения токена: {response.status_code} - {error_text}")
                
                # Дополнительная диагностика
                if response.status_code == 400 or response.status_code == 401:
                    if 'invalid_client' in error_text:
                        logger.error("КРИТИЧЕСКАЯ ОШИБКА: Клиент не найден или требует client_secret!")
                        logger.error("Проверьте в Keycloak:")
                        logger.error("  1. Существует ли клиент в realm 'Rubik'")
                        logger.error("  2. Если клиент 'confidential' - нужен client_secret в .env")
                        logger.error("  3. Если клиент 'public' - убедитесь, что Client authentication = OFF")
                    elif 'unauthorized_client' in error_text or 'not allowed for direct access grants' in error_text:
                        logger.error("Ошибка: Клиент не поддерживает Direct Access Grants!")
                        logger.error("Проверьте в Keycloak:")
                        logger.error("  1. Включен ли 'Direct Access Grants Enabled' для клиента")
                        logger.error("  2. Используйте клиент, который поддерживает grant_type='password'")
                    elif 'invalid_grant' in error_text:
                        logger.error("Ошибка: Неверный username или password")
                        logger.error("Проверьте в Keycloak:")
                        logger.error("  1. Существует ли пользователь с таким username")
                        logger.error("  2. Правильный ли пароль")
                
                return None
            
            token = response.json()
            
            if not token or 'access_token' not in token:
                logger.warning(f"Не удалось получить токен для пользователя {username}. Ответ: {token}")
                return None
            
            logger.debug(f"Токен получен успешно")
            
            # Получаем информацию о пользователе
            userinfo_url = f"{self.server_url}/realms/{self.realm_name}/protocol/openid-connect/userinfo"
            userinfo_response = requests.get(
                userinfo_url,
                headers={'Authorization': f"Bearer {token['access_token']}"},
                verify=self.verify_ssl,
                timeout=10
            )
            
            if userinfo_response.status_code != 200:
                logger.warning(f"Не удалось получить информацию о пользователе: {userinfo_response.status_code}")
                # Используем username из запроса, если userinfo недоступен
                userinfo = {'preferred_username': username, 'username': username}
            else:
                userinfo = userinfo_response.json()
            
            logger.debug(f"Получена информация о пользователе: {bool(userinfo)}")
            
            result = {
                'username': userinfo.get('preferred_username') or userinfo.get('username') or username,
                'email': userinfo.get('email'),
                'first_name': userinfo.get('given_name') or userinfo.get('first_name', ''),
                'last_name': userinfo.get('family_name') or userinfo.get('last_name', ''),
                'token': token,
                'userinfo': userinfo
            }
            
            logger.info(f"Успешная аутентификация через Keycloak для пользователя: {result['username']}")
            return result
            
        except Exception as e:
            # Логируем детали ошибки для отладки
            error_msg = str(e)
            error_type = type(e).__name__
            
            # Пытаемся получить больше информации об ошибке
            if hasattr(e, 'response'):
                if hasattr(e.response, 'text'):
                    error_msg += f" Response text: {e.response.text}"
                if hasattr(e.response, 'status_code'):
                    error_msg += f" Status code: {e.response.status_code}"
                if hasattr(e.response, 'headers'):
                    error_msg += f" Headers: {e.response.headers}"
            
            logger.error(f"Ошибка аутентификации через Keycloak для {username} (тип: {error_type}): {error_msg}", exc_info=True)
            return None
    
    def get_or_create_user(self, keycloak_user_info):
        """
        Получает или создает пользователя Django на основе данных из Keycloak
        
        Args:
            keycloak_user_info: Словарь с информацией о пользователе из Keycloak
            
        Returns:
            User: Объект пользователя Django
        """
        username = keycloak_user_info.get('username')
        email = keycloak_user_info.get('email')
        
        if not username:
            logger.error("Не указано имя пользователя из Keycloak")
            return None
        
        try:
            # Пытаемся найти существующего пользователя
            user = User.objects.filter(username=username).first()
            
            if user:
                # Обновляем информацию о пользователе
                if email and not user.email:
                    user.email = email
                if keycloak_user_info.get('first_name') and not user.first_name:
                    user.first_name = keycloak_user_info.get('first_name')
                if keycloak_user_info.get('last_name') and not user.last_name:
                    user.last_name = keycloak_user_info.get('last_name')
                user.save()
                return user
            else:
                # Создаем нового пользователя
                # По умолчанию без прав администратора (is_staff=False)
                # Права администратора можно установить вручную через Django Admin
                user = User.objects.create_user(
                    username=username,
                    email=email or '',
                    first_name=keycloak_user_info.get('first_name', ''),
                    last_name=keycloak_user_info.get('last_name', ''),
                    is_active=True,
                    is_staff=False,  # По умолчанию без доступа к админке
                )
                logger.info(f"Создан новый пользователь из Keycloak: {username} (is_staff=False)")
                return user
                
        except Exception as e:
            logger.error(f"Ошибка при создании/получении пользователя {username}: {e}")
            return None


# Глобальный экземпляр для использования в приложении
keycloak_auth = KeycloakAuth()

