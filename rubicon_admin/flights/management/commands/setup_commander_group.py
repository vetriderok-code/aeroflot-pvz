from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand

from flights.utils.commander import COMMANDER_GROUP_NAME


PERMISSION_CODENAMES = (
    'view_operatorlocation',
    'change_operatorlocation',
    'view_operatorprofile',
    'change_operatorprofile',
    'view_pilot',
    'change_pilot',
)


class Command(BaseCommand):
    help = 'Создаёт группу «Командиры» с правами для кабинета командира.'

    def handle(self, *args, **options):
        group, created = Group.objects.get_or_create(name=COMMANDER_GROUP_NAME)
        perms = Permission.objects.filter(
            content_type__app_label='flights',
            codename__in=PERMISSION_CODENAMES,
        )
        group.permissions.set(perms)
        action = 'Создана' if created else 'Обновлена'
        self.stdout.write(
            self.style.SUCCESS(
                f'{action} группа «{COMMANDER_GROUP_NAME}»: {perms.count()} прав.'
            )
        )
        self.stdout.write(
            'Назначение: пользователю привязать pilot (старший точки), '
            f'добавить в группу «{COMMANDER_GROUP_NAME}», is_staff=False.'
        )
