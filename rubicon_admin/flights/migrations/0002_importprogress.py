# Generated manually for ImportProgress model

import uuid
from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ImportProgress',
            fields=[
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('file_name', models.CharField(db_index=True, max_length=255, verbose_name='file_name')),
                ('file_size', models.BigIntegerField(help_text='Размер файла в байтах', verbose_name='file_size')),
                ('file_hash', models.CharField(db_index=True, help_text='MD5 hash файла для идентификации', max_length=64, verbose_name='file_hash')),
                ('last_processed_row', models.IntegerField(default=0, help_text='Последняя обработанная строка', verbose_name='last_processed_row')),
                ('total_rows', models.IntegerField(default=0, help_text='Общее количество строк в файле', verbose_name='total_rows')),
                ('total_created', models.IntegerField(default=0, help_text='Всего создано записей', verbose_name='total_created')),
                ('is_completed', models.BooleanField(default=False, help_text='Импорт завершен', verbose_name='is_completed')),
                ('last_import_date', models.DateTimeField(auto_now=True, help_text='Дата последнего импорта', verbose_name='last_import_date')),
            ],
            options={
                'verbose_name': 'import_progress',
                'verbose_name_plural': 'import_progresses',
                'db_table': 'import_progress',
                'ordering': ['-last_import_date'],
            },
        ),
        migrations.AlterUniqueTogether(
            name='importprogress',
            unique_together={('file_name', 'file_hash')},
        ),
    ]










