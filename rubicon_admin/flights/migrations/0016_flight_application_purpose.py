from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0015_operatorlocation_comm_links'),
    ]

    operations = [
        migrations.AddField(
            model_name='flight',
            name='application_purpose',
            field=models.CharField(
                blank=True,
                help_text='Исходный текст «Цель применения» из сводной Excel (колонка N)',
                max_length=127,
                null=True,
                verbose_name='application purpose',
            ),
        ),
    ]
