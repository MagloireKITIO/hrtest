# recruitment/views/skillzone_import.py - Version sans création de recrutement

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
    SkillZone, SkillZoneImportHistory, SkillZoneCandidate
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
                
                # Lancer le traitement
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
    """Version synchrone du traitement d'import - SANS création de recrutement"""
    classifier = get_skillzone_classifier()
    cv_data_to_classify = []
    
    try:
        # Traiter chaque fichier CV
        for idx, file in enumerate(files):
            try:
                logger.info(f"Traitement du fichier {idx+1}/{len(files)}: {file.name}")
                
                # Sauvegarder le fichier
                file_name = f"skillzone_import/{uuid4().hex}_{file.name}"
                file_path = default_storage.save(file_name, ContentFile(file.read()))
                
                # Préparer les données du CV pour classification
                cv_data = {
                    'file_path': file_path,
                    'original_filename': file.name,
                    'file_url': default_storage.url(file_path)
                }
                cv_data_to_classify.append(cv_data)
                logger.info(f"CV préparé: {file.name}")
                    
            except Exception as e:
                logger.error(f"Erreur traitement fichier {file.name}: {str(e)}")
                import_history.add_error(file.name, str(e))
                import_history.failed_classifications += 1
                import_history.save()
        
        # Classifier tous les CV directement dans les SkillZones
        logger.info(f"Classification de {len(cv_data_to_classify)} CV...")
        
        for idx, cv_data in enumerate(cv_data_to_classify):
            try:
                # Mettre à jour la progression
                import_history.processed_cvs = idx + 1
                import_history.save()
                
                # Classifier le CV directement
                result = classify_cv_to_skillzone(
                    cv_data, 
                    import_history.company_id,
                    form_data
                )
                
                if result.get("success"):
                    import_history.successful_classifications += 1
                    if result.get("new_zone_created"):
                        import_history.new_zones_created += 1
                    logger.info(f"CV {cv_data['original_filename']} classifié avec succès")
                else:
                    import_history.failed_classifications += 1
                    import_history.add_error(
                        cv_data['original_filename'],
                        result.get("error", "Erreur inconnue")
                    )
                    logger.error(f"Erreur classification CV: {result.get('error')}")
                
                import_history.save()
                
            except Exception as e:
                logger.error(f"Erreur classification CV {cv_data['original_filename']}: {str(e)}")
                import_history.failed_classifications += 1
                import_history.add_error(
                    cv_data['original_filename'],
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


def classify_cv_to_skillzone(cv_data, company_id, form_data):
    """
    Classifier un CV directement dans une SkillZone sans créer de candidat
    """
    try:
        classifier = get_skillzone_classifier()
        
        # Extraire le texte du CV
        import pdfplumber
        import io
        
        # Lire le contenu du fichier
        with default_storage.open(cv_data['file_path'], 'rb') as pdf_file:
            pdf_bytes = io.BytesIO(pdf_file.read())
            with pdfplumber.open(pdf_bytes) as pdf:
                text = []
                for page in pdf.pages:
                    try:
                        text.append(page.extract_text() or "")
                    except Exception as e:
                        logger.warning(f"Erreur extraction page: {str(e)}")
                cv_text = " ".join(text).strip()
        
        if len(cv_text) < 50:
            return {"success": False, "error": "Texte PDF insuffisant"}
        
        # Obtenir la configuration IA
        from recruitment.models import AIConfiguration, SkillZone
        
        # Stratégie pour obtenir la config :
        # 1. Si company_id existe, chercher une config associée à cette company
        # 2. Sinon, chercher la config par défaut
        # 3. Sinon, prendre la première config active
        
        ai_config = None
        
        if company_id:
            # Chercher une config associée à cette company (relation M2M)
            ai_config = AIConfiguration.objects.filter(
                companies__id=company_id,
                is_active=True
            ).first()
        
        # Si pas trouvé, chercher la config par défaut
        if not ai_config:
            ai_config = AIConfiguration.objects.filter(
                is_default=True,
                is_active=True
            ).first()
        
        # Si toujours pas trouvé, prendre la première config active
        if not ai_config:
            ai_config = AIConfiguration.objects.filter(
                is_active=True
            ).first()
        
        if not ai_config:
            return {"success": False, "error": "Aucune configuration IA disponible. Veuillez créer une configuration dans l'administration."}
        
        # Obtenir les zones disponibles
        zones_query = SkillZone.objects.filter(is_active=True)
        
        # Si company_id est spécifié, filtrer par company
        if company_id:
            zones_query = zones_query.filter(company_id=company_id)
        
        available_zones = list(zones_query)
        
        logger.info(f"Zones disponibles: {len(available_zones)}")
        
        # Classifier avec l'IA
        classification_result = async_to_sync(classifier._call_ai_for_classification)(
            cv_text, 
            ai_config.get_skillzone_prompt(available_zones), 
            ai_config
        )
        
        # Créer les entrées SkillZone basées sur les résultats
        matched_zones = classification_result.get("matched_zones", [])
        success = False
        
        for match in matched_zones[:ai_config.max_zones_per_candidate]:
            if match["confidence"] >= ai_config.min_confidence_for_auto_classification:
                # Trouver la zone correspondante
                zone = None
                zone_identifier = match.get("zone_id") or match.get("zone")
                
                for z in available_zones:
                    if str(z.id) == str(zone_identifier) or z.title.lower() == str(zone_identifier).lower():
                        zone = z
                        break
                
                if zone:
                    # Créer une entrée CV dans la zone (sans candidat)
                    from recruitment.models import SkillZoneCandidate
                    SkillZoneCandidate.objects.create(
                        skill_zone_id=zone,
                        candidate_id=None,  # Pas de candidat pour l'instant
                        reason=f"Import CV - Score: {match['confidence']:.2f}",
                        confidence_score=match["confidence"],
                        auto_classified=True,
                        source_tag='import',
                        classification_details={
                            "cv_file": cv_data['file_path'],
                            "original_filename": cv_data['original_filename'],
                            "reasons": match.get("reasons", []),
                            "analysis_date": timezone.now().isoformat(),
                            "extracted_skills": classification_result.get("extracted_skills", []),
                            "professional_level": classification_result.get("professional_level"),
                            "can_be_converted_to_candidate": True
                        }
                    )
                    success = True
                    logger.info(f"CV classifié dans la zone: {zone.title}")
        
        # Si aucune zone ne correspond et auto-création activée
        if not success and classification_result.get("suggested_new_zone") and form_data.get("auto_create_zones"):
            new_zone_data = classification_result["suggested_new_zone"]
            
            # Créer la nouvelle zone
            new_zone_kwargs = {
                "title": new_zone_data["name"],
                "description": new_zone_data["description"],
                "auto_generated": True,
                "keywords": new_zone_data.get("keywords", []),
                "typical_skills": new_zone_data.get("typical_skills", [])
            }
            
            # Ajouter company_id seulement si elle existe
            if company_id:
                new_zone_kwargs["company_id_id"] = company_id
            
            new_zone = SkillZone.objects.create(**new_zone_kwargs)
            
            # Ajouter le CV à cette nouvelle zone
            SkillZoneCandidate.objects.create(
                skill_zone_id=new_zone,
                candidate_id=None,
                reason="Import CV - Nouvelle zone créée",
                confidence_score=0.8,
                auto_classified=True,
                source_tag='import',
                classification_details={
                    "cv_file": cv_data['file_path'],
                    "original_filename": cv_data['original_filename'],
                    "analysis_date": timezone.now().isoformat(),
                    "extracted_skills": classification_result.get("extracted_skills", []),
                    "can_be_converted_to_candidate": True
                }
            )
            
            logger.info(f"Nouvelle zone créée: {new_zone.title}")
            
            return {
                "success": True,
                "new_zone_created": True,
                "zone_name": new_zone.title
            }
        
        return {"success": success}
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Erreur classification CV: {str(e)}\nDétails:\n{error_details}")
        return {"success": False, "error": str(e) if str(e) else error_details}


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


# Nouvelle fonction pour convertir un CV importé en candidat
@login_required
@permission_required("recruitment.add_candidate")
def convert_cv_to_candidate(request, sz_cand_id):
    """
    Convertir un CV importé en candidat pour un recrutement spécifique
    """
    from recruitment.models import SkillZoneCandidate, Candidate, Recruitment
    
    sz_candidate = SkillZoneCandidate.objects.get(id=sz_cand_id)
    
    if sz_candidate.candidate_id:
        messages.warning(request, _("Ce CV a déjà été converti en candidat"))
        return redirect('skill-zone-view')
    
    if request.method == "POST":
        recruitment_id = request.POST.get("recruitment_id")
        recruitment = Recruitment.objects.get(id=recruitment_id)
        
        # Créer le candidat
        cv_details = sz_candidate.classification_details
        candidate = Candidate.objects.create(
            name=cv_details.get("original_filename", "Candidat importé"),
            email=f"imported_{uuid4().hex[:8]}@temp.local",
            recruitment_id=recruitment,
            stage_id=recruitment.stage_set.filter(stage_type='applied').first(),
            resume=cv_details.get("cv_file"),
            source='skillzone_import',
            mobile="0000000000",
            is_active=True
        )
        
        # Mettre à jour la référence
        sz_candidate.candidate_id = candidate
        sz_candidate.save()
        
        messages.success(request, _("CV converti en candidat avec succès"))
        return redirect('candidate-view-individual', cand_id=candidate.id)
    
    # Afficher le formulaire de sélection du recrutement
    recruitments = Recruitment.objects.filter(
        company_id=request.user.employee_get.company_id,
        closed=False,
        is_active=True
    )
    
    return render(request, 'skill_zone/convert_to_candidate.html', {
        'sz_candidate': sz_candidate,
        'recruitments': recruitments
    })