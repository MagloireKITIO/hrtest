# recruitment/views/skillzone_import.py - Version corrigée sans Redis

import os
import json
import logging
from uuid import uuid4
from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.utils.translation import gettext_lazy as _
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db import transaction
from django.utils import timezone
from asgiref.sync import async_to_sync

from horilla.decorators import login_required, permission_required, hx_request_required
from recruitment.models import (
    Candidate, SkillZone, SkillZoneImportHistory, 
    Recruitment, Stage
)
from recruitment.utils.skillzone_classifier import get_skillzone_classifier
from recruitment.forms import SkillZoneBulkImportForm

logger = logging.getLogger(__name__)


@login_required
@permission_required("recruitment.add_skillzonecandidate")
def skillzone_bulk_import(request):
    """Vue principale pour l'import en masse de CV"""
    if request.method == "POST":
        form = SkillZoneBulkImportForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                # Créer l'historique d'import
                import_history = SkillZoneImportHistory.objects.create(
                    initiated_by=request.user.employee_get,
                    company_id=request.user.employee_get.company_id,
                    status='pending'
                )
                
                # Traiter les fichiers
                files = request.FILES.getlist('cv_files')
                import_history.total_cvs = len(files)
                import_history.status = 'in_progress'
                import_history.save()
                
                # Lancer le traitement de manière synchrone mais par lots
                # (pour éviter les problèmes sans Redis/Celery)
                process_bulk_import_sync(files, import_history, form.cleaned_data)
                
                messages.success(
                    request, 
                    _("Import terminé avec succès!")
                )
                return redirect('skillzone-import-detail', import_id=import_history.id)
                
            except Exception as e:
                logger.error(f"Erreur import: {str(e)}")
                messages.error(request, _(f"Erreur lors de l'import: {str(e)}"))
    else:
        form = SkillZoneBulkImportForm()
    
    # Récupérer les imports récents
    recent_imports = SkillZoneImportHistory.objects.filter(
        company_id=request.user.employee_get.company_id
    ).order_by('-import_date')[:5]
    
    return render(request, 'skill_zone/bulk_import.html', {
        'form': form,
        'recent_imports': recent_imports
    })


def process_bulk_import_sync(files, import_history, form_data):
    """Version synchrone du traitement d'import"""
    classifier = get_skillzone_classifier()
    candidates_to_classify = []
    
    try:
        # Récupérer ou créer un recrutement par défaut
        recruitment = form_data.get('default_recruitment')
        if not recruitment:
            # Créer un recrutement générique pour l'import
            recruitment = Recruitment.objects.create(
                title="Import SkillZone",
                description="Recrutement créé automatiquement pour l'import",
                company_id=import_history.company_id,
                start_date=timezone.now().date(),
                end_date=timezone.now().date() + timezone.timedelta(days=365),
                is_completed=False,  # Ajouter ce champ
                closed=False,  # Ajouter ce champ si nécessaire
                is_active=True  # Ajouter ce champ si nécessaire
            )
            # Créer un stage par défaut
            Stage.objects.create(
                recruitment_id=recruitment,
                stage_name="Candidature",
                stage_type="applied",
                company_id=import_history.company_id
            )
        
        # Traiter chaque fichier
        for idx, file in enumerate(files):
            try:
                logger.info(f"Traitement du fichier {idx+1}/{len(files)}: {file.name}")
                
                # Sauvegarder le fichier
                file_name = f"skillzone_import/{uuid4().hex}_{file.name}"
                file_path = default_storage.save(file_name, ContentFile(file.read()))
                
                # Créer un candidat temporaire
                candidate = create_candidate_from_cv_sync(
                    file_path, file.name, recruitment, form_data, import_history.company_id
                )
                
                if candidate:
                    candidates_to_classify.append(candidate)
                    logger.info(f"Candidat créé: {candidate.id}")
                    
            except Exception as e:
                logger.error(f"Erreur traitement fichier {file.name}: {str(e)}")
                import_history.add_error(file.name, str(e))
                import_history.failed_classifications += 1
                import_history.save()
        
        # Classifier tous les candidats de manière synchrone
        logger.info(f"Classification de {len(candidates_to_classify)} candidats...")
        
        for idx, candidate in enumerate(candidates_to_classify):
            try:
                # Mettre à jour la progression
                import_history.processed_cvs = idx + 1
                import_history.save()
                
                # Classifier le candidat de manière synchrone
                result = async_to_sync(classifier.classify_candidate)(
                    candidate, 
                    source_tag='import'
                )
                
                if "error" not in result:
                    import_history.successful_classifications += 1
                    if result.get("new_zone_created"):
                        import_history.new_zones_created += 1
                    logger.info(f"Candidat {candidate.id} classifié avec succès")
                else:
                    import_history.failed_classifications += 1
                    import_history.add_error(
                        f"Candidate {candidate.name}",
                        result["error"]
                    )
                    logger.error(f"Erreur classification candidat {candidate.id}: {result['error']}")
                
                import_history.save()
                
            except Exception as e:
                logger.error(f"Erreur classification candidat {candidate.id}: {str(e)}")
                import_history.failed_classifications += 1
                import_history.add_error(
                    f"Candidate {candidate.name}",
                    str(e)
                )
                import_history.save()
        
        # Mettre à jour le statut final
        import_history.status = 'completed'
        import_history.save()
        logger.info(f"Import terminé: {import_history.successful_classifications} réussis, {import_history.failed_classifications} échoués")
        
    except Exception as e:
        logger.error(f"Erreur générale import: {str(e)}")
        import_history.status = 'failed'
        import_history.error_log.append({
            'general_error': str(e),
            'timestamp': timezone.now().isoformat()
        })
        import_history.save()


def create_candidate_from_cv_sync(file_path, original_filename, recruitment, form_data, company_id):
    """Crée un candidat à partir d'un CV pour classification"""
    try:
        from django.utils import timezone
        
        # Récupérer le stage "applied" du recrutement
        stage = recruitment.stage_set.filter(stage_type='applied').first()
        if not stage:
            stage = recruitment.stage_set.first()
        
        # Créer le candidat avec des données minimales
        candidate = Candidate.objects.create(
            name=f"Import - {os.path.splitext(original_filename)[0]}",
            email=f"import_{uuid4().hex[:8]}@skillzone.temp",
            recruitment_id=recruitment,
            job_position_id=recruitment.job_position_id if recruitment.job_position_id else None,
            stage_id=stage,
            resume=file_path,
            source='other',
            mobile="0000000000",  # Valeur par défaut
            is_active=True
        )
        
        logger.info(f"Candidat créé: {candidate.id} - {candidate.name}")
        return candidate
        
    except Exception as e:
        logger.error(f"Erreur création candidat: {str(e)}")
        return None


@login_required
@permission_required("recruitment.view_skillzoneimporthistory")
def skillzone_import_history(request):
    """Affiche l'historique des imports"""
    imports = SkillZoneImportHistory.objects.filter(
        company_id=request.user.employee_get.company_id
    ).order_by('-import_date')
    
    return render(request, 'skill_zone/import_history.html', {
        'imports': imports
    })


@login_required
@hx_request_required
def skillzone_import_status(request, import_id):
    """API pour vérifier le statut d'un import"""
    try:
        import_history = SkillZoneImportHistory.objects.get(
            id=import_id,
            company_id=request.user.employee_get.company_id
        )
        
        return JsonResponse({
            'status': import_history.status,
            'progress': import_history.get_progress_percentage(),
            'processed': import_history.processed_cvs,
            'total': import_history.total_cvs,
            'successful': import_history.successful_classifications,
            'failed': import_history.failed_classifications,
            'new_zones': import_history.new_zones_created
        })
        
    except SkillZoneImportHistory.DoesNotExist:
        return JsonResponse({'error': 'Import not found'}, status=404)


@login_required
@permission_required("recruitment.add_skillzone")
@hx_request_required
def create_skillzone_for_import(request):
    """Créer rapidement une zone de compétences pendant l'import"""
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            zone = SkillZone.objects.create(
                title=data['title'],
                description=data['description'],
                company_id=request.user.employee_get.company_id,
                keywords=data.get('keywords', []),
                typical_skills=data.get('typical_skills', [])
            )
            
            return JsonResponse({
                'id': zone.id,
                'title': zone.title,
                'message': _("Zone créée avec succès")
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)