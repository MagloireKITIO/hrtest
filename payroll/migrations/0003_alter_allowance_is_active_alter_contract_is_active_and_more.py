# Generated by Django 5.1.6 on 2025-02-20 13:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payroll', '0002_alter_allowance_created_by_alter_allowance_is_active_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='allowance',
            name='is_active',
            field=models.BooleanField(default=True, verbose_name='Est actif'),
        ),
        migrations.AlterField(
            model_name='contract',
            name='is_active',
            field=models.BooleanField(default=True, verbose_name='Est actif'),
        ),
        migrations.AlterField(
            model_name='deduction',
            name='is_active',
            field=models.BooleanField(default=True, verbose_name='Est actif'),
        ),
        migrations.AlterField(
            model_name='filingstatus',
            name='is_active',
            field=models.BooleanField(default=True, verbose_name='Est actif'),
        ),
        migrations.AlterField(
            model_name='historicalcontract',
            name='is_active',
            field=models.BooleanField(default=True, verbose_name='Est actif'),
        ),
        migrations.AlterField(
            model_name='historicalpayslip',
            name='is_active',
            field=models.BooleanField(default=True, verbose_name='Est actif'),
        ),
        migrations.AlterField(
            model_name='loanaccount',
            name='is_active',
            field=models.BooleanField(default=True, verbose_name='Est actif'),
        ),
        migrations.AlterField(
            model_name='payrollsettings',
            name='is_active',
            field=models.BooleanField(default=True, verbose_name='Est actif'),
        ),
        migrations.AlterField(
            model_name='payslip',
            name='is_active',
            field=models.BooleanField(default=True, verbose_name='Est actif'),
        ),
        migrations.AlterField(
            model_name='reimbursement',
            name='is_active',
            field=models.BooleanField(default=True, verbose_name='Est actif'),
        ),
        migrations.AlterField(
            model_name='reimbursementrequestcomment',
            name='is_active',
            field=models.BooleanField(default=True, verbose_name='Est actif'),
        ),
        migrations.AlterField(
            model_name='taxbracket',
            name='is_active',
            field=models.BooleanField(default=True, verbose_name='Est actif'),
        ),
    ]
