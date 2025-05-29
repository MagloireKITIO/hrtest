# recruitment/signals.py - Modifier le fichier existant

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
import asyncio
import logging

from .models import Candidate
from .utils.cv_analysis import cv_analysis_manager
from .utils.skillzone_classifier import get_skillzone_classifier

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Candidate)
def analyze_new_candidate(sender, instance, created, **kwargs):
    """Déclenche l'analyse automatique et la classification pour les nouveaux candidats"""
    if created:  # Uniquement pour les nouveaux candidats
        try:
            # Créer une nouvelle boucle d'événements pour l'analyse asynchrone
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Ajouter le candidat à la file d'analyse CV (existant)
            loop.run_until_complete(cv_analysis_manager.add_to_queue(instance))
            
            # Ajouter la classification SkillZone automatique
            if hasattr(settings, 'ENABLE_AUTO_SKILLZONE_CLASSIFICATION') and settings.ENABLE_AUTO_SKILLZONE_CLASSIFICATION:
                classifier = get_skillzone_classifier()
                # Déterminer la source selon l'origine du candidat
                source_tag = 'application' if instance.source == 'application' else 'manual'
                
                # Lancer la classification de manière asynchrone
                loop.run_until_complete(
                    classifier.classify_candidate(instance, source_tag=source_tag)
                )
                logger.info(f"Classification SkillZone lancée pour candidat {instance.id}")
            
        except Exception as e:
            logger.error(f"Erreur lors de l'analyse automatique du candidat {instance.id}: {str(e)}")
        finally:
            loop.close()