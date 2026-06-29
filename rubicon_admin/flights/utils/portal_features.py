from django.conf import settings
from django.http import Http404


def dashboard_enabled() -> bool:
    return getattr(settings, 'DASHBOARD_ENABLED', True)


def require_dashboard_enabled():
    if not dashboard_enabled():
        raise Http404()
