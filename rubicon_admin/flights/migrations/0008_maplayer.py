from django.db import migrations, models
import django.core.validators
import flights.models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0007_pilot_tg_id_nullable'),
    ]

    operations = [
        migrations.CreateModel(
            name='MapLayer',
            fields=[
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255, verbose_name='name')),
                ('description', models.TextField(blank=True, verbose_name='description')),
                ('source_file', models.FileField(help_text='LDK, KML, KMZ, GPX или GeoJSON', upload_to=flights.models.map_layer_upload_to, verbose_name='source file')),
                ('file_format', models.CharField(blank=True, max_length=16, verbose_name='file format')),
                ('geojson', models.JSONField(blank=True, null=True, verbose_name='geojson')),
                ('feature_count', models.PositiveIntegerField(default=0, verbose_name='feature count')),
                ('conversion_error', models.TextField(blank=True, verbose_name='conversion error')),
                ('converted_at', models.DateTimeField(blank=True, null=True, verbose_name='converted at')),
                ('is_active', models.BooleanField(db_index=True, default=True, verbose_name='is active')),
                ('sort_order', models.IntegerField(db_index=True, default=0, verbose_name='sort order')),
                ('color', models.CharField(default='#00BFFF', max_length=7, verbose_name='color')),
                ('stroke_width', models.PositiveSmallIntegerField(default=3, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(12)], verbose_name='stroke width')),
                ('opacity', models.FloatField(default=0.85, validators=[django.core.validators.MinValueValidator(0.1), django.core.validators.MaxValueValidator(1.0)], verbose_name='opacity')),
            ],
            options={
                'verbose_name': 'map layer',
                'verbose_name_plural': 'map layers',
                'db_table': 'map_layer',
                'ordering': ('sort_order', 'name'),
            },
        ),
    ]
