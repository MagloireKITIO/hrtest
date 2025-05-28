# candidate_portal/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags
from django.urls import reverse
from datetime import datetime, date
from django.views.decorators.csrf import csrf_protect
from .models import (
    CandidateAuth, CandidateProfile, CandidateExperience, 
    CandidateEducation, CandidateDocument, VerificationToken
)
from .forms import CandidateLoginForm, CandidateRegistrationForm
from .auth import (
    authenticate_candidate, login_candidate, 
    logout_candidate, candidate_login_required, 
    get_current_candidate
)
from recruitment.models import Candidate, Recruitment, Skill, Stage

@csrf_protect
def login_view(request):
    """Vue de connexion pour les candidats"""
    # Si un candidat est déjà connecté, rediriger vers le tableau de bord
    if get_current_candidate(request):
        return redirect('candidate_portal:dashboard')
    
    if request.method == 'POST':
        form = CandidateLoginForm(request.POST)
        if form.is_valid():
            candidate_auth = form.cleaned_data['candidate_auth']
            login_candidate(request, candidate_auth)
            
            next_url = request.GET.get('next')
            if next_url:
                return redirect(next_url)
            return redirect('candidate_portal:dashboard')
    else:
        form = CandidateLoginForm()
    
    return render(request, 'candidate_portal/login.html', {'form': form})

def logout_view(request):
    """Vue de déconnexion pour les candidats"""
    logout_candidate(request)
    messages.success(request, _("Vous avez été déconnecté avec succès."))
    return redirect('candidate_portal:login')

@csrf_protect
def register_view(request, token):
    """Vue d'inscription pour les candidats"""
    # Si un candidat est déjà connecté, rediriger vers le tableau de bord
    if get_current_candidate(request):
        return redirect('candidate_portal:dashboard')
    
    token_obj = get_object_or_404(VerificationToken, token=token, is_used=False)
    if token_obj.is_expired:
        messages.error(request, _("Ce lien d'inscription a expiré."))
        return redirect('recruitment:open-recruitments')
    
    if request.method == 'POST':
        form = CandidateRegistrationForm(request.POST, token=token_obj)
        if form.is_valid():
            candidate_auth = form.save()
            login_candidate(request, candidate_auth)
            messages.success(request, _("Compte créé avec succès. Vous êtes maintenant connecté."))
            return redirect('candidate_portal:dashboard')
    else:
        form = CandidateRegistrationForm(token=token_obj)
    
    return render(request, 'candidate_portal/register.html', {'form': form, 'token': token})

@candidate_login_required
def dashboard_view(request):
    """Tableau de bord principal du candidat"""
    candidate = request.candidate
    email = candidate.email
    applications = Candidate.objects.filter(email=email)
    
    # Statistiques pour le tableau de bord
    stats = {
        'total_applications': applications.count(),
        'in_progress': applications.filter(hired=False, canceled=False).count(),
        'hired': applications.filter(hired=True).count(),
        'rejected': applications.filter(canceled=True).count(),
    }
    
    # Candidatures récentes
    recent_applications = applications.order_by('-last_updated')[:5]
    
    # Offres recommandées (basées sur les postes précédents)
    job_positions = applications.values_list('job_position_id', flat=True).distinct()
    recommended_jobs = Recruitment.objects.filter(
        is_active=True, 
        closed=False,
        open_positions__in=job_positions
    ).distinct()[:3]
    
    context = {
        'stats': stats,
        'applications': recent_applications,
        'recommended_jobs': recommended_jobs,
    }
    
    return render(request, 'candidate_portal/dashboard.html', context)

@candidate_login_required
def applications_view(request):
    """Vue de toutes les candidatures du candidat"""
    candidate = request.candidate
    email = candidate.email
    applications = Candidate.objects.filter(email=email).order_by('-last_updated')
    
    context = {
        'applications': applications,
    }
    
    return render(request, 'candidate_portal/applications.html', context)

@candidate_login_required
def application_detail_view(request, application_id):
    """Vue détaillée d'une candidature"""
    candidate = request.candidate
    application = get_object_or_404(Candidate, id=application_id, email=candidate.email)
    
    context = {
        'application': application,
    }
    
    return render(request, 'candidate_portal/application_detail.html', context)

@candidate_login_required
def jobs_view(request):
    """Vue de toutes les offres d'emploi disponibles"""
    candidate = request.candidate
    
    # Obtenir le profil s'il existe
    profile = None
    try:
        profile = CandidateProfile.objects.get(candidate_auth=candidate)
        company = profile.company
    except CandidateProfile.DoesNotExist:
        company = None
    
    # Filtrer par entreprise si spécifiée
    jobs = Recruitment.objects.filter(is_active=True, closed=False)
    if company:
        jobs = jobs.filter(company_id=company)
    
    # Vérifier les offres sauvegardées
    saved_job_ids = []
    try:
        from .models import SavedJob
        saved_job_ids = SavedJob.objects.filter(
            candidate_auth=candidate
        ).values_list('recruitment_id', flat=True)
    except:
        pass
    
    context = {
        'jobs': jobs,
        'saved_job_ids': list(saved_job_ids),
    }
    
    return render(request, 'candidate_portal/jobs.html', context)

@candidate_login_required
@require_POST
def toggle_save_job(request, job_id):
    """Vue pour sauvegarder/désauvegarder une offre d'emploi"""
    candidate = request.candidate
    job = get_object_or_404(Recruitment, id=job_id)
    
    from .models import SavedJob
    saved_job = SavedJob.objects.filter(candidate_auth=candidate, recruitment=job)
    
    if saved_job.exists():
        saved_job.delete()
        messages.success(request, _("Offre d'emploi retirée des favoris."))
    else:
        SavedJob.objects.create(candidate_auth=candidate, recruitment=job)
        messages.success(request, _("Offre d'emploi ajoutée aux favoris."))
    
    return redirect('candidate_portal:jobs')

@candidate_login_required
def messages_view(request):
    """Vue des messages du candidat"""
    candidate = request.candidate
    
    from .models import ConversationThread
    conversations = ConversationThread.objects.filter(
        candidate_auth=candidate,
        is_active=True
    ).order_by('-created_at')
    
    # Ajouter le nombre de messages non lus pour chaque conversation
    from django.db.models import Count, Q
    from .models import Message
    conversations = conversations.annotate(
        unread_count=Count(
            'messages',
            filter=Q(messages__is_read=False, messages__sender_type='recruiter')
        )
    )
    
    context = {
        'conversations': conversations,
    }
    
    return render(request, 'candidate_portal/messages.html', context)

@candidate_login_required
def conversation_view(request, thread_id):
    """Vue d'une conversation spécifique"""
    candidate = request.candidate
    
    from .models import ConversationThread, Message
    thread = get_object_or_404(
        ConversationThread,
        id=thread_id,
        candidate_auth=candidate,
        is_active=True
    )
    
    messages_list = thread.messages.all().order_by('timestamp')
    
    # Marquer les messages comme lus
    messages_list.filter(sender_type='recruiter', is_read=False).update(is_read=True)
    
    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        
        if content:
            Message.objects.create(
                thread=thread,
                sender_type='candidate',
                sender_id=candidate.id,
                content=content
            )
            
            return redirect('candidate_portal:conversation', thread_id=thread.id)
    
    context = {
        'thread': thread,
        'messages': messages_list,
    }
    
    return render(request, 'candidate_portal/conversation.html', context)

@candidate_login_required
def profile_view(request):
    """Vue du profil du candidat"""
    candidate = request.candidate
    
    # Récupération du profil s'il existe
    try:
        profile = CandidateProfile.objects.get(candidate_auth=candidate)
    except CandidateProfile.DoesNotExist:
        # Si le profil n'existe pas encore, initialiser une variable pour éviter les erreurs
        messages.warning(request, _("Veuillez compléter votre profil pour accéder à toutes les fonctionnalités."))
        profile = None
    
    # Récupération des données associées si le profil existe
    if profile:
        experiences = CandidateExperience.objects.filter(candidate_auth=candidate).order_by('-start_date')
        education = CandidateEducation.objects.filter(candidate_auth=candidate).order_by('-start_year')
        documents = CandidateDocument.objects.filter(candidate_auth=candidate).order_by('-uploaded_at')
        skills = profile.skills.all() if hasattr(profile, 'skills') else []
        
        # Calcul du pourcentage de complétion du profil
        completion_percentage = profile.get_profile_completion_percentage() if hasattr(profile, 'get_profile_completion_percentage') else 0
        completion_items = profile.get_completion_items() if hasattr(profile, 'get_completion_items') else []
    else:
        # Valeurs par défaut si le profil n'existe pas
        experiences = []
        education = []
        documents = []
        skills = []
        completion_percentage = 0
        completion_items = []
    
    # Définition de la classe CSS basée sur le pourcentage
    if completion_percentage < 40:
        completion_class = 'danger'
    elif completion_percentage < 70:
        completion_class = 'warning'
    else:
        completion_class = 'success'
        
    # Récupérer toutes les compétences disponibles
    all_skills = Skill.objects.all().order_by('title')
    
    context = {
        'candidate': candidate,
        'profile': profile,
        'experiences': experiences,
        'education': education,
        'documents': documents,
        'skills': skills,
        'all_skills': all_skills,
        'completion_percentage': completion_percentage,
        'completion_items': completion_items,
        'completion_class': completion_class,
    }
    
    return render(request, 'candidate_portal/profile.html', context)

@candidate_login_required
@require_POST
def update_profile(request):
    """Mettre à jour les informations de base du profil"""
    candidate = request.candidate
    
    # Validation de base
    first_name = request.POST.get('first_name')
    last_name = request.POST.get('last_name')
    phone = request.POST.get('phone')
    
    if not first_name or not last_name:
        messages.error(request, _("Les champs prénom et nom sont obligatoires."))
        return redirect('candidate_portal:profile')
    
    # Mise à jour du candidat
    candidate.first_name = first_name
    candidate.last_name = last_name
    candidate.save()
    
    # Mise à jour du profil s'il existe
    try:
        profile = CandidateProfile.objects.get(candidate_auth=candidate)
        profile.phone = phone
        profile.save()
        messages.success(request, _("Votre profil a été mis à jour avec succès."))
    except CandidateProfile.DoesNotExist:
        messages.warning(request, _("Votre nom a été mis à jour. Veuillez compléter votre profil."))
    
    return redirect('candidate_portal:profile')

@candidate_login_required
@require_POST
def update_personal_info(request):
    """Mettre à jour les informations personnelles"""
    candidate = request.candidate
    
    # Récupération des données du formulaire
    gender = request.POST.get('gender')
    date_of_birth = request.POST.get('date_of_birth')
    address = request.POST.get('address')
    city = request.POST.get('city')
    zip_code = request.POST.get('zip_code')
    country = request.POST.get('country')
    
    # Mise à jour du profil s'il existe
    try:
        profile = CandidateProfile.objects.get(candidate_auth=candidate)
        
        if gender:
            profile.gender = gender
        if date_of_birth:
            profile.date_of_birth = date_of_birth
        
        profile.address = address
        profile.city = city
        profile.zip_code = zip_code
        profile.country = country
        
        profile.save()
        
        messages.success(request, _("Vos informations personnelles ont été mises à jour."))
    except CandidateProfile.DoesNotExist:
        messages.error(request, _("Veuillez d'abord compléter votre profil."))
    
    return redirect('candidate_portal:profile')

@candidate_login_required
@require_POST
def update_photo(request):
    """Mettre à jour la photo de profil"""
    candidate = request.candidate
    
    if 'photo' in request.FILES:
        photo = request.FILES['photo']
        
        # Validation du fichier (type, taille)
        if photo.size > 2 * 1024 * 1024:  # 2 MB
            messages.error(request, _("La taille de l'image ne doit pas dépasser 2 MB."))
            return redirect('candidate_portal:profile')
            
        # Vérifier l'extension du fichier
        valid_extensions = ['jpg', 'jpeg', 'png']
        extension = photo.name.split('.')[-1].lower()
        
        if extension not in valid_extensions:
            messages.error(request, _("Le format de l'image doit être JPG ou PNG."))
            return redirect('candidate_portal:profile')
            
        # Mettre à jour la photo
        try:
            profile = CandidateProfile.objects.get(candidate_auth=candidate)
            
            # Supprimer l'ancienne photo si elle existe
            if profile.photo:
                try:
                    old_photo_path = profile.photo.path
                    import os
                    if os.path.isfile(old_photo_path):
                        os.remove(old_photo_path)
                except:
                    pass
                    
            profile.photo = photo
            profile.save()
            
            messages.success(request, _("Votre photo de profil a été mise à jour."))
        except CandidateProfile.DoesNotExist:
            messages.error(request, _("Veuillez d'abord compléter votre profil."))
    else:
        messages.error(request, _("Aucune photo n'a été fournie."))
        
    return redirect('candidate_portal:profile')

@candidate_login_required
@require_POST
def add_experience(request):
    """Ajouter une expérience professionnelle"""
    candidate = request.candidate
    
    # Récupération des données du formulaire
    job_title = request.POST.get('job_title')
    company = request.POST.get('company')
    industry = request.POST.get('industry')
    start_date_str = request.POST.get('start_date')
    end_date_str = request.POST.get('end_date')
    currently_working = 'currently_working' in request.POST
    description = request.POST.get('description')
    
    # Validation des champs obligatoires
    if not job_title or not company or not start_date_str:
        messages.error(request, _("Veuillez remplir tous les champs obligatoires."))
        return redirect('candidate_portal:profile')
    
    # Correction du format de date
    try:
        # Nettoyer les espaces insécables et autres caractères spéciaux
        start_date_str = start_date_str.strip().replace('\xa0', '')
        
        # Si la date est au format AAAA-MM, ajouter le jour (01)
        if len(start_date_str) == 7 and '-' in start_date_str:
            start_date_str += '-01'
            
        # Convertir en objet date
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        
        # Traiter la date de fin seulement si elle est fournie et que "actuellement" n'est pas coché
        end_date = None
        if end_date_str and not currently_working:
            end_date_str = end_date_str.strip().replace('\xa0', '')
            if len(end_date_str) == 7 and '-' in end_date_str:
                end_date_str += '-01'
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    except ValueError as e:
        messages.error(request, _(f"Format de date invalide: {e}"))
        return redirect('candidate_portal:profile')
    
    # Récupérer le profil existant
    try:
        profile = CandidateProfile.objects.get(candidate_auth=candidate)
        
        # Création de l'expérience
        experience = CandidateExperience(
            candidate_auth=candidate,
            job_title=job_title,
            company=company,
            industry=industry,
            start_date=start_date,
            end_date=end_date,
            currently_working=currently_working,
            description=description
        )
        
        experience.save()
        messages.success(request, _("Votre expérience professionnelle a été ajoutée."))
    except CandidateProfile.DoesNotExist:
        messages.error(request, _("Veuillez d'abord compléter votre profil."))
        
    return redirect('candidate_portal:profile')

@candidate_login_required
@require_POST
def edit_experience(request, experience_id):
    """Modifier une expérience professionnelle"""
    candidate = request.candidate
    
    # Récupération de l'expérience
    experience = get_object_or_404(CandidateExperience, id=experience_id, candidate_auth=candidate)
    
    # Récupération des données du formulaire
    job_title = request.POST.get('job_title')
    company = request.POST.get('company')
    industry = request.POST.get('industry')
    start_date_str = request.POST.get('start_date')
    end_date_str = request.POST.get('end_date')
    currently_working = 'currently_working' in request.POST
    description = request.POST.get('description')
    
    # Validation des champs obligatoires
    if not job_title or not company or not start_date_str:
        messages.error(request, _("Veuillez remplir tous les champs obligatoires."))
        return redirect('candidate_portal:profile')

    # Correction du format de date
    try:
        # Nettoyer les espaces insécables et autres caractères spéciaux
        start_date_str = start_date_str.strip().replace('\xa0', '')
        
        # Si la date est au format AAAA-MM, ajouter le jour (01)
        if len(start_date_str) == 7 and '-' in start_date_str:
            start_date_str += '-01'
            
        # Convertir en objet date
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        
        # Traiter la date de fin seulement si elle est fournie et que "actuellement" n'est pas coché
        end_date = None
        if end_date_str and not currently_working:
            end_date_str = end_date_str.strip().replace('\xa0', '')
            if len(end_date_str) == 7 and '-' in end_date_str:
                end_date_str += '-01'
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    except ValueError as e:
        messages.error(request, _(f"Format de date invalide: {e}"))
        return redirect('candidate_portal:profile')
    
    # Mise à jour de l'expérience
    experience.job_title = job_title
    experience.company = company
    experience.industry = industry
    experience.start_date = start_date
    experience.end_date = end_date
    experience.currently_working = currently_working
    experience.description = description
    
    try:
        experience.save()
        messages.success(request, _("Votre expérience professionnelle a été mise à jour."))
    except Exception as e:
        messages.error(request, str(e))
    
    return redirect('candidate_portal:profile')

@candidate_login_required
def get_experience(request, experience_id):
    """API pour récupérer les détails d'une expérience professionnelle"""
    candidate = request.candidate
    
    try:
        experience = CandidateExperience.objects.get(id=experience_id, candidate_auth=candidate)
        data = {
            'id': experience.id,
            'job_title': experience.job_title,
            'company': experience.company,
            'industry': experience.industry,
            'start_date': experience.start_date.isoformat() if experience.start_date else None,
            'end_date': experience.end_date.isoformat() if experience.end_date else None,
            'currently_working': experience.currently_working,
            'description': experience.description
        }
        return JsonResponse(data)
    except CandidateExperience.DoesNotExist:
        return JsonResponse({'error': 'Expérience non trouvée'}, status=404)

@candidate_login_required
def get_education(request, education_id):
    """API pour récupérer les détails d'une formation"""
    candidate = request.candidate
    
    try:
        education = CandidateEducation.objects.get(id=education_id, candidate_auth=candidate)
        data = {
            'id': education.id,
            'degree': education.degree,
            'institution': education.institution,
            'field_of_study': education.field_of_study,
            'start_year': education.start_year,
            'end_year': education.end_year,
            'currently_studying': education.currently_studying,
            'description': education.description
        }
        return JsonResponse(data)
    except CandidateEducation.DoesNotExist:
        return JsonResponse({'error': 'Formation non trouvée'}, status=404)

@candidate_login_required
@require_POST
def create_skill(request):
    """API pour créer une nouvelle compétence"""
    try:
        # Vérifie si la requête contient du JSON
        if request.content_type == 'application/json':
            import json
            data = json.loads(request.body)
            title = data.get('title', '').strip().capitalize()
        else:
            # Fallback pour les requêtes form-data
            title = request.POST.get('title', '').strip().capitalize()
        
        if not title:
            return JsonResponse({'error': 'Le titre de la compétence est requis'}, status=400)
        
        # Créer ou récupérer la compétence
        skill, created = Skill.objects.get_or_create(title=title)
        
        # Ajouter au profil du candidat
        try:
            profile = CandidateProfile.objects.get(candidate_auth=request.candidate)
            profile.skills.add(skill)
        except CandidateProfile.DoesNotExist:
            return JsonResponse({'error': 'Profil candidat introuvable'}, status=404)
        
        return JsonResponse({'id': skill.id, 'title': skill.title})
    except Exception as e:
        # Log l'erreur pour le débogage
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Erreur lors de la création d'une compétence: {str(e)}")
        
        # Retourner une réponse d'erreur
        return JsonResponse({'error': 'Une erreur est survenue: ' + str(e)}, status=500)
    

@candidate_login_required
@require_POST
def delete_experience(request, experience_id):
    """Supprimer une expérience professionnelle"""
    candidate = request.candidate
    
    # Récupération de l'expérience
    experience = get_object_or_404(CandidateExperience, id=experience_id, candidate_auth=candidate)
    
    try:
        experience.delete()
        messages.success(request, _("Votre expérience professionnelle a été supprimée."))
    except Exception as e:
        messages.error(request, str(e))
    
    return redirect('candidate_portal:profile')

@candidate_login_required
@require_POST
def add_education(request):
    """Ajouter une formation"""
    candidate = request.candidate
    
    # Récupération des données du formulaire
    degree = request.POST.get('degree')
    institution = request.POST.get('institution')
    field_of_study = request.POST.get('field_of_study')
    start_year = request.POST.get('start_year')
    end_year = request.POST.get('end_year')
    currently_studying = 'currently_studying' in request.POST
    description = request.POST.get('description')
    
    # Validation des champs obligatoires
    if not degree or not institution or not start_year:
        messages.error(request, _("Veuillez remplir tous les champs obligatoires."))
        return redirect('candidate_portal:profile')
    
    # Si actuellement en formation, pas d'année de fin
    if currently_studying:
        end_year = None
    
    # Création de la formation
    try:
        education = CandidateEducation(
            candidate_auth=candidate,
            degree=degree,
            institution=institution,
            field_of_study=field_of_study,
            start_year=start_year,
            end_year=end_year,
            currently_studying=currently_studying,
            description=description
        )
        
        education.save()
        messages.success(request, _("Votre formation a été ajoutée."))
    except Exception as e:
        messages.error(request, str(e))
    
    return redirect('candidate_portal:profile')

@candidate_login_required
@require_POST
def edit_education(request, education_id):
    """Modifier une formation"""
    candidate = request.candidate
    
    # Récupération de la formation
    education = get_object_or_404(CandidateEducation, id=education_id, candidate_auth=candidate)
    
    # Récupération des données du formulaire
    degree = request.POST.get('degree')
    institution = request.POST.get('institution')
    field_of_study = request.POST.get('field_of_study')
    start_year = request.POST.get('start_year')
    end_year = request.POST.get('end_year')
    currently_studying = 'currently_studying' in request.POST
    description = request.POST.get('description')
    
    # Validation des champs obligatoires
    if not degree or not institution or not start_year:
        messages.error(request, _("Veuillez remplir tous les champs obligatoires."))
        return redirect('candidate_portal:profile')
    
    # Si actuellement en formation, pas d'année de fin
    if currently_studying:
        end_year = None
    
    # Mise à jour de la formation
    education.degree = degree
    education.institution = institution
    education.field_of_study = field_of_study
    education.start_year = start_year
    education.end_year = end_year
    education.currently_studying = currently_studying
    education.description = description
    
    try:
        education.save()
        messages.success(request, _("Votre formation a été mise à jour."))
    except Exception as e:
        messages.error(request, str(e))
    
    return redirect('candidate_portal:profile')

@candidate_login_required
@require_POST
def delete_education(request, education_id):
    """Supprimer une formation"""
    candidate = request.candidate
    
    # Récupération de la formation
    education = get_object_or_404(CandidateEducation, id=education_id, candidate_auth=candidate)
    
    try:
        education.delete()
        messages.success(request, _("Votre formation a été supprimée."))
    except Exception as e:
        messages.error(request, str(e))
    
    return redirect('candidate_portal:profile')

@candidate_login_required
@require_POST
def add_document(request):
    """Ajouter un document"""
    candidate = request.candidate
    
    # Vérification du fichier
    if 'file' not in request.FILES:
        messages.error(request, _("Veuillez sélectionner un fichier."))
        return redirect('candidate_portal:profile')
    
    # Récupération des données du formulaire
    title = request.POST.get('title')
    document_type = request.POST.get('document_type')
    file = request.FILES['file']
    
    # Validation du fichier (taille)
    if file.size > 5 * 1024 * 1024:  # 5 MB
        messages.error(request, _("La taille du fichier ne doit pas dépasser 5 MB."))
        return redirect('candidate_portal:profile')
    
    # Création du document
    try:
        document = CandidateDocument(
            candidate_auth=candidate,
            title=title,
            document_type=document_type,
            file=file
        )
        
        document.save()
        messages.success(request, _("Votre document a été ajouté."))
    except Exception as e:
        messages.error(request, str(e))
    
    return redirect('candidate_portal:profile')

@candidate_login_required
@require_POST
def delete_document(request, document_id):
    """Supprimer un document"""
    candidate = request.candidate
    
    # Récupération du document
    document = get_object_or_404(CandidateDocument, id=document_id, candidate_auth=candidate)
    
    try:
        # Supprimer le fichier physique
        if document.file:
            try:
                import os
                if os.path.isfile(document.file.path):
                    os.remove(document.file.path)
            except:
                pass
        
        # Supprimer l'enregistrement
        document.delete()
        messages.success(request, _("Votre document a été supprimé."))
    except Exception as e:
        messages.error(request, str(e))
    
    return redirect('candidate_portal:profile')

@candidate_login_required
@require_POST
def update_skills(request):
    """Mettre à jour les compétences"""
    candidate = request.candidate
    
    # Récupération du profil
    try:
        profile = CandidateProfile.objects.get(candidate_auth=candidate)
        
        # Récupération des IDs de compétences sélectionnées
        skill_ids = request.POST.getlist('skills', [])
        
        # Ajout d'une nouvelle compétence si fournie
        new_skill = request.POST.get('new_skill', '').strip()
        if new_skill:
            skill, created = Skill.objects.get_or_create(title=new_skill.capitalize())
            skill_ids.append(str(skill.id))
        
        # Mise à jour des compétences
        try:
            with transaction.atomic():
                # Vider les compétences actuelles
                profile.skills.clear()
                
                # Ajouter les nouvelles compétences
                for skill_id in skill_ids:
                    try:
                        skill = Skill.objects.get(id=skill_id)
                        profile.skills.add(skill)
                    except Skill.DoesNotExist:
                        continue
                
                messages.success(request, _("Vos compétences ont été mises à jour."))
        except Exception as e:
            messages.error(request, str(e))
    except CandidateProfile.DoesNotExist:
        messages.error(request, _("Veuillez d'abord compléter votre profil."))
    
    return redirect('candidate_portal:profile')

@candidate_login_required
def get_skill_suggestions(request):
    """API pour les suggestions de compétences (pour l'autocomplétion)"""
    query = request.GET.get('q', '').lower()
    
    if not query or len(query) < 2:
        return JsonResponse({'results': []})
    
    # Recherche des compétences correspondantes
    skills = Skill.objects.filter(title__icontains=query).values('id', 'title')[:10]
    
    results = [{'id': skill['id'], 'text': skill['title']} for skill in skills]
    
    return JsonResponse({'results': results})

@csrf_protect
def forgot_password(request):
    """Vue pour réinitialiser le mot de passe"""
    if request.method == 'POST':
        email = request.POST.get('email')
        try:
            candidate = CandidateAuth.objects.get(email=email)
            # Créer un token de réinitialisation
            token = VerificationToken.objects.create(
                email=email,
                expires_at=timezone.now() + timezone.timedelta(days=1)
            )
            
            # Construire l'URL de réinitialisation
            reset_url = request.build_absolute_uri(
                reverse('candidate_portal:reset_password', args=[token.token])
            )
            
            # Préparer le contenu de l'email
            subject = _("Réinitialisation de votre mot de passe")
            html_message = render_to_string('candidate_portal/emails/reset_password_email.html', {
                'first_name': candidate.first_name,
                'reset_url': reset_url,
                'valid_hours': 24  # Validité du lien en heures
            })
            plain_message = strip_tags(html_message)
            
            # Envoyer l'email
            send_mail(
                subject,
                plain_message,
                settings.DEFAULT_FROM_EMAIL,
                [email],
                html_message=html_message,
                fail_silently=False,
            )
            
            messages.success(
                request, 
                _("Si un compte existe avec cette adresse, un email de réinitialisation a été envoyé.")
            )
            return redirect('candidate_portal:login')
            
        except CandidateAuth.DoesNotExist:
            # Ne pas indiquer que l'email n'existe pas (sécurité)
            messages.success(
                request, 
                _("Si un compte existe avec cette adresse, un email de réinitialisation a été envoyé.")
            )
            return redirect('candidate_portal:login')
    
    return render(request, 'candidate_portal/forgot_password.html')

@csrf_protect
def reset_password(request, token):
    """Vue pour définir un nouveau mot de passe"""
    token_obj = get_object_or_404(
        VerificationToken, 
        token=token, 
        is_used=False
    )
    
    if token_obj.is_expired:
        messages.error(request, _("Ce lien de réinitialisation a expiré."))
        return redirect('candidate_portal:forgot_password')
    
    if request.method == 'POST':
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        
        if not password1 or not password2:
            messages.error(request, _("Veuillez remplir tous les champs."))
        elif password1 != password2:
            messages.error(request, _("Les mots de passe ne correspondent pas."))
        else:
            try:
                candidate = CandidateAuth.objects.get(email=token_obj.email)
                candidate.set_password(password1)
                candidate.save()
                
                # Marquer le token comme utilisé
                token_obj.is_used = True
                token_obj.save()
                
                messages.success(
                    request, 
                    _("Votre mot de passe a été réinitialisé avec succès. Vous pouvez maintenant vous connecter.")
                )
                return redirect('candidate_portal:login')
            except CandidateAuth.DoesNotExist:
                messages.error(request, _("Aucun compte trouvé avec cette adresse email."))
    
    return render(request, 'candidate_portal/reset_password.html', {'token': token})


@candidate_login_required
def update_password(request):
    """
    Vue pour mettre à jour le mot de passe du candidat
    """
    if request.method == "POST":
        current_password = request.POST.get("current_password")
        new_password = request.POST.get("new_password")
        confirm_password = request.POST.get("confirm_password")
        
        candidate = request.candidate
        
        # Vérifier le mot de passe actuel
        if not candidate.check_password(current_password):
            messages.error(request, _("Le mot de passe actuel est incorrect."))
            return redirect("candidate_portal:settings")
        
        # Vérifier que les nouveaux mots de passe correspondent
        if new_password != confirm_password:
            messages.error(request, _("Les nouveaux mots de passe ne correspondent pas."))
            return redirect("candidate_portal:settings")
        
        # Mettre à jour le mot de passe
        candidate.set_password(new_password)
        candidate.save()
        
        messages.success(request, _("Votre mot de passe a été mis à jour avec succès."))
        logout_candidate(request)  # Déconnecter l'utilisateur pour qu'il se reconnecte avec son nouveau mot de passe
        return redirect("candidate_portal:login")
    
    return redirect("candidate_portal:settings")


@candidate_login_required
def update_notifications(request):
    """
    Vue pour mettre à jour les préférences de notification
    """
    if request.method == "POST":
        profile = CandidateProfile.objects.get(candidate_auth=request.candidate)
        
        # Mettre à jour les préférences
        profile.email_notifications = 'email_notifications' in request.POST
        profile.application_updates = 'application_updates' in request.POST
        profile.new_messages = 'new_messages' in request.POST
        profile.interview_schedules = 'interview_schedules' in request.POST
        profile.job_recommendations = 'job_recommendations' in request.POST
        profile.notification_frequency = request.POST.get('notification_frequency', 'immediately')
        
        profile.save()
        
        messages.success(request, _("Vos préférences de notification ont été mises à jour."))
    
    return redirect("candidate_portal:settings")


@candidate_login_required
def update_privacy(request):
    """
    Vue pour mettre à jour les paramètres de confidentialité
    """
    if request.method == "POST":
        profile = CandidateProfile.objects.get(candidate_auth=request.candidate)
        
        # Mettre à jour les préférences de confidentialité
        profile.profile_visible = 'profile_visible' in request.POST
        profile.share_contact_info = 'share_contact_info' in request.POST
        profile.share_experience = 'share_experience' in request.POST
        profile.share_education = 'share_education' in request.POST
        
        profile.save()
        
        messages.success(request, _("Vos paramètres de confidentialité ont été mis à jour."))
    
    return redirect("candidate_portal:settings")


@candidate_login_required
def delete_account(request):
    """
    Vue pour supprimer le compte candidat
    """
    if request.method == "POST":
        candidate = request.candidate
        
        # Désactiver le compte plutôt que de le supprimer complètement
        candidate.is_active = False
        candidate.save()
        
        logout_candidate(request)
        messages.success(request, _("Votre compte a été supprimé avec succès. Nous espérons vous revoir bientôt."))
        return redirect("open-recruitments")
    
    return redirect("candidate_portal:settings")


@candidate_login_required
def settings_view(request):
    """
    Vue pour afficher la page des paramètres
    """
    candidate = request.candidate
    
    try:
        profile = CandidateProfile.objects.get(candidate_auth=candidate)
    except CandidateProfile.DoesNotExist:
        profile = None
    
    return render(
        request,
        "candidate_portal/settings.html",
        {
            "candidate": candidate,
            "profile": profile,
        }
    )


@candidate_login_required
def withdraw_application(request, application_id):
    """
    Vue pour retirer une candidature
    """
    if request.method == "POST":
        candidate = request.candidate
        application = get_object_or_404(Candidate, id=application_id, email=candidate.email)
        
        # Trouver l'étape "cancelled" ou en créer une
        cancelled_stage = Stage.objects.filter(
            recruitment_id=application.recruitment_id, 
            stage_type="cancelled"
        ).first()
        
        if not cancelled_stage:
            # Créer une étape "cancelled" si elle n'existe pas
            cancelled_stage = Stage.objects.create(
                recruitment_id=application.recruitment_id,
                stage="Candidature retirée",
                stage_type="cancelled",
                sequence=99
            )
        
        # Mettre à jour la candidature
        application.stage_id = cancelled_stage
        application.canceled = True
        application.save()
        
        messages.success(request, _("Votre candidature a été retirée avec succès."))
    
    return redirect("candidate_portal:applications")