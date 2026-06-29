from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0002_importprogress'),
    ]

    operations = [
        migrations.AddField(
            model_name='flight',
            name='result_raw',
            field=models.CharField(
                blank=True,
                help_text='Исходный текст результата из сводной Excel',
                max_length=127,
                null=True,
                verbose_name='result raw',
            ),
        ),
    ]
