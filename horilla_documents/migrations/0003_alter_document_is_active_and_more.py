# Generated by Django 5.1.6 on 2025-02-20 13:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('horilla_documents', '0002_alter_document_created_by_alter_document_is_active_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='document',
            name='is_active',
            field=models.BooleanField(default=True, verbose_name='Est actif'),
        ),
        migrations.AlterField(
            model_name='documentrequest',
            name='is_active',
            field=models.BooleanField(default=True, verbose_name='Est actif'),
        ),
    ]
