from django.contrib import admin
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _

from flights.admin_operators import OperatorLocationAdmin, OperatorProfileAdmin
from flights.forms_operators import CommanderOperatorLocationAdminForm, PilotAdminForm
from flights.models import OperatorLocation, OperatorProfile, Pilot
from flights.utils.commander import (
    commander_team_pilot_qs,
    commander_team_profile_qs,
    user_is_commander,
)


class CommanderAdminSite(admin.AdminSite):
    site_header = _('Кабинет командира')
    site_title = _('Командир')
    index_title = _('Управление командой')
    index_template = 'admin/commander/index.html'

    def has_permission(self, request):
        return request.user.is_active and user_is_commander(request.user)

    def login(self, request, extra_context=None):
        next_url = request.GET.get('next', '/commander/')
        return redirect(f'/login/?next={next_url}')


class CommanderAdminMixin:
    change_list_template = 'admin/commander/change_list.html'
    change_form_template = 'admin/commander/change_form.html'


class CommanderOperatorLocationAdmin(CommanderAdminMixin, OperatorLocationAdmin):
    """Все активные расположения; командир может менять название и связь."""

    form = CommanderOperatorLocationAdminForm
    list_display = ('name', 'comm_links_display', 'senior', 'operators_count')
    list_editable = ()
    list_filter = ('is_active',)
    search_fields = ('name', 'senior__callname')
    readonly_fields = (
        'id', 'created', 'modified', 'senior', 'description', 'sort_order', 'is_active',
    )
    fieldsets = (
        (None, {
            'fields': ('name', 'comm_links'),
        }),
        (_('Информация'), {
            'fields': ('senior', 'description', 'sort_order', 'is_active'),
        }),
        (_('Служебное'), {
            'fields': ('id', 'created', 'modified'),
            'classes': ('collapse',),
        }),
    )

    def get_queryset(self, request):
        return (
            super(OperatorLocationAdmin, self)
            .get_queryset(request)
            .filter(is_active=True)
            .select_related('senior')
        )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return user_is_commander(request.user)


class CommanderOperatorProfileAdmin(CommanderAdminMixin, OperatorProfileAdmin):
    """Пилоты команды: перемещение и смена зоны."""

    list_display = (
        'pilot',
        'location',
        'placement_zone',
        'senior',
        'duty_started_at',
    )
    list_editable = ('location', 'placement_zone')
    list_filter = ('placement_zone', 'location', 'is_active')
    actions = ('mark_day_shift', 'mark_night_shift', 'mark_detachment')

    def get_queryset(self, request):
        return commander_team_profile_qs(request.user)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        if not user_is_commander(request.user):
            return False
        if obj is None:
            return True
        return commander_team_profile_qs(request.user).filter(pk=obj.pk).exists()

    def has_view_permission(self, request, obj=None):
        return self.has_change_permission(request, obj)


class CommanderPilotAdmin(CommanderAdminMixin, admin.ModelAdmin):
    """Модель дрона для пилотов своей команды."""

    form = PilotAdminForm
    list_display = ('callname', 'drone_type', 'duty_location', 'duty_zone')
    search_fields = ('callname',)
    ordering = ('callname',)
    readonly_fields = ('callname',)

    fieldsets = (
        (None, {
            'fields': ('callname', 'drone_model'),
            'description': _('Измените модель дрона для пилота вашей команды.'),
        }),
    )

    def get_queryset(self, request):
        return commander_team_pilot_qs(request.user)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        if not user_is_commander(request.user):
            return False
        if obj is None:
            return True
        return commander_team_pilot_qs(request.user).filter(pk=obj.pk).exists()

    def has_view_permission(self, request, obj=None):
        return self.has_change_permission(request, obj)

    @admin.display(description=_('Расположение'))
    def duty_location(self, obj):
        profile = getattr(obj, 'operator_profile', None)
        if profile and profile.location_id:
            return profile.location.name
        return '—'

    @admin.display(description=_('Зона'))
    def duty_zone(self, obj):
        profile = getattr(obj, 'operator_profile', None)
        if profile:
            return profile.get_placement_zone_display()
        return '—'


commander_site = CommanderAdminSite(name='commander')

commander_site.register(OperatorLocation, CommanderOperatorLocationAdmin)
commander_site.register(OperatorProfile, CommanderOperatorProfileAdmin)
commander_site.register(Pilot, CommanderPilotAdmin)
