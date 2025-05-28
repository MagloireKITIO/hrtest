# candidate_portal/models.py
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.contrib.auth.hashers import make_password, check_password
from recruitment.models import Candidate, Recruitment
from base.models import Company
import uuid
import secrets
import string
from django.core.validators import FileExtensionValidator, MinValueValidator, MaxValueValidator
from recruitment.models import Skill
import os
from uuid import uuid4

class CandidateAuth(models.Model):
    """Modèle d'authentification distinct pour les candidats"""
    email = models.EmailField(unique=True, verbose_name=_("Email"))
    password = models.CharField(max_length=128, verbose_name=_("Mot de passe"))
    first_name = models.CharField(max_length=150, verbose_name=_("Prénom"))
    last_name = models.CharField(max_length=150, verbose_name=_("Nom"))
    is_active = models.BooleanField(default=True, verbose_name=_("Actif"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Date de création"))
    last_login = models.DateTimeField(null=True, blank=True, verbose_name=_("Dernière connexion"))
    
    def set_password(self, raw_password):
        """Hash le mot de passe avant de le stocker"""
        self.password = make_password(raw_password)
        
    def check_password(self, raw_password):
        """Vérifie si le mot de passe fourni correspond au mot de passe hashé"""
        return check_password(raw_password, self.password)
    
    def save(self, *args, **kwargs):
        """S'assure que le mot de passe est toujours hashé avant d'être sauvegardé"""
        if self._state.adding and self.password and not self.password.startswith('pbkdf2_sha256$'):
            self.set_password(self.password)
        super().save(*args, **kwargs)
    
    def get_full_name(self):
        """Retourne le nom complet du candidat"""
        return f"{self.first_name} {self.last_name}"
    
    def __str__(self):
        return self.email
    
    class Meta:
        verbose_name = _("Authentification Candidat")
        verbose_name_plural = _("Authentifications Candidats")


class CandidateProfile(models.Model):
    """Informations supplémentaires sur le candidat"""
    candidate_auth = models.OneToOneField(
        CandidateAuth,
        on_delete=models.CASCADE,
        related_name="profile",
        verbose_name=_("Authentification")
    )
    company = models.ForeignKey(
        'base.Company',
        on_delete=models.CASCADE,
        verbose_name=_("Entreprise")
    )
    phone = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name=_("Téléphone")
    )
    photo = models.ImageField(
        upload_to='candidate_photos/',
        blank=True,
        null=True,
        verbose_name=_("Photo de profil")
    )
    date_of_birth = models.DateField(
        blank=True,
        null=True,
        verbose_name=_("Date de naissance")
    )
    gender = models.CharField(
        max_length=10,
        choices=[('male', _('Monsieur')), ('female', _('Madame'))],
        default='male',
        verbose_name=_("Genre")
    )
    address = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Adresse")
    )
    city = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_("Ville")
    )
    zip_code = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name=_("Code postal")
    )
    country = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_("Pays")
    )
    linkedin_url = models.URLField(
        blank=True,
        null=True,
        verbose_name=_("Profil LinkedIn")
    )
    portfolio_url = models.URLField(
        blank=True,
        null=True,
        verbose_name=_("Site web / Portfolio")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    headline = models.CharField(
        max_length=150, 
        blank=True, 
        null=True,
        verbose_name=_("Titre professionnel")
    )
    biography = models.TextField(
        blank=True, 
        null=True,
        verbose_name=_("Biographie")
    )
    preferred_job_type = models.CharField(
        max_length=50,
        choices=[
            ('full_time', _('Temps plein')),
            ('part_time', _('Temps partiel')),
            ('contract', _('Contrat')),
            ('internship', _('Stage')),
            ('any', _('Tous types'))
        ],
        default='any',
        verbose_name=_("Type d'emploi recherché")
    )
    preferred_work_location = models.CharField(
        max_length=50,
        choices=[
            ('on_site', _('Sur site')),
            ('remote', _('Télétravail')),
            ('hybrid', _('Hybride')),
            ('any', _('Indifférent'))
        ],
        default='any',
        verbose_name=_("Mode de travail préféré")
    )
    years_of_experience = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Années d'expérience")
    )
    skills = models.ManyToManyField(
        'recruitment.Skill',
        blank=True,
        related_name='candidate_profiles',
        verbose_name=_("Compétences")
    )
    availability_date = models.DateField(
        blank=True,
        null=True,
        verbose_name=_("Disponibilité")
    )

    # Champs pour les notifications
    email_notifications = models.BooleanField(default=True, verbose_name=_("Notifications par e-mail"))
    application_updates = models.BooleanField(default=True, verbose_name=_("Mises à jour de candidature"))
    new_messages = models.BooleanField(default=True, verbose_name=_("Nouveaux messages"))
    interview_schedules = models.BooleanField(default=True, verbose_name=_("Planification d'entretien"))
    job_recommendations = models.BooleanField(default=True, verbose_name=_("Offres recommandées"))
    notification_frequency = models.CharField(
        max_length=20,
        choices=[
            ('immediately', _('Immédiatement')),
            ('daily', _('Résumé quotidien')),
            ('weekly', _('Résumé hebdomadaire')),
        ],
        default='immediately',
        verbose_name=_("Fréquence des notifications")
    )

    # Champs pour la confidentialité
    profile_visible = models.BooleanField(default=True, verbose_name=_("Profil visible"))
    share_contact_info = models.BooleanField(default=True, verbose_name=_("Partager coordonnées"))
    share_experience = models.BooleanField(default=True, verbose_name=_("Partager expérience"))
    share_education = models.BooleanField(default=True, verbose_name=_("Partager formation"))

    
    @property
    def gender_display(self):
        """Affiche le genre en format lisible"""
        return dict(self._meta.get_field('gender').choices).get(self.gender, '')
    
    @property
    def age(self):
        """Calcule l'âge du candidat"""
        if self.date_of_birth:
            today = timezone.now().date()
            return today.year - self.date_of_birth.year - (
                (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
            )
        return None
    
    def get_profile_completion_percentage(self):
        """
        Version simplifiée pour calculer le pourcentage de complétion
        """
        # Liste des champs de base à vérifier
        fields_to_check = [field for field in ['phone', 'photo', 'date_of_birth', 'address', 'city'] 
                          if hasattr(self, field)]
        
        # Compte combien de champs sont remplis
        completed_fields = sum(1 for field in fields_to_check if getattr(self, field))
        
        # Si aucun champ à vérifier, retourne 0%
        if not fields_to_check:
            return 0
        
        # Calcule le pourcentage
        percentage = int((completed_fields / len(fields_to_check)) * 100)
        return min(percentage, 100)  # Max 100%
    
    def get_completion_items(self):
        items = []
        
        items.append({
            'name': _('Téléphone'),
            'completed': bool(self.phone),
            'url': '#editProfileModal'
        })
        
        items.append({
            'name': _('Photo de profil'),
            'completed': bool(self.photo),
            'url': '#updatePhotoModal'
        })
        
        items.append({
            'name': _('Informations personnelles'),
            'completed': bool(self.gender and self.date_of_birth),
            'url': '#editPersonalInfoModal'
        })
        
        items.append({
            'name': _('Adresse'),
            'completed': bool(self.address and self.city and self.zip_code and self.country),
            'url': '#editPersonalInfoModal'
        })
        
        items.append({
            'name': _('CV'),
            'completed': hasattr(self.candidate_auth, 'documents') and self.candidate_auth.documents.filter(document_type='cv').exists(),
            'url': '#addDocumentModal'
        })
        
        items.append({
            'name': _('Expérience professionnelle'),
            'completed': hasattr(self.candidate_auth, 'experiences') and self.candidate_auth.experiences.exists(),
            'url': '#addExperienceModal'
        })
        
        items.append({
            'name': _('Formation'),
            'completed': hasattr(self.candidate_auth, 'education') and self.candidate_auth.education.exists(),
            'url': '#addEducationModal'
        })
        
        items.append({
            'name': _('Compétences'),
            'completed': hasattr(self, 'skills') and self.skills.exists(),
            'url': '#editSkillsModal'
        })
        
        return items
    
    def __str__(self):
        return f"Profil de {self.candidate_auth.email}"
    
    class Meta:
        verbose_name = _("Profil Candidat")
        verbose_name_plural = _("Profils Candidats")


class VerificationToken(models.Model):
    """Token pour vérifier l'email lors de l'inscription et lier une candidature"""
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    email = models.EmailField()
    candidate_id = models.IntegerField(null=True, blank=True)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    
    def __str__(self):
        return f"Token for {self.email}"
    
    def save(self, *args, **kwargs):
        if not self.expires_at:
            # Par défaut, expire après 7 jours
            self.expires_at = timezone.now() + timezone.timedelta(days=7)
        super().save(*args, **kwargs)
    
    @property
    def is_expired(self):
        return timezone.now() > self.expires_at
    
    class Meta:
        verbose_name = _("Token de vérification")
        verbose_name_plural = _("Tokens de vérification")


class CandidateSession(models.Model):
    """Session utilisateur pour les candidats"""
    candidate_auth = models.ForeignKey(
        CandidateAuth,
        on_delete=models.CASCADE,
        related_name='sessions',
        verbose_name=_("Candidat")
    )
    session_key = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    
    @classmethod
    def generate_session_key(cls):
        """Génère une clé de session unique"""
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(64))
    
    @classmethod
    def create_session(cls, candidate_auth, expiry_days=30):
        """Crée une nouvelle session pour un candidat"""
        # Supprimer les anciennes sessions qui pourraient exister
        cls.objects.filter(candidate_auth=candidate_auth).delete()
        
        session_key = cls.generate_session_key()
        expires_at = timezone.now() + timezone.timedelta(days=expiry_days)
        
        return cls.objects.create(
            candidate_auth=candidate_auth,
            session_key=session_key,
            expires_at=expires_at
        )
    
    @classmethod
    def get_candidate_from_session_key(cls, session_key):
        """Récupère un candidat à partir d'une clé de session"""
        try:
            session = cls.objects.get(
                session_key=session_key,
                expires_at__gt=timezone.now()
            )
            return session.candidate_auth
        except cls.DoesNotExist:
            return None
    
    class Meta:
        verbose_name = _("Session Candidat")
        verbose_name_plural = _("Sessions Candidats")


class SavedJob(models.Model):
    """Offres d'emploi sauvegardées par les candidats"""
    candidate_auth = models.ForeignKey(
        CandidateAuth,
        on_delete=models.CASCADE,
        related_name='saved_jobs',
        verbose_name=_("Candidat"),
        null=True,  # Ajoutez ceci temporairement
        blank=True  # Ajoutez ceci temporairement
    )
    recruitment = models.ForeignKey(
        Recruitment,
        on_delete=models.CASCADE,
        verbose_name=_("Recrutement")
    )
    date_saved = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Date de sauvegarde")
    )
    
    class Meta:
        unique_together = ('candidate_auth', 'recruitment')
        verbose_name = _("Offre sauvegardée")
        verbose_name_plural = _("Offres sauvegardées")
        
    def __str__(self):
        return f"{self.candidate_auth.email} - {self.recruitment.title}"


class ConversationThread(models.Model):
    """Thread de conversation entre un candidat et un recruteur"""
    candidate_auth = models.ForeignKey(
        CandidateAuth,
        on_delete=models.CASCADE,
        related_name='conversations',
        verbose_name=_("Candidat"),
        null=True,  # Ajoutez ceci temporairement
        blank=True  # Ajoutez ceci temporairement
    )
    recruitment = models.ForeignKey(
        Recruitment,
        on_delete=models.CASCADE,
        related_name='conversations',
        verbose_name=_("Recrutement")
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Date de création")
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Actif")
    )
    
    def __str__(self):
        return f"Conversation: {self.candidate_auth.email} - {self.recruitment.title}"
    
    class Meta:
        verbose_name = _("Conversation")
        verbose_name_plural = _("Conversations")


class Message(models.Model):
    """Message dans un thread de conversation"""
    thread = models.ForeignKey(
        ConversationThread,
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name=_("Conversation")
    )
    sender_type = models.CharField(
        max_length=10,
        choices=[('candidate', _('Candidat')), ('recruiter', _('Recruteur'))],
        verbose_name=_("Type d'expéditeur")
    )
    sender_id = models.IntegerField(verbose_name=_("ID de l'expéditeur"))
    content = models.TextField(verbose_name=_("Contenu"))
    timestamp = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Horodatage")
    )
    is_read = models.BooleanField(
        default=False,
        verbose_name=_("Lu")
    )
    
    def __str__(self):
        return f"{self.sender_type} message - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"
    
    class Meta:
        verbose_name = _("Message")
        verbose_name_plural = _("Messages")
        ordering = ['timestamp']

class CandidateExperience(models.Model):
    """Expérience professionnelle du candidat"""
    candidate_auth = models.ForeignKey(
        'CandidateAuth',
        on_delete=models.CASCADE,
        related_name='experiences',
        verbose_name=_("Candidat")
    )
    job_title = models.CharField(
        max_length=100,
        verbose_name=_("Intitulé du poste")
    )
    company = models.CharField(
        max_length=100,
        verbose_name=_("Entreprise")
    )
    industry = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_("Secteur d'activité")
    )
    start_date = models.DateField(
        verbose_name=_("Date de début")
    )
    end_date = models.DateField(
        blank=True,
        null=True,
        verbose_name=_("Date de fin")
    )
    currently_working = models.BooleanField(
        default=False,
        verbose_name=_("Emploi actuel")
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Description")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.job_title} à {self.company}"

    class Meta:
        verbose_name = _("Expérience professionnelle")
        verbose_name_plural = _("Expériences professionnelles")
        ordering = ['-start_date']


class CandidateEducation(models.Model):
    """Formation du candidat"""
    candidate_auth = models.ForeignKey(
        'CandidateAuth',
        on_delete=models.CASCADE,
        related_name='education',
        verbose_name=_("Candidat")
    )
    degree = models.CharField(
        max_length=100,
        verbose_name=_("Diplôme/Formation")
    )
    institution = models.CharField(
        max_length=100,
        verbose_name=_("Établissement")
    )
    field_of_study = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_("Domaine d'études")
    )
    start_year = models.IntegerField(
        validators=[MinValueValidator(1950), MaxValueValidator(2050)],
        verbose_name=_("Année de début")
    )
    end_year = models.IntegerField(
        validators=[MinValueValidator(1950), MaxValueValidator(2050)],
        blank=True,
        null=True,
        verbose_name=_("Année de fin")
    )
    currently_studying = models.BooleanField(
        default=False,
        verbose_name=_("En cours")
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Description")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.degree} - {self.institution}"

    class Meta:
        verbose_name = _("Formation")
        verbose_name_plural = _("Formations")
        ordering = ['-start_year']


def document_upload_path(instance, filename):
    """Définit le chemin d'upload des documents"""
    ext = filename.split('.')[-1]
    filename = f"{instance.document_type}_{uuid4().hex}.{ext}"
    return os.path.join(f"candidate_documents/{instance.candidate_auth.id}", filename)


class CandidateDocument(models.Model):
    """Documents du candidat (CV, lettres de motivation, certificats, etc.)"""
    DOCUMENT_TYPES = [
        ('cv', _('CV')),
        ('cover_letter', _('Lettre de motivation')),
        ('diploma', _('Diplôme')),
        ('certificate', _('Certificat')),
        ('other', _('Autre'))
    ]
    
    candidate_auth = models.ForeignKey(
        'CandidateAuth',
        on_delete=models.CASCADE,
        related_name='documents',
        verbose_name=_("Candidat")
    )
    title = models.CharField(
        max_length=100,
        verbose_name=_("Titre")
    )
    document_type = models.CharField(
        max_length=20,
        choices=DOCUMENT_TYPES,
        default='other',
        verbose_name=_("Type de document")
    )
    file = models.FileField(
        upload_to=document_upload_path,
        validators=[FileExtensionValidator(['pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png'])],
        verbose_name=_("Fichier")
    )
    uploaded_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Date d'ajout")
    )
    is_public = models.BooleanField(
        default=False,
        verbose_name=_("Visible par les recruteurs")
    )
    
    @property
    def file_size(self):
        """Retourne la taille du fichier en format lisible"""
        if self.file and hasattr(self.file, 'size'):
            return self.file.size
        return 0
        
    def __str__(self):
        return self.title

    class Meta:
        verbose_name = _("Document")
        verbose_name_plural = _("Documents")
        ordering = ['-uploaded_at']
