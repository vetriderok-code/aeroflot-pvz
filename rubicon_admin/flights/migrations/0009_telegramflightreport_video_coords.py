from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0008_maplayer'),
    ]

    operations = [
        migrations.AddField(
            model_name='telegramflightreport',
            name='coordinates_sk42',
            field=models.CharField(blank=True, max_length=64, verbose_name='coordinates sk42'),
        ),
        migrations.AddField(
            model_name='telegramflightreport',
            name='lat_wgs84',
            field=models.FloatField(blank=True, db_index=True, null=True, verbose_name='latitude wgs84'),
        ),
        migrations.AddField(
            model_name='telegramflightreport',
            name='lon_wgs84',
            field=models.FloatField(blank=True, db_index=True, null=True, verbose_name='longitude wgs84'),
        ),
        migrations.AddField(
            model_name='telegramflightreport',
            name='local_video_path',
            field=models.CharField(blank=True, max_length=512, verbose_name='local video path'),
        ),
        migrations.AddField(
            model_name='telegramflightreport',
            name='target_type',
            field=models.CharField(blank=True, max_length=255, verbose_name='target type'),
        ),
        migrations.AddField(
            model_name='telegramflightreport',
            name='telegram_file_id',
            field=models.CharField(blank=True, max_length=255, verbose_name='telegram file id'),
        ),
        migrations.AddField(
            model_name='telegramflightreport',
            name='video_downloaded_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='video downloaded at'),
        ),
        migrations.AddField(
            model_name='telegramflightreport',
            name='video_duration',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name='video duration sec'),
        ),
        migrations.AddField(
            model_name='telegramflightreport',
            name='video_mime',
            field=models.CharField(blank=True, max_length=127, verbose_name='video mime'),
        ),
        migrations.AddField(
            model_name='telegramflightreport',
            name='video_size',
            field=models.PositiveBigIntegerField(blank=True, null=True, verbose_name='video size'),
        ),
    ]
