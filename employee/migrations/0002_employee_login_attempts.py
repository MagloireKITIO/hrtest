# Generated by Django 4.2.7 on 2024-11-28 15:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('employee', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='employee',
            name='login_attempts',
            field=models.IntegerField(default=0),
        ),
    ]
