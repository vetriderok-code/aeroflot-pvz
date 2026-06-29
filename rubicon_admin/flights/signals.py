from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from flights.models import Flight
import logging


logger = logging.getLogger(__name__)

@receiver(post_save, sender=Flight)
def update_flight_coordinates(sender, instance, created, **kwargs):
    logger.info('Updating flight coordinates')
    if created or instance.coordinates:
        with transaction.atomic():
            try:
                fresh_instance = sender.objects.get(pk=instance.pk)
                if (fresh_instance.lat_wgs84 is None or fresh_instance.lon_wgs84 is None or
                        fresh_instance.coordinates != getattr(instance, '_original_coordinates', None)):
                    fresh_instance.get_coordinates_info_cached()

            except Exception as e:
                logger.error(f"Ошибка при автоматическом пересчете координат для полета {instance.id}: {e}")