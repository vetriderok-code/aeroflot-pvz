from django.db import migrations, models


def migrate_comm_link_to_links(apps, schema_editor):
    OperatorLocation = apps.get_model('flights', 'OperatorLocation')
    for location in OperatorLocation.objects.exclude(comm_link='').iterator():
        value = (location.comm_link or '').strip()
        if value:
            location.comm_links = [value]
            location.save(update_fields=['comm_links'])


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0014_operatorlocation_comm_link'),
    ]

    operations = [
        migrations.AddField(
            model_name='operatorlocation',
            name='comm_links',
            field=models.JSONField(blank=True, default=list, verbose_name='Связь'),
        ),
        migrations.RunPython(migrate_comm_link_to_links, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='operatorlocation',
            name='comm_link',
        ),
    ]
