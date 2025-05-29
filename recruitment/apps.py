# recruitment/apps.py

from django.apps import AppConfig


class RecruitmentConfig(AppConfig):
    """
    AppConfig for the 'recruitment' app.

    This class represents the configuration for the 'recruitment' app. It provides
    the necessary settings and metadata for the app.

    Attributes:
        default_auto_field (str): The default auto field to use for model field IDs.
        name (str): The name of the app.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "recruitment"

    def ready(self):
        from django.urls import include, path

        from horilla.urls import urlpatterns
        from . import signals

        urlpatterns.append(
            path("recruitment/", include("recruitment.urls")),
        )
        
        # Initialiser le SkillZone Classifier
        try:
            from recruitment.utils.skillzone_classifier import get_skillzone_classifier
            import logging
            logger = logging.getLogger(__name__)
            get_skillzone_classifier()
            logger.info("SkillZone Classifier initialisé")
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Impossible d'initialiser SkillZone Classifier: {str(e)}")
        
        super().ready()