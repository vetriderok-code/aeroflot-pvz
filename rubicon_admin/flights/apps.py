from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class FlightConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'flights'
    verbose_name = _('Вылеты')

    def ready(self):
        import flights.signals  # noqa: F401
        import flights.admin_commander  # noqa: F401
