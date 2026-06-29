import uuid

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0009_telegramflightreport_video_coords'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='OperatorProfile',
            fields=[
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('is_active', models.BooleanField(db_index=True, default=True, verbose_name='is active')),
                ('placement_zone', models.CharField(
                    choices=[('day', 'Day shift'), ('night', 'Night shift'), ('detachment', 'Detachment')],
                    db_index=True,
                    default='day',
                    max_length=16,
                    verbose_name='placement zone',
                )),
                ('day_shift_start', models.TimeField(blank=True, null=True, verbose_name='day shift start')),
                ('day_shift_end', models.TimeField(blank=True, null=True, verbose_name='day shift end')),
                ('night_shift_start', models.TimeField(blank=True, null=True, verbose_name='night shift start')),
                ('night_shift_end', models.TimeField(blank=True, null=True, verbose_name='night shift end')),
                ('duty_started_at', models.DateTimeField(blank=True, null=True, verbose_name='duty started at')),
                ('lat', models.FloatField(blank=True, null=True, verbose_name='latitude wgs84')),
                ('lon', models.FloatField(blank=True, null=True, verbose_name='longitude wgs84')),
                ('location_label', models.CharField(blank=True, max_length=255, verbose_name='location label')),
                ('notes', models.TextField(blank=True, verbose_name='notes')),
                ('pilot', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='operator_profile',
                    to='flights.pilot',
                    verbose_name='pilot',
                )),
            ],
            options={
                'verbose_name': 'operator profile',
                'verbose_name_plural': 'operator profiles',
                'db_table': 'public"."operator_profile',
                'ordering': ('pilot__callname',),
            },
        ),
        migrations.CreateModel(
            name='OperatorPositionLog',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('placement_zone', models.CharField(
                    choices=[('day', 'Day shift'), ('night', 'Night shift'), ('detachment', 'Detachment')],
                    max_length=16,
                    verbose_name='placement zone',
                )),
                ('lat', models.FloatField(verbose_name='latitude wgs84')),
                ('lon', models.FloatField(verbose_name='longitude wgs84')),
                ('location_label', models.CharField(blank=True, max_length=255, verbose_name='location label')),
                ('recorded_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name='recorded at')),
                ('comment', models.CharField(blank=True, max_length=512, verbose_name='comment')),
                ('profile', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='position_logs',
                    to='flights.operatorprofile',
                    verbose_name='operator profile',
                )),
                ('recorded_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='operator_position_logs',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='recorded by',
                )),
            ],
            options={
                'verbose_name': 'operator position log',
                'verbose_name_plural': 'operator position logs',
                'db_table': 'public"."operator_position_log',
                'ordering': ('-recorded_at',),
            },
        ),
    ]
