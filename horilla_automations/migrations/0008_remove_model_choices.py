# horilla_automations/migrations/0008_remove_model_choices.py
# Generated manually to fix MODEL_CHOICES issue

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('horilla_automations', '0007_alter_mailautomation_is_active_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='mailautomation',
            name='model',
            field=models.CharField(
                max_length=100,
                help_text="Model path (e.g., 'employee.models.Employee')"
            ),
        ),
    ]