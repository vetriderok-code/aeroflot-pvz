import datetime
import logging
import re

from asgiref.sync import async_to_sync
from config import settings
from django import forms
from django.contrib import admin, messages
from django.contrib.admin import SimpleListFilter
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.templatetags.static import static
from django.urls import path
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from flights.admin_operators import OperatorProfileInline, save_operator_profile_instances
from flights.forms_operators import PilotAdminForm
from flights.models import Pilot, ExplosiveDevice, ExplosiveType, Drone, TargetType, CorrectiveType, Flight, \
    FlightResultTypes, \
    FlightObjectiveTypes, User, DirectionType, DroneTypes, ImportProgress, LiveFlight, MapLayer, \
    OperatorProfile, OperatorPlacementZone
from telegram import Bot

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


admin.AdminSite.site_header = 'Аэрофлот'
admin.AdminSite.site_title = 'Панель управления'
admin.AdminSite.index_title = 'Администрирование'


def send_telegram_message(bot_token, chat_id, message):
    """Отправка сообщения через Telegram"""

    async def _send():
        bot = Bot(token=bot_token)
        await bot.send_message(chat_id=chat_id, text=message)

    return async_to_sync(_send)()


@admin.action(description="Отправить сообщение в Telegram")
def send_telegram_broadcast(modeladmin, request, queryset):
    """Action для отправки сообщения выбранным пилотам"""
    if 'apply' in request.POST:
        message = request.POST.get('message', '')
        if not message:
            modeladmin.message_user(request, "Сообщение не может быть пустым!", messages.ERROR)
            return HttpResponseRedirect(request.get_full_path())

        BOT_TOKEN = settings.TOKEN

        success_count = 0
        fail_count = 0

        for pilot in queryset:
            if not pilot.tg_id:
                fail_count += 1
                modeladmin.message_user(
                    request,
                    f'Пропущен {pilot.callname}: не указан TG ID',
                    messages.WARNING,
                )
                continue
            try:
                send_telegram_message(BOT_TOKEN, pilot.tg_id, message)
                success_count += 1
            except Exception as e:
                fail_count += 1
                modeladmin.message_user(
                    request,
                    f"Ошибка отправки {pilot.callname}: {str(e)}",
                    messages.WARNING
                )

        modeladmin.message_user(
            request,
            f"Сообщение отправлено: {success_count} успешно, {fail_count} ошибок",
            messages.SUCCESS if fail_count == 0 else messages.WARNING
        )
        return HttpResponseRedirect(request.get_full_path())

    # Показываем форму для ввода сообщения
    context = {
        'pilots': queryset,
        'pilot_count': queryset.count(),
        'action_checkbox_name': '_selected_action',  # Исправлено!
    }
    return render(request, 'admin/pilot_broadcast.html', context)


class CustomAdminSite(admin.AdminSite):
    def each_context(self, request):
        context = super().each_context(request)
        context['custom_css'] = static('admin/css/custom_admin.css')
        return context

#admin_site = CustomAdminSite(name='custom_admin')


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'email', 'phone')}),
        (_('Permissions'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
        (_('Pilot Info'), {'fields': ('pilot',)}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2', 'phone', 'pilot', 'is_staff', 'is_superuser'),
        }),
    )

    # Добавляем автозаполнение для поля pilot
    autocomplete_fields = ['pilot']

    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'get_pilot_callname')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'groups')
    search_fields = ('username', 'first_name', 'last_name', 'email', 'phone')
    ordering = ('username',)

    def get_pilot_callname(self, obj):
        if obj.pilot:
            return obj.pilot.callname
        return "-"

    get_pilot_callname.short_description = _('Pilot Callname')
    get_pilot_callname.admin_order_field = 'pilot__callname'


@admin.register(ExplosiveDevice)
class ExplosiveDeviceAdmin(admin.ModelAdmin):
    search_fields = ('name',)
    ordering = ('name',)
    actions = ['delete_all']
    
    def delete_all(self, request, queryset):
        """Удалить все записи"""
        count = ExplosiveDevice.objects.count()
        ExplosiveDevice.objects.all().delete()
        self.message_user(request, f'Удалено записей: {count}', level='success')
    delete_all.short_description = "Удалить все записи"

@admin.register(ExplosiveType)
class ExplosiveTypeAdmin(admin.ModelAdmin):
    search_fields = ('name',)
    ordering = ('name',)
    actions = ['delete_all']
    
    def delete_all(self, request, queryset):
        """Удалить все записи"""
        count = ExplosiveType.objects.count()
        ExplosiveType.objects.all().delete()
        self.message_user(request, f'Удалено записей: {count}', level='success')
    delete_all.short_description = "Удалить все записи"

@admin.register(MapLayer)
class MapLayerAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'file_format', 'feature_count', 'is_active',
        'sort_order', 'converted_at', 'conversion_status',
    )
    list_filter = ('is_active', 'file_format')
    search_fields = ('name', 'description')
    readonly_fields = (
        'file_format', 'geojson', 'feature_count', 'conversion_error',
        'converted_at', 'created', 'modified',
    )
    ordering = ('sort_order', 'name')
    actions = ['reconvert_layers', 'activate_layers', 'deactivate_layers']

    fieldsets = (
        (None, {
            'fields': (
                'name', 'description', 'source_file', 'is_active', 'sort_order',
            ),
        }),
        (_('Отображение'), {
            'fields': ('color', 'stroke_width', 'opacity'),
        }),
        (_('Конвертация'), {
            'fields': (
                'file_format', 'feature_count', 'converted_at',
                'conversion_error', 'geojson',
            ),
        }),
        (_('Служебные'), {
            'fields': ('created', 'modified'),
        }),
    )

    def conversion_status(self, obj):
        if obj.conversion_error:
            return format_html('<span style="color:#c00;">Ошибка</span>')
        if obj.geojson and obj.feature_count:
            return format_html('<span style="color:#080;">OK ({} объектов)</span>', obj.feature_count)
        return '—'

    conversion_status.short_description = _('Статус')

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if 'source_file' in form.changed_data or not obj.geojson:
            try:
                obj.process_source_file()
                self.message_user(
                    request,
                    f'Слой «{obj.name}»: {obj.feature_count} объектов',
                    messages.SUCCESS,
                )
            except Exception as exc:
                obj.conversion_error = str(exc)
                obj.geojson = None
                obj.feature_count = 0
                obj.save(update_fields=['conversion_error', 'geojson', 'feature_count', 'modified'])
                self.message_user(
                    request,
                    f'Ошибка конвертации «{obj.name}»: {exc}',
                    messages.ERROR,
                )

    @admin.action(description='Пересчитать GeoJSON из файла')
    def reconvert_layers(self, request, queryset):
        ok, fail = 0, 0
        for layer in queryset:
            try:
                layer.process_source_file()
                ok += 1
            except Exception as exc:
                layer.conversion_error = str(exc)
                layer.save(update_fields=['conversion_error', 'modified'])
                fail += 1
        level = messages.SUCCESS if fail == 0 else messages.WARNING
        self.message_user(request, f'Пересчитано: {ok}, ошибок: {fail}', level)

    @admin.action(description='Включить на карте')
    def activate_layers(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, f'Включено слоёв: {queryset.count()}', messages.SUCCESS)

    @admin.action(description='Скрыть с карты')
    def deactivate_layers(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, f'Скрыто слоёв: {queryset.count()}', messages.SUCCESS)


@admin.register(ImportProgress)
class ImportProgressAdmin(admin.ModelAdmin):
    list_display = ('file_name', 'file_size', 'last_processed_row', 'total_rows', 'total_created', 'is_completed', 'last_import_date')
    list_filter = ('is_completed', 'last_import_date')
    search_fields = ('file_name', 'file_hash')
    readonly_fields = ('file_hash', 'last_import_date', 'created', 'modified')
    ordering = ['-last_import_date']
    
    def has_add_permission(self, request):
        return False  # Записи создаются автоматически при импорте
    
    def has_delete_permission(self, request, obj=None):
        return True  # Можно удалять для сброса прогресса

@admin.register(Drone)
class DroneAdmin(admin.ModelAdmin):
    search_fields = ('name', 'drone_type')
    list_display = ('name', 'drone_type')
    ordering = ('name',)
    actions = ['delete_all']
    
    def delete_all(self, request, queryset):
        """Удалить все записи"""
        count = Drone.objects.count()
        Drone.objects.all().delete()
        self.message_user(request, f'Удалено записей: {count}', level='success')
    delete_all.short_description = "Удалить все записи"

@admin.register(TargetType)
class TargetTypeAdmin(admin.ModelAdmin):
    search_fields = ('name',)
    ordering = ('name',)

@admin.register(DirectionType)
class DirectionTypeAdmin(admin.ModelAdmin):
    search_fields = ('name',)
    ordering = ('name',)

@admin.register(CorrectiveType)
class CorrectiveTypeAdmin(admin.ModelAdmin):
    search_fields = ('name',)
    ordering = ('name',)


@admin.register(LiveFlight)
class LiveFlightAdmin(admin.ModelAdmin):
    list_display = ('pilot', 'started_at', 'ended_at', 'close_reason', 'telegram_user_id')
    list_filter = ('close_reason',)
    search_fields = ('pilot__callname',)
    readonly_fields = ('id', 'created', 'modified')
    ordering = ('-started_at',)


@admin.register(Pilot)
class PilotAdmin(admin.ModelAdmin):
    form = PilotAdminForm
    inlines = (OperatorProfileInline,)
    list_display = (
        'callname',
        'drone_type',
        'duty_active',
        'duty_location',
        'duty_zone',
        'tg_id',
        'flights_count',
    )
    list_filter = (
        'drone_type',
        'operator_profile__is_active',
        'operator_profile__placement_zone',
        'operator_profile__location',
    )
    search_fields = (
        'callname',
        'tg_id', # Поиск по Telegram ID
    )
    ordering = ('callname',)
    readonly_fields = ('id', 'created', 'modified')
    actions = [
        send_telegram_broadcast,
        'add_to_duty_roster',
        'remove_from_duty',
        'delete_unknown_pilots',
        'delete_all',
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'operator_profile',
            'operator_profile__location',
        )

    @admin.display(description='На дежурстве', boolean=True)
    def duty_active(self, obj):
        profile = getattr(obj, 'operator_profile', None)
        return bool(profile and profile.is_active)

    @admin.display(description='Расположение')
    def duty_location(self, obj):
        profile = getattr(obj, 'operator_profile', None)
        if profile and profile.location_id:
            return profile.location.name
        return '—'

    @admin.display(description='Смена')
    def duty_zone(self, obj):
        profile = getattr(obj, 'operator_profile', None)
        if not profile or not profile.is_active:
            return '—'
        return profile.get_placement_zone_display()

    @admin.action(description='Вынести на дежурство')
    def add_to_duty_roster(self, request, queryset):
        activated = 0
        created = 0
        for pilot in queryset:
            profile, was_created = OperatorProfile.objects.get_or_create(
                pilot=pilot,
                defaults={
                    'is_active': True,
                    'placement_zone': OperatorPlacementZone.DAY,
                },
            )
            if was_created:
                created += 1
            elif not profile.is_active:
                profile.is_active = True
                profile.save(update_fields=['is_active', 'modified'])
                activated += 1
        self.message_user(
            request,
            f'На дежурство: новых {created}, активировано {activated}. '
            f'Укажите расположение в карточке пилота.',
            messages.SUCCESS,
        )

    @admin.action(description='Снять с дежурства')
    def remove_from_duty(self, request, queryset):
        updated = OperatorProfile.objects.filter(pilot__in=queryset, is_active=True).update(is_active=False)
        self.message_user(request, f'Снято с дежурства: {updated}', messages.SUCCESS)

    def save_formset(self, request, form, formset, change):
        if formset.model is OperatorProfile:
            old_locations = {}
            old_zones = {}
            for f in formset.forms:
                if f.instance.pk:
                    prev = (
                        OperatorProfile.objects.filter(pk=f.instance.pk)
                        .values('location_id', 'placement_zone')
                        .first()
                    )
                    if prev:
                        old_locations[str(f.instance.pk)] = prev['location_id']
                        old_zones[str(f.instance.pk)] = prev['placement_zone']
            instances = formset.save(commit=False)
            for obj in instances:
                if not obj.pilot_id:
                    obj.pilot = form.instance
            for deleted in formset.deleted_objects:
                deleted.delete()
            save_operator_profile_instances(
                instances,
                user=request.user,
                old_locations=old_locations,
                old_zones=old_zones,
                comment='Изменение в карточке пилота',
            )
            formset.save_m2m()
            return
        super().save_formset(request, form, formset, change)
    
    def delete_unknown_pilots(self, request, queryset):
        """Удалить всех пилотов с позывным Неизвестный_* (и связанные полёты)."""
        to_delete = Pilot.objects.filter(callname__istartswith='Неизвестный_')
        count = to_delete.count()
        to_delete.delete()
        self.message_user(
            request,
            f'Удалено пилотов «Неизвестный_*»: {count}. Связанные полёты удалены (CASCADE).',
            level=messages.SUCCESS
        )
    delete_unknown_pilots.short_description = "Удалить пилотов Неизвестный_*"
    
    def delete_all(self, request, queryset):
        """Удалить все записи"""
        count = Pilot.objects.count()
        Pilot.objects.all().delete()
        self.message_user(request, f'Удалено записей: {count}', level='success')
    delete_all.short_description = "Удалить все записи"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('broadcast/', self.admin_site.admin_view(self.broadcast_view), name='flights_pilot_broadcast'),
        ]
        return custom_urls + urls

    def broadcast_view(self, request):
        """Страница массовой рассылки"""
        if request.method == 'POST':
            message = request.POST.get('message', '')
            if message:
                pilots = Pilot.objects.all()
                BOT_TOKEN = settings.TOKEN

                success_count = 0
                fail_count = 0

                for pilot in pilots:
                    if not pilot.tg_id:
                        fail_count += 1
                        continue
                    try:
                        send_telegram_message(BOT_TOKEN, pilot.tg_id, message)
                        success_count += 1
                    except Exception as e:
                        fail_count += 1

                messages.success(
                    request,
                    f"Рассылка завершена: {success_count} успешно, {fail_count} ошибок"
                )
            else:
                messages.error(request, "Сообщение не может быть пустым!")

        context = {
            'pilot_count': Pilot.objects.count(),
            **self.admin_site.each_context(request),
        }
        return render(request, 'admin/broadcast_form.html', context)

    def send_message_link(self, obj):
        return format_html(
            '<a class="button" href="{}">Сообщение</a>&nbsp;'
            '<a class="button" href="{}" style="background: #28a745;">Массовая рассылка</a>',
            f"?action=send_single_message&pilot_id={obj.id}",
            reverse('admin:flights_pilot_broadcast')
        )

    send_message_link.short_description = "Действия"

    def changelist_view(self, request, extra_context=None):
        if 'action' in request.GET and request.GET['action'] == 'send_single_message':
            pilot_id = request.GET.get('pilot_id')
            if pilot_id:
                # Перенаправляем на action с этим пилотом
                request.POST = request.POST.copy()
                request.POST['_selected_action'] = [pilot_id]
                request.POST['action'] = 'send_telegram_broadcast'
                request.method = 'POST'
                return self.changelist_view(request, extra_context)

        return super().changelist_view(request, extra_context)

    def flights_count(self, obj):
        count = obj.flights.count() # Если related_name='flights' в модели Flight
        url = reverse('admin:flights_flight_changelist') + f'?pilot__id__exact={obj.id}' # Замените 'flights' на имя вашего приложения
        return format_html('<a href="{}">{}</a>', url, count)
    flights_count.short_description = 'Кол-во полетов'


class FlightAdminForm(forms.ModelForm):
    class Meta:
        model = Flight
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class FlightDateFilter(SimpleListFilter):
    title = _('Дата вылета (точная)')
    parameter_name = 'exact_flight_date'
    template = 'admin/date_filter.html'

    def lookups(self, request, model_admin):
        return []

    def queryset(self, request, queryset):
        date_value = request.GET.get(self.parameter_name)
        if date_value:
            try:
                from django.utils.dateparse import parse_date
                parsed_date = parse_date(date_value)
                if parsed_date:
                    return queryset.filter(flight_date=parsed_date)
            except (ValueError, TypeError):
                pass
        return queryset

    def value(self):
        return self.used_parameters.get(self.parameter_name, '')

    def has_output(self):
        return True

    def choices(self, changelist):
        yield {
            'selected': self.value() is not None,
            'query_string': changelist.get_query_string(remove=[self.parameter_name]),
            'display': _('Все даты'),
        }

@admin.register(Flight)
class FlightAdmin(admin.ModelAdmin):
    list_display = (
        'number',
        'pilot_link',
        'drone',
        'formatted_flight_date',
        'formatted_flight_time',
        'target',
        'result_colored',
        'coordinates_preview',
        'comment_short',
        'created_display',
    )

    list_filter = (
        'flight_date',
        #FlightDateFilter,
        'pilot',
        'drone',
        'target',
        'result',
    )

    search_fields = (
        'number',
        'pilot__callname',
        'target',
        'coordinates',
    )

    fieldsets = (
        ('Основная информация', {
            'fields': (
                'number',
                'pilot',
                'drone',
                'flight_date',
                'flight_time',
                'target',
                'comment'
            )
        }),
        ('Детали выполнения', {
            'fields': (
                'engineer',
                'driver',
                'video',
                'manage',
                'distance',
                'corrective',
                'result',
                'direction',
            )
        }),
        ('Боеприпасы', {
            'fields': (
                'explosive_type',
                'explosive_device',
            ),
            'classes': ('collapse',),
        }),
        ('Цель и координаты', {
            'fields': (
                'coordinates',
                'coordinates_info_display',
                'objective',
                'drone_remains',
            )
        }),
        ('Служебная информация', {
            'fields': (
                'id',
                'created',
                'modified',
            ),
            'classes': ('collapse',),
        }),
    )

    readonly_fields = (
        'id',
        'created',
        'modified',
        'coordinates_info_display',
    )

    ordering = ('-created',)

    list_per_page = 100

    actions = ['mark_as_destroyed',
               'mark_as_defeated',
               'mark_as_not_defeated',
               'delete_all',
               'recalculate_coordinates',
               'precalculate_coordinates',
               'clear_coordinate_cache',
               'process_all_coordinates',
               ]

    change_list_template = "admin/flight_changelist.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<path:object_id>/recalculate-coordinates/',
                self.admin_site.admin_view(self.recalculate_coordinates_view),
                name='flights_flight_recalculate_coordinates',

            ),
            path(
                'import-xlsx/',
                self.admin_site.admin_view(self.import_xlsx_view),
                name='flights_flight_import_xlsx'),
            path(
                'clear-database/',
                self.admin_site.admin_view(self.clear_database_view),
                name='flights_flight_clear_database'),

        ]
        return custom_urls + urls

    def recalculate_coordinates_view(self, request, object_id):
        try:
            flight = self.get_object(request, object_id)
            if flight:
                flight.lat_sk42 = None
                flight.lon_sk42 = None
                flight.lat_wgs84 = None
                flight.lon_wgs84 = None
                flight.save(update_fields=[])

                coord_info = flight.get_coordinates_info_cached()

                if coord_info:
                    self.message_user(
                        request,
                        f"Координаты для полета №{flight.number} успешно пересчитаны!",
                        level=messages.SUCCESS
                    )
                else:
                    self.message_user(
                        request,
                        f"Ошибка пересчета координат для полета №{flight.number}",
                        level=messages.ERROR
                    )
            else:
                self.message_user(
                    request,
                    "Полет не найден",
                    level=messages.ERROR
                )

        except Exception as e:
            self.message_user(
                request,
                f"Ошибка: {str(e)}",
                level=messages.ERROR
            )

        return HttpResponseRedirect(request.META.get('HTTP_REFERER', '..'))

    def mark_as_defeated(self, request, queryset):
        updated_count = queryset.update(result=FlightResultTypes.DEFEATED)
        self.message_user(request, f"{updated_count} полетов отмечены как 'Поражен'.")
    mark_as_defeated.short_description = "🔥 Отметить выбранные как 'Поражен'"

    def mark_as_destroyed(self, request, queryset):
        updated_count = queryset.update(result=FlightResultTypes.DESTROYED)
        self.message_user(request, f"{updated_count} полетов отмечены как 'Уничтожен'.")
    mark_as_destroyed.short_description = "✅ Отметить выбранные как 'Уничтожен'"

    def mark_as_not_defeated(self, request, queryset):
        updated_count = queryset.update(result=FlightResultTypes.NOT_DEFEATED)
        self.message_user(request, f"{updated_count} полетов отмечены как 'Не поражен'.")
    mark_as_not_defeated.short_description = "❌ Отметить выбранные как 'Не поражен'"
    
    def delete_all(self, request, queryset):
        """Удалить все записи"""
        count = Flight.objects.count()
        Flight.objects.all().delete()
        self.message_user(request, f'Удалено записей: {count}', level='success')
    delete_all.short_description = "🗑️ Удалить все записи"

    def recalculate_coordinates(self, request, queryset):
        updated_count = 0
        error_count = 0

        for flight in queryset:
            try:
                flight.lat_sk42 = None
                flight.lon_sk42 = None
                flight.lat_wgs84 = None
                flight.lon_wgs84 = None
                flight.save(update_fields=[])

                coord_info = flight.get_coordinates_info_cached()

                if coord_info:
                    updated_count += 1
                else:
                    error_count += 1

            except Exception as e:
                error_count += 1
                self.message_user(
                    request,
                    f"Ошибка пересчета координат для полета {flight.number}: {str(e)}",
                    level=messages.ERROR
                )

        if updated_count > 0:
            self.message_user(
                request,
                f"Успешно пересчитаны координаты для {updated_count} полетов.",
                level=messages.SUCCESS
            )

        if error_count > 0:
            self.message_user(
                request,
                f"Ошибка при пересчете координат для {error_count} полетов.",
                level=messages.WARNING
            )

    recalculate_coordinates.short_description = "🔄 Пересчитать кэшированные координаты"

    def precalculate_coordinates(self, request, queryset):
        updated_count = 0
        error_count = 0

        for flight in queryset:
            try:
                coord_info = flight.update_coordinates_from_cache()

                if coord_info:
                    updated_count += 1
                else:
                    error_count += 1

            except Exception as e:
                error_count += 1
                self.message_user(
                    request,
                    f"Ошибка пересчета координат для полета {flight.number}: {str(e)}",
                    level=messages.ERROR
                )

        if updated_count > 0:
            self.message_user(
                request,
                f"Успешно пересчитаны координаты для {updated_count} полетов.",
                level=messages.SUCCESS
            )

        if error_count > 0:
            self.message_user(
                request,
                f"Ошибка при пересчете координат для {error_count} полетов.",
                level=messages.WARNING
            )

    precalculate_coordinates.short_description = "🔄 Пересчитать координаты из кеша"

    def clear_coordinate_cache(self, request, queryset):
        cleared_count = 0

        for flight in queryset:
            try:
                flight.lat_sk42 = 90.0
                flight.lon_sk42 = 0.0
                flight.lat_wgs84 = 90.0
                flight.lon_wgs84 = 0.0
                flight.save(update_fields=['lat_sk42', 'lon_sk42', 'lat_wgs84', 'lon_wgs84'])
                cleared_count += 1

            except Exception as e:
                self.message_user(
                    request,
                    f"Ошибка очистки кэша для полета {flight.number}: {str(e)}",
                    level=messages.ERROR
                )

        self.message_user(
            request,
            f"Очищен кэш координат для {cleared_count} полетов.",
            level=messages.INFO
        )

    clear_coordinate_cache.short_description = "🧹 Очистить кэш координат"

    def recalculate_all_coordinates(self, request, queryset):
        all_flights = Flight.objects.all()
        total_count = all_flights.count()
        updated_count = 0
        error_count = 0

        self.message_user(
            request,
            f"Начинаем пересчет координат для всех {total_count} полетов...",
            level=messages.INFO
        )

        for flight in all_flights:
            try:
                flight.lat_sk42 = None
                flight.lon_sk42 = None
                flight.lat_wgs84 = None
                flight.lon_wgs84 = None
                flight.save(update_fields=[])

                coord_info = flight.get_coordinates_info_cached()

                if coord_info:
                    updated_count += 1
                else:
                    error_count += 1

                if (updated_count + error_count) % 100 == 0:
                    self.message_user(
                        request,
                        f"Обработано {updated_count + error_count} из {total_count} полетов...",
                        level=messages.INFO
                    )

            except Exception as e:
                error_count += 1
                continue

        self.message_user(
            request,
            f"Пересчет завершен! Успешно: {updated_count}, Ошибок: {error_count}",
            level=messages.SUCCESS if error_count == 0 else messages.WARNING
        )

    recalculate_all_coordinates.short_description = "🔄 Пересчитать ВСЕ координаты"

    def process_all_coordinates(self, request, queryset):
        """Обработка координат для всех полетов с необработанными координатами"""
        # Получаем все полеты с координатами, которые еще не обработаны
        flights_to_process = Flight.objects.filter(
            coordinates__isnull=False
        ).exclude(
            coordinates=''
        ).filter(
            lat_wgs84__isnull=True
        )
        
        total_count = flights_to_process.count()
        if total_count == 0:
            self.message_user(
                request,
                "Нет полетов с необработанными координатами.",
                level=messages.INFO
            )
            return
        
        self.message_user(
            request,
            f"Найдено {total_count} полетов с необработанными координатами. Начинаем обработку (это может занять некоторое время)...",
            level=messages.INFO
        )
        
        def progress_callback(processed, total):
            """Callback для отслеживания прогресса"""
            if processed % 1000 == 0 or processed == total:
                self.message_user(
                    request,
                    f"Обработано координат: {processed}/{total}",
                    level=messages.INFO
                )
        
        try:
            success_count, error_count = Flight.batch_process_coordinates(
                queryset=flights_to_process,
                batch_size=500,
                update_callback=progress_callback
            )
            
            if success_count > 0:
                self.message_user(
                    request,
                    f"✓ Успешно обработано координат для {success_count} полетов.",
                    level=messages.SUCCESS
                )
            
            if error_count > 0:
                self.message_user(
                    request,
                    f"⚠️ Ошибка при обработке координат для {error_count} полетов.",
                    level=messages.WARNING
                )
        except Exception as e:
            logger.error(f"Ошибка при обработке координат: {e}", exc_info=True)
            self.message_user(
                request,
                f"❌ Критическая ошибка при обработке координат: {str(e)}",
                level=messages.ERROR
            )
            return
        
        # Очищаем кэш API карты
        from django.core.cache import cache
        try:
            if hasattr(cache, 'delete_pattern'):
                cache.delete_pattern('rubicon:flights_total:*')
            else:
                cache.clear()
            logger.info("Кэш для API карты очищен после обработки координат")
        except Exception as cache_error:
            logger.warning(f"Не удалось очистить кэш: {cache_error}")

    process_all_coordinates.short_description = "🗺️ Обработать координаты для всех полетов без координат"

    def pilot_link(self, obj):
        if obj.pilot:
            url = reverse('admin:flights_pilot_change', args=[obj.pilot.id])
            return format_html('<a href="{}">{}</a>', url, obj.pilot.callname)
        return "-"
    pilot_link.short_description = 'Пилот'
    pilot_link.admin_order_field = 'pilot__callname'

    def formatted_flight_date(self, obj):
        if obj.flight_date:
            return obj.flight_date.strftime('%d.%m.%Y')
        return "-"
    formatted_flight_date.short_description = 'Дата'
    formatted_flight_date.admin_order_field = 'flight_date'

    def formatted_flight_time(self, obj):
        if obj.flight_time:
            return obj.flight_time.strftime('%H:%M')
        return "-"
    formatted_flight_time.short_description = 'Время'
    formatted_flight_time.admin_order_field = 'flight_time'

    def created_display(self, obj):
        if obj.created:
            return obj.created.strftime('%d.%m.%Y %H:%M')
        return "-"

    created_display.short_description = 'Создан'
    created_display.admin_order_field = 'created'

    def modified_display(self, obj):
        if obj.modified:
            return obj.modified.strftime('%d.%m.%Y %H:%M')
        return "-"

    modified_display.short_description = 'Изменен'
    modified_display.admin_order_field = 'modified'

    def result_colored(self, obj):
        if obj.result == FlightResultTypes.DESTROYED:
            color = 'green'
            text = '✅ Уничтожено'
        elif obj.result == FlightResultTypes.NOT_DEFEATED:
            color = 'red'
            text = '❌ Не поражено'
        elif obj.result == FlightResultTypes.DEFEATED:
            color = 'orange'
            text = '🔥 Поражено'
        else:
            color = 'gray'
            text = obj.result
        return format_html('<span style="color: {};">{}</span>', color, text)
    result_colored.short_description = 'Результат'
    result_colored.admin_order_field = 'result'

    def objective_colored(self, obj):
        if obj.objective == FlightObjectiveTypes.EXISTS:
            color = 'blue'
            text = 'Есть'
        elif obj.objective == FlightObjectiveTypes.NOT_EXISTS:
            color = 'gray'
            text = 'Нет'
        else:
            color = 'black'
            text = obj.objective
        return format_html('<span style="color: {};">{}</span>', color, text)
    objective_colored.short_description = 'Объектив'
    objective_colored.admin_order_field = 'objective'

    def coordinates_preview(self, obj):
        if obj.coordinates:
            preview = (obj.coordinates[:20] + '...') if len(obj.coordinates) > 20 else obj.coordinates
            coord_info = obj.get_coordinates_info_cached()
            if coord_info and coord_info.get('lat_wgs84') and coord_info.get('lon_wgs84'):
                lat = coord_info['lat_wgs84']
                lon = coord_info['lon_wgs84']
                map_url = f"https://www.google.com/maps?q={lat},{lon}"
                return format_html(
                    '<span title="{}">{}</span>',
                    f"СК-42: {obj.coordinates}",
                    preview
                )
            else:
                return format_html('<span title="{}">{}</span>', f"СК-42: {obj.coordinates}", preview)
        return "-"
    coordinates_preview.short_description = 'Координаты (СК-42)'

    def comment_short(self, obj):
        if obj.comment:
            return (obj.comment[:20] + '...') if len(obj.comment) > 20 else obj.comment
        return "-"
    comment_short.short_description = 'Комментарий'

    def coordinates_info_display(self, obj):
        coord_info = obj.get_coordinates_info_cached() # Используем кэшированную версию
        if coord_info:
            try:
                lat_sk42 = coord_info.get('lat_sk42', 'N/A')
                lon_sk42 = coord_info.get('lon_sk42', 'N/A')
                lat_wgs84 = coord_info.get('lat_wgs84', 'N/A')
                lon_wgs84 = coord_info.get('lon_wgs84', 'N/A')

                return format_html(
                    "<strong>СК-42 (градусы):</strong> широта: {}, долгота: {}<br>"
                    "<strong>WGS-84 (градусы):</strong> широта: {}, долгота: {}",
                    round(lat_sk42, 6) if lat_sk42 != 'N/A' else 'N/A',
                    round(lon_sk42, 6) if lon_sk42 != 'N/A' else 'N/A',
                    round(lat_wgs84, 6) if lat_wgs84 != 'N/A' else 'N/A',
                    round(lon_wgs84, 6) if lon_wgs84 != 'N/A' else 'N/A'
                )
            except Exception as e:
                return f"Ошибка отображения: {e}"
        else:
            try:
                temp_info = obj.get_coordinates_info() # Не кэшированная версия
                if temp_info:
                    lat_sk42 = temp_info.get('lat_sk42', 'N/A')
                    lon_sk42 = temp_info.get('lon_sk42', 'N/A')
                    lat_wgs84 = temp_info.get('lat_wgs84', 'N/A')
                    lon_wgs84 = temp_info.get('lon_wgs84', 'N/A')
                    return format_html(
                        "<strong>СК-42 (градусы):</strong> широта: {}, долгота: {}<br>"
                        "<strong>WGS-84 (градусы):</strong> широта: {}, долгота: {}",
                        round(lat_sk42, 6) if lat_sk42 != 'N/A' else 'N/A',
                        round(lon_sk42, 6) if lon_sk42 != 'N/A' else 'N/A',
                        round(lat_wgs84, 6) if lat_wgs84 != 'N/A' else 'N/A',
                        round(lon_wgs84, 6) if lon_wgs84 != 'N/A' else 'N/A'
                    )
                else:
                     return "Информация недоступна"
            except Exception as e:
                return f"Ошибка получения данных: {e}"
    coordinates_info_display.short_description = 'Преобразованные координаты'

    @staticmethod
    def _manual_import_will_process(sources) -> bool:
        """True, если хотя бы один файл ещё не полностью импортирован (по hash)."""
        import hashlib

        for source in sources:
            source.seek(0)
            file_hash = hashlib.md5(source.read()).hexdigest()
            source.seek(0)
            already_done = ImportProgress.objects.filter(
                file_name=source.name,
                file_hash=file_hash,
                is_completed=True,
            ).exists()
            if not already_done:
                return True
        return False

    def _spawn_async_import(self, request, xlsx_files, incremental_import=False):
        """Сохраняет файл на диск и запускает import_flights_uploaded в отдельном процессе."""
        import subprocess
        import uuid
        from pathlib import Path

        queue_dir = Path(settings.BASE_DIR) / 'media' / 'import_queue'
        queue_dir.mkdir(parents=True, exist_ok=True)
        lock_file = queue_dir / '.running'

        if lock_file.exists():
            self.message_user(
                request,
                _('Импорт уже выполняется. Дождитесь завершения или проверьте «Прогресс импорта».'),
                level=messages.WARNING,
            )
            return HttpResponseRedirect('../')

        saved_paths = []
        try:
            for uploaded in xlsx_files:
                if not (uploaded.name.endswith('.xlsx') or uploaded.name.endswith('.xlsm')):
                    self.message_user(
                        request,
                        _(f"Файл '{uploaded.name}' не является .xlsx или .xlsm файлом."),
                        level=messages.ERROR,
                    )
                    return HttpResponseRedirect('../')

                dest = queue_dir / f'{uuid.uuid4().hex}_{uploaded.name}'
                with dest.open('wb') as out:
                    for chunk in uploaded.chunks(1024 * 1024):
                        out.write(chunk)
                saved_paths.append(str(dest))

            log_path = Path(settings.BASE_DIR) / 'logs' / 'import.log'
            log_path.parent.mkdir(parents=True, exist_ok=True)

            cmd = ['python', 'manage.py', 'import_flights_uploaded']
            for path in saved_paths:
                cmd.extend(['--file', path])
            if incremental_import:
                cmd.append('--incremental')

            log_handle = log_path.open('a', encoding='utf-8')
            log_handle.write('\n--- async import start ---\n')
            log_handle.flush()
            proc = subprocess.Popen(
                cmd,
                cwd=str(settings.BASE_DIR),
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            lock_file.write_text(str(proc.pid), encoding='utf-8')
        except Exception as exc:
            logger.exception('Не удалось запустить фоновый импорт Excel')
            if lock_file.exists():
                lock_file.unlink(missing_ok=True)
            for path in saved_paths:
                try:
                    Path(path).unlink(missing_ok=True)
                except OSError:
                    pass
            self.message_user(
                request,
                _(f'Ошибка запуска фонового импорта: {exc}'),
                level=messages.ERROR,
            )
            return HttpResponseRedirect('../')

        self.message_user(
            request,
            _(
                'Импорт запущен в фоне. Сайт остаётся доступным — прогресс смотрите в «Прогресс импорта».'
            ),
            level=messages.SUCCESS,
        )
        return HttpResponseRedirect('../')

    def import_xlsx_view(self, request):
        import_sources = getattr(request, '_import_sources', None)

        if request.method == 'GET':
            context = dict(
                self.admin_site.each_context(request),
                title=_('Импорт вылетов из XLSX'),
                opts=self.model._meta,
            )
            return render(request, 'admin/import_xlsx.html', context)

        xlsx_files = []
        if not import_sources:
            xlsx_files = request.FILES.getlist('xlsx_files') or request.FILES.getlist('xlsx_file')
            if not xlsx_files:
                self.message_user(
                    request,
                    _('Пожалуйста, выберите хотя бы один .xlsx или .xlsm файл.'),
                    level=messages.ERROR,
                )
                return HttpResponseRedirect('../')

            if getattr(settings, 'EXCEL_IMPORT_ASYNC', False):
                incremental_from_form = bool(request.POST.get('incremental_import'))
                return self._spawn_async_import(request, xlsx_files, incremental_from_form)

        from flights.utils.excel_import_source import UploadedExcelSource

        sources = import_sources or [UploadedExcelSource(f) for f in xlsx_files]
        incremental_import = getattr(request, 'incremental_import', False)

        # Ручная загрузка: при новом импорте очищаем вылеты.
        # Автоимпорт с шары: сохраняем вылеты, дозагружаем новые строки.
        if incremental_import:
            self.message_user(
                request,
                _("Инкрементальный импорт: существующие вылеты сохраняются, добавляются только новые строки."),
                level=messages.INFO,
            )
            logger.info('Инкрементальный импорт: очистка вылетов пропущена')
        else:
            has_unfinished_imports = ImportProgress.objects.filter(is_completed=False).exists()
            will_process = self._manual_import_will_process(sources)
            if not has_unfinished_imports:
                if not will_process:
                    self.message_user(
                        request,
                        _(
                            'Файл уже полностью импортирован — вылеты не удаляем. '
                            'Если нужен полный переимпорт, измените файл или сбросьте прогресс импорта.'
                        ),
                        level=messages.WARNING,
                    )
                    logger.info('Ручной импорт: все файлы уже импортированы, очистка пропущена')
                    return HttpResponseRedirect('../')
                self.message_user(request, _('Очистка базы вылетов перед импортом...'), level=messages.INFO)
                flights_count_before = Flight.objects.count()
                Flight.objects.all().delete()
                self.message_user(
                    request,
                    _(f"Удалено {flights_count_before} записей вылетов. Начинаем импорт..."),
                    level=messages.SUCCESS,
                )
            else:
                self.message_user(
                    request,
                    _("Найдены незавершенные импорты. Продолжаем импорт с сохраненных позиций..."),
                    level=messages.INFO,
                )

        for source in sources:
            if not (source.name.endswith('.xlsx') or source.name.endswith('.xlsm')):
                self.message_user(request, _(f"Файл '{source.name}' не является .xlsx или .xlsm файлом."),
                                  level=messages.ERROR)
                return HttpResponseRedirect("../")

        total_created = 0
        total_errors = []

        for source in sources:
                try:
                    logger.info(f"Начинаем импорт из файла: {source.name}, размер: {source.size} байт")
                    self.message_user(request, _(f"Начинаем импорт из файла: {source.name}"), level=messages.INFO)

                    # Вычисляем hash файла для идентификации
                    import hashlib
                    source.seek(0)  # Сбрасываем позицию файла
                    file_content = source.read()
                    file_hash = hashlib.md5(file_content).hexdigest()
                    source.seek(0)  # Возвращаем позицию для чтения
                    
                    import_progress = None
                    start_row = 5
                    skip_file = False
                    try:
                        if incremental_import:
                            import_progress = (
                                ImportProgress.objects
                                .filter(file_name=source.name)
                                .order_by('-last_import_date')
                                .first()
                            )
                        else:
                            import_progress = ImportProgress.objects.filter(
                                file_name=source.name,
                                file_hash=file_hash,
                            ).first()
                    except Exception as e:
                        logger.warning(f"Ошибка при проверке прогресса импорта: {e}")

                    wb = source.open_workbook()
                    logger.info(f"Файл '{source.name}' открыт (источник: {'диск' if hasattr(source, 'path') else 'загрузка'})")
                    
                    from flights.utils.excel_import_share import (
                        find_svodnaya_sheet_name,
                        load_calculation_pilot_mapping,
                        sheet_last_data_row,
                    )

                    sheet_name = find_svodnaya_sheet_name(wb)
                    if sheet_name is None:
                        self.message_user(request,
                                          _(f"Лист 'СВОДНАЯ' не найден в файле '{source.name}'."),
                                          level=messages.ERROR)
                        continue

                    logger.info("Импорт данных с листа «%s»", sheet_name)
                    ws = wb[sheet_name]

                    calculation_pilot_map = load_calculation_pilot_mapping(wb)

                    if incremental_import:

                        if import_progress:
                            file_changed = (import_progress.file_hash or '') != file_hash
                            last_data_row = sheet_last_data_row(ws)
                            if file_changed:
                                start_row = 5
                                import_progress.file_hash = file_hash
                                import_progress.file_size = source.size
                                import_progress.is_completed = False
                                import_progress.last_processed_row = start_row - 1
                                import_progress.save(
                                    update_fields=[
                                        'file_hash',
                                        'file_size',
                                        'is_completed',
                                        'last_processed_row',
                                        'last_import_date',
                                    ],
                                )
                                self.message_user(
                                    request,
                                    _(
                                        f"📌 Файл изменился — повторный проход с строки {start_row} "
                                        f"(дубликаты пропускаются, данных до строки {last_data_row})"
                                    ),
                                    level=messages.INFO,
                                )
                                logger.info(
                                    "Инкрементальный импорт %s: файл изменился, повтор с %s (данные до %s)",
                                    source.name,
                                    start_row,
                                    last_data_row,
                                )
                            else:
                                start_row = import_progress.last_processed_row + 1
                                if start_row > last_data_row:
                                    self.message_user(
                                        request,
                                        _(
                                            f"✓ Новых строк в «{source.name}» нет "
                                            f"(обработано до {import_progress.last_processed_row}, "
                                            f"данные до {last_data_row})"
                                        ),
                                        level=messages.INFO,
                                    )
                                    logger.info(
                                        "Инкрементальный импорт: пропуск %s, новых строк нет",
                                        source.name,
                                    )
                                    skip_file = True
                                else:
                                    import_progress.file_size = source.size
                                    import_progress.is_completed = False
                                    import_progress.save(
                                        update_fields=[
                                            'file_size', 'is_completed', 'last_import_date',
                                        ],
                                    )
                                    self.message_user(
                                        request,
                                        _(
                                            f"📌 Дозагрузка с строки {start_row} "
                                            f"(ранее до {import_progress.last_processed_row}, "
                                            f"данные до {last_data_row})"
                                        ),
                                        level=messages.INFO,
                                    )
                                    logger.info(
                                        "Инкрементальный импорт %s: строки %s..%s",
                                        source.name,
                                        start_row,
                                        last_data_row,
                                    )
                        else:
                            import_progress = ImportProgress.objects.create(
                                file_name=source.name,
                                file_size=source.size,
                                file_hash=file_hash,
                                last_processed_row=start_row - 1,
                                total_rows=0,
                                total_created=0,
                                is_completed=False,
                            )
                            self.message_user(
                                request,
                                _(f"Первый автоимпорт «{source.name}» с строки {start_row}."),
                                level=messages.INFO,
                            )
                            logger.info(
                                "Первый инкрементальный импорт %s с строки %s",
                                source.name,
                                start_row,
                            )
                    elif import_progress and not import_progress.is_completed:
                        start_row = import_progress.last_processed_row + 1
                        self.message_user(
                            request,
                            _(
                                f"📌 Найден сохраненный прогресс! Продолжаем импорт с строки {start_row} "
                                f"(было обработано {import_progress.last_processed_row} из {import_progress.total_rows})"
                            ),
                            level=messages.INFO,
                        )
                        logger.info(
                            "Продолжаем импорт файла '%s' с строки %s (hash: %s)",
                            source.name,
                            start_row,
                            file_hash,
                        )
                    elif import_progress and import_progress.is_completed:
                        self.message_user(
                            request,
                            _(f"✓ Файл '{source.name}' уже полностью импортирован. Пропускаем."),
                            level=messages.INFO,
                        )
                        logger.info("Файл '%s' уже полностью импортирован, пропускаем", source.name)
                        skip_file = True
                    else:
                        import_progress = ImportProgress.objects.create(
                            file_name=source.name,
                            file_size=source.size,
                            file_hash=file_hash,
                            last_processed_row=start_row - 1,
                            total_rows=0,
                            total_created=0,
                            is_completed=False,
                        )
                        logger.info(
                            "Создана новая запись прогресса для файла '%s' (hash: %s)",
                            source.name,
                            file_hash,
                        )

                    if skip_file:
                        wb.close()
                        continue

                    # Структура файла: заголовки в строке 4 (B4-V4), данные с строки 5
                    # Определяем колонки по описанию (openpyxl использует 1-based индексы):
                    # B=2, C=3, D=4, E=5, F=6, H=8, I=9, J=10, K=11, L=12, M=13, O=15, Q=17, R=18, S=19, T=20, U=21, V=22
                    COL_TIME = 2  # B - время
                    COL_TARGET = 3  # C - характер цели
                    COL_COMMENT = 4  # D - комментарий
                    COL_COORD_X = 5  # E - координата X
                    COL_COORD_Y = 6  # F - координата Y
                    COL_DRONE = 8  # H - тип дрона
                    COL_DRONE_COUNT = 9  # I - кол-во дронов (не используется в модели)
                    COL_EXPLOSIVE_TYPE = 10  # J - вид БП
                    COL_EXPLOSIVE_USAGE = 11  # K - расход БП (не используется в модели)
                    COL_EXPLOSIVE_DEVICE = 12  # L - вид взрывателя
                    COL_EXPLOSIVE_DEVICE_COUNT = 13  # M - кол-во взрывателя (не используется в модели)
                    COL_APPLICATION_PURPOSE = 14  # N - цель применения
                    COL_RESULT = 15  # O - результат применения
                    COL_CALCULATION_NUMBER = 17  # Q - номер расчета (не используется в модели)
                    COL_FLIGHT_DATE = 18  # R - дата вылета
                    COL_FLIGHT_NUMBER = 19  # S - номер вылета
                    COL_DISTANCE = 20  # T - дистанция
                    COL_FLIGHT_TIME_DURATION = 21  # U - время полета (не используется в модели, есть flight_time)
                    COL_OPERATOR_CALLNAME = 22  # V - позывной оператора

                    created_count = 0
                    error_messages = []
                    
                    # Предзагружаем справочники в память для быстрого доступа
                    self.message_user(request, _("Предзагрузка справочников..."), level=messages.INFO)
                    
                    # Вспомогательная функция для сравнения дронов (определяем один раз в начале)
                    def get_drone_comparison_key(drone_name):
                        """Возвращает ключ для сравнения дронов (без дефисов)"""
                        return re.sub(r'[-]', '', str(drone_name).lower().strip())
                    
                    # Кэш пилотов по позывному
                    pilots_cache = {pilot.callname.lower(): pilot for pilot in Pilot.objects.all()}
                    
                    # Кэш типов целей
                    target_types_cache = {tt.name.lower(): tt for tt in TargetType.objects.all()}
                    
                    # Кэш типов дронов
                    # Создаем кэш дронов с ключом без дефисов для группировки X-51 и X51
                    drones_cache = {get_drone_comparison_key(drone.name): drone for drone in Drone.objects.all()}
                    
                    # Кэш видов БП
                    explosive_types_cache = {et.name.lower(): et for et in ExplosiveType.objects.all()}
                    
                    # Кэш видов взрывателей
                    explosive_devices_cache = {ed.name.lower(): ed for ed in ExplosiveDevice.objects.all()}
                    
                    # Проверяем существующие полеты для избежания дубликатов
                    # Создаем множество ключей существующих полетов: (number, pilot_id, flight_date, flight_time)
                    existing_flights_set = set(
                        Flight.objects.values_list('number', 'pilot_id', 'flight_date', 'flight_time')
                    )
                    logger.info(f"Найдено {len(existing_flights_set)} существующих полетов в БД")
                    
                    # Списки для создания новых записей в справочниках
                    new_target_types = {}
                    new_drones = {}
                    new_pilots = {}
                    new_explosive_types = {}
                    new_explosive_devices = {}
                    
                    # Инициализируем списки для bulk операций
                    flights_to_create = []
                    # Кэш дубликатов больше не используется - база очищена, все записи новые
                    
                    # Функции нормализации для целей и дронов (чтобы избежать дублирования)
                    def normalize_target_name(target_name):
                        """Нормализует название цели для объединения дубликатов"""
                        if not target_name:
                            return None
                        target_str = str(target_name).strip()
                        if not target_str:
                            return None
                        
                        target_lower = target_str.lower()
                        # Удаляем лишние пробелы, дефисы, точки, запятые
                        target_normalized = re.sub(r'[-\s\.\,]+', ' ', target_lower).strip()
                        
                        # Объединяем похожие варианты
                        # Автомобильная техника
                        if any(word in target_normalized for word in ['автомобильн', 'автотехник', 'авто техник', 'авто-техник']):
                            return 'Автомобильная техника'
                        # ПВХ
                        if 'пвх' in target_normalized:
                            match = re.search(r'пвх\s*[-\s]*(\d+[и]?)', target_normalized, re.IGNORECASE)
                            if match:
                                return f"ПВХ-{match.group(1).upper()}"
                            return 'ПВХ'
                        
                        # Общая нормализация
                        normalized = re.sub(r'[^\w\s]', '', target_str)
                        normalized = ' '.join(normalized.split())
                        if normalized:
                            normalized = normalized[0].upper() + normalized[1:].lower() if len(normalized) > 1 else normalized.upper()
                        return normalized if normalized else None
                    
                    def normalize_drone_name(drone_name):
                        """Нормализует название дрона для объединения дубликатов.
                        Сохраняет дефисы в названии, но группирует X-51 и X51 как один дрон."""
                        if not drone_name:
                            return None
                        drone_str = str(drone_name).strip()
                        if not drone_str:
                            return None
                        
                        drone_lower = drone_str.lower()
                        # Удаляем лишние пробелы, точки, запятые (но НЕ дефисы!)
                        drone_normalized = re.sub(r'[\s\.\,]+', ' ', drone_lower).strip()
                        
                        # Объединяем похожие варианты
                        # ПВХ
                        if 'пвх' in drone_normalized:
                            match = re.search(r'пвх\s*[-]?\s*(\d+[и]?)', drone_normalized, re.IGNORECASE)
                            if match:
                                # Всегда возвращаем версию с дефисом
                                return f"ПВХ-{match.group(1).upper()}"
                            return 'ПВХ'
                        # Молния
                        if 'молния' in drone_normalized:
                            match = re.search(r'молния\s*[-]?\s*(\d+[дт]?)', drone_normalized, re.IGNORECASE)
                            if match:
                                # Всегда возвращаем версию с дефисом
                                return f"Молния-{match.group(1).upper()}"
                            return 'Молния'
                        # КВН - преобразуем все варианты в два: КВН или КВН-Т
                        if 'квн' in drone_normalized:
                            # Находим позицию "квн" в строке
                            kvn_pos = drone_normalized.find('квн')
                            if kvn_pos != -1:
                                # Берем все после "квн" (3 символа: к, в, н)
                                substring_after_kvn = drone_normalized[kvn_pos + 3:]
                                # Убираем все символы кроме букв и цифр для проверки наличия "т"
                                # Это покроет все варианты: квн-т, квн-16т, квн-16-т, квн-23т, квн-23-т, квн 16 т, квнт и т.д.
                                cleaned = re.sub(r'[^а-яё0-9]', '', substring_after_kvn)
                                if 'т' in cleaned:
                                    return 'КВН-Т'
                            return 'КВН'
                        
                        # Для остальных - нормализуем пробелы, но сохраняем дефисы
                        # Приводим к правильному регистру: первая буква заглавная, остальные строчные
                        normalized = re.sub(r'\s+', ' ', drone_str.strip())
                        if normalized:
                            # Сохраняем дефисы и буквенно-цифровые символы
                            # Разбиваем на слова по пробелам и дефисам, но сохраняем структуру
                            words = re.split(r'([-\s])', normalized)
                            result = ''
                            for word in words:
                                if word in ['-', ' ']:
                                    result += word
                                elif word:
                                    # Первая буква заглавная, остальные строчные
                                    result += word[0].upper() + word[1:].lower() if len(word) > 1 else word.upper()
                            return result if result else None
                        return None
                    
                    # Показываем прогресс каждые 1000 строк
                    progress_interval = 1000

                    # Данные начинаются с сохраненной строки или с строки 5 (заголовки в строке 4)
                    data_start_row = start_row
                    # Не ограничиваем data_end_row - будем обрабатывать до конца файла или до 30 пустых строк подряд
                    data_end_row = ws.max_row
                    
                    # Обновляем total_rows в import_progress
                    if import_progress:
                        import_progress.total_rows = data_end_row
                        import_progress.save(update_fields=['total_rows'])
                    
                    # Определяем константу для максимального количества пустых строк подряд
                    # Увеличено до 50000, чтобы не останавливаться на больших разрывах данных
                    # Если после 50000 пустых строк подряд все еще нет данных, значит файл закончился
                    MAX_EMPTY_ROWS = 50000  # Увеличено для очень больших файлов с разрывами
                    CHECK_AHEAD_ROWS = 50000  # Сколько строк проверять после MAX_EMPTY_ROWS
                    
                    self.message_user(request, 
                                      _(f"Начинаем обработку с строки {data_start_row} до конца файла (или до {MAX_EMPTY_ROWS} пустых строк подряд). Всего строк в файле: {ws.max_row}"),
                                      level=messages.INFO)

                    # Получаем только нужные ячейки напрямую (оптимизация)
                    # Обрабатываем все строки (bulk операции позволяют обрабатывать большие объемы)
                    total_rows_to_process = data_end_row - data_start_row + 1
                    self.message_user(request,
                                      _(f"Начинаем обработку {total_rows_to_process} строк..."),
                                      level=messages.INFO)
                    
                    processed_row_count = 0
                    empty_rows_count = 0  # Счетчик пустых строк подряд
                    skipped_no_flight_number = 0  # Счетчик пропущенных строк без номера вылета
                    skipped_errors = 0  # Счетчик пропущенных строк из-за ошибок
                    skipped_no_date = 0  # Счетчик пропущенных строк без даты
                    skipped_no_pilot = 0  # Счетчик пропущенных строк без пилота
                    processed_successfully = 0  # Счетчик успешно обработанных строк
                    skipped_duplicates = 0  # Счетчик пропущенных дубликатов
                    updated_result_raw = 0  # Обновлён «Результат применения» у существующих вылетов
                    
                    for row_idx in range(data_start_row, data_end_row + 1):
                        processed_row_count += 1
                        
                        # Показываем прогресс и сохраняем его каждые 1000 обработанных строк
                        if processed_row_count % 1000 == 0:
                            progress_percent = processed_row_count * 100 // total_rows_to_process
                            self.message_user(request,
                                              _(f"📊 Обработано строк: {processed_row_count} из {total_rows_to_process} ({progress_percent}%). Создано записей: {created_count}, успешно обработано: {processed_successfully}"),
                                              level=messages.INFO)
                            # Сохраняем прогресс каждые 1000 строк для возможности продолжения при сбое
                            if import_progress:
                                try:
                                    import_progress.last_processed_row = data_start_row + processed_row_count - 1
                                    import_progress.total_created = created_count
                                    import_progress.save(update_fields=['last_processed_row', 'total_created', 'last_import_date'])
                                    logger.debug(f"Прогресс импорта сохранен: строка {import_progress.last_processed_row}, создано {created_count}")
                                except Exception as progress_error:
                                    logger.warning(f"Ошибка сохранения прогресса импорта: {progress_error}")
                        # Используем iter_rows для более быстрого чтения (только нужные колонки)
                        # Читаем только нужные колонки напрямую
                        row_values = [None] * (COL_OPERATOR_CALLNAME + 1)
                        
                        # Читаем только нужные колонки напрямую (оптимизировано)
                        try:
                            # Используем прямое чтение ячеек через cell() для нужных колонок
                            # Это быстрее чем читать всю строку
                            row_values[COL_TIME - 1] = ws.cell(row=row_idx, column=COL_TIME).value
                            row_values[COL_TARGET - 1] = ws.cell(row=row_idx, column=COL_TARGET).value
                            row_values[COL_COMMENT - 1] = ws.cell(row=row_idx, column=COL_COMMENT).value
                            row_values[COL_COORD_X - 1] = ws.cell(row=row_idx, column=COL_COORD_X).value
                            row_values[COL_COORD_Y - 1] = ws.cell(row=row_idx, column=COL_COORD_Y).value
                            row_values[COL_DRONE - 1] = ws.cell(row=row_idx, column=COL_DRONE).value
                            row_values[COL_EXPLOSIVE_TYPE - 1] = ws.cell(row=row_idx, column=COL_EXPLOSIVE_TYPE).value
                            row_values[COL_EXPLOSIVE_DEVICE - 1] = ws.cell(row=row_idx, column=COL_EXPLOSIVE_DEVICE).value
                            row_values[COL_APPLICATION_PURPOSE - 1] = ws.cell(row=row_idx, column=COL_APPLICATION_PURPOSE).value
                            row_values[COL_RESULT - 1] = ws.cell(row=row_idx, column=COL_RESULT).value
                            row_values[COL_FLIGHT_DATE - 1] = ws.cell(row=row_idx, column=COL_FLIGHT_DATE).value
                            row_values[COL_FLIGHT_NUMBER - 1] = ws.cell(row=row_idx, column=COL_FLIGHT_NUMBER).value
                            row_values[COL_DISTANCE - 1] = ws.cell(row=row_idx, column=COL_DISTANCE).value
                            row_values[COL_CALCULATION_NUMBER - 1] = ws.cell(row=row_idx, column=COL_CALCULATION_NUMBER).value
                            row_values[COL_OPERATOR_CALLNAME - 1] = ws.cell(row=row_idx, column=COL_OPERATOR_CALLNAME).value
                        except Exception as row_error:
                            # Если не удалось прочитать строку, пропускаем
                            logger.warning(f"Ошибка чтения строки {row_idx}: {row_error}")
                            continue

                        # Проверяем, есть ли данные в строке
                        # Строка считается пустой только если нет даты, позывного И типа дрона (минимальные требования)
                        time_value = row_values[COL_TIME - 1] if len(row_values) >= COL_TIME else None
                        pilot_value = row_values[COL_OPERATOR_CALLNAME - 1] if len(row_values) >= COL_OPERATOR_CALLNAME else None
                        date_value = row_values[COL_FLIGHT_DATE - 1] if len(row_values) >= COL_FLIGHT_DATE else None
                        drone_value = row_values[COL_DRONE - 1] if len(row_values) >= COL_DRONE else None
                        
                        # Нормализуем значения (убираем пробелы, проверяем на None и пустоту)
                        def is_empty_value(val):
                            if val is None:
                                return True
                            val_str = str(val).strip()
                            return not val_str or val_str == "" or val_str.lower() == "none" or val_str.lower() == "null"
                        
                        # Проверяем, является ли строка пустой
                        # Строка считается пустой только если нет ВСЕХ критических полей одновременно
                        # Но проверяем более мягко - если есть хотя бы одно из полей (дата, пилот, дрон, время, координаты), то строка не пустая
                        flight_number_value = row_values[COL_FLIGHT_NUMBER - 1] if len(row_values) >= COL_FLIGHT_NUMBER else None
                        coord_x_value = row_values[COL_COORD_X - 1] if len(row_values) >= COL_COORD_X else None
                        coord_y_value = row_values[COL_COORD_Y - 1] if len(row_values) >= COL_COORD_Y else None
                        target_value = row_values[COL_TARGET - 1] if len(row_values) >= COL_TARGET else None
                        
                        # Строка НЕ пустая, если есть хотя бы одно из критических полей (включая координаты и цель)
                        has_data = not is_empty_value(date_value) or \
                                  not is_empty_value(pilot_value) or \
                                  not is_empty_value(drone_value) or \
                                  not is_empty_value(time_value) or \
                                  not is_empty_value(flight_number_value) or \
                                  not is_empty_value(coord_x_value) or \
                                  not is_empty_value(coord_y_value) or \
                                  not is_empty_value(target_value)
                        
                        is_empty = not has_data
                        
                        # Логируем каждую 5000-ю строку для отладки (чтобы видеть прогресс)
                        if processed_row_count % 5000 == 0:
                            logger.info(f"Строка {row_idx}: пустая={is_empty}, дата={date_value}, пилот={pilot_value}, дрон={drone_value}, время={time_value}, номер={flight_number_value}, создано={created_count}")

                        if is_empty:
                            # Пустая строка - увеличиваем счетчик
                            empty_rows_count += 1
                            
                            # Логируем каждые 1000 пустых строк для отладки (чтобы не спамить)
                            if empty_rows_count % 1000 == 0:
                                logger.info(f"Обнаружено {empty_rows_count} пустых строк подряд (строка {row_idx})")
                                self.message_user(request,
                                                  _(f"⚠️ Обнаружено {empty_rows_count} пустых строк подряд на строке {row_idx}..."),
                                                  level=messages.WARNING)
                            
                            # Если подряд MAX_EMPTY_ROWS пустых строк - проверяем, есть ли дальше данные
                            if empty_rows_count >= MAX_EMPTY_ROWS:
                                # Улучшенная проверка: проверяем более тщательно и дальше
                                has_data_anywhere = False
                                max_check = min(row_idx + CHECK_AHEAD_ROWS, data_end_row + 1)
                                
                                # Проверяем каждую строку в первых 5000 строках (увеличено для больших файлов)
                                for check_row in range(row_idx + 1, min(row_idx + 5001, max_check)):
                                    try:
                                        check_flight_num = ws.cell(row=check_row, column=COL_FLIGHT_NUMBER).value
                                        check_time = ws.cell(row=check_row, column=COL_TIME).value
                                        check_pilot = ws.cell(row=check_row, column=COL_OPERATOR_CALLNAME).value
                                        check_date = ws.cell(row=check_row, column=COL_FLIGHT_DATE).value
                                        check_drone = ws.cell(row=check_row, column=COL_DRONE).value
                                        check_target = ws.cell(row=check_row, column=COL_TARGET).value
                                        check_coord_x = ws.cell(row=check_row, column=COL_COORD_X).value
                                        check_coord_y = ws.cell(row=check_row, column=COL_COORD_Y).value
                                        
                                        # Проверяем все ключевые поля
                                        if (check_flight_num is not None and str(check_flight_num).strip() and str(check_flight_num).strip().lower() not in ['none', 'null']) or \
                                           (check_time is not None and str(check_time).strip() and str(check_time).strip().lower() not in ['none', 'null']) or \
                                           (check_pilot is not None and str(check_pilot).strip() and str(check_pilot).strip().lower() not in ['none', 'null']) or \
                                           (check_date is not None and str(check_date).strip() and str(check_date).strip().lower() not in ['none', 'null']) or \
                                           (check_drone is not None and str(check_drone).strip() and str(check_drone).strip().lower() not in ['none', 'null']) or \
                                           (check_target is not None and str(check_target).strip() and str(check_target).strip().lower() not in ['none', 'null']) or \
                                           (check_coord_x is not None and str(check_coord_x).strip() and str(check_coord_x).strip().lower() not in ['none', 'null']) or \
                                           (check_coord_y is not None and str(check_coord_y).strip() and str(check_coord_y).strip().lower() not in ['none', 'null']):
                                            has_data_anywhere = True
                                            logger.info(f"Найдены данные на строке {check_row} после {empty_rows_count} пустых строк (текущая строка: {row_idx})")
                                            break
                                    except Exception as e:
                                        logger.debug(f"Ошибка при проверке строки {check_row}: {e}")
                                        continue
                                
                                # Если в первых 5000 строках данных нет, проверяем дальше более тщательно:
                                # - следующие 10000 строк проверяем каждые 50 строк
                                # - следующие 100000 строк проверяем каждые 100 строк  
                                # - дальше каждые 500 строк до конца файла
                                if not has_data_anywhere:
                                    # Следующие 10000 строк - каждые 50
                                    next_range_end = min(row_idx + 15001, max_check)
                                    for check_row in range(row_idx + 5001, next_range_end, 50):
                                        try:
                                            check_flight_num = ws.cell(row=check_row, column=COL_FLIGHT_NUMBER).value
                                            check_time = ws.cell(row=check_row, column=COL_TIME).value
                                            check_pilot = ws.cell(row=check_row, column=COL_OPERATOR_CALLNAME).value
                                            check_date = ws.cell(row=check_row, column=COL_FLIGHT_DATE).value
                                            check_drone = ws.cell(row=check_row, column=COL_DRONE).value
                                            
                                            if (check_flight_num is not None and str(check_flight_num).strip() and str(check_flight_num).strip().lower() not in ['none', 'null']) or \
                                               (check_time is not None and str(check_time).strip() and str(check_time).strip().lower() not in ['none', 'null']) or \
                                               (check_pilot is not None and str(check_pilot).strip() and str(check_pilot).strip().lower() not in ['none', 'null']) or \
                                               (check_date is not None and str(check_date).strip() and str(check_date).strip().lower() not in ['none', 'null']) or \
                                               (check_drone is not None and str(check_drone).strip() and str(check_drone).strip().lower() not in ['none', 'null']):
                                                has_data_anywhere = True
                                                logger.info(f"Найдены данные на строке {check_row} после {empty_rows_count} пустых строк (текущая строка: {row_idx})")
                                                break
                                        except Exception as e:
                                            logger.debug(f"Ошибка при проверке строки {check_row}: {e}")
                                            continue
                                    
                                    # Если все еще не нашли, проверяем дальше каждые 100 строк
                                    if not has_data_anywhere:
                                        next_range_end = min(row_idx + 110001, max_check)
                                        for check_row in range(row_idx + 15001, next_range_end, 100):
                                            try:
                                                check_flight_num = ws.cell(row=check_row, column=COL_FLIGHT_NUMBER).value
                                                check_time = ws.cell(row=check_row, column=COL_TIME).value
                                                check_pilot = ws.cell(row=check_row, column=COL_OPERATOR_CALLNAME).value
                                                check_date = ws.cell(row=check_row, column=COL_FLIGHT_DATE).value
                                                check_drone = ws.cell(row=check_row, column=COL_DRONE).value
                                                
                                                if (check_flight_num is not None and str(check_flight_num).strip() and str(check_flight_num).strip().lower() not in ['none', 'null']) or \
                                                   (check_time is not None and str(check_time).strip() and str(check_time).strip().lower() not in ['none', 'null']) or \
                                                   (check_pilot is not None and str(check_pilot).strip() and str(check_pilot).strip().lower() not in ['none', 'null']) or \
                                                   (check_date is not None and str(check_date).strip() and str(check_date).strip().lower() not in ['none', 'null']) or \
                                                   (check_drone is not None and str(check_drone).strip() and str(check_drone).strip().lower() not in ['none', 'null']):
                                                    has_data_anywhere = True
                                                    logger.info(f"Найдены данные на строке {check_row} после {empty_rows_count} пустых строк (текущая строка: {row_idx})")
                                                    break
                                            except Exception as e:
                                                logger.debug(f"Ошибка при проверке строки {check_row}: {e}")
                                                continue
                                    
                                    # Если все еще не нашли, проверяем дальше каждые 500 строк до конца файла
                                    if not has_data_anywhere:
                                        for check_row in range(row_idx + 110001, max_check, 500):
                                            try:
                                                check_flight_num = ws.cell(row=check_row, column=COL_FLIGHT_NUMBER).value
                                                check_time = ws.cell(row=check_row, column=COL_TIME).value
                                                check_pilot = ws.cell(row=check_row, column=COL_OPERATOR_CALLNAME).value
                                                check_date = ws.cell(row=check_row, column=COL_FLIGHT_DATE).value
                                                check_drone = ws.cell(row=check_row, column=COL_DRONE).value
                                                
                                                if (check_flight_num is not None and str(check_flight_num).strip() and str(check_flight_num).strip().lower() not in ['none', 'null']) or \
                                                   (check_time is not None and str(check_time).strip() and str(check_time).strip().lower() not in ['none', 'null']) or \
                                                   (check_pilot is not None and str(check_pilot).strip() and str(check_pilot).strip().lower() not in ['none', 'null']) or \
                                                   (check_date is not None and str(check_date).strip() and str(check_date).strip().lower() not in ['none', 'null']) or \
                                                   (check_drone is not None and str(check_drone).strip() and str(check_drone).strip().lower() not in ['none', 'null']):
                                                    has_data_anywhere = True
                                                    logger.info(f"Найдены данные на строке {check_row} после {empty_rows_count} пустых строк (текущая строка: {row_idx})")
                                                    break
                                            except Exception as e:
                                                logger.debug(f"Ошибка при проверке строки {check_row}: {e}")
                                                continue
                                
                                if not has_data_anywhere:
                                    self.message_user(request,
                                                      _(f"⚠️ Обнаружено {MAX_EMPTY_ROWS}+ пустых строк подряд. Проверено еще до {max_check} строки - данных нет. Обработка файла прекращена на строке {row_idx}."),
                                                      level=messages.WARNING)
                                    logger.info(f"Остановка импорта: {MAX_EMPTY_ROWS}+ пустых строк подряд на строке {row_idx}, данных дальше нет (проверено до строки {max_check})")
                                    break
                                else:
                                    # Есть данные дальше - сбрасываем счетчик и продолжаем
                                    self.message_user(request,
                                                      _(f"⚠️ Обнаружено {empty_rows_count} пустых строк подряд, но дальше есть данные (найдено на строке {check_row}). Продолжаем обработку..."),
                                                      level=messages.INFO)
                                    empty_rows_count = 0
                            continue
                        
                        # Если строка не пустая - сбрасываем счетчик пустых строк
                        if empty_rows_count > 0:
                            logger.debug(f"Сброс счетчика пустых строк (было {empty_rows_count}) на строке {row_idx}")
                            empty_rows_count = 0
                        else:
                            # Сбрасываем счетчик, если строка не пустая
                            empty_rows_count = 0

                        try:
                            # Номер вылета из колонки S (необязательное поле)
                            flight_number_raw = row_values[COL_FLIGHT_NUMBER - 1] if len(row_values) >= COL_FLIGHT_NUMBER else None
                            flight_number = None
                            
                            if flight_number_raw is not None:
                                # Пробуем разные способы преобразования номера вылета
                                try:
                                    # Сначала пробуем как число
                                    if isinstance(flight_number_raw, (int, float)):
                                        flight_number = int(float(flight_number_raw))
                                    else:
                                        # Пробуем извлечь число из строки
                                        flight_number_str = str(flight_number_raw).strip()
                                        # Убираем все нецифровые символы, кроме минуса в начале
                                        numbers = re.findall(r'-?\d+', flight_number_str)
                                        if numbers:
                                            flight_number = int(float(numbers[0]))
                                except (ValueError, TypeError):
                                    # Если номер вылета некорректный, просто игнорируем его
                                    flight_number = None
                            
                            # Если номера вылета нет - генерируем его автоматически на основе даты, пилота и времени
                            # Это позволит обрабатывать строки без номера вылета, но с датой, позывным и типом дрона
                            # Сначала получаем пилота и дату, чтобы сгенерировать номер

                            # Позывной оператора из колонки V; если пусто — по № расчёта (Q) с листа «Информация»
                            pilot_callname_raw = row_values[COL_OPERATOR_CALLNAME - 1] if len(row_values) >= COL_OPERATOR_CALLNAME else None
                            if is_empty_value(pilot_callname_raw) and calculation_pilot_map:
                                calc_raw = (
                                    row_values[COL_CALCULATION_NUMBER - 1]
                                    if len(row_values) >= COL_CALCULATION_NUMBER
                                    else None
                                )
                                if calc_raw is not None:
                                    try:
                                        calc_num = int(float(calc_raw))
                                        pilot_callname_raw = calculation_pilot_map.get(calc_num)
                                    except (TypeError, ValueError):
                                        pass
                            pilot = None
                            if pilot_callname_raw:
                                callname_to_search = str(pilot_callname_raw).strip()
                                if callname_to_search.startswith("пилот "):
                                    parts = callname_to_search.split()
                                    if len(parts) > 1:
                                        callname_to_search = parts[1]  # Берем вторую часть
                                
                                # Если позывной пустой после очистки — не создаём "Неизвестный_N", строка будет пропущена
                                if not callname_to_search:
                                    logger.debug(f"Строка {row_idx}: пустой позывной, строка будет пропущена")
                                else:
                                    # Ищем пилота в кэше (быстрее чем запрос к БД)
                                    callname_lower = callname_to_search.lower()
                                    pilot = pilots_cache.get(callname_lower)
                                    
                                    if pilot is None:
                                        # Проверяем список новых пилотов
                                        if callname_to_search in new_pilots:
                                            pilot = new_pilots[callname_to_search]
                                        else:
                                            # Создаем нового пилота и сохраняем сразу в БД
                                            import uuid
                                            temp_tg_id = abs(hash(callname_to_search)) % (10 ** 10)
                                            while Pilot.objects.filter(tg_id=temp_tg_id).exists():
                                                temp_tg_id = abs(hash(f"{callname_to_search}{uuid.uuid4()}")) % (10 ** 10)
                                            
                                            # Сохраняем пилота сразу, чтобы получить id для foreign key
                                            pilot, created = Pilot.objects.get_or_create(
                                                callname=callname_to_search,
                                                defaults={'tg_id': temp_tg_id}
                                            )
                                            if created:
                                                logger.info(f"Автоматически создан пилот '{callname_to_search}' с временным TG ID: {temp_tg_id}")
                                            
                                            # Добавляем в кэши
                                            new_pilots[callname_to_search] = pilot
                                            pilots_cache[callname_lower] = pilot
                            else:
                                # Колонка пилота пуста — не создаём "Неизвестный_N", строка будет пропущена
                                pilot = None

                            # Строки без валидного пилота пропускаем (не создаём полёты и не создаём фейковых пилотов)
                            if pilot is None:
                                skipped_no_pilot += 1
                                continue

                            # Время из колонки B
                            time_str = row_values[COL_TIME - 1] if len(row_values) >= COL_TIME else None
                            flight_time = None
                            if time_str and isinstance(time_str, datetime.time):
                                flight_time = time_str
                            elif time_str and isinstance(time_str, str):
                                time_str_clean = str(time_str).strip()
                                if time_str_clean:
                                    try:
                                        flight_time = datetime.datetime.strptime(time_str_clean, "%H:%M").time()
                                    except ValueError:
                                        try:
                                            flight_time = datetime.datetime.strptime(time_str_clean, "%H:%M:%S").time()
                                        except ValueError:
                                            # Пробуем другие форматы
                                            try:
                                                # Формат "HH:MM:SS" или "HH:MM"
                                                parts = time_str_clean.split(':')
                                                if len(parts) >= 2:
                                                    hour = int(parts[0])
                                                    minute = int(parts[1])
                                                    second = int(parts[2]) if len(parts) > 2 else 0
                                                    flight_time = datetime.time(hour, minute, second)
                                            except (ValueError, IndexError):
                                                pass
                            elif time_str and isinstance(time_str, datetime.datetime):
                                flight_time = time_str.time()
                            
                            # Если время не удалось распарсить, используем значение по умолчанию (00:00:00)
                            if flight_time is None:
                                flight_time = datetime.time(0, 0, 0)

                            # Дата вылета из колонки R
                            flight_date = None
                            date_value = row_values[COL_FLIGHT_DATE - 1] if len(row_values) >= COL_FLIGHT_DATE else None
                            if date_value:
                                if isinstance(date_value, datetime.datetime):
                                    flight_date = date_value.date()
                                elif isinstance(date_value, datetime.date):
                                    flight_date = date_value
                                elif isinstance(date_value, str):
                                    # Пробуем распарсить строку с датой
                                    for date_format in ['%d.%m.%Y', '%d-%m-%Y', '%d/%m/%Y', '%Y-%m-%d', '%d.%m.%y', '%d-%m-%y']:
                                        try:
                                            flight_date = datetime.datetime.strptime(date_value.strip(), date_format).date()
                                            break
                                        except ValueError:
                                            continue
                            
                            # Если даты нет - используем текущую дату
                            if flight_date is None:
                                flight_date = datetime.date.today()
                                logger.debug(f"Строка {row_idx}: нет даты вылета, используется текущая дата {flight_date}")
                            
                            # Если номера вылета нет, но есть дата и пилот - генерируем номер автоматически
                            # Пилот всегда должен быть создан к этому моменту (либо из данных, либо временный)
                            if flight_number is None:
                                if flight_date and pilot:
                                    # Генерируем номер на основе даты, пилота и номера строки
                                    import hashlib
                                    unique_str = f"{flight_date.isoformat()}_{pilot.id}_{row_idx}"
                                    hash_value = int(hashlib.md5(unique_str.encode()).hexdigest()[:8], 16)
                                    flight_number = abs(hash_value) % (10 ** 8)
                                    # Убеждаемся, что номер не конфликтует с существующими полетами этого пилота
                                    while Flight.objects.filter(number=flight_number, pilot=pilot).exists():
                                        flight_number = (flight_number + 1) % (10 ** 8)
                                    logger.debug(f"Строка {row_idx}: автоматически сгенерирован номер вылета {flight_number}")
                                else:
                                    # Если нет даты или пилота - это критическая ошибка, но пилот должен быть создан
                                    # Если пилота нет - это ошибка в логике выше
                                    if not pilot:
                                        logger.error(f"Строка {row_idx}: КРИТИЧЕСКАЯ ОШИБКА - пилот не создан!")
                                        skipped_no_pilot += 1
                                        continue
                                    if not flight_date:
                                        logger.warning(f"Строка {row_idx}: нет даты, используется текущая дата")
                                        flight_date = datetime.date.today()
                                    # Повторяем генерацию номера
                                    import hashlib
                                    unique_str = f"{flight_date.isoformat()}_{pilot.id}_{row_idx}"
                                    hash_value = int(hashlib.md5(unique_str.encode()).hexdigest()[:8], 16)
                                    flight_number = abs(hash_value) % (10 ** 8)
                                    while Flight.objects.filter(number=flight_number, pilot=pilot).exists():
                                        flight_number = (flight_number + 1) % (10 ** 8)
                                    logger.debug(f"Строка {row_idx}: автоматически сгенерирован номер вылета {flight_number} (после исправления)")
                            
                            # Теперь номер вылета должен быть всегда (либо из данных, либо сгенерирован)
                            if flight_number is None:
                                # Это не должно происходить, но на всякий случай
                                skipped_no_flight_number += 1
                                if skipped_no_flight_number <= 20:
                                    logger.error(f"Строка {row_idx}: КРИТИЧЕСКАЯ ОШИБКА - не удалось создать номер вылета! Дата: {flight_date}, Пилот: {pilot.callname if pilot else None}")
                                continue
                            
                            # Логируем каждую 1000-ю успешно обработанную строку для отладки
                            if processed_successfully > 0 and processed_successfully % 1000 == 0:
                                logger.info(f"Успешно обработано строк: {processed_successfully}, создано записей в памяти: {len(flights_to_create)}, всего создано в БД: {created_count}")

                            # Характер цели из колонки C
                            target_raw = row_values[COL_TARGET - 1] if len(row_values) >= COL_TARGET else None
                            target_raw = str(target_raw).strip() if target_raw else None
                            
                            # Нормализуем название цели для избежания дублирования
                            target = normalize_target_name(target_raw) if target_raw else None
                            
                            # Добавляем в список для создания, если нужно (создадим батчем позже)
                            if target:
                                # Проверяем в кэше по нормализованному значению
                                target_lower = target.lower()
                                if target_lower not in target_types_cache:
                                    # Проверяем, нет ли уже в списке новых с таким же нормализованным значением
                                    existing_in_new = None
                                    for existing_target in new_target_types.keys():
                                        if existing_target.lower() == target_lower:
                                            existing_in_new = existing_target
                                            break
                                    
                                    if existing_in_new:
                                        # Используем существующее нормализованное значение
                                        target = existing_in_new
                                    else:
                                        # Создаем новое с нормализованным именем
                                        new_target_types[target] = TargetType(name=target, weight=1)
                                else:
                                    # Используем значение из кэша (уже нормализованное)
                                    target = target_types_cache[target_lower].name
                            
                            corrective = None  # В новой структуре нет отдельной колонки для corrective

                            application_purpose_raw = (
                                row_values[COL_APPLICATION_PURPOSE - 1]
                                if len(row_values) >= COL_APPLICATION_PURPOSE
                                else None
                            )
                            application_purpose = (
                                str(application_purpose_raw).strip()
                                if application_purpose_raw
                                else None
                            )

                            # Результат применения из колонки O
                            result_raw = row_values[COL_RESULT - 1] if len(row_values) >= COL_RESULT else None
                            result_raw_text = str(result_raw).strip() if result_raw else ''
                            result = FlightResultTypes.from_excel_text(result_raw)

                            # Координаты из колонок E и F
                            coord_x = row_values[COL_COORD_X - 1] if len(row_values) >= COL_COORD_X else None
                            coord_y = row_values[COL_COORD_Y - 1] if len(row_values) >= COL_COORD_Y else None
                            coordinates = None
                            if coord_x is not None and coord_y is not None:
                                coordinates = f"{coord_x} {coord_y}"

                            # Тип дрона из колонки H
                            drone_raw = row_values[COL_DRONE - 1] if len(row_values) >= COL_DRONE else None
                            drone_raw = str(drone_raw).strip() if drone_raw else None
                            
                            # Нормализуем название дрона для избежания дублирования
                            drone = normalize_drone_name(drone_raw) if drone_raw else None
                            
                            # Добавляем в список для создания, если нужно (создадим батчем позже)
                            if drone:
                                # Создаем ключ для сравнения без дефисов (чтобы X-51 и X51 группировались)
                                drone_key = get_drone_comparison_key(drone)
                                
                                # Проверяем в кэше по ключу без дефисов
                                found_in_cache = None
                                for cached_key, cached_drone in drones_cache.items():
                                    if get_drone_comparison_key(cached_drone.name) == drone_key:
                                        found_in_cache = cached_drone
                                        # Если новый дрон имеет дефис, а найденный - нет, обновляем
                                        if '-' in drone and '-' not in cached_drone.name:
                                            cached_drone.name = drone
                                            cached_drone.save(update_fields=['name'])
                                        drone = found_in_cache.name
                                        break
                                
                                if not found_in_cache:
                                    # Проверяем, нет ли уже в списке новых с таким же ключом
                                    existing_in_new = None
                                    for existing_drone in new_drones.keys():
                                        if get_drone_comparison_key(existing_drone) == drone_key:
                                            existing_in_new = existing_drone
                                            # Если новый дрон имеет дефис, используем его
                                            if '-' in drone and '-' not in existing_drone:
                                                # Обновляем существующий в new_drones
                                                drone_obj = new_drones.pop(existing_drone)
                                                drone_obj.name = drone
                                                new_drones[drone] = drone_obj
                                                existing_in_new = drone
                                            break
                                    
                                    if existing_in_new:
                                        # Используем существующее значение
                                        drone = existing_in_new
                                    else:
                                        # Определяем тип дрона (KT или ST) по названию
                                        drone_lower = drone.lower()
                                        drone_type_choice = DroneTypes.KT  # По умолчанию KT
                                        if 'ст' in drone_lower or 'st' in drone_lower:
                                            drone_type_choice = DroneTypes.ST
                                        elif 'кт' in drone_lower or 'kt' in drone_lower:
                                            drone_type_choice = DroneTypes.KT
                                        new_drones[drone] = Drone(name=drone, drone_type=drone_type_choice, description='')
                            
                            # Вид БП из колонки J
                            explosive_type_raw = row_values[COL_EXPLOSIVE_TYPE - 1] if len(row_values) >= COL_EXPLOSIVE_TYPE else None
                            explosive_type = None
                            if explosive_type_raw:
                                explosive_type_str = str(explosive_type_raw).strip()
                                if explosive_type_str:
                                    # Проверяем в кэше
                                    explosive_type_lower = explosive_type_str.lower()
                                    explosive_type_obj = explosive_types_cache.get(explosive_type_lower)
                                    
                                    if explosive_type_obj is None:
                                        # Добавляем в список для создания
                                        if explosive_type_str not in new_explosive_types:
                                            new_explosive_types[explosive_type_str] = ExplosiveType(name=explosive_type_str)
                                        explosive_type = explosive_type_str
                                    else:
                                        explosive_type = explosive_type_obj.name
                            
                            # Вид взрывателя из колонки L
                            explosive_device_raw = row_values[COL_EXPLOSIVE_DEVICE - 1] if len(row_values) >= COL_EXPLOSIVE_DEVICE else None
                            explosive_device = None
                            if explosive_device_raw:
                                explosive_device_str = str(explosive_device_raw).strip()
                                if explosive_device_str:
                                    # Проверяем в кэше
                                    explosive_device_lower = explosive_device_str.lower()
                                    explosive_device_obj = explosive_devices_cache.get(explosive_device_lower)
                                    
                                    if explosive_device_obj is None:
                                        # Добавляем в список для создания
                                        if explosive_device_str not in new_explosive_devices:
                                            new_explosive_devices[explosive_device_str] = ExplosiveDevice(name=explosive_device_str)
                                        explosive_device = explosive_device_str
                                    else:
                                        explosive_device = explosive_device_obj.name
                            
                            # Дистанция из колонки T
                            distance = row_values[COL_DISTANCE - 1] if len(row_values) >= COL_DISTANCE else None
                            distance = str(distance).strip() if distance else None
                            
                            # Поля, которых нет в новой структуре, оставляем None
                            engineer = None
                            driver = None
                            video = None
                            manage = None
                            video_length = None
                            
                            # Комментарий из колонки D
                            comment_raw = row_values[COL_COMMENT - 1] if len(row_values) >= COL_COMMENT else None
                            comment = None
                            if comment_raw:
                                try:
                                    comment = str(comment_raw).strip()
                                    if comment and comment.lower() not in ('none', 'null', ''):
                                        # Обрезаем до 255 символов (ограничение поля в БД)
                                        if len(comment) > 255:
                                            comment = comment[:255]
                                    else:
                                        comment = None
                                except Exception as comment_error:
                                    logger.warning(f"Ошибка обработки комментария в строке {row_idx}: {comment_error}")
                                    comment = None
                            
                            drone_remains = None
                            direction = None
                            objective = FlightObjectiveTypes.NOT_EXISTS  # По умолчанию
                            
                            # Подготавливаем данные для сохранения
                            flight_defaults = {
                                'flight_date': flight_date,
                                'flight_time': flight_time,
                                'target': target,
                                'application_purpose': application_purpose,
                                'corrective': corrective,
                                'result': result,
                                'result_raw': result_raw_text or None,
                                'drone': drone,
                                'explosive_type': explosive_type,
                                'explosive_device': explosive_device,
                                'distance': distance,
                                'objective': objective,
                                'comment': comment,
                            }
                            
                            # Добавляем coordinates только если они есть
                            if coordinates and coordinates.strip():
                                flight_defaults['coordinates'] = coordinates
                            
                            # Удаляем None значения, но оставляем comment даже если он None (это валидное значение)
                            # comment может быть None, и это нормально
                            flight_defaults_clean = {k: v for k, v in flight_defaults.items() if v is not None or k == 'comment'}
                            flight_defaults = flight_defaults_clean
                            
                            # Проверяем, существует ли уже такой полет
                            # Сначала проверяем по ключевым полям (быстрая проверка)
                            flight_key = (
                                flight_number,
                                pilot.id if pilot else None,
                                flight_defaults.get('flight_date'),
                                flight_defaults.get('flight_time')
                            )
                            
                            # Пропускаем, если полет уже существует в текущем импорте
                            if flight_key in existing_flights_set:
                                skipped_duplicates += 1
                                if skipped_duplicates <= 10:  # Логируем только первые 10
                                    logger.debug(f"Пропущен дубликат полета в текущем импорте: номер={flight_number}, пилот={pilot.callname if pilot else None}, дата={flight_defaults.get('flight_date')}, время={flight_defaults.get('flight_time')}")
                                continue

                            # Существующий вылет по ключу — дополняем result_raw из колонки «Результат»
                            existing_by_key = Flight.objects.filter(
                                number=flight_number,
                                pilot=pilot,
                                flight_date=flight_defaults.get('flight_date'),
                                flight_time=flight_defaults.get('flight_time'),
                            ).first()
                            if existing_by_key:
                                update_fields = []
                                if result_raw_text and (existing_by_key.result_raw or '') != result_raw_text:
                                    existing_by_key.result_raw = result_raw_text
                                    existing_by_key.result = result
                                    update_fields.extend(['result_raw', 'result'])
                                if application_purpose and (existing_by_key.application_purpose or '') != application_purpose:
                                    existing_by_key.application_purpose = application_purpose
                                    update_fields.append('application_purpose')
                                if update_fields:
                                    existing_by_key.save(update_fields=update_fields)
                                    if 'result_raw' in update_fields:
                                        updated_result_raw += 1
                                skipped_duplicates += 1
                                existing_flights_set.add(flight_key)
                                continue
                            
                            # Строгая проверка на полностью одинаковые записи (все поля)
                            # Проверяем в базе данных на полностью одинаковые записи только если не найден в текущем импорте
                            # Это оптимизация - избегаем лишних запросов к БД
                            existing_duplicate = None
                            try:
                                existing_duplicate = Flight.objects.filter(
                                    number=flight_number,
                                    pilot=pilot,
                                    flight_date=flight_defaults.get('flight_date'),
                                    flight_time=flight_defaults.get('flight_time'),
                                    target=flight_defaults.get('target'),
                                    drone=flight_defaults.get('drone'),
                                    result=flight_defaults.get('result'),
                                    result_raw=flight_defaults.get('result_raw'),
                                    coordinates=flight_defaults.get('coordinates'),
                                    distance=flight_defaults.get('distance'),
                                    explosive_type=flight_defaults.get('explosive_type'),
                                    explosive_device=flight_defaults.get('explosive_device'),
                                    application_purpose=flight_defaults.get('application_purpose'),
                                    corrective=flight_defaults.get('corrective'),
                                    objective=flight_defaults.get('objective'),
                                    comment=flight_defaults.get('comment'),
                                ).first()
                            except Exception as dup_check_error:
                                logger.warning(f"Ошибка при проверке дубликата для строки {row_idx}: {dup_check_error}")
                            
                            if existing_duplicate:
                                skipped_duplicates += 1
                                if skipped_duplicates <= 10:  # Логируем только первые 10
                                    logger.debug(f"Пропущен полностью идентичный дубликат полета: номер={flight_number}, пилот={pilot.callname if pilot else None}, дата={flight_defaults.get('flight_date')}, время={flight_defaults.get('flight_time')}")
                                continue
                            
                            # Создаем новый полет
                            try:
                                new_flight = Flight(
                                    number=flight_number,
                                    pilot=pilot,
                                    **flight_defaults
                                )
                                flights_to_create.append(new_flight)
                                # Добавляем в множество существующих, чтобы не создавать дубликаты в рамках одного импорта
                                existing_flights_set.add(flight_key)
                                processed_successfully += 1
                                
                                # Логируем каждую 1000-ю успешно обработанную строку
                                if processed_successfully % 1000 == 0:
                                    logger.info(f"Обработано успешно: {processed_successfully}, в памяти для создания: {len(flights_to_create)}, всего создано в БД: {created_count}")
                            except Exception as flight_create_error:
                                logger.error(f"Ошибка создания объекта Flight для строки {row_idx}: {flight_create_error}")
                                logger.error(f"Данные: номер={flight_number}, пилот={pilot.callname if pilot else None}, defaults={flight_defaults}")
                                skipped_errors += 1
                                continue
                            
                            # Сохраняем батчами каждые 25 записей (уменьшено для избежания нехватки памяти)
                            total_batch = len(flights_to_create)
                            if total_batch >= 25:
                                from django.db import transaction
                                try:
                                    with transaction.atomic():
                                        # Сначала создаем справочники, если нужно
                                        if new_target_types:
                                            TargetType.objects.bulk_create(new_target_types.values(), ignore_conflicts=True)
                                            # Перезагружаем кэш из базы для получения актуальных нормализованных значений
                                            target_types_cache = {tt.name.lower(): tt for tt in TargetType.objects.all()}
                                            new_target_types.clear()
                                        
                                        if new_drones:
                                            Drone.objects.bulk_create(new_drones.values(), ignore_conflicts=True)
                                            # Перезагружаем кэш из базы для получения актуальных нормализованных значений
                                            # Создаем кэш дронов с ключом без дефисов для группировки X-51 и X51
                                            drones_cache = {get_drone_comparison_key(drone.name): drone for drone in Drone.objects.all()}
                                            new_drones.clear()
                                        
                                        if new_explosive_types:
                                            ExplosiveType.objects.bulk_create(new_explosive_types.values(), ignore_conflicts=True)
                                            for et in new_explosive_types.values():
                                                explosive_types_cache[et.name.lower()] = et
                                            new_explosive_types.clear()
                                        
                                        if new_explosive_devices:
                                            ExplosiveDevice.objects.bulk_create(new_explosive_devices.values(), ignore_conflicts=True)
                                            for ed in new_explosive_devices.values():
                                                explosive_devices_cache[ed.name.lower()] = ed
                                            new_explosive_devices.clear()
                                        
                                        if flights_to_create:
                                            # Сохраняем копию для обновления existing_flights_set
                                            temp_flights_for_set = flights_to_create.copy()
                                            # Разбиваем на меньшие батчи для избежания нехватки памяти
                                            batch_size = 25
                                            total_created_in_batch = 0
                                            total_failed_in_batch = 0
                                            for i in range(0, len(flights_to_create), batch_size):
                                                batch = flights_to_create[i:i + batch_size]
                                                try:
                                                    created_objects = Flight.objects.bulk_create(batch, ignore_conflicts=True)
                                                    # bulk_create с ignore_conflicts=True возвращает ТОЛЬКО созданные объекты
                                                    # Если объект не был создан из-за конфликта, он НЕ будет в списке
                                                    created_count_in_sub_batch = len(created_objects) if created_objects else 0
                                                    total_created_in_batch += created_count_in_sub_batch
                                                    
                                                    # Если создано меньше, чем в батче - значит были конфликты
                                                    if created_count_in_sub_batch < len(batch):
                                                        failed_count = len(batch) - created_count_in_sub_batch
                                                        total_failed_in_batch += failed_count
                                                        if total_failed_in_batch <= 10:  # Логируем только первые 10
                                                            logger.warning(f"В батче {i//batch_size + 1} не создано {failed_count} записей из-за конфликтов (строка ~{row_idx})")
                                                        # Пробуем создать по одной записи для тех, что не создались
                                                        for flight in batch:
                                                            # Проверяем, был ли создан этот полет (проверяем по всем ключевым полям)
                                                            existing = Flight.objects.filter(
                                                                number=flight.number,
                                                                pilot=flight.pilot,
                                                                flight_date=flight.flight_date,
                                                                flight_time=flight.flight_time
                                                            ).first()
                                                            
                                                            if not existing:
                                                                try:
                                                                    flight.save()
                                                                    total_created_in_batch += 1
                                                                    total_failed_in_batch -= 1
                                                                    if total_failed_in_batch <= 5:
                                                                        logger.info(f"Успешно создан полет {flight.number} для пилота {flight.pilot.callname} при повторной попытке")
                                                                except Exception as single_error:
                                                                    if total_failed_in_batch <= 10:
                                                                        logger.warning(f"Не удалось создать полет {flight.number} для пилота {flight.pilot.callname}: {single_error}")
                                                            else:
                                                                # Запись уже существует - это нормально, просто не считаем как ошибку
                                                                total_failed_in_batch -= 1
                                                                if total_failed_in_batch <= 5:
                                                                    logger.debug(f"Полет {flight.number} для пилота {flight.pilot.callname} уже существует в БД")
                                                except Exception as batch_create_error:
                                                    logger.error(f"Ошибка при bulk_create батча {i//batch_size + 1}: {batch_create_error}", exc_info=True)
                                                    # Пробуем создать по одной записи
                                                    for flight in batch:
                                                        try:
                                                            flight.save()
                                                            total_created_in_batch += 1
                                                        except Exception as single_error:
                                                            total_failed_in_batch += 1
                                                            if total_failed_in_batch <= 10:
                                                                logger.warning(f"Не удалось создать полет {flight.number} для пилота {flight.pilot.callname}: {single_error}")
                                            
                                            created_count += total_created_in_batch
                                            if total_created_in_batch != len(flights_to_create):
                                                logger.warning(f"Создано {total_created_in_batch} из {len(flights_to_create)} записей в батче (строка ~{row_idx}). Не создано: {total_failed_in_batch}")
                                                self.message_user(request,
                                                                  _(f"⚠️ В батче создано {total_created_in_batch} из {len(flights_to_create)} записей (строка ~{row_idx}). Не создано: {total_failed_in_batch}"),
                                                                  level=messages.WARNING)
                                            
                                            # Координаты — один раз после завершения файла (см. process_coordinates_background ниже)
                                            
                                            # Очищаем список после сохранения
                                            # (не добавляем в existing_flights_set, так как база уже очищена)
                                            flights_to_create = []
                                        
                                        # Явная очистка памяти после каждого батча
                                        import gc
                                        gc.collect()
                                        
                                        # Сохраняем прогресс импорта после каждого батча
                                        if import_progress:
                                            try:
                                                import_progress.last_processed_row = row_idx
                                                import_progress.total_created = created_count
                                                import_progress.save(update_fields=['last_processed_row', 'total_created', 'last_import_date'])
                                                logger.debug(f"Прогресс импорта сохранен: строка {row_idx}, создано {created_count}")
                                            except Exception as progress_error:
                                                logger.warning(f"Ошибка сохранения прогресса импорта: {progress_error}")
                                        
                                        # flights_to_update не используется, так как база очищена
                                    
                                    # Кэш больше не используется, так как не проверяем дубликаты
                                    
                                    # Показываем прогресс каждые 1000 сохраненных записей
                                    total_processed = created_count
                                    if total_processed % 1000 == 0:
                                        self.message_user(request,
                                                          _(f"💾 Сохранено {total_processed} записей (создано: {created_count})..."),
                                                          level=messages.INFO)
                                    
                                except Exception as batch_error:
                                    error_msg = f"Ошибка при сохранении батча (строка ~{row_idx}): {str(batch_error)}"
                                    if len(error_messages) < 200:
                                        error_messages.append(error_msg)
                                    logger.error(f"Ошибка при сохранении батча: {batch_error}", exc_info=True)
                                    # НЕ очищаем списки - оставим записи для повторной попытки в финальном батче
                                    # Только логируем ошибку и продолжаем
                                    self.message_user(request,
                                                      _(f"⚠️ Ошибка при сохранении батча на строке ~{row_idx}. Записи будут сохранены в финальном батче."),
                                                      level=messages.WARNING)

                        except Exception as e:
                            error_msg = f"Ошибка обработки строки {row_idx} в файле '{source.name}': {str(e)}"
                            
                            # Не добавляем ошибки для пропущенных строк (без номера вылета или времени)
                            if "Номер вылета не указан" in str(e) or "Некорректный номер вылета" in str(e):
                                # Это не критическая ошибка, просто пропускаем строку
                                skipped_errors += 1
                                if skipped_errors <= 20:
                                    logger.warning(f"Строка {row_idx} пропущена: {str(e)}")
                                continue
                            
                            # Добавляем только критические ошибки
                            skipped_errors += 1
                            if len(error_messages) < 200:
                                error_messages.append(error_msg)
                            if skipped_errors <= 20:
                                logger.warning(error_msg, exc_info=True)
                            
                            # Продолжаем обработку даже при ошибках
                        
                        # Проверяем после обработки строки, не был ли прерван цикл из-за пустых строк
                        if empty_rows_count >= MAX_EMPTY_ROWS:
                            break
                    
                    # Создаем оставшиеся записи в справочниках
                    # Пилоты уже создаются сразу при первом использовании через get_or_create, поэтому их не нужно создавать здесь
                    
                    if new_target_types:
                        TargetType.objects.bulk_create(new_target_types.values(), ignore_conflicts=True)
                        # Перезагружаем кэш из базы для получения актуальных нормализованных значений
                        target_types_cache = {tt.name.lower(): tt for tt in TargetType.objects.all()}
                    
                    if new_drones:
                        Drone.objects.bulk_create(new_drones.values(), ignore_conflicts=True)
                        # Перезагружаем кэш из базы для получения актуальных нормализованных значений
                        # Создаем кэш дронов с ключом без дефисов для группировки X-51 и X51
                        drones_cache = {get_drone_comparison_key(drone.name): drone for drone in Drone.objects.all()}
                        new_drones.clear()
                    
                    if new_explosive_types:
                        ExplosiveType.objects.bulk_create(new_explosive_types.values(), ignore_conflicts=True)
                        for et in new_explosive_types.values():
                            explosive_types_cache[et.name.lower()] = et
                    
                    if new_explosive_devices:
                        ExplosiveDevice.objects.bulk_create(new_explosive_devices.values(), ignore_conflicts=True)
                        for ed in new_explosive_devices.values():
                            explosive_devices_cache[ed.name.lower()] = ed
                    
                    # Сохраняем оставшиеся записи полетов (последний батч)
                    from django.db import transaction
                    if flights_to_create:
                        try:
                            with transaction.atomic():
                                # Сначала создаем справочники, если нужно
                                if new_target_types:
                                    TargetType.objects.bulk_create(new_target_types.values(), ignore_conflicts=True)
                                    # Перезагружаем кэш из базы для получения актуальных нормализованных значений
                                    target_types_cache = {tt.name.lower(): tt for tt in TargetType.objects.all()}
                                
                                if new_drones:
                                    Drone.objects.bulk_create(new_drones.values(), ignore_conflicts=True)
                                    # Перезагружаем кэш из базы для получения актуальных нормализованных значений
                                    # Создаем кэш дронов с ключом без дефисов для группировки X-51 и X51
                                    drones_cache = {get_drone_comparison_key(drone.name): drone for drone in Drone.objects.all()}
                                    new_drones.clear()
                                
                                if new_explosive_types:
                                    ExplosiveType.objects.bulk_create(new_explosive_types.values(), ignore_conflicts=True)
                                    for et in new_explosive_types.values():
                                        explosive_types_cache[et.name.lower()] = et
                                
                                if new_explosive_devices:
                                    ExplosiveDevice.objects.bulk_create(new_explosive_devices.values(), ignore_conflicts=True)
                                    for ed in new_explosive_devices.values():
                                        explosive_devices_cache[ed.name.lower()] = ed
                                
                                if flights_to_create:
                                    logger.info(f"Сохранение последнего батча: {len(flights_to_create)} записей для создания")
                                    # Разбиваем на меньшие батчи для избежания нехватки памяти
                                    batch_size = 50
                                    total_created_in_final = 0
                                    total_failed_in_final = 0
                                    for i in range(0, len(flights_to_create), batch_size):
                                        batch = flights_to_create[i:i + batch_size]
                                        try:
                                            created_objects = Flight.objects.bulk_create(batch, ignore_conflicts=True)
                                            # bulk_create с ignore_conflicts=True возвращает ТОЛЬКО созданные объекты
                                            created_count_in_sub_batch = len(created_objects) if created_objects else 0
                                            total_created_in_final += created_count_in_sub_batch
                                            
                                            # Если создано меньше, чем в батче - значит были конфликты
                                            if created_count_in_sub_batch < len(batch):
                                                failed_count = len(batch) - created_count_in_sub_batch
                                                total_failed_in_final += failed_count
                                                # Пробуем создать по одной записи для тех, что не создались
                                                for flight in batch:
                                                    # Проверяем, был ли создан этот полет (проверяем по всем ключевым полям)
                                                    existing = Flight.objects.filter(
                                                        number=flight.number,
                                                        pilot=flight.pilot,
                                                        flight_date=flight.flight_date,
                                                        flight_time=flight.flight_time
                                                    ).first()
                                                    
                                                    if not existing:
                                                        try:
                                                            flight.save()
                                                            total_created_in_final += 1
                                                            total_failed_in_final -= 1
                                                            if total_failed_in_final <= 5:
                                                                logger.info(f"Успешно создан полет {flight.number} для пилота {flight.pilot.callname} при повторной попытке (финальный батч)")
                                                        except Exception as single_error:
                                                            if total_failed_in_final <= 10:
                                                                logger.warning(f"Не удалось создать полет {flight.number} для пилота {flight.pilot.callname}: {single_error}")
                                                    else:
                                                        # Запись уже существует - это нормально, просто не считаем как ошибку
                                                        total_failed_in_final -= 1
                                                        if total_failed_in_final <= 5:
                                                            logger.debug(f"Полет {flight.number} для пилота {flight.pilot.callname} уже существует в БД (финальный батч)")
                                        except Exception as batch_create_error:
                                            logger.error(f"Ошибка при bulk_create финального батча {i//batch_size + 1}: {batch_create_error}", exc_info=True)
                                            # Пробуем создать по одной записи
                                            for flight in batch:
                                                try:
                                                    flight.save()
                                                    total_created_in_final += 1
                                                except Exception as single_error:
                                                    total_failed_in_final += 1
                                                    if total_failed_in_final <= 10:
                                                        logger.warning(f"Не удалось создать полет {flight.number} для пилота {flight.pilot.callname}: {single_error}")
                                    
                                    created_count += total_created_in_final
                                    if total_created_in_final != len(flights_to_create):
                                        logger.warning(f"Создано {total_created_in_final} из {len(flights_to_create)} записей в финальном батче. Не создано: {total_failed_in_final}")
                                        self.message_user(request,
                                                          _(f"⚠️ В финальном батче создано {total_created_in_final} из {len(flights_to_create)} записей. Не создано: {total_failed_in_final}"),
                                                          level=messages.WARNING)
                                    
                                    # Координаты — один раз после завершения файла (см. process_coordinates_background ниже)
                                    
                                    # База очищена, поэтому не нужно обновлять existing_flights_set
                                    
                                    # Явная очистка памяти после финального батча
                                    import gc
                                    gc.collect()
                                    
                                    # Сохраняем прогресс импорта после финального батча
                                    if import_progress:
                                        try:
                                            import_progress.last_processed_row = data_start_row + processed_row_count - 1
                                            import_progress.total_created = created_count
                                            import_progress.save(update_fields=['last_processed_row', 'total_created', 'last_import_date'])
                                            logger.info(f"Прогресс импорта сохранен после финального батча: строка {import_progress.last_processed_row}, создано {created_count}")
                                        except Exception as progress_error:
                                            logger.warning(f"Ошибка сохранения прогресса импорта: {progress_error}")
                                
                                if flights_to_create:
                                    self.message_user(request,
                                                      _(f"💾 Сохранен последний батч: {len(flights_to_create)} создано"),
                                                      level=messages.INFO)
                        except Exception as final_error:
                            error_msg = f"Ошибка при сохранении финального батча: {str(final_error)}"
                            error_messages.append(error_msg)
                            logger.error(f"Ошибка при сохранении финального батча: {final_error}", exc_info=True)
                            self.message_user(request,
                                              _(f"⚠️ Ошибка при сохранении последнего батча ({len(flights_to_create)} создано): {str(final_error)}"),
                                              level=messages.ERROR)

                    if error_messages:
                        for msg in error_messages[:5]:  # Покажем только первые 5 ошибок из этого файла
                            self.message_user(request, msg, level=messages.WARNING)
                        if len(error_messages) > 5:
                            self.message_user(request,
                                              f"... и ещё {len(error_messages) - 5} ошибок в файле '{source.name}'.",
                                              level=messages.WARNING)

                    total_created += created_count
                    total_errors.extend(error_messages)

                    # Формируем итоговое сообщение с детальной статистикой
                    total_processed = created_count
                    total_skipped = skipped_no_flight_number + skipped_errors + skipped_no_date + skipped_no_pilot
                    summary_message = f"Импорт из файла '{source.name}' завершен:\n"
                    summary_message += f"  - Создано записей: {created_count}\n"
                    if updated_result_raw:
                        summary_message += f"  - Обновлён «Результат применения» у существующих вылетов: {updated_result_raw}\n"
                    summary_message += f"  - Успешно обработано строк: {processed_successfully}\n"
                    summary_message += f"  - Обработано строк из файла: {processed_row_count} из {total_rows_to_process} (до строки {data_start_row + processed_row_count - 1})\n"
                    if empty_rows_count >= MAX_EMPTY_ROWS:
                        summary_message += f"  - ⚠️ Импорт остановлен на строке {data_start_row + processed_row_count - 1} из-за {empty_rows_count} пустых строк подряд\n"
                    elif processed_row_count >= total_rows_to_process:
                        summary_message += f"  - ✓ Обработан весь файл до строки {data_end_row}\n"
                    if total_skipped > 0:
                        summary_message += f"  - Пропущено строк без номера вылета: {skipped_no_flight_number}\n"
                        if skipped_no_date > 0:
                            summary_message += f"  - Пропущено строк без даты: {skipped_no_date}\n"
                        if skipped_no_pilot > 0:
                            summary_message += f"  - Пропущено строк без пилота: {skipped_no_pilot}\n"
                        if skipped_errors > 0:
                            summary_message += f"  - Пропущено строк из-за ошибок: {skipped_errors}\n"
                        summary_message += f"  - Всего пропущено: {total_skipped}"
                    
                    self.message_user(
                        request,
                        _(summary_message),
                        level=messages.SUCCESS
                    )
                    
                    # Обновляем прогресс импорта - помечаем как завершенный, если файл обработан полностью
                    if import_progress:
                        try:
                            final_row = data_start_row + processed_row_count - 1
                            is_completed = (processed_row_count >= total_rows_to_process) or (empty_rows_count >= MAX_EMPTY_ROWS)
                            import_progress.last_processed_row = final_row
                            import_progress.total_created = created_count
                            import_progress.is_completed = is_completed
                            import_progress.save(update_fields=['last_processed_row', 'total_created', 'is_completed', 'last_import_date'])
                            if is_completed:
                                logger.info(f"Импорт файла '{source.name}' завершен полностью (строка {final_row}, создано {created_count})")
                                
                                # Асинхронная обработка координат после завершения импорта (в фоновом потоке)
                                import threading
                                def process_coordinates_background():
                                    """Фоновая функция для обработки координат после импорта"""
                                    try:
                                        logger.info("Начинается фоновая обработка координат после импорта...")
                                        flights_without_coords = Flight.objects.filter(
                                            coordinates__isnull=False
                                        ).exclude(
                                            coordinates=''
                                        ).filter(
                                            lat_wgs84__isnull=True
                                        )
                                        
                                        total_to_convert = flights_without_coords.count()
                                        if total_to_convert > 0:
                                            logger.info(f"Найдено {total_to_convert} полетов для обработки координат")
                                            
                                            def progress_callback(processed, total):
                                                if processed % 1000 == 0 or processed == total:
                                                    logger.info(f"Обработано координат: {processed}/{total}")
                                            
                                            success_count, error_count = Flight.batch_process_coordinates(
                                                queryset=flights_without_coords,
                                                batch_size=500,
                                                update_callback=progress_callback
                                            )
                                            
                                            logger.info(f"Обработка координат завершена: успешно {success_count}, ошибок {error_count}")
                                    except Exception as bg_error:
                                        logger.error(f"Ошибка в фоновой обработке координат после импорта: {bg_error}", exc_info=True)
                                
                                # Запускаем обработку в фоновом потоке
                                thread = threading.Thread(target=process_coordinates_background, daemon=True)
                                thread.start()
                                logger.info("Запущена фоновая задача обработки координат после импорта")
                                
                                self.message_user(request,
                                                  _(f"✓ Прогресс импорта сохранен. Файл обработан полностью. Координаты обрабатываются в фоновом режиме."),
                                                  level=messages.SUCCESS)
                            else:
                                logger.info(f"Импорт файла '{source.name}' приостановлен (строка {final_row}, создано {created_count}). Можно продолжить при следующей загрузке.")
                                self.message_user(request,
                                                  _(f"📌 Прогресс импорта сохранен. При следующей загрузке файла импорт продолжится с строки {final_row + 1}."),
                                                  level=messages.INFO)
                        except Exception as progress_error:
                            logger.warning(f"Ошибка сохранения финального прогресса импорта: {progress_error}")
                    
                    # Закрываем workbook и очищаем память после обработки файла
                    if 'wb' in locals():
                        wb.close()
                        del wb
                    if 'ws' in locals():
                        del ws
                    import gc
                    gc.collect()
                    logger.info(f"Память очищена после обработки файла '{source.name}'")

                except Exception as e:
                    import traceback
                    error_traceback = traceback.format_exc()
                    logger.error(f"Критическая ошибка при импорте из файла '{source.name}': {str(e)}\n{error_traceback}")
                    
                    # Сохраняем прогресс даже при критической ошибке
                    if import_progress and 'processed_row_count' in locals():
                        try:
                            final_row = data_start_row + processed_row_count - 1
                            import_progress.last_processed_row = final_row
                            import_progress.total_created = created_count if 'created_count' in locals() else 0
                            import_progress.is_completed = False
                            import_progress.save(update_fields=['last_processed_row', 'total_created', 'is_completed', 'last_import_date'])
                            logger.info(f"Прогресс импорта сохранен после ошибки: строка {final_row}, создано {import_progress.total_created}")
                            self.message_user(request,
                                              _(f"⚠️ Импорт прерван из-за ошибки. Прогресс сохранен (строка {final_row}, создано {import_progress.total_created}). Загрузите файл снова, чтобы продолжить."),
                                              level=messages.WARNING)
                        except Exception as progress_error:
                            logger.warning(f"Не удалось сохранить прогресс при ошибке: {progress_error}")
                    
                    self.message_user(request,
                                      _(f"Критическая ошибка при импорте из файла '{source.name}': {str(e)}"),
                                      level=messages.ERROR)
                    # Закрываем workbook и очищаем память даже при ошибке
                    if 'wb' in locals():
                        try:
                            wb.close()
                        except:
                            pass
                        del wb
                    if 'ws' in locals():
                        del ws
                    import gc
                    gc.collect()

        final_message = f"Импорт всех файлов завершен. Всего: {total_created} создано."
        if total_errors:
            final_message += f" Всего ошибок: {len(total_errors)}."

        message_level = messages.SUCCESS if not total_errors else messages.WARNING
        self.message_user(request, _(final_message), level=message_level)
        
        # Очищаем кэш для API карты после импорта
        from django.core.cache import cache
        try:
            # Очищаем все ключи кэша, начинающиеся с 'flights_total:'
            # Используем delete_pattern если доступен (django-redis)
            if hasattr(cache, 'delete_pattern'):
                cache.delete_pattern('rubicon:flights_total:*')
            else:
                # Альтернативный способ - очистить весь кэш
                cache.clear()
            logger.info("Кэш для API карты очищен после импорта")
        except Exception as cache_error:
            logger.warning(f"Не удалось очистить кэш: {cache_error}")

        return HttpResponseRedirect("../")

    def clear_database_view(self, request):
        """Очистка всех данных, загруженных из Excel"""
        if request.method == 'POST':
            from django.db import transaction
            try:
                with transaction.atomic():
                    # Подсчитываем количество записей перед удалением
                    flights_count = Flight.objects.count()
                    pilots_count = Pilot.objects.count()
                    drones_count = Drone.objects.count()
                    explosive_types_count = ExplosiveType.objects.count()
                    explosive_devices_count = ExplosiveDevice.objects.count()
                    target_types_count = TargetType.objects.count()
                    corrective_types_count = CorrectiveType.objects.count()
                    direction_types_count = DirectionType.objects.count()
                    import_progress_count = ImportProgress.objects.count()
                    
                    # Удаляем все данные
                    Flight.objects.all().delete()
                    Pilot.objects.all().delete()
                    Drone.objects.all().delete()
                    ExplosiveType.objects.all().delete()
                    ExplosiveDevice.objects.all().delete()
                    TargetType.objects.all().delete()
                    CorrectiveType.objects.all().delete()
                    DirectionType.objects.all().delete()
                    ImportProgress.objects.all().delete()

                self.message_user(
                    request,
                    _(f"✅ База данных очищена! Удалено:\n"
                      f"• Вылеты: {flights_count}\n"
                      f"• Пилоты: {pilots_count}\n"
                      f"• Дроны: {drones_count}\n"
                      f"• Виды БП: {explosive_types_count}\n"
                      f"• Виды взрывателя: {explosive_devices_count}\n"
                      f"• Типы целей: {target_types_count}\n"
                      f"• Типы корректировок: {corrective_types_count}\n"
                      f"• Типы направлений: {direction_types_count}\n"
                      f"• Прогресс импорта: {import_progress_count}"),
                    level=messages.SUCCESS
                )
                logger.info(f"База данных очищена пользователем {request.user.username}")
            except Exception as e:
                logger.error(f"Ошибка при очистке базы данных: {e}", exc_info=True)
                self.message_user(
                    request,
                    _(f"❌ Ошибка при очистке базы данных: {str(e)}"),
                    level=messages.ERROR
                )
            
            return HttpResponseRedirect("../")
        
        # GET запрос - показываем страницу подтверждения
        context = {
            **self.admin_site.each_context(request),
            'title': _('Очистка базы данных'),
            'opts': self.model._meta,
            'has_view_permission': self.has_view_permission(request),
            'flights_count': Flight.objects.count(),
            'pilots_count': Pilot.objects.count(),
            'drones_count': Drone.objects.count(),
            'explosive_types_count': ExplosiveType.objects.count(),
            'explosive_devices_count': ExplosiveDevice.objects.count(),
        }
        return render(request, "admin/clear_database.html", context)


from flights import admin_operators  # noqa: F401, E402

