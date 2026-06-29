from django.conf import settings


def portal_branding(request):
    return {
        'PORTAL_SITE_NAME': settings.PORTAL_SITE_NAME,
        'DASHBOARD_ENABLED': settings.DASHBOARD_ENABLED,
    }
