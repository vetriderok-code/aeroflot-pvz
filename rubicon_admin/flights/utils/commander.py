from django.db.models import Q, QuerySet

from flights.models import OperatorLocation, OperatorProfile, Pilot

COMMANDER_GROUP_NAME = 'Командиры'


def get_commander_pilot_id(user) -> str | None:
    if not user or not user.is_authenticated:
        return None
    return getattr(user, 'pilot_id', None)


def user_is_commander(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if user.groups.filter(name=COMMANDER_GROUP_NAME).exists():
        return bool(get_commander_pilot_id(user))
    pilot_id = get_commander_pilot_id(user)
    if pilot_id and OperatorLocation.objects.filter(senior_id=pilot_id, is_active=True).exists():
        return True
    return False


def user_is_commander_only(user) -> bool:
    """Командир без доступа к полной админке."""
    return user_is_commander(user) and not user.is_superuser and not user.is_staff


def commander_team_profile_qs(user) -> QuerySet[OperatorProfile]:
    pilot_id = get_commander_pilot_id(user)
    if not pilot_id:
        return OperatorProfile.objects.none()
    return (
        OperatorProfile.objects
        .filter(Q(senior_id=pilot_id) | Q(location__senior_id=pilot_id))
        .select_related('pilot', 'senior', 'location', 'location__senior')
    )


def commander_team_pilot_qs(user) -> QuerySet[Pilot]:
    pilot_ids = commander_team_profile_qs(user).values_list('pilot_id', flat=True)
    return Pilot.objects.filter(pk__in=pilot_ids).select_related(
        'operator_profile',
        'operator_profile__location',
    )


def commander_can_edit_location(user, location: OperatorLocation) -> bool:
    pilot_id = get_commander_pilot_id(user)
    return bool(pilot_id and location.senior_id == pilot_id)


def get_post_login_url(user) -> str:
    if user.is_superuser:
        return '/admin/'
    if user.groups.filter(name=COMMANDER_GROUP_NAME).exists() and get_commander_pilot_id(user):
        return '/commander/'
    pilot_id = get_commander_pilot_id(user)
    if pilot_id and OperatorLocation.objects.filter(senior_id=pilot_id, is_active=True).exists():
        return '/commander/'
    if user.is_staff:
        return '/admin/'
    return '/'
