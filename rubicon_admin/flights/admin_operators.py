from functools import partial

from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.forms.models import modelformset_factory
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _

from flights.forms_operators import (
    OperatorLocationAdminForm,
    OperatorProfileAdminForm,
    OperatorProfileChangeListForm,
    OperatorProfileInlineForm,
    detachment_dest_post_key,
)
from flights.models import OperatorLocation, OperatorPlacementZone, OperatorPositionLog, OperatorProfile
from flights.utils.operator_dashboard import (
    comm_link_labels,
    log_operator_position_change,
)


def _log_location_change(profile, *, old_location_id, old_placement_zone, new_location, user=None, comment=''):
    log_operator_position_change(
        profile=profile,
        old_location_id=old_location_id,
        old_placement_zone=old_placement_zone,
        new_location=new_location,
        recorded_by=user,
        comment=comment,
    )


def save_operator_profile_instances(instances, *, user=None, old_locations=None, old_zones=None, comment=''):
    old_locations = old_locations or {}
    old_zones = old_zones or {}
    for obj in instances:
        obj.save()
        _log_location_change(
            obj,
            old_location_id=old_locations.get(str(obj.pk)),
            old_placement_zone=old_zones.get(str(obj.pk)),
            new_location=obj.location,
            user=user,
            comment=comment,
        )


class OperatorProfileInline(admin.StackedInline):
    model = OperatorProfile
    form = OperatorProfileInlineForm
    fk_name = 'pilot'
    extra = 0
    max_num = 1
    min_num = 0
    can_delete = True

    def get_extra(self, request, obj=None, **kwargs):
        """Без профиля форма не показывалась (extra=0) — смену было негде сохранить."""
        if obj is None:
            return 1
        if OperatorProfile.objects.filter(pilot_id=obj.pk).exists():
            return 0
        return 1
    verbose_name = _('Дежурство')
    verbose_name_plural = _('Дежурство на дашборде')
    fieldsets = (
        (None, {
            'fields': (
                'is_active',
                'location',
                'senior',
                'placement_zone',
                'duty_started_at',
            ),
        }),
        (_('График дневной смены'), {
            'fields': ('day_shift_start', 'day_shift_end'),
            'classes': ('collapse',),
        }),
        (_('График ночной смены'), {
            'fields': ('night_shift_start', 'night_shift_end'),
            'classes': ('collapse',),
        }),
        (None, {
            'fields': ('notes',),
            'description': _('При переводе на отрыв укажите, куда перемещаем — это отображается на дашборде.'),
        }),
    )
    class Media:
        js = ('admin/js/operator_detachment.js',)


@admin.register(OperatorLocation)
class OperatorLocationAdmin(admin.ModelAdmin):
    form = OperatorLocationAdminForm
    list_display = ('name', 'senior', 'comm_links_display', 'description', 'sort_order', 'is_active', 'operators_count')
    list_editable = ('sort_order', 'is_active')
    list_filter = ('is_active', 'senior')
    search_fields = ('name', 'description', 'senior__callname')
    ordering = ('sort_order', 'name')
    readonly_fields = ('id', 'created', 'modified')
    fieldsets = (
        (None, {
            'fields': ('name', 'senior', 'comm_links', 'description', 'sort_order', 'is_active'),
        }),
        (_('Служебное'), {
            'fields': ('id', 'created', 'modified'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description=_('Связь'))
    def comm_links_display(self, obj):
        labels = comm_link_labels(obj.comm_links)
        return ', '.join(labels) if labels else '—'

    @admin.display(description=_('Операторов'))
    def operators_count(self, obj):
        return obj.operators.filter(is_active=True).count()


@admin.register(OperatorProfile)
class OperatorProfileAdmin(admin.ModelAdmin):
    """Сводный список для быстрого редактирования. Новых записей здесь не создаём — только из «Пилоты»."""
    form = OperatorProfileAdminForm
    list_display = (
        'pilot',
        'location',
        'placement_zone',
        'is_active',
        'senior',
        'duty_started_at',
    )
    list_editable = ('location', 'placement_zone')
    list_display_links = ('pilot',)
    list_filter = ('is_active', 'placement_zone', 'senior', 'location')
    search_fields = ('pilot__callname', 'senior__callname', 'location__name', 'notes')
    readonly_fields = ('id', 'created', 'modified', 'pilot')
    fieldsets = (
        (None, {
            'fields': (
                'pilot',
                'location',
                'senior',
                'is_active',
                'placement_zone',
                'duty_started_at',
                'notes',
            ),
            'description': _('Расположение и зону можно менять в списке. При переводе на отрыв появится запрос «Куда перемещаем?».'),
        }),
        (_('График дневной смены'), {
            'fields': ('day_shift_start', 'day_shift_end'),
        }),
        (_('График ночной смены'), {
            'fields': ('night_shift_start', 'night_shift_end'),
        }),
        (_('Служебное'), {
            'fields': ('id', 'created', 'modified'),
            'classes': ('collapse',),
        }),
    )
    actions = ('mark_day_shift', 'mark_night_shift', 'mark_detachment')

    class Media:
        js = ('admin/js/operator_detachment.js',)

    def get_changelist_form(self, request, **kwargs):
        return OperatorProfileChangeListForm

    def get_changelist_formset(self, request, **kwargs):
        kwargs.setdefault('form', self.get_changelist_form(request))
        kwargs.setdefault('fields', self.list_editable)
        kwargs.setdefault(
            'formfield_callback',
            partial(self.formfield_for_dbfield, request=request),
        )
        FormSet = modelformset_factory(self.model, **kwargs)

        class OperatorProfileChangeListFormSet(FormSet):
            def get_queryset(self):
                if not self.is_bound:
                    return super().get_queryset()
                pks = []
                prefix = self.prefix or 'form'
                pk_name = self.model._meta.pk.name
                for i in range(self.total_form_count()):
                    pk = self.data.get(f'{prefix}-{i}-{pk_name}')
                    if pk:
                        pks.append(pk)
                if not pks:
                    return super().get_queryset()
                return (
                    OperatorProfile.objects
                    .filter(pk__in=pks)
                    .select_related('pilot', 'location', 'location__senior')
                )

        OperatorProfileChangeListFormSet.__name__ = 'OperatorProfileChangeListFormSet'
        OperatorProfileChangeListFormSet.__qualname__ = 'OperatorProfileChangeListFormSet'
        return OperatorProfileChangeListFormSet

    def has_add_permission(self, request):
        return False

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('pilot', 'senior', 'location', 'location__senior')

    def save_form(self, request, form, change):
        obj = super().save_form(request, form, change)
        if obj.pk and not obj.pilot_id:
            obj.pilot_id = (
                OperatorProfile.objects.filter(pk=obj.pk)
                .values_list('pilot_id', flat=True)
                .first()
            )
        return obj

    def log_change(self, request, obj, message):
        if obj is None or not obj.pilot_id:
            return
        super().log_change(request, obj, message)

    def save_model(self, request, obj, form, change):
        if obj.pk and not obj.pilot_id:
            obj.pilot_id = (
                OperatorProfile.objects.filter(pk=obj.pk)
                .values_list('pilot_id', flat=True)
                .first()
            )
        if not obj.pilot_id:
            return

        old_location_id = None
        old_placement_zone = None
        if change and obj.pk:
            prev = OperatorProfile.objects.filter(pk=obj.pk).only('location_id', 'placement_zone').first()
            if prev:
                old_location_id = prev.location_id
                old_placement_zone = prev.placement_zone

        moving_to_detachment = (
            obj.placement_zone == OperatorPlacementZone.DETACHMENT
            and old_placement_zone != OperatorPlacementZone.DETACHMENT
        )
        if moving_to_detachment:
            destination = (request.POST.get(detachment_dest_post_key(obj.pk)) or '').strip()
            if not destination:
                destination = (obj.notes or '').strip()
            if not destination:
                obj.placement_zone = old_placement_zone
                callname = obj.pilot.callname if obj.pilot_id else str(obj.pk)
                self.message_user(
                    request,
                    f'{callname}: укажите «куда перемещаем» — перевод на отрыв не выполнен.',
                    messages.ERROR,
                )
            else:
                obj.notes = destination

        super().save_model(request, obj, form, change)
        comment = (obj.notes or '').strip() if obj.placement_zone == OperatorPlacementZone.DETACHMENT else ''
        _log_location_change(
            obj,
            old_location_id=old_location_id,
            old_placement_zone=old_placement_zone,
            new_location=obj.location,
            user=request.user,
            comment=comment,
        )

    def save_formset(self, request, form, formset, change):
        if formset.model is OperatorProfile:
            old_locations = {
                str(row.pk): row.location_id
                for row in OperatorProfile.objects.filter(
                    pk__in=[f.instance.pk for f in formset.forms if f.instance.pk],
                ).only('pk', 'location_id')
            }
            old_zones = {
                str(row.pk): row.placement_zone
                for row in OperatorProfile.objects.filter(
                    pk__in=[f.instance.pk for f in formset.forms if f.instance.pk],
                ).only('pk', 'placement_zone')
            }
            instances = formset.save(commit=False)
            save_operator_profile_instances(
                instances,
                user=request.user,
                old_locations=old_locations,
                old_zones=old_zones,
                comment='Изменение в списке',
            )
            formset.save_m2m()
            return
        super().save_formset(request, form, formset, change)

    @admin.action(description='Перевести в дневную смену')
    def mark_day_shift(self, request, queryset):
        updated = queryset.update(placement_zone=OperatorPlacementZone.DAY)
        self.message_user(request, f'Переведено в дневную смену: {updated}', messages.SUCCESS)

    @admin.action(description='Перевести в ночную смену')
    def mark_night_shift(self, request, queryset):
        updated = queryset.update(placement_zone=OperatorPlacementZone.NIGHT)
        self.message_user(request, f'Переведено в ночную смену: {updated}', messages.SUCCESS)

    @admin.action(description='Перевести на отрыв (с указанием места назначения)')
    def mark_detachment(self, request, queryset):
        if 'apply' in request.POST:
            operators = list(queryset.select_related('pilot'))
            updated = 0
            for operator in operators:
                if len(operators) == 1:
                    destination = (request.POST.get('destination') or '').strip()
                else:
                    destination = (request.POST.get(f'destination_{operator.pk}') or '').strip()
                if not destination:
                    self.message_user(
                        request,
                        f'Не указано место назначения для {operator.pilot.callname}.',
                        messages.ERROR,
                    )
                    return render(
                        request,
                        'admin/flights/operatorprofile/mark_detachment.html',
                        {'operators': operators, 'action_checkbox_name': helpers.ACTION_CHECKBOX_NAME},
                    )

                old_location_id = operator.location_id
                old_placement_zone = operator.placement_zone
                operator.placement_zone = OperatorPlacementZone.DETACHMENT
                operator.notes = destination
                operator.save(update_fields=['placement_zone', 'notes', 'modified'])
                _log_location_change(
                    operator,
                    old_location_id=old_location_id,
                    old_placement_zone=old_placement_zone,
                    new_location=operator.location,
                    user=request.user,
                    comment=destination,
                )
                updated += 1

            self.message_user(request, f'Переведено на отрыв: {updated}', messages.SUCCESS)
            return None

        operators = list(queryset.select_related('pilot').order_by('pilot__callname'))
        return render(
            request,
            'admin/flights/operatorprofile/mark_detachment.html',
            {'operators': operators, 'action_checkbox_name': helpers.ACTION_CHECKBOX_NAME},
        )


@admin.register(OperatorPositionLog)
class OperatorPositionLogAdmin(admin.ModelAdmin):
    list_display = (
        'profile',
        'location',
        'placement_zone',
        'recorded_at',
        'recorded_by',
        'comment',
    )
    list_filter = ('placement_zone', 'location', 'recorded_at')
    search_fields = ('profile__pilot__callname', 'location__name', 'location_label', 'comment')
    readonly_fields = (
        'id',
        'profile',
        'placement_zone',
        'location',
        'location_label',
        'recorded_at',
        'recorded_by',
        'comment',
    )
    ordering = ('-recorded_at',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
