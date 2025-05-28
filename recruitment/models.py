"""
models.py

This module is used to register models for recruitment app

"""

import json
import os
import re
from datetime import date, timedelta
from uuid import uuid4

import django
from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _
from django.utils import timezone 
from base.horilla_company_manager import HorillaCompanyManager
from base.models import Company, JobPosition
from employee.models import Employee
from horilla.models import HorillaModel
from horilla_audit.methods import get_diff
from horilla_audit.models import HorillaAuditInfo, HorillaAuditLog
from django.db.models.signals import post_save, m2m_changed

# Create your models here.


def validate_mobile(value):
    """
    This method is used to validate the mobile number using regular expression
    """
    pattern = r"^\+[0-9 ]+$|^[0-9 ]+$"

    if re.match(pattern, value) is None:
        if "+" in value:
            raise forms.ValidationError(
                "Invalid input: Plus symbol (+) should only appear at the beginning \
                    or no other characters allowed."
            )
        raise forms.ValidationError(
            "Invalid input: Only digits and spaces are allowed."
        )


def validate_pdf(value):
    """
    This method is used to validate PDF files and limit the size to 10MB.
    """
    ext = os.path.splitext(value.name)[1]  # Get file extension
    if ext.lower() != ".pdf":
        raise ValidationError(_("File must be a PDF."))

    # Taille maximale : 10MB
    max_size = 10 * 1024 * 1024  # 10MB en octets
    if value.size > max_size:
        raise ValidationError(_("The file size must be less than 10MB."))


def validate_image(value):
    """
    This method is used to validate the image
    """
    return value


def candidate_photo_upload_path(instance, filename):
    ext = filename.split(".")[-1]
    filename = f"{instance.name.replace(' ', '_')}_{filename}_{uuid4()}.{ext}"
    return os.path.join("recruitment/profile/", filename)


class SurveyTemplate(HorillaModel):
    """
    SurveyTemplate Model
    """

    title = models.CharField(max_length=30, unique=True)
    description = models.TextField(null=True, blank=True)
    is_general_template = models.BooleanField(default=False, editable=False)
    company_id = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name=_("Company"),
    )

    def __str__(self) -> str:
        return self.title


class Skill(HorillaModel):
    title = models.CharField(max_length=100)

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        self.title = self.title.capitalize()
        super().save(*args, **kwargs)


class Recruitment(HorillaModel):
    """
    Recruitment model
    """

    title = models.CharField(max_length=100, null=True, blank=True)
    description = models.TextField(null=True)
    google_form_url = models.URLField(
        max_length=500, 
        null=True,
        blank=True,
        verbose_name=_("Google Form URL"),
        help_text=_("URL of the linked Google Form")
    )
    generate_form = models.BooleanField(
        default=False,
        verbose_name=_("Generate Google Form"),
        help_text=_("Check to automatically generate a new Google Form")
    )
    is_event_based = models.BooleanField(
        default=False,
        help_text=_("To start recruitment for multiple job positions"),
    )
    closed = models.BooleanField(  
        default=False,
        help_text=_(
            "To close the recruitment, If closed then not visible on pipeline view."
        ),
    )
    is_published = models.BooleanField(
        default=True,
        help_text=_(
            "To publish a recruitment in website, if false then it \
            will not appear on open recruitment page."
        ),
    )
    is_active = models.BooleanField(
        default=True,
        help_text=_(
            "To archive and un-archive a recruitment, if active is false then it \
            will not appear on recruitment list view."
        ),
    )
    open_positions = models.ManyToManyField(
        JobPosition, related_name="open_positions", blank=True
    )
    optional_motivation = models.BooleanField(
        default=False, 
        help_text=_("Motivation letter not mandatory for candidate creation")
    )
    job_position_id = models.ForeignKey(
        JobPosition,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_constraint=False,
        related_name="recruitment",
        verbose_name=_("Job Position"),
        editable=False,
    )
    vacancy = models.IntegerField(default=0, null=True)
    recruitment_managers = models.ManyToManyField(Employee)
    survey_templates = models.ManyToManyField(SurveyTemplate, blank=True)
    company_id = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name=_("Company"),
    )
    start_date = models.DateField(default=django.utils.timezone.now)
    end_date = models.DateField(blank=True, null=True)
    skills = models.ManyToManyField(Skill, blank=True)
    objects = HorillaCompanyManager()
    default = models.manager.Manager()
    optional_profile_image = models.BooleanField(
        default=False, help_text=_("Profile image not mandatory for candidate creation")
    )
    optional_resume = models.BooleanField(
        default=False, help_text=_("Resume not mandatory for candidate creation")
    )
    selectors = models.ManyToManyField(
        'employee.Employee',
        blank=True,
        related_name='recruitment_selections',
        verbose_name=_("Demandeur"),
        help_text=_("Only these selectors can view and manage this recruitment if they are marked as selectors")
    )

    RECRUITMENT_TYPES = [
        ('INTERNAL', _('Internal')),
        ('EXTERNAL', _('External')),
        ('BOTH', _('Internal/External'))
    ]
    
    recruitment_type = models.CharField(
        max_length=10,
        choices=RECRUITMENT_TYPES,
        default='BOTH',
        verbose_name=_("Recruitment Type"),
        help_text=_("Internal: Only @group-activa emails, Internal/External: All emails")
    )

    VALIDITY_DURATION_CHOICES = [
        (30, _('30 jours')),
        (45, _('45 jours')),
        (60, _('60 jours')),
        (90, _('90 jours')),
        (120, _('120 jours')),
        (180, _('180 jours')),
        (365, _('1 an')),
        (0, _('Personnalisé')),  # Pour permettre la saisie manuelle
    ]
    
    validity_duration = models.IntegerField(
        choices=VALIDITY_DURATION_CHOICES,
        default=60,
        verbose_name=_("Durée de validité (jours)"),
        help_text=_("Durée de validité de l'offre en jours")
    )

    class Meta:
        """
        Meta class to add the additional info
        """

        unique_together = [
            (
                "job_position_id",
                "start_date",
            ),
            ("job_position_id", "start_date", "company_id"),
        ]
        permissions = (("archive_recruitment", "Archive Recruitment"),)

    def is_email_eligible(self, email):
        """
        Vérifie si un email est éligible pour ce recrutement.
        """
        if self.recruitment_type == 'INTERNAL':
        # Les candidatures internes doivent avoir un email @group-activa.com
            return email.endswith('@group-activa.com')
        elif self.recruitment_type == 'EXTERNAL':
        # Les candidatures externes ne doivent pas utiliser un email @group-activa.com
            return not email.endswith('@group-activa.com')
        return True

    def get_active_applications_count(self):
        """
        Retourne le nombre de candidatures actives
        """
        return self.candidate.filter(is_active=True).count()

    def get_internal_applications_count(self):
        """
        Retourne le nombre de candidatures internes
        """
        return self.candidate.filter(
            is_active=True,
            email__endswith='@group-activa.com'
        ).count()

    def get_external_applications_count(self):
        """
        Retourne le nombre de candidatures externes
        """
        return self.candidate.filter(
            is_active=True
        ).exclude(email__endswith='@group-activa.com').count()

    def total_hires(self):
        """
        This method is used to get the count of
        hired candidates
        """
        return self.candidate.filter(hired=True).count()
    
    def is_user_selector(self, user):
        """
        Check if given user is a selector for this recruitment
        """
        if hasattr(user, 'employee_get'):
            employee = user.employee_get
            return employee.is_selector and self.selectors.filter(id=employee.id).exists()
        return False
    
    def is_visible_to(self, employee):
        """
        Vérifie si un employé peut voir ce recrutement
        """
        if employee.employee_user_id.is_superuser:
            return True
        if employee.is_selector:
            return self.selectors.filter(id=employee.id).exists()
        return employee.company_id == self.company_id

    

    def ordered_stages(self):
        """
        This method will returns all the stage respectively to the ascending order of stages
        """
        return self.stage_set.order_by("sequence")

    def is_vacancy_filled(self):
        """
        This method is used to check wether the vaccancy for the recruitment is completed or not
        """
        hired_stage = Stage.objects.filter(
            recruitment_id=self, stage_type="hired"
        ).first()
        if hired_stage:
            hired_candidate = hired_stage.candidate_set.all().exclude(canceled=True)
            if len(hired_candidate) >= self.vacancy:
                return True
    
    def get_days_remaining(self):
        """
        Retourne le nombre de jours restants avant la fin de validité
        """
        if not self.end_date:
            return None
            
        today = timezone.now().date()
        
        if self.end_date < today:
            return 0  # Expiré
        else:
            delta = self.end_date - today
            return delta.days
    
    def is_expired(self):
        """
        Retourne True si l'offre est expirée
        """
        days_remaining = self.get_days_remaining()
        return days_remaining is not None and days_remaining <= 0
    
    def get_validity_status(self):
        """
        Retourne le statut de validité avec une classe CSS appropriée
        """
        days_remaining = self.get_days_remaining()
        
        if days_remaining is None:
            return {'status': _('Pas de date de fin'), 'class': 'oh-badge--warning'}
        elif days_remaining <= 0:
            return {'status': _('Expiré'), 'class': 'oh-badge--danger'}
        elif days_remaining <= 7:
            return {'status': f'{days_remaining} jour(s)', 'class': 'oh-badge--warning'}
        else:
            return {'status': f'{days_remaining} jour(s)', 'class': 'oh-badge--success'}
    
    def __str__(self):
        title = (
            f"{self.job_position_id.job_position} {self.start_date}"
            if self.title is None and self.job_position_id
            else self.title
        )

        if not self.is_event_based and self.job_position_id is not None:
            self.open_positions.add(self.job_position_id)

        return title

    def clean(self):
        """
        Validation des règles métier pour le recrutement
        """
        
        if self.title is None:
            raise ValidationError({"title": _("This field is required")})
        if self.is_published:
            if self.vacancy <= 0:
                raise ValidationError(
                    _(
                        "Vacancy must be greater than zero if the recruitment is publishing."
                    )
                )

        if self.end_date is not None and (
            self.start_date is not None and self.start_date > self.end_date
        ):
            raise ValidationError(
                {"end_date": _("End date cannot be less than start date.")}
            )
        
        # VALIDATION POUR LES SÉLECTEURS
        if self.pk:  # Seulement si l'objet existe déjà
            for selector in self.selectors.all():
                if (selector.company_id and 
                    self.company_id and 
                    selector.company_id != self.company_id and 
                    not selector.employee_user_id.is_superuser):
                    
                    raise ValidationError({
                        'selectors': _(
                            f"Le sélecteur {selector.get_full_name()} (compagnie: {selector.company_id}) "
                            f"ne peut pas être assigné à un recrutement de la compagnie {self.company_id}."
                        )
                    })
        
        return super().clean()

    def save(self, *args, **kwargs):
        """
        Sauvegarde avec validation et calcul automatique des dates
        """
        # VALIDATION POUR LES OBJETS EXISTANTS
        if self.pk:
            self.full_clean()
        
        # VALIDATION DES CHAMPS REQUIS AVANT SAUVEGARDE
        if self.is_event_based and not self.open_positions.exists():
            raise ValidationError({"open_positions": _("This field is required")})
        
        # CALCUL AUTOMATIQUE DE LA DATE DE FIN AVANT SAUVEGARDE
        if (self.validity_duration and 
            self.validity_duration > 0 and 
            self.start_date and
            # Ne recalculer que si c'est explicitement demandé ou si c'est un nouvel objet
            (not self.pk or not self.end_date)):
            
            self.end_date = self.start_date + timedelta(days=self.validity_duration)
        
        # LOGIQUE EXISTANTE - Sauvegarde unique
        super().save(*args, **kwargs)
            
    # def is_expired(self):
    #     """
    #     Retourne True si la date de fin est passée
    #     """
    #     if self.end_date:
    #         today = timezone.now().date()
    #         return self.end_date < today
    #     return False


@receiver(post_save, sender=Recruitment)
def create_initial_stage(sender, instance, created, **kwargs):
    """Create default stages for the recruitment"""
    if created:
        stages = [
            ("Présélection des CV", "applied", 0),
            ("validation des CVs par le demandeur", "selector", 1),
            ("Test de présélection", "Test", 2),
            ("Entretien en panel", "interview", 3),
            ("Entretien avec le DG", "interview", 4),
            ("Mail aux candidats malheureux", "cancelled", 5),
            ("Mail aux candidats retenus", "hired", 6),
                        
        ]
        for stage_name, stage_type, sequence in stages:
            Stage.objects.create(
                recruitment_id=instance,
                stage=stage_name,
                stage_type=stage_type, 
                sequence=sequence
            )

@receiver(m2m_changed, sender=Recruitment.selectors.through) 
def update_selector_stage(sender, instance, action, pk_set, **kwargs):
    """Update selector stage managers when selectors change"""
    if action == "post_add":
        selector_stage = instance.stage_set.filter(stage_type='selector').first()
        if selector_stage and pk_set:
            selector_stage.stage_managers.add(*pk_set)
    elif action == "post_remove":
        selector_stage = instance.stage_set.filter(stage_type='selector').first()
        if selector_stage and pk_set:
            selector_stage.stage_managers.remove(*pk_set)


class Stage(HorillaModel):
    """
    Stage model
    """

    stage_types = [
        # ("initial", _("Initial")),
        ("applied", _("Applied")),
        ("test", _("Test")),
        ("interview", _("Interview")),
        ("cancelled", _("Cancelled")),
        ("hired", _("Hired")),
        ("selector", _("Demandeur")),
    ]
    recruitment_id = models.ForeignKey(
        Recruitment,
        on_delete=models.CASCADE,
        related_name="stage_set",
        verbose_name=_("Recruitment"),
    )
    stage_managers = models.ManyToManyField(Employee)
    stage = models.CharField(max_length=50)
    stage_type = models.CharField(
        max_length=20, choices=stage_types, default="interview"
    )
    sequence = models.IntegerField(null=True, default=0)
    objects = HorillaCompanyManager(related_company_field="recruitment_id__company_id")

    def __str__(self):
        return f"{self.stage}"

    class Meta:
        """
        Meta class to add the additional info
        """

        permissions = (("archive_Stage", "Archive Stage"),)
        unique_together = ["recruitment_id", "stage"]
        ordering = ["sequence"]

    def active_candidates(self):
        """
        This method is used to get all the active candidate like related objects
        """
        return {
            "all": Candidate.objects.filter(
                stage_id=self, canceled=False, is_active=True
            )
        }

    def has_active_candidates(self):
        """Return True si l'étape a des candidats actifs"""
        return self.candidate_set.filter(is_active=True).exists()

    def get_display_priority(self):
        """
        Calcule la priorité d'affichage de l'étape en tenant compte 
        des candidats actifs et de la progression
        """
        # Ordre statique de base
        base_priority = {
            'applied': 0,      # Présélection CV
            'selector': 1,     # Validation demandeur
            'test': 2,         # Test de présélection
            'interview': 3,    # Entretiens
            'cancelled': 98,   # Candidats malheureux
            'hired': 99        # Candidats retenus
        }
        
        priority = base_priority.get(self.stage_type, 50)
        has_active = self.candidate_set.filter(is_active=True).exists()

        # Si étape active avec candidats, on la monte au-dessus 
        # des étapes précédentes non-obligatoires
        if has_active and self.stage_type in ['interview', 'test']:
            # On réduit la priorité pour monter l'étape
            priority -= 2
            
            # On vérifie s'il y a eu un saut d'étapes
            previous_stages = Stage.objects.filter(
                recruitment_id=self.recruitment_id,
                sequence__lt=self.sequence
            ).exclude(stage_type__in=['cancelled', 'hired'])
            
            if previous_stages.exists():
                # L'étape monte juste au-dessus de la dernière étape active
                last_active = previous_stages.order_by('-sequence').first()
                if last_active:
                    priority = base_priority.get(last_active.stage_type, 50) - 1

        return priority



class Candidate(HorillaModel):
    """
    Candidate model
    """

    choices = [("male", _("Monsieur")), ("female", _("Madame"))]
    offer_letter_statuses = [
        ("not_sent", "Not Sent"),
        ("sent", "Sent"),
        ("accepted", "Accepted"),
        ("rejected", "Rejected"),
        ("joined", "Joined"),
    ]
    source_choices = [
        ("application", _("Application Form")),
        ("software", _("Inside software")),
        ("other", _("Other")),
    ]
    AI_ANALYSIS_STATUS_CHOICES = [
        ('pending', _('Pending')),
        ('in_progress', _('In Progress')),
        ('completed', _('Completed')),
        ('failed', _('Failed'))
    ]
    name = models.CharField(max_length=100, null=True, verbose_name=_("Name"))
    profile = models.ImageField(upload_to=candidate_photo_upload_path, null=True)
    portfolio = models.URLField(max_length=200, blank=True)
    recruitment_id = models.ForeignKey(
        Recruitment,
        on_delete=models.PROTECT,
        null=True,
        related_name="candidate",
        verbose_name=_("Recruitment"),
    )
    job_position_id = models.ForeignKey(
        JobPosition,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name=_("Job Position"),
    )
    stage_id = models.ForeignKey(
        Stage,
        on_delete=models.PROTECT,
        null=True,
        verbose_name=_("Stage"),
    )
    converted_employee_id = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="candidate_get",
        verbose_name=_("Employee"),
    )
    schedule_date = models.DateTimeField(
        blank=True, null=True, verbose_name=_("Schedule date")
    )
    email = models.EmailField(max_length=254, verbose_name=_("Email"))
    
    
    mobile = models.CharField(
        max_length=15,
        blank=True,
        validators=[
            validate_mobile,
        ],
        verbose_name=_("Phone"),
    )
    resume = models.FileField(
        upload_to="recruitment/resume",
        validators=[
            validate_pdf,
        ],
    )
    #shortlisting
    score = models.FloatField(null=True, blank=True, verbose_name=_("Score"))

    # ajout motivation model
    motivation = models.FileField(
        upload_to="recruitment/motivation",
        validators=[validate_pdf],
        blank=True,
        null=True
    )
    referral = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="candidate_referral",
        verbose_name=_("Referral"),
    )
    address = models.TextField(
        null=True, blank=True, verbose_name=_("Address"), max_length=255
    )
    
    country = models.CharField(
        max_length=30, null=True, blank=True, verbose_name=_("Country")
    )
    dob = models.DateField(null=True, blank=True, verbose_name=_("Date of Birth"))
    state = models.CharField(
        max_length=30, null=True, blank=True, verbose_name=_("State")
    )
    city = models.CharField(
        max_length=30, null=True, blank=True, verbose_name=_("City")
    )
    zip = models.CharField(
        max_length=30, null=True, blank=True, verbose_name=_("Zip Code")
    )
    gender = models.CharField(
        max_length=15,
        choices=choices,
        null=True,
        default="male",
        verbose_name=_("Gender"),
    )
    source = models.CharField(
        max_length=20,
        choices=source_choices,
        null=True,
        blank=True,
        verbose_name=_("Source"),
    )
    start_onboard = models.BooleanField(default=False, verbose_name=_("Start Onboard"))
    hired = models.BooleanField(default=False, verbose_name=_("Hired"))
    canceled = models.BooleanField(default=False, verbose_name=_("Canceled"))
    joining_date = models.DateField(
        blank=True, null=True, verbose_name=_("Joining Date")
    )
    history = HorillaAuditLog(
        related_name="history_set",
        bases=[
            HorillaAuditInfo,
        ],
    )
    sequence = models.IntegerField(null=True, default=0)

    probation_end = models.DateField(null=True, editable=False)
    offer_letter_status = models.CharField(
        max_length=10,
        choices=offer_letter_statuses,
        default="not_sent",
        editable=False,
    )
    objects = HorillaCompanyManager(related_company_field="recruitment_id__company_id")
    last_updated = models.DateField(null=True, auto_now=True)

    ai_score = models.FloatField(
        null=True, 
        blank=True,
        verbose_name=_("AI Score")
    )
    
    ai_analysis_status = models.CharField(
        max_length=20,
        choices=AI_ANALYSIS_STATUS_CHOICES,
        default='pending',
        verbose_name=_("Analysis Status")
    )
    
    ai_analysis_details = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_("Analysis Details")
    )
    
    ai_analysis_timestamp = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Last Analysis")
    )

    def update_ai_analysis(self, score, details):
        """Update AI analysis results and status"""
        self.ai_score = score
        self.ai_analysis_details = details
        # Utiliser le status depuis details si présent
        if isinstance(details, dict) and "status" in details:
            self.ai_analysis_status = 'completed'
        else:
            self.ai_analysis_status = 'completed'
        self.ai_analysis_timestamp = timezone.now()
        self.save(update_fields=[
            'ai_score', 
            'ai_analysis_details',
            'ai_analysis_status',
            'ai_analysis_timestamp'
        ])

    def start_ai_analysis(self):
        """Mark analysis as started"""
        self.ai_analysis_status = 'in_progress'
        self.save(update_fields=['ai_analysis_status'])

    def mark_analysis_failed(self):
        """Mark analysis as failed"""
        self.ai_analysis_status = 'failed'
        self.save(update_fields=['ai_analysis_status'])

    def get_gender(self):

        """
        Return formatted gender
        """
        # Les choix sont définis comme : 
        # choices = [("male", _("Male")), ("female", _("Female")), ("other", _("Other"))]
        return dict(self.choices).get(self.gender, '')
    
    def get_title(self):
        """
        Return appropriate title based on gender
        """
        titles = {
            'male': _('Mr.'),
            'female': _('Ms.'),
            'other': _('Mx.')
    }
        return titles.get(self.gender, '')

    def __str__(self):
        return f"{self.name}"

    def is_offer_rejected(self):
        """
        Is offer rejected checking method
        """
        first = RejectedCandidate.objects.filter(candidate_id=self).first()
        if first:
            return first.reject_reason_id.count() > 0
        return first

    def get_full_name(self):
        """
        Method will return employee full name
        """
        return str(self.name)

    def get_avatar(self):
        """
        Method will rerun the api to the avatar or path to the profile image
        """
        url = (
            f"https://ui-avatars.com/api/?name={self.get_full_name()}&background=random"
        )
        if self.profile:
            full_filename = self.profile.name

            if default_storage.exists(full_filename):
                url = self.profile.url

        return url

    def get_company(self):
        """
        This method is used to return the company
        """
        return getattr(
            getattr(getattr(self, "recruitment_id", None), "company_id", None),
            "company",
            None,
        )

    def get_job_position(self):
        """
        This method is used to return the job position of the candidate
        """
        return self.job_position_id.job_position

    def get_email(self):
        """
        Return email
        """
        return self.email

    def get_mail(self):
        """ """
        return self.get_email()

    def tracking(self):
        """
        This method is used to return the tracked history of the instance
        """
        return get_diff(self)

    def get_last_sent_mail(self):
        """
        This method is used to get last send mail
        """
        from base.models import EmailLog

        return (
            EmailLog.objects.filter(to__icontains=self.email)
            .order_by("-created_at")
            .first()
        )
    
    
    def get_validation_status(self, selector):
        """
        Retourne le statut de validation pour un sélecteur donné
        """
        validation = self.selector_validations.filter(
            selector=selector, 
            is_validated=True
        ).first()
        return bool(validation)
    
    def is_validated_by_selector(self, selector):
        """Vérifie si le candidat est validé par un demandeur spécifique"""
        return self.selector_validations.filter(
            selector=selector,
            is_validated=True
        ).exists()
    
    def is_currently_validated(self):
        """
        Retourne True si le candidat est actuellement validé
        """
        validation = self.selector_validations.filter(is_validated=True).first()
        return bool(validation)

    def is_validated_in_stage(self, stage):
        """Vérifie si le candidat est validé dans l'étape donnée"""
        return self.selector_validations.filter(
            stage=stage,
            is_validated=True
        ).exists()
    
    

    def get_interview(self):
        """
        This method is used to get the interview dates and times for the candidate for the mail templates
        """

        interviews = InterviewSchedule.objects.filter(candidate_id=self.id)
        if interviews:
            interview_info = "<table>"
            interview_info += "<tr><th>Sl No.</th><th>Date</th><th>Time</th><th>Is Completed</th></tr>"
            for index, interview in enumerate(interviews, start=1):
                interview_info += f"<tr><td>{index}</td>"
                interview_info += (
                    f"<td class='dateformat_changer'>{interview.interview_date}</td>"
                )
                interview_info += (
                    f"<td class='timeformat_changer'>{interview.interview_time}</td>"
                )
                interview_info += (
                    f"<td>{'Yes' if interview.completed else 'No'}</td></tr>"
                )
            interview_info += "</table>"
            return interview_info
        else:
            return ""

    def save(self, *args, **kwargs):
        # Check if the 'stage_id' attribute is not None
        if self.stage_id is not None:
            # Check if the stage type is 'hired'
            if self.stage_id.stage_type == "hired":
                self.hired = True

        if not self.recruitment_id.is_event_based and self.job_position_id is None:
            self.job_position_id = self.recruitment_id.job_position_id
        if self.job_position_id not in self.recruitment_id.open_positions.all():
            raise ValidationError({"job_position_id": _("Choose valid choice")})
        if self.recruitment_id.is_event_based and self.job_position_id is None:
            raise ValidationError({"job_position_id": _("This field is required.")})
        if self.stage_id and self.stage_id.stage_type == "cancelled":
            self.canceled = True
        if self.canceled:
            cancelled_stage = Stage.objects.filter(
                recruitment_id=self.recruitment_id, stage_type="cancelled"
            ).first()
            if not cancelled_stage:
                cancelled_stage = Stage.objects.create(
                    recruitment_id=self.recruitment_id,
                    stage="Cancelled Candidates",
                    stage_type="cancelled",
                    sequence=50,
                )
            self.stage_id = cancelled_stage
        if (
            self.converted_employee_id
            and Candidate.objects.filter(
                converted_employee_id=self.converted_employee_id
            )
            .exclude(id=self.id)
            .exists()
        ):
            raise ValidationError(_("Employee is uniques for candidate"))

        super().save(*args, **kwargs)

    class Meta:
        """
        Meta class to add the additional info
        """

        unique_together = ('email', 'recruitment_id')
        permissions = (
            ("view_history", "View Candidate History"),
            ("archive_candidate", "Archive Candidate"),
        )
        ordering = ["sequence"]

    def clean(self):
        super().clean()
        # Vérifier si le candidat a déjà postulé pour ce recrutement spécifique
        if Candidate.objects.filter(email=self.email, recruitment_id=self.recruitment_id).exclude(pk=self.pk).exists():
            raise ValidationError(_("Vous avez déjà postulé pour cette offre d'emploi."))

    def save(self, *args, **kwargs):
        self.clean()  # Appeler la méthode clean avant la sauvegarde
        # ... le reste de la logique de sauvegarde ...
        super().save(*args, **kwargs)

        


from horilla.signals import pre_bulk_update


class CandidateValidation(HorillaModel):
    """
    Stocke les validations des candidats par les demandeurs
    """
    stage = models.ForeignKey(
        Stage,
        on_delete=models.CASCADE,
        related_name='validations',
        null=True,
        blank=True,
    )
    candidate = models.ForeignKey(
        Candidate,
        on_delete=models.CASCADE,
        related_name='selector_validations',
        null=True,
        blank=True,
    )
    selector = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE, 
        related_name='candidate_validations',
        null=True,
        blank=True,
    )
    is_validated = models.BooleanField(
        default=True,
        verbose_name=_("Validé")
    )
    validated_at = models.DateTimeField(
        auto_now_add=True
    )
    comments = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Commentaires")
    )

    class Meta:
        unique_together = ['stage', 'candidate', 'selector']
        verbose_name = _("Validation du demandeur")
        verbose_name_plural = _("Validations des demandeurs")
        ordering = ['-validated_at']

    def __str__(self):
        if self.candidate and self.selector:
            return f"{self.candidate.name} - validé par {self.selector.get_full_name()}"
        return f"Validation #{self.id}"

    def save(self, *args, **kwargs):
        if not self.validated_at:
            self.validated_at = timezone.now()
        super().save(*args, **kwargs)

    @property
    def status_display(self):
        return _("Validé") if self.is_validated else _("Non validé")

class RejectReason(HorillaModel):
    """
    RejectReason
    """

    title = models.CharField(
        max_length=20,
    )
    description = models.TextField(null=True, blank=True, max_length=255)
    company_id = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name=_("Company"),
    )
    objects = HorillaCompanyManager()

    def __str__(self) -> str:
        return self.title


class RejectedCandidate(HorillaModel):
    """
    RejectedCandidate
    """

    candidate_id = models.OneToOneField(
        Candidate,
        on_delete=models.PROTECT,
        verbose_name="Candidate",
        related_name="rejected_candidate",
    )
    reject_reason_id = models.ManyToManyField(
        RejectReason, verbose_name="Reject reason", blank=True
    )
    description = models.TextField(max_length=255)
    objects = HorillaCompanyManager(
        related_company_field="candidate_id__recruitment_id__company_id"
    )
    history = HorillaAuditLog(
        related_name="history_set",
        bases=[
            HorillaAuditInfo,
        ],
    )

    def __str__(self) -> str:
        return super().__str__()


class StageFiles(HorillaModel):
    files = models.FileField(upload_to="recruitment/stageFiles", blank=True, null=True)

    def __str__(self):
        return self.files.name.split("/")[-1]


class StageNote(HorillaModel):
    """
    StageNote model
    """

    candidate_id = models.ForeignKey(Candidate, on_delete=models.CASCADE)
    description = models.TextField(verbose_name=_("Description"), max_length=255)
    stage_id = models.ForeignKey(Stage, on_delete=models.CASCADE)
    stage_files = models.ManyToManyField(StageFiles, blank=True)
    updated_by = models.ForeignKey(Employee, on_delete=models.CASCADE)
    objects = HorillaCompanyManager(
        related_company_field="candidate_id__recruitment_id__company_id"
    )

    def __str__(self) -> str:
        return f"{self.description}"


class RecruitmentSurvey(HorillaModel):
    """
    RecruitmentSurvey model
    """

    question_types = [
        ("checkbox", _("Yes/No")),
        ("options", _("Choices")),
        ("multiple", _("Multiple Choice")),
        ("text", _("Text")),
        ("number", _("Number")),
        ("percentage", _("Percentage")),
        ("date", _("Date")),
        ("textarea", _("Textarea")),
        ("file", _("File Upload")),
        ("rating", _("Rating")),
    ]
    question = models.TextField(null=False, max_length=255)
    template_id = models.ManyToManyField(
        SurveyTemplate, verbose_name="Template", blank=True
    )
    is_mandatory = models.BooleanField(default=False)
    recruitment_ids = models.ManyToManyField(
        Recruitment,
        verbose_name=_("Recruitment"),
    )
    question = models.TextField(null=False)
    job_position_ids = models.ManyToManyField(
        JobPosition, verbose_name=_("Job Positions"), editable=False
    )
    sequence = models.IntegerField(null=True, default=0)
    type = models.CharField(
        max_length=15,
        choices=question_types,
    )
    options = models.TextField(
        null=True, default="", help_text=_("Separate choices by ',  '"), max_length=255
    )
    objects = HorillaCompanyManager(related_company_field="recruitment_ids__company_id")

    def __str__(self) -> str:
        return str(self.question)

    def choices(self):
        """
        Used to split the choices
        """
        return self.options.split(", ")

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.template_id is None:
            general_template = SurveyTemplate.objects.filter(
                is_general_template=True
            ).first()
            if general_template:
                self.template_id.add(general_template)
                super().save(*args, **kwargs)

    class Meta:
        ordering = [
            "sequence",
        ]


class QuestionOrdering(HorillaModel):
    """
    Survey Template model
    """

    question_id = models.ForeignKey(RecruitmentSurvey, on_delete=models.CASCADE)
    recruitment_id = models.ForeignKey(Recruitment, on_delete=models.CASCADE)
    sequence = models.IntegerField(default=0)
    objects = HorillaCompanyManager(related_company_field="recruitment_ids__company_id")


class RecruitmentSurveyAnswer(HorillaModel):
    """
    RecruitmentSurveyAnswer
    """

    candidate_id = models.ForeignKey(Candidate, on_delete=models.CASCADE)
    recruitment_id = models.ForeignKey(
        Recruitment,
        on_delete=models.PROTECT,
        verbose_name=_("Recruitment"),
        null=True,
    )
    job_position_id = models.ForeignKey(
        JobPosition,
        on_delete=models.PROTECT,
        verbose_name=_("Job Position"),
        null=True,
    )
    answer_json = models.JSONField()
    attachment = models.FileField(
        upload_to="recruitment_attachment", null=True, blank=True
    )
    objects = HorillaCompanyManager(related_company_field="recruitment_id__company_id")

    @property
    def answer(self):
        """
        Used to convert the json to dict
        """
        # Convert the JSON data to a dictionary
        try:
            return json.loads(self.answer_json)
        except json.JSONDecodeError:
            return {}  # Return an empty dictionary if JSON is invalid or empty

    def __str__(self) -> str:
        return f"{self.candidate_id.name}-{self.recruitment_id}"


class RecruitmentMailTemplate(HorillaModel):
    title = models.CharField(max_length=25, unique=True)
    body = models.TextField()
    company_id = models.ForeignKey(
        Company,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        verbose_name=_("Company"),
    )

    def __str__(self) -> str:
        return f"{self.title}"


class SkillZone(HorillaModel):
    """ "
    Model for talent pool
    """

    title = models.CharField(max_length=50, verbose_name="Skill Zone")
    description = models.TextField(verbose_name=_("Description"), max_length=255)
    company_id = models.ForeignKey(
        Company,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        verbose_name=_("Company"),
    )
    objects = HorillaCompanyManager()

    def get_active(self):
        return SkillZoneCandidate.objects.filter(is_active=True, skill_zone_id=self)

    def __str__(self) -> str:
        return self.title


class SkillZoneCandidate(HorillaModel):
    """
    Model for saving candidate data's for future recruitment
    """

    skill_zone_id = models.ForeignKey(
        SkillZone,
        verbose_name=_("Skill Zone"),
        related_name="skillzonecandidate_set",
        on_delete=models.PROTECT,
        null=True,
    )
    candidate_id = models.ForeignKey(
        Candidate,
        on_delete=models.PROTECT,
        null=True,
        related_name="skillzonecandidate_set",
        verbose_name=_("Candidate"),
    )
    # job_position_id=models.ForeignKey(
    #     JobPosition,
    #     on_delete=models.PROTECT,
    #     null=True,
    #     related_name="talent_pool",
    #     verbose_name=_("Job Position")
    # )

    reason = models.CharField(max_length=200, verbose_name=_("Reason"))
    added_on = models.DateField(auto_now_add=True)
    objects = HorillaCompanyManager(
        related_company_field="candidate_id__recruitment_id__company_id"
    )

    class Meta:
        """
        Meta class to add the additional info
        """

        unique_together = (
            "skill_zone_id",
            "candidate_id",
        )

    def __str__(self) -> str:
        return str(self.candidate_id.get_full_name())


class CandidateRating(HorillaModel):
    employee_id = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="candidate_rating"
    )
    candidate_id = models.ForeignKey(
        Candidate, on_delete=models.CASCADE, related_name="candidate_rating"
    )
    rating = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(5)]
    )

    class Meta:
        unique_together = ["employee_id", "candidate_id"]

    def __str__(self) -> str:
        return f"{self.employee_id} - {self.candidate_id} rating {self.rating}"


class RecruitmentGeneralSetting(HorillaModel):
    """
    RecruitmentGeneralSettings model
    """

    candidate_self_tracking = models.BooleanField(default=False)
    show_overall_rating = models.BooleanField(default=False)
    company_id = models.ForeignKey(Company, on_delete=models.CASCADE, null=True)


class InterviewSchedule(HorillaModel):
    """
    Interview Scheduling Model
    """
    candidate_id = models.ForeignKey(
        Candidate,
        verbose_name=_("Candidate"),
        related_name="candidate_interview",
        on_delete=models.CASCADE,
    )
    employee_id = models.ManyToManyField(Employee, verbose_name=_("interviewer"))
    interview_date = models.DateField(verbose_name=_("Interview Date"))
    interview_time = models.TimeField(verbose_name=_("Interview Time"))
    duration = models.IntegerField(
        default=60,
        verbose_name=_("Duration (minutes)"),
        validators=[MinValueValidator(15)]
    )
    description = models.TextField(
        verbose_name=_("Description"), 
        blank=True,
        max_length=255
    )
    google_event_id = models.CharField(
        max_length=255, 
        blank=True,
        null=True,
        verbose_name=_("Google Calendar Event ID")
    )
    google_meet_link = models.URLField(
        blank=True,
        null=True,
        verbose_name=_("Google Meet Link")
    )
    completed = models.BooleanField(
        default=False,
        verbose_name=_("Is Interview Completed")
    )
    attendees = models.JSONField(null=True, blank=True)
    google_event_id = models.CharField(max_length=255, null=True, blank=True)
    
    def __str__(self) -> str:
        return f"{self.candidate_id} -Interview."


class Resume(models.Model):
    file = models.FileField(
        upload_to="recruitment/resume",
        validators=[
            validate_pdf,
        ],
    )
    recruitment_id = models.ForeignKey(
        Recruitment, on_delete=models.CASCADE, related_name="resume"
    )
    is_candidate = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.recruitment_id} - Resume {self.pk}"
    
# ajout de class motivation
class Motivation(models.Model):
    file = models.FileField(
        upload_to="recruitment/motivation",
        validators=[
            validate_pdf,
        ],
    )
    recruitment_id = models.ForeignKey(
        Recruitment, on_delete=models.CASCADE, related_name="motivation"
    )
    is_candidate = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.recruitment_id} - Motivation {self.pk}"

class AIConfiguration(HorillaModel):
    """
    Configuration IA pour l'analyse des CV par filiale
    """
    name = models.CharField(
        max_length=100,
        verbose_name=_("Configuration Name"),
        help_text=_("Nom de la configuration IA")
    )
    
    api_key = models.CharField(
        max_length=255,
        verbose_name=_("together API Key"),
        help_text=_("Clé API together pour l'analyse des CV")
    )
    
    model_name = models.CharField(
        max_length=100,
        default="deepseek-ai/DeepSeek-V3", 
        verbose_name=_("Model Name"),
        help_text=_("Nom du modèle IA à utiliser")
    )
    
    analysis_prompt = models.TextField(
        verbose_name=_("Analysis Prompt"),
        help_text=_("Prompt utilisé pour l'analyse des CV"),
        default="""IMPORTANT: Répondez uniquement avec un JSON valide sans texte additionnel.
        Vous êtes un expert RH qui analyse des CV pour évaluer l'adéquation avec un poste.
        
        Critères d'évaluation:
        1. Pertinence du domaine (30%) - Si le domaine ne correspond PAS DU TOUT au poste, score=0
        2. Expérience professionnelle (25%) - Durée, postes similaires, responsabilités
        3. Formation/Éducation (20%) - Diplômes pertinents, niveau d'études
        4. Compétences techniques (15%) - Adéquation avec les technologies requises
        5. Certifications/Projets (10%) - Certifications spécifiques, projets pertinents
        
        Description du poste à analyser:
        {}
        
        Format JSON requis (OBLIGATOIRE):
        {{
            "job_matching": {{
                "is_relevant": true/false,
                "reason": "Expliquer pourquoi le CV correspond ou non au poste"
            }},
            "score": 0-100,
            "details": {{
                "education": "Analyse de la formation",
                "experience": "Analyse de l'expérience", 
                "technical_skills": "Analyse des compétences techniques",
                "certifications": "Certifications et projets pertinents"
            }},
            "strengths": ["Point fort 1", "Point fort 2"],
            "areas_for_improvement": ["Amélioration 1", "Amélioration 2"]
        }}"""
    )
    
    companies = models.ManyToManyField(
        'base.Company',
        blank=True,
        verbose_name=_("Companies"),
        help_text=_("Filiales utilisant cette configuration")
    )
    
    is_default = models.BooleanField(
        default=False,
        verbose_name=_("Default Configuration"),
        help_text=_("Configuration par défaut si aucune n'est assignée à la filiale")
    )
    
    max_tokens = models.IntegerField(
        default=2500,
        verbose_name=_("Max Tokens"),
        help_text=_("Nombre maximum de tokens pour la réponse")
    )
    
    temperature = models.FloatField(
        default=0.1,
        validators=[MinValueValidator(0.0), MaxValueValidator(2.0)],
        verbose_name=_("Temperature"),
        help_text=_("Température du modèle (0.0 = déterministe, 2.0 = créatif)")
    )
    
    objects = HorillaCompanyManager()

    class Meta:
        verbose_name = _("AI Configuration")
        verbose_name_plural = _("AI Configurations")
        # Django génère automatiquement les permissions de base, pas besoin de les redéfinir

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Si cette config est définie comme par défaut, retirer le flag des autres
        if self.is_default:
            AIConfiguration.objects.exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)

    @classmethod
    def get_config_for_company(cls, company):
        """
        Récupère la configuration IA pour une filiale donnée
        """
        if company:
            config = cls.objects.filter(companies=company, is_active=True).first()
            if config:
                return config
        
        # Fallback sur la configuration par défaut
        return cls.objects.filter(is_default=True, is_active=True).first()

    @classmethod  
    def get_default_config(cls):
        """
        Récupère la configuration par défaut
        """
        return cls.objects.filter(is_default=True, is_active=True).first()

    def test_api_key(self):
        """
        Teste la validité de la clé API Together AI
        """
        try:
            from together import Together
            import os
            
            # Configuration temporaire de la clé
            os.environ['TOGETHER_API_KEY'] = self.api_key
            
            client = Together()
            
            # Test simple
            response = client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "user", "content": "Hello"}
                ],
                max_tokens=10
            )
            return True
        except Exception as e:
            logger.error(f"Test API key failed: {str(e)}")
            return False