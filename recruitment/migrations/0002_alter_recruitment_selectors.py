# Generated by Django 4.2.7 on 2024-12-01 17:29

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('employee', '0003_remove_employee_login_attempts'),
        ('recruitment', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='recruitment',
            name='selectors',
            field=models.ManyToManyField(blank=True, help_text='Only these selectors can view and manage this recruitment if they are marked as selectors', limit_choices_to={'is_selector': True}, related_name='recruitment_selections', to='employee.employee', verbose_name='Selectors'),
        ),
    ]
