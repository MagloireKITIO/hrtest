# candidate_portal/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from recruitment.models import Candidate
from .models import VerificationToken
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.utils import timezone

@receiver(post_save, sender=Candidate)
def create_verification_token(sender, instance, created, **kwargs):
    """Crée un token de vérification quand une candidature est soumise"""
    if created:
        # Créer un token unique pour cette candidature
        token = VerificationToken.objects.create(
            email=instance.email,
            candidate_id=instance.id,
            expires_at=timezone.now() + timezone.timedelta(days=7)
        )
        
        # Envoyer l'email avec le lien de création de compte
        send_account_creation_email(instance, token)

def send_account_creation_email(candidate, token):
    """Envoie un email avec un lien pour créer un compte"""
    subject = 'Suivez votre candidature en créant un compte'
    register_url = f"{settings.BASE_URL}/candidate-portal/register/{token.token}/"
    
    context = {
        'candidate': candidate,
        'register_url': register_url,
        'token': token,
    }
    
    html_content = render_to_string('candidate_portal/emails/create_account.html', context)
    text_content = strip_tags(html_content)
    
    email = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[candidate.email]
    )
    
    email.attach_alternative(html_content, "text/html")
    email.send()