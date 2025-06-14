# Generated by Django 4.2.7 on 2025-01-22 14:41

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0003_alter_announcement_created_by_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('employee', '0005_alter_employee_options_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='actiontype',
            name='created_by',
            field=models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name='Créé par'),
        ),
        migrations.AlterField(
            model_name='actiontype',
            name='is_active',
            field=models.BooleanField(default=True, verbose_name='Actif'),
        ),
        migrations.AlterField(
            model_name='bonuspoint',
            name='created_by',
            field=models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name='Créé par'),
        ),
        migrations.AlterField(
            model_name='bonuspoint',
            name='is_active',
            field=models.BooleanField(default=True, verbose_name='Actif'),
        ),
        migrations.AlterField(
            model_name='disciplinaryaction',
            name='created_by',
            field=models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name='Créé par'),
        ),
        migrations.AlterField(
            model_name='disciplinaryaction',
            name='employee_id',
            field=models.ManyToManyField(to='employee.employee', verbose_name='Employés'),
        ),
        migrations.AlterField(
            model_name='disciplinaryaction',
            name='is_active',
            field=models.BooleanField(default=True, verbose_name='Actif'),
        ),
        migrations.AlterField(
            model_name='disciplinaryaction',
            name='unit_in',
            field=models.CharField(choices=[('days', 'Jours'), ('hours', 'Hours')], default='days', max_length=10),
        ),
        migrations.AlterField(
            model_name='employee',
            name='company_id',
            field=models.ForeignKey(blank=True, help_text='Employee will only see data from this company. Leave blank for all companies access.', null=True, on_delete=django.db.models.deletion.PROTECT, to='base.company', verbose_name='Entreprise'),
        ),
        migrations.AlterField(
            model_name='employee',
            name='employee_first_name',
            field=models.CharField(max_length=200, verbose_name='Prénom'),
        ),
        migrations.AlterField(
            model_name='employee',
            name='employee_last_name',
            field=models.CharField(blank=True, max_length=200, null=True, verbose_name='Nom de famille'),
        ),
        migrations.AlterField(
            model_name='employee',
            name='employee_user_id',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='employee_get', to=settings.AUTH_USER_MODEL, verbose_name='Utilisateur'),
        ),
        migrations.AlterField(
            model_name='employeebankdetails',
            name='created_by',
            field=models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name='Créé par'),
        ),
        migrations.AlterField(
            model_name='employeebankdetails',
            name='employee_id',
            field=models.OneToOneField(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='employee_bank_details', to='employee.employee', verbose_name='Employé'),
        ),
        migrations.AlterField(
            model_name='employeebankdetails',
            name='is_active',
            field=models.BooleanField(default=True, verbose_name='Actif'),
        ),
        migrations.AlterField(
            model_name='employeegeneralsetting',
            name='created_by',
            field=models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name='Créé par'),
        ),
        migrations.AlterField(
            model_name='employeegeneralsetting',
            name='is_active',
            field=models.BooleanField(default=True, verbose_name='Actif'),
        ),
        migrations.AlterField(
            model_name='employeenote',
            name='created_by',
            field=models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name='Créé par'),
        ),
        migrations.AlterField(
            model_name='employeenote',
            name='is_active',
            field=models.BooleanField(default=True, verbose_name='Actif'),
        ),
        migrations.AlterField(
            model_name='employeetag',
            name='created_by',
            field=models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name='Créé par'),
        ),
        migrations.AlterField(
            model_name='employeetag',
            name='is_active',
            field=models.BooleanField(default=True, verbose_name='Actif'),
        ),
        migrations.AlterField(
            model_name='employeetag',
            name='title',
            field=models.CharField(max_length=50, null=True, verbose_name='Titre'),
        ),
        migrations.AlterField(
            model_name='employeeworkinformation',
            name='date_joining',
            field=models.DateField(blank=True, null=True, verbose_name="Date d'inscription"),
        ),
        migrations.AlterField(
            model_name='employeeworkinformation',
            name='department_id',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='base.department', verbose_name='Département'),
        ),
        migrations.AlterField(
            model_name='employeeworkinformation',
            name='employee_id',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='employee_work_info', to='employee.employee', verbose_name='Employé'),
        ),
        migrations.AlterField(
            model_name='employeeworkinformation',
            name='employee_type_id',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='base.employeetype', verbose_name="Type d'employé"),
        ),
        migrations.AlterField(
            model_name='employeeworkinformation',
            name='job_position_id',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='base.jobposition', verbose_name='Poste'),
        ),
        migrations.AlterField(
            model_name='employeeworkinformation',
            name='job_role_id',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='base.jobrole', verbose_name='Rôle du poste'),
        ),
        migrations.AlterField(
            model_name='employeeworkinformation',
            name='location',
            field=models.CharField(blank=True, max_length=50, null=True, verbose_name='Lieu de travail'),
        ),
        migrations.AlterField(
            model_name='employeeworkinformation',
            name='reporting_manager_id',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='reporting_manager', to='employee.employee', verbose_name='Responsable du reporting'),
        ),
        migrations.AlterField(
            model_name='employeeworkinformation',
            name='salary_hour',
            field=models.IntegerField(blank=True, default=0, null=True, verbose_name='Salaire par heure'),
        ),
        migrations.AlterField(
            model_name='employeeworkinformation',
            name='shift_id',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.DO_NOTHING, to='base.employeeshift', verbose_name='Quarts Info'),
        ),
        migrations.AlterField(
            model_name='employeeworkinformation',
            name='work_type_id',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='base.worktype', verbose_name='Type de travail'),
        ),
        migrations.AlterField(
            model_name='historicalbonuspoint',
            name='created_by',
            field=models.ForeignKey(blank=True, db_constraint=False, editable=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='Créé par'),
        ),
        migrations.AlterField(
            model_name='historicalbonuspoint',
            name='is_active',
            field=models.BooleanField(default=True, verbose_name='Actif'),
        ),
        migrations.AlterField(
            model_name='historicalemployeeworkinformation',
            name='date_joining',
            field=models.DateField(blank=True, null=True, verbose_name="Date d'inscription"),
        ),
        migrations.AlterField(
            model_name='historicalemployeeworkinformation',
            name='department_id',
            field=models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='base.department', verbose_name='Département'),
        ),
        migrations.AlterField(
            model_name='historicalemployeeworkinformation',
            name='employee_id',
            field=models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='employee.employee', verbose_name='Employé'),
        ),
        migrations.AlterField(
            model_name='historicalemployeeworkinformation',
            name='employee_type_id',
            field=models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='base.employeetype', verbose_name="Type d'employé"),
        ),
        migrations.AlterField(
            model_name='historicalemployeeworkinformation',
            name='job_position_id',
            field=models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='base.jobposition', verbose_name='Poste'),
        ),
        migrations.AlterField(
            model_name='historicalemployeeworkinformation',
            name='job_role_id',
            field=models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='base.jobrole', verbose_name='Rôle du poste'),
        ),
        migrations.AlterField(
            model_name='historicalemployeeworkinformation',
            name='location',
            field=models.CharField(blank=True, max_length=50, null=True, verbose_name='Lieu de travail'),
        ),
        migrations.AlterField(
            model_name='historicalemployeeworkinformation',
            name='reporting_manager_id',
            field=models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='employee.employee', verbose_name='Responsable du reporting'),
        ),
        migrations.AlterField(
            model_name='historicalemployeeworkinformation',
            name='salary_hour',
            field=models.IntegerField(blank=True, default=0, null=True, verbose_name='Salaire par heure'),
        ),
        migrations.AlterField(
            model_name='historicalemployeeworkinformation',
            name='shift_id',
            field=models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='base.employeeshift', verbose_name='Quarts Info'),
        ),
        migrations.AlterField(
            model_name='historicalemployeeworkinformation',
            name='work_type_id',
            field=models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='base.worktype', verbose_name='Type de travail'),
        ),
        migrations.AlterField(
            model_name='notefiles',
            name='created_by',
            field=models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name='Créé par'),
        ),
        migrations.AlterField(
            model_name='notefiles',
            name='is_active',
            field=models.BooleanField(default=True, verbose_name='Actif'),
        ),
        migrations.AlterField(
            model_name='policy',
            name='company_id',
            field=models.ManyToManyField(blank=True, to='base.company', verbose_name='Entreprise'),
        ),
        migrations.AlterField(
            model_name='policy',
            name='created_by',
            field=models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name='Créé par'),
        ),
        migrations.AlterField(
            model_name='policy',
            name='is_active',
            field=models.BooleanField(default=True, verbose_name='Actif'),
        ),
        migrations.AlterField(
            model_name='policymultiplefile',
            name='created_by',
            field=models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name='Créé par'),
        ),
        migrations.AlterField(
            model_name='policymultiplefile',
            name='is_active',
            field=models.BooleanField(default=True, verbose_name='Actif'),
        ),
    ]
