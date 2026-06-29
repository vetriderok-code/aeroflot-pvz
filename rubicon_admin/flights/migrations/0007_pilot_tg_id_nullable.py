from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0006_telegramflightreport'),
    ]

    operations = [
        migrations.AlterField(
            model_name='pilot',
            name='tg_id',
            field=models.PositiveBigIntegerField(
                blank=True,
                null=True,
                unique=True,
                verbose_name='TG ID',
            ),
        ),
    ]
