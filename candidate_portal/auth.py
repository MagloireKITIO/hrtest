# candidate_portal/auth.py
from django.shortcuts import redirect
from django.urls import reverse
from functools import wraps
from .models import CandidateSession
import logging

logger = logging.getLogger(__name__)

def authenticate_candidate(email, password):
    """
    Authentifie un candidat à partir de son email et mot de passe
    """
    from .models import CandidateAuth
    
    try:
        candidate = CandidateAuth.objects.get(email=email)
        if candidate.check_password(password):
            return candidate
    except CandidateAuth.DoesNotExist:
        return None
    
    return None

def login_candidate(request, candidate_auth):
    """
    Connecte un candidat en créant une session
    """
    session = CandidateSession.create_session(candidate_auth)
    request.session['candidate_session_key'] = session.session_key
    candidate_auth.last_login = session.created_at
    candidate_auth.save(update_fields=['last_login'])
    
    # Log pour le débogage
    logger.info(f"Candidat connecté: {candidate_auth.email}")
    
    return session

def logout_candidate(request):
    """
    Déconnecte un candidat en supprimant sa session
    """
    session_key = request.session.get('candidate_session_key')
    if session_key:
        try:
            session = CandidateSession.objects.get(session_key=session_key)
            logger.info(f"Déconnexion candidat: {session.candidate_auth.email}")
            session.delete()
        except CandidateSession.DoesNotExist:
            pass
        
        if 'candidate_session_key' in request.session:
            del request.session['candidate_session_key']

def get_current_candidate(request):
    """
    Récupère le candidat actuellement connecté
    """
    session_key = request.session.get('candidate_session_key')
    if not session_key:
        return None
    
    candidate = CandidateSession.get_candidate_from_session_key(session_key)
    return candidate

def candidate_login_required(function):
    """
    Décorateur pour protéger une vue et nécessiter qu'un candidat soit connecté
    """
    @wraps(function)
    def wrapper(request, *args, **kwargs):
        candidate = get_current_candidate(request)
        if candidate is None:
            return redirect(reverse('candidate_portal:login') + '?next=' + request.path)
        
        # Ajoute le candidat à la request pour faciliter l'accès
        request.candidate = candidate
        return function(request, *args, **kwargs)
    
    return wrapper