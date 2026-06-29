# БЛОКИРОВКА ОТКЛЮЧЕНА
# Отключаем блокировку пользователей по неправильному вводу
AXES_ENABLED = False

# Максимальное количество неудачных попыток (не используется, т.к. блокировка отключена)
AXES_FAILURE_LIMIT = 999999

AXES_LOCKOUT_PARAMETERS = [["username"], ["ip_address"]]

# Сообщение при блокировке (не используется, т.к. блокировка отключена)
AXES_LOCKOUT_TEMPLATE = 'lockout.html'

# AXES_PROXY_COUNT устарел в новой версии axes, используем AXES_META_IP

# Используйте правильный заголовок для получения IP
#AXES_META_IP = 'HTTP_X_FORWARDED_FOR'
AXES_META_IP = 'REMOTE_ADDR'

# Логирование (можно оставить для мониторинга попыток входа)
AXES_ENABLE_ACCESS_LOG = True

# Сброс счетчика при успешном входе
AXES_RESET_ON_SUCCESS = False