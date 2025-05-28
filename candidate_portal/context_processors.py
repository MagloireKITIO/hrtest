# candidate_portal/context_processors.py

from .models import CandidateProfile
from .auth import get_current_candidate

def profile_completion(request):
    """
    Context processor qui ajoute le pourcentage de complétion du profil
    au contexte global de tous les templates.
    """
    context = {
        'completion_percentage': 0,
    }
    
    # Vérifier si l'utilisateur est connecté
    candidate = get_current_candidate(request)
    if not candidate:
        return context
    
    # Récupérer le profil s'il existe
    try:
        profile = CandidateProfile.objects.get(candidate_auth=candidate)
        # Calculer le pourcentage de complétion seulement si la méthode existe
        if hasattr(profile, 'get_profile_completion_percentage'):
            context['completion_percentage'] = profile.get_profile_completion_percentage()
        else:
            # Calcul de base si la méthode n'existe pas
            # On peut adapter cette logique en fonction des champs importants pour vous
            completed_fields = 0
            total_fields = 4  # Exemple: photo, phone, gender, birth_date
            
            if hasattr(profile, 'photo') and profile.photo:
                completed_fields += 1
            if hasattr(profile, 'phone') and profile.phone:
                completed_fields += 1
            if hasattr(profile, 'gender') and profile.gender:
                completed_fields += 1
            if hasattr(profile, 'date_of_birth') and profile.date_of_birth:
                completed_fields += 1
                
            context['completion_percentage'] = int((completed_fields / total_fields) * 100)
    except CandidateProfile.DoesNotExist:
        # Pas de profil, laissez le pourcentage à 0
        pass
    
    return context