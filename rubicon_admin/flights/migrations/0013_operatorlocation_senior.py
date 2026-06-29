import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0012_operator_location'),
    ]

    operations = [
        migrations.AddField(
            model_name='operatorlocation',
            name='senior',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='operator_locations_led',
                to='flights.pilot',
                verbose_name='Старший (ответственный)',
            ),
        ),
    ]
