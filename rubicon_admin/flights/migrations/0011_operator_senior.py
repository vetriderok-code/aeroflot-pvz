import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0010_operator_profile'),
    ]

    operations = [
        migrations.AddField(
            model_name='operatorprofile',
            name='senior',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='operator_team_members',
                to='flights.pilot',
                verbose_name='старший (ответственный)',
            ),
        ),
        migrations.AlterField(
            model_name='operatorpositionlog',
            name='lat',
            field=models.FloatField(blank=True, null=True, verbose_name='latitude wgs84'),
        ),
        migrations.AlterField(
            model_name='operatorpositionlog',
            name='lon',
            field=models.FloatField(blank=True, null=True, verbose_name='longitude wgs84'),
        ),
        migrations.AlterModelOptions(
            name='operatorprofile',
            options={
                'ordering': ('senior__callname', 'pilot__callname'),
                'verbose_name': 'оператор (дежурство)',
                'verbose_name_plural': 'операторы (дежурство)',
            },
        ),
    ]
