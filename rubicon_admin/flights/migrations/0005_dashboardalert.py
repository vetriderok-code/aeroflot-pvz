import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0004_liveflight'),
    ]

    operations = [
        migrations.CreateModel(
            name='DashboardAlert',
            fields=[
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('chat_id', models.BigIntegerField(verbose_name='chat id')),
                ('message_thread_id', models.BigIntegerField(blank=True, null=True, verbose_name='topic id')),
                ('telegram_message_id', models.BigIntegerField(verbose_name='telegram message id')),
                ('text', models.TextField(verbose_name='text')),
                ('posted_at', models.DateTimeField(db_index=True, verbose_name='posted at')),
            ],
            options={
                'verbose_name': 'dashboard alert',
                'verbose_name_plural': 'dashboard alerts',
                'db_table': 'public"."dashboard_alert',
                'ordering': ('-posted_at',),
            },
        ),
        migrations.AddConstraint(
            model_name='dashboardalert',
            constraint=models.UniqueConstraint(
                fields=('chat_id', 'telegram_message_id'),
                name='dashboard_alert_chat_message_uniq',
            ),
        ),
    ]
