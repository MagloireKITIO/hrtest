# horilla_automations/apps.py
from django.apps import AppConfig

class HorillaAutomationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "horilla_automations"

    def ready(self) -> None:
        ready = super().ready()
        
        # Ne plus manipuler MODEL_CHOICES ici
        # Les choix sont maintenant entièrement dynamiques
        
        try:
            from horilla_automations.signals import start_automation
            start_automation()
        except Exception as e:
            # Les migrations ne sont pas encore appliquées ou autre erreur
            print(f"Warning: Could not start automations: {e}")
            pass
            
        return ready