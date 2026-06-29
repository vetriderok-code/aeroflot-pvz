from django import forms
from django.utils.translation import gettext_lazy as _

from flights.models import Drone, OperatorCommLink, OperatorLocation, OperatorPlacementZone, OperatorProfile, Pilot
from flights.utils.operator_dashboard import normalize_comm_links


PILOT_QUERYSET = Pilot.objects.order_by('callname')
DRONE_QUERYSET = Drone.objects.order_by('name')
LOCATION_QUERYSET = OperatorLocation.objects.filter(is_active=True).select_related('senior').order_by('sort_order', 'name')
DETACHMENT_DESTINATION_LABEL = _('Куда перемещаем?')
DETACHMENT_DESTINATION_REQUIRED = _('Укажите, куда перемещаем.')


def detachment_dest_post_key(profile_id) -> str:
    return f'detachment_dest_{profile_id}'


def _patch_changelist_post_data(data, instance, prefix=''):
    """Подставляет значения из БД, если поле не пришло в POST (Jazzmin / узкий экран)."""
    if data is None or not getattr(instance, 'pk', None) or not hasattr(data, 'copy'):
        return data
    patched = data.copy()
    if hasattr(patched, '_mutable'):
        patched._mutable = True
    pfx = f'{prefix}-' if prefix else ''
    if f'{pfx}location' not in patched:
        patched[f'{pfx}location'] = str(instance.location_id) if instance.location_id else ''
    if f'{pfx}placement_zone' not in patched:
        patched[f'{pfx}placement_zone'] = instance.placement_zone
    return patched


def _configure_notes_field(form: forms.ModelForm) -> None:
    if 'notes' not in form.fields:
        return
    zone = None
    if form.data:
        prefix = form.prefix + '-' if form.prefix else ''
        zone = form.data.get(f'{prefix}placement_zone')
    if zone is None and form.instance and form.instance.pk:
        zone = form.instance.placement_zone
    if zone == OperatorPlacementZone.DETACHMENT:
        form.fields['notes'].label = DETACHMENT_DESTINATION_LABEL


def _resolve_drone_by_name(name: str | None) -> Drone | None:
    value = (name or '').strip()
    if not value:
        return None
    return DRONE_QUERYSET.filter(name=value).first()


class OperatorLocationAdminForm(forms.ModelForm):
    comm_links = forms.MultipleChoiceField(
        label=_('Связь'),
        choices=OperatorCommLink.choices,
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = OperatorLocation
        fields = ('name', 'senior', 'description', 'sort_order', 'is_active')
        widgets = {
            'senior': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'senior' in self.fields:
            self.fields['senior'].queryset = PILOT_QUERYSET
            self.fields['senior'].label_from_instance = lambda obj: obj.callname
            self.fields['senior'].required = False
            self.fields['senior'].empty_label = _('— не назначен —')
        if self.instance and self.instance.pk and 'comm_links' in self.fields:
            self.initial['comm_links'] = normalize_comm_links(self.instance.comm_links)

    def save(self, commit=True):
        obj = super().save(commit=False)
        if 'comm_links' in self.cleaned_data:
            obj.comm_links = normalize_comm_links(self.cleaned_data.get('comm_links'))
        if commit:
            obj.save()
        return obj


class CommanderOperatorLocationAdminForm(forms.ModelForm):
    """Командир может менять название и связь точки."""

    comm_links = forms.MultipleChoiceField(
        label=_('Связь'),
        choices=OperatorCommLink.choices,
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = OperatorLocation
        fields = ('name',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.initial['comm_links'] = normalize_comm_links(self.instance.comm_links)

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.comm_links = normalize_comm_links(self.cleaned_data.get('comm_links'))
        if commit:
            obj.save()
        return obj


class OperatorProfileInlineForm(forms.ModelForm):
    """Дежурство — редактируется в карточке пилота, без повторного выбора пилота."""

    class Meta:
        model = OperatorProfile
        exclude = ('pilot',)
        widgets = {
            'location': forms.Select(attrs={'class': 'form-control'}),
            'placement_zone': forms.Select(attrs={'class': 'form-control'}),
            'senior': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['location'].queryset = LOCATION_QUERYSET
        self.fields['location'].required = False
        self.fields['location'].empty_label = _('— не указано —')
        if 'senior' in self.fields:
            self.fields['senior'].queryset = PILOT_QUERYSET
            self.fields['senior'].label_from_instance = lambda obj: obj.callname
            self.fields['senior'].required = False
            self.fields['senior'].empty_label = _('— не назначен —')
        self.fields['notes'].required = False
        _configure_notes_field(self)

    def clean(self):
        cleaned = super().clean()
        location = cleaned.get('location')
        pilot = self.instance.pilot if self.instance and self.instance.pilot_id else None
        if pilot and location and location.senior_id and pilot.pk == location.senior_id:
            self.add_error('location', _('Пилот не может быть на точке, где он сам старший.'))
        return cleaned

    def save(self, commit=True):
        profile = super().save(commit=False)
        if commit:
            profile.save()
            self.save_m2m()
        return profile


class OperatorProfileAdminForm(OperatorProfileInlineForm):
    """Карточка оператора — пилот только для просмотра."""


class OperatorProfileChangeListForm(forms.ModelForm):
    """Быстрое редактирование: расположение и зона. «Куда» — через prompt при отрыве."""

    class Meta:
        model = OperatorProfile
        fields = ('location', 'placement_zone')

    def __init__(self, *args, **kwargs):
        instance = kwargs.get('instance')
        prefix = kwargs.get('prefix', '')
        data = kwargs.get('data')
        if data is None and args:
            data = args[0]

        if data is not None and prefix:
            pk_val = data.get(f'{prefix}-id')
            if pk_val:
                db_instance = (
                    OperatorProfile.objects
                    .select_related('pilot', 'location')
                    .filter(pk=pk_val)
                    .first()
                )
                if db_instance:
                    kwargs['instance'] = db_instance
                    instance = db_instance

        if data is not None and instance and instance.pk:
            patched = _patch_changelist_post_data(data, instance, prefix)
            if 'data' in kwargs:
                kwargs['data'] = patched
            elif args:
                args = (patched, *args[1:])
        super().__init__(*args, **kwargs)
        self.fields['location'].queryset = LOCATION_QUERYSET
        self.fields['location'].required = False
        self.fields['location'].empty_label = _('— не указано —')
        self.fields['placement_zone'].required = False

    def clean(self):
        cleaned = super().clean()
        if not self.instance.pk:
            return cleaned
        if not (cleaned.get('placement_zone') or '').strip():
            cleaned['placement_zone'] = self.instance.placement_zone
        if cleaned.get('location') is None and self.instance.location_id:
            cleaned['location'] = self.instance.location
        new_zone = cleaned.get('placement_zone')
        if (
            new_zone == OperatorPlacementZone.DETACHMENT
            and self.instance.placement_zone != OperatorPlacementZone.DETACHMENT
            and self.data
        ):
            destination = (self.data.get(detachment_dest_post_key(self.instance.pk)) or '').strip()
            if destination:
                self.instance.notes = destination
        return cleaned


class PilotAdminForm(forms.ModelForm):
    drone_model = forms.ModelChoiceField(
        label=_('Модель дрона'),
        queryset=DRONE_QUERYSET,
        required=False,
        empty_label=_('— не указана —'),
    )

    class Meta:
        model = Pilot
        fields = (
            'callname',
            'tg_id',
            'driver_callname',
            'engineer_callname',
            'drone_model',
            'video_type',
            'manual_type',
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'tg_id' in self.fields:
            self.fields['tg_id'].required = False
            self.fields['tg_id'].help_text = _('Необязательно. Нужен для Telegram-бота и входа по коду.')
        if self.instance and self.instance.pk:
            self.fields['drone_model'].initial = _resolve_drone_by_name(self.instance.drone_type)

    def clean_tg_id(self):
        value = self.cleaned_data.get('tg_id')
        if value in (None, ''):
            return None
        return value

    def save(self, commit=True):
        pilot = super().save(commit=False)
        drone = self.cleaned_data.get('drone_model')
        pilot.drone_type = drone.name if drone else None
        if commit:
            pilot.save()
            self.save_m2m()
        return pilot
