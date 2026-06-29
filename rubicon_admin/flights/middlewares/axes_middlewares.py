# middleware.py
import logging

logger = logging.getLogger('axes')


class RealIPMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Извлекаем реальный IP
        real_ip = self.get_real_ip(request)
        if real_ip:
            # Сохраняем оригинальный REMOTE_ADDR для отладки
            request.original_remote_addr = request.META.get('REMOTE_ADDR')
            # Заменяем REMOTE_ADDR на реальный IP
            request.META['REMOTE_ADDR'] = real_ip
            logger.info(f"IP overridden: {request.original_remote_addr} -> {real_ip}")
        else:
            logger.info("Real IP not found, using original REMOTE_ADDR")

        response = self.get_response(request)
        return response

    def get_real_ip(self, request):
        """Извлекаем реальный IP клиента"""
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
            logger.info(f"Parsed X-Forwarded-For IPs: {ips}")
            if ips:
                # Ищем первый "внешний" IP
                internal_prefixes = ['127.', '10.', '172.16.', '172.17.', '172.18.', '172.19.', '192.168.']
                for ip in ips:
                    is_internal = any(ip.startswith(prefix) for prefix in internal_prefixes)
                    if not is_internal:
                        logger.info(f"Using external IP: {ip}")
                        return ip
                # Если внешних нет, берем первый
                logger.info(f"Using first IP: {ips[0]}")
                return ips[0]

        # Приоритет 3: X-Real-IP
        real_ip = request.META.get('HTTP_X_REAL_IP')
        if real_ip:
            logger.info(f"Using X-Real-IP: {real_ip}")
            return real_ip

        logger.info("No real IP found in headers")
        return None