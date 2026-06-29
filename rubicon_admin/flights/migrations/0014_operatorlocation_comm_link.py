from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0013_operatorlocation_senior'),
    ]

    operations = [
        migrations.AddField(
            model_name='operatorlocation',
            name='comm_link',
            field=models.CharField(
                blank=True,
                choices=[
                    ('starlink', 'StarLink'),
                    ('bshpd', 'БШПД'),
                    ('optics', 'Оптика'),
                    ('lte', 'LTE'),
                    ('sks', 'СКС'),
                    ('rj45', 'RJ45'),
                    ('p274m', 'П-274М'),
                ],
                default='',
                max_length=16,
                verbose_name='Связь',
            ),
        ),
    ]
