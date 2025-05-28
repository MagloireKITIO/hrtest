# Dans recruitment/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from responses import logger
from .models import Candidate
from .utils.cv_analysis import cv_analysis_manager
import asyncio


@receiver(post_save, sender=Candidate)
def analyze_new_candidate(sender, instance, created, **kwargs):
    """Déclenche l'analyse automatique pour les nouveaux candidats"""
    if created:  # Uniquement pour les nouveaux candidats
        try:
            # Créer une nouvelle boucle d'événements pour l'analyse asynchrone
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Ajouter le candidat à la file d'analyse
            loop.run_until_complete(cv_analysis_manager.add_to_queue(instance))
            
        except Exception as e:
            logger.error(f"Erreur lors de l'analyse automatique du candidat {instance.id}: {str(e)}")
        finally:
            loop.close()