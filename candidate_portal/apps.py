# candidate_portal/apps.py
from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

class CandidatePortalConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'candidate_portal'
    verbose_name = _("Portail Candidat")