# Generated by Django 5.0.3 on 2024-03-26 09:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Mpapp', '0006_playlist_status'),
    ]

    operations = [
        migrations.AlterField(
            model_name='playlist',
            name='name',
            field=models.CharField(blank=True, default='Default Name', max_length=100),
        ),
    ]
