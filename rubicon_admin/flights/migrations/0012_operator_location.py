import uuid

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


def migrate_location_labels(apps, schema_editor):
    OperatorProfile = apps.get_model('flights', 'OperatorProfile')
    OperatorLocation = apps.get_model('flights', 'OperatorLocation')
    OperatorPositionLog = apps.get_model('flights', 'OperatorPositionLog')

    cache: dict[str, object] = {}
    for profile in OperatorProfile.objects.exclude(location_label='').iterator():
        label = (profile.location_label or '').strip()
        if not label:
            continue
        if label not in cache:
            cache[label] = OperatorLocation.objects.create(
                name=label,
                sort_order=len(cache),
                is_active=True,
            )
        profile.location_id = cache[label].id
        profile.save(update_fields=['location_id'])

    for log in OperatorPositionLog.objects.exclude(location_label='').iterator():
        label = (log.location_label or '').strip()
        if not label:
            continue
        if label not in cache:
            cache[label] = OperatorLocation.objects.create(
                name=label,
                sort_order=len(cache),
                is_active=True,
            )
        log.location_id = cache[label].id
        log.save(update_fields=['location_id'])


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0011_operator_senior'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='OperatorLocation',
            fields=[
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255, unique=True, verbose_name='Название')),
                ('description', models.TextField(blank=True, verbose_name='Описание')),
                ('sort_order', models.IntegerField(db_index=True, default=0, verbose_name='Порядок сортировки')),
                ('is_active', models.BooleanField(db_index=True, default=True, verbose_name='Активна')),
            ],
            options={
                'verbose_name': 'Расположение',
                'verbose_name_plural': 'Расположения',
                'db_table': 'public"."operator_location',
                'ordering': ('sort_order', 'name'),
            },
        ),
        migrations.AddField(
            model_name='operatorprofile',
            name='location',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='operators',
                to='flights.operatorlocation',
                verbose_name='Расположение',
            ),
        ),
        migrations.AddField(
            model_name='operatorpositionlog',
            name='location',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='position_logs',
                to='flights.operatorlocation',
                verbose_name='Расположение',
            ),
        ),
        migrations.RunPython(migrate_location_labels, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='operatorprofile',
            name='location_label',
        ),
        migrations.RemoveField(
            model_name='operatorprofile',
            name='lat',
        ),
        migrations.RemoveField(
            model_name='operatorprofile',
            name='lon',
        ),
        migrations.RemoveField(
            model_name='operatorpositionlog',
            name='lat',
        ),
        migrations.RemoveField(
            model_name='operatorpositionlog',
            name='lon',
        ),
        migrations.AlterField(
            model_name='operatorprofile',
            name='day_shift_end',
            field=models.TimeField(blank=True, null=True, verbose_name='Конец дневной смены'),
        ),
        migrations.AlterField(
            model_name='operatorprofile',
            name='day_shift_start',
            field=models.TimeField(blank=True, null=True, verbose_name='Начало дневной смены'),
        ),
        migrations.AlterField(
            model_name='operatorprofile',
            name='duty_started_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Начало дежурства'),
        ),
        migrations.AlterField(
            model_name='operatorprofile',
            name='is_active',
            field=models.BooleanField(db_index=True, default=True, verbose_name='Активен'),
        ),
        migrations.AlterField(
            model_name='operatorprofile',
            name='night_shift_end',
            field=models.TimeField(blank=True, null=True, verbose_name='Конец ночной смены'),
        ),
        migrations.AlterField(
            model_name='operatorprofile',
            name='night_shift_start',
            field=models.TimeField(blank=True, null=True, verbose_name='Начало ночной смены'),
        ),
        migrations.AlterField(
            model_name='operatorprofile',
            name='notes',
            field=models.TextField(blank=True, verbose_name='Примечания'),
        ),
        migrations.AlterField(
            model_name='operatorprofile',
            name='pilot',
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='operator_profile',
                to='flights.pilot',
                verbose_name='Пилот',
            ),
        ),
        migrations.AlterField(
            model_name='operatorprofile',
            name='placement_zone',
            field=models.CharField(
                choices=[('day', 'Дневная смена'), ('night', 'Ночная смена'), ('detachment', 'Отрыв')],
                db_index=True,
                default='day',
                max_length=16,
                verbose_name='Зона размещения',
            ),
        ),
        migrations.AlterField(
            model_name='operatorprofile',
            name='senior',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='operator_team_members',
                to='flights.pilot',
                verbose_name='Старший (ответственный)',
            ),
        ),
        migrations.AlterField(
            model_name='operatorpositionlog',
            name='comment',
            field=models.CharField(blank=True, max_length=512, verbose_name='Комментарий'),
        ),
        migrations.AlterField(
            model_name='operatorpositionlog',
            name='location_label',
            field=models.CharField(blank=True, max_length=255, verbose_name='Расположение (текст)'),
        ),
        migrations.AlterField(
            model_name='operatorpositionlog',
            name='placement_zone',
            field=models.CharField(
                choices=[('day', 'Дневная смена'), ('night', 'Ночная смена'), ('detachment', 'Отрыв')],
                max_length=16,
                verbose_name='Зона размещения',
            ),
        ),
        migrations.AlterField(
            model_name='operatorpositionlog',
            name='profile',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='position_logs',
                to='flights.operatorprofile',
                verbose_name='Оператор',
            ),
        ),
        migrations.AlterField(
            model_name='operatorpositionlog',
            name='recorded_at',
            field=models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name='Время записи'),
        ),
        migrations.AlterField(
            model_name='operatorpositionlog',
            name='recorded_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='operator_position_logs',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Кто изменил',
            ),
        ),
    ]
