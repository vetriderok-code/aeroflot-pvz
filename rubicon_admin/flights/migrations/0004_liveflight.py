import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0003_flight_result_raw'),
    ]

    operations = [
        migrations.CreateModel(
            name='LiveFlight',
            fields=[
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('telegram_user_id', models.PositiveBigIntegerField(db_index=True, verbose_name='telegram user id')),
                ('chat_id', models.BigIntegerField(verbose_name='chat id')),
                ('started_at', models.DateTimeField(db_index=True, verbose_name='started at')),
                ('ended_at', models.DateTimeField(blank=True, db_index=True, null=True, verbose_name='ended at')),
                (
                    'close_reason',
                    models.CharField(
                        blank=True,
                        choices=[('stop', 'Stop'), ('new_start', 'New start'), ('timeout', 'Timeout')],
                        max_length=16,
                        null=True,
                        verbose_name='close reason',
                    ),
                ),
                ('message_id_start', models.BigIntegerField(blank=True, null=True)),
                ('message_id_stop', models.BigIntegerField(blank=True, null=True)),
                (
                    'pilot',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='live_flights',
                        to='flights.pilot',
                        verbose_name='pilot',
                    ),
                ),
            ],
            options={
                'verbose_name': 'live flight',
                'verbose_name_plural': 'live flights',
                'db_table': 'public"."live_flight',
                'ordering': ('-started_at',),
            },
        ),
    ]
