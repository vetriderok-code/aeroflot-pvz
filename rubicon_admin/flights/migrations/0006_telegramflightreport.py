import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0005_dashboardalert'),
    ]

    operations = [
        migrations.CreateModel(
            name='TelegramFlightReport',
            fields=[
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('chat_id', models.BigIntegerField(db_index=True, verbose_name='chat id')),
                ('message_thread_id', models.BigIntegerField(blank=True, db_index=True, null=True, verbose_name='topic id')),
                ('telegram_message_id', models.BigIntegerField(verbose_name='telegram message id')),
                ('flight_number', models.IntegerField(default=0, verbose_name='flight number')),
                ('work_date', models.CharField(blank=True, max_length=32, verbose_name='work date')),
                ('result', models.CharField(blank=True, max_length=512, verbose_name='result')),
                ('pilot_callsign', models.CharField(blank=True, max_length=255, verbose_name='pilot callsign')),
                ('is_successful', models.BooleanField(db_index=True, default=False, verbose_name='is successful')),
                ('parse_ok', models.BooleanField(default=True, verbose_name='parse ok')),
                ('sent_at', models.DateTimeField(db_index=True, verbose_name='sent at')),
                ('raw_text', models.TextField(blank=True, verbose_name='raw text')),
            ],
            options={
                'verbose_name': 'telegram flight report',
                'verbose_name_plural': 'telegram flight reports',
                'db_table': 'public"."telegram_flight_report',
                'ordering': ('-sent_at',),
            },
        ),
        migrations.AddConstraint(
            model_name='telegramflightreport',
            constraint=models.UniqueConstraint(
                fields=('chat_id', 'telegram_message_id'),
                name='telegram_flight_report_chat_msg_uniq',
            ),
        ),
    ]
