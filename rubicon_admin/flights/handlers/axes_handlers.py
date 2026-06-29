# axes_handlers.py
from axes.handlers.database import AxesDatabaseHandler
import logging

logger = logging.getLogger(__name__)


class CustomIPHandler(AxesDatabaseHandler):
    def get_client_ip_address(self, request):
        """Извлекаем реальный IP клиента"""

        logger.info("CustomIPHandler called")

        # Приоритет 1: X-Original-Forwarded-For (самый точный)
        original_forwarded = request.META.get('HTTP_X_ORIGINAL_FORWARDED_FOR')
        if original_forwarded:
            ip = original_forwarded.strip()
            logger.info(f"Using X-Original-Forwarded-For: {ip}")
            return ip

        # Приоритет 2: X-Forwarded-For
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ips = [ip.strip() for ip in x_forwarded_for.split(',')]
            if ips:
                internal_prefixes = ['127.', '10.', '172.16.', '172.17.', '172.18.', '172.19.', '192.168.']
                for ip in ips:
                    is_internal = any(ip.startswith(prefix) for prefix in internal_prefixes)
                    if not is_internal:
                        logger.info(f"Using external IP from X-Forwarded-For: {ip}")
                        return ip
                logger.info(f"Using first IP from X-Forwarded-For: {ips[0]}")
                return ips[0]

        # Приоритет 3: X-Real-IP
        real_ip = request.META.get('HTTP_X_REAL_IP')
        if real_ip:
            logger.info(f"Using X-Real-IP: {real_ip}")
            return real_ip

        # Приоритет 4: REMOTE_ADDR
        remote_addr = request.META.get('REMOTE_ADDR')
        logger.info(f"Using REMOTE_ADDR: {remote_addr}")
        return remote_addr or super().get_client_ip_address(request)