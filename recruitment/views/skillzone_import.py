# recruitment/views/skillzone_import.py - Version sans création de recrutement

import os
import json
import logging
import time
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
    SkillZone, SkillZoneImportHistory, SkillZoneCandidate, AIConfiguration
)
from recruitment.utils.skillzone_classifier import get_skillzone_classifier
from recruitment.forms import SkillZoneBulkImportForm

logger = logging.getLogger(__name__)

# Ajout d'un mécanisme de contrôle des tâches pour éviter la surcharge
import threading
_import_lock = threading.Lock()
_active_imports = {}

@login_required
@permission_required("recruitment.add_skillzonecandidate")
def skillzone_bulk_import(request):
    """Vue principale pour l'import en masse de CV"""
    if request.method == "POST":
        form = SkillZoneBulkImportForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                # Vérifier si un import est déjà en cours pour cet utilisateur
                user_id = request.user.id
                with _import_lock:
                    if user_id in _active_imports and _active_imports[user_id]['active']:
                        messages.warning(
                            request, 
                            _("Un import est déjà en cours. Veuillez attendre qu'il se termine.")
                        )
                        return redirect('skillzone-import-history')
                
                # Créer l'historique d'import
                import_history = SkillZoneImportHistory.objects.create(
                    initiated_by=request.user.employee_get,
                    company_id=request.user.employee_get.company_id,
                    status='pending'
                )
                
                # Traiter les fichiers
                files = request.FILES.getlist('cv_files')
                
                # Vérifier qu'il y a des fichiers à traiter
                if not files:
                    messages.error(request, _("Aucun fichier sélectionné"))
                    import_history.delete()
                    return redirect('skillzone-bulk-import')
                
                import_history.total_cvs = len(files)
                import_history.status = 'in_progress'
                import_history.save()
                
                # Enregistrer cet import comme actif
                with _import_lock:
                    _active_imports[user_id] = {
                        'active': True,
                        'import_id': import_history.id,
                        'start_time': timezone.now()
                    }
                
                # Lancer le traitement dans un thread séparé
                import_thread = threading.Thread(
                    target=_run_import_with_cleanup,
                    args=(files, import_history, form.cleaned_data, user_id),
                    daemon=True
                )
                import_thread.start()
                
                messages.success(
                    request, 
                    _("Import démarré avec succès! Vous pouvez suivre sa progression dans l'historique.")
                )
                return redirect('skillzone-import-detail', import_id=import_history.id)
                
            except Exception as e:
                logger.error(f"Erreur démarrage import: {str(e)}")
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

def _run_import_with_cleanup(files, import_history, form_data, user_id):
    """Exécute l'import et nettoie les ressources à la fin"""
    try:
        process_bulk_import_sync(files, import_history, form_data)
    finally:
        # Nettoyer le statut d'import actif
        with _import_lock:
            if user_id in _active_imports:
                _active_imports[user_id]['active'] = False


def process_bulk_import_sync(files, import_history, form_data):
    """Version synchrone du traitement d'import - SANS création de recrutement"""
    classifier = get_skillzone_classifier()
    cv_data_to_classify = []
    
    try:
        # Traiter chaque fichier CV
        for idx, file in enumerate(files):
            try:
                logger.info(f"Traitement du fichier {idx+1}/{len(files)}: {file.name}")
                
                # Créer une copie des données du fichier avant qu'il ne soit fermé
                file_content = file.read()
                file.seek(0)  # Rembobiner le fichier pour d'autres opérations si nécessaire
                
                # Sauvegarder le fichier
                file_name = f"skillzone_import/{uuid4().hex}_{file.name}"
                file_path = default_storage.save(file_name, ContentFile(file_content))
                
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
        
        # Vérifier s'il y a des CV à traiter
        if not cv_data_to_classify:
            import_history.status = 'failed'
            import_history.error_log.append({
                'general_error': "Aucun CV valide à traiter",
                'timestamp': timezone.now().isoformat()
            })
            import_history.save()
            return
            
        company_id = import_history.company_id.id if import_history.company_id else None
        
        # Vérifier que le traitement peut commencer
        # 1. Vérifier la configuration IA
        try:
            ai_config = AIConfiguration.get_config_for_company(import_history.company_id)
            if not ai_config:
                ai_config = AIConfiguration.objects.filter(is_default=True).first()
            
            if not ai_config:
                raise ValueError("Aucune configuration IA disponible")
                
            # 2. Vérifier l'existence de zones ou la possibilité d'en créer
            if not SkillZone.objects.filter(is_active=True, company_id=company_id).exists() and not form_data.get("auto_create_zones", True):
                raise ValueError("Aucune zone de compétence disponible et auto-création désactivée")
                
        except Exception as setup_error:
            import_history.status = 'failed'
            import_history.error_log.append({
                'general_error': str(setup_error),
                'timestamp': timezone.now().isoformat()
            })
            import_history.save()
            logger.error(f"Erreur de configuration: {str(setup_error)}")
            return
        
        # Classifier chaque CV avec une robustesse améliorée
        for idx, cv_data in enumerate(cv_data_to_classify):
            try:
                # Mettre à jour la progression
                import_history.processed_cvs = idx + 1
                import_history.save()
                
                # Traiter les CV par lots avec pauses pour éviter de surcharger l'API
                if idx > 0 and idx % 5 == 0:
                    time.sleep(2)  # Pause toutes les 5 classifications
                
                # Classifier le CV avec gestion d'erreurs améliorée
                result = classify_cv_to_skillzone(
                    cv_data, 
                    company_id,
                    form_data
                )
                
                if result.get("success"):
                    import_history.successful_classifications += 1
                    if result.get("new_zone_created"):
                        import_history.new_zones_created += 1
                    logger.info(f"CV {cv_data['original_filename']} classifié avec succès")
                else:
                    import_history.failed_classifications += 1
                    error_msg = result.get("error", "Erreur inconnue")
                    import_history.add_error(
                        cv_data['original_filename'],
                        error_msg
                    )
                    logger.error(f"Erreur classification CV: {error_msg}")
                
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
        
    # S'assurer que le statut est correctement défini, même en cas d'erreur
    if import_history.status not in ['completed', 'failed']:
        if import_history.successful_classifications > 0:
            import_history.status = 'completed'
        else:
            import_history.status = 'failed'
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
        
        # Si aucune zone n'est disponible et que l'auto-création est activée, créer quelques zones par défaut
        if not available_zones and form_data.get('auto_create_zones', True):
            logger.warning("Aucune zone disponible. Création de zones par défaut...")
            default_zones = [
                {"title": "Développement Web", "description": "Développeurs front-end et back-end", 
                 "keywords": ["javascript", "html", "css", "react", "angular", "vue", "django", "flask"]},
                {"title": "Data Science", "description": "Analyse de données et machine learning", 
                 "keywords": ["python", "R", "machine learning", "statistiques", "pandas", "numpy"]},
                {"title": "DevOps", "description": "Administration système et déploiement", 
                 "keywords": ["linux", "docker", "kubernetes", "ci/cd", "jenkins", "aws", "azure"]}
            ]
            
            for zone_data in default_zones:
                zone_kwargs = {
                    "title": zone_data["title"],
                    "description": zone_data["description"],
                    "keywords": zone_data["keywords"],
                    "is_active": True
                }
                
                if company_id:
                    zone_kwargs["company_id_id"] = company_id
                
                SkillZone.objects.create(**zone_kwargs)
                logger.info(f"Zone par défaut créée: {zone_data['title']}")
            
            # Recharger les zones
            available_zones = list(zones_query)
        
        # Classifier avec l'IA
        try:
            classification_result = async_to_sync(classifier._call_ai_for_classification)(
                cv_text, 
                ai_config.get_skillzone_prompt(available_zones), 
                ai_config
            )
        except Exception as api_error:
            logger.error(f"Erreur API IA: {str(api_error)}")
            # Créer une classification par défaut basée sur le titre du fichier
            filename = cv_data['original_filename'].lower()
            default_zone = None
            
            # Trouver une zone qui pourrait correspondre au nom de fichier
            for zone in available_zones:
                keywords = [k.lower() for k in zone.keywords] if zone.keywords else []
                title_words = zone.title.lower().split()
                if any(word in filename for word in title_words + keywords):
                    default_zone = zone
                    break
            
            # Si aucune zone ne correspond, prendre la première disponible
            if not default_zone and available_zones:
                default_zone = available_zones[0]
            
            if default_zone:
                # Créer une entrée avec une faible confiance
                SkillZoneCandidate.objects.create(
                    skill_zone_id=default_zone,
                    candidate_id=None,
                    reason=f"Classification par défaut suite à une erreur API",
                    confidence_score=0.5,  # Score faible
                    auto_classified=True,
                    source_tag='import',
                    classification_details={
                        "cv_file": cv_data['file_path'],
                        "original_filename": cv_data['original_filename'],
                        "analysis_date": timezone.now().isoformat(),
                        "error": str(api_error),
                        "can_be_converted_to_candidate": True
                    }
                )
                logger.warning(f"Classification par défaut dans {default_zone.title} après erreur API")
                return {"success": True, "emergency_fallback": True}
            else:
                return {"success": False, "error": f"Erreur IA et aucune zone disponible: {str(api_error)}"}
        
        if not classification_result:
            return {"success": False, "error": "Réponse IA vide"}
        
        # Créer les entrées SkillZone basées sur les résultats
        matched_zones = classification_result.get("matched_zones", [])
        success = False
        
        # Parcourir les zones correspondantes
        for match in matched_zones:
            confidence = match.get("confidence", 0)
            
            # Vérifier le seuil de confiance
            if confidence >= ai_config.min_confidence_for_auto_classification:
                # Trouver la zone correspondante
                zone = None
                zone_identifier = match.get("zone_id") or match.get("zone")
                
                if not zone_identifier:
                    continue
                
                # Recherche de la zone par ID ou titre
                for z in available_zones:
                    if (str(z.id) == str(zone_identifier) or 
                        z.title.lower() == str(zone_identifier).lower()):
                        zone = z
                        break
                
                if zone:
                    # Créer une entrée CV dans la zone (sans candidat)
                    SkillZoneCandidate.objects.create(
                        skill_zone_id=zone,
                        candidate_id=None,  # Pas de candidat pour l'instant
                        reason=f"Import CV - Score: {confidence:.2f}",
                        confidence_score=confidence,
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
        if not success and classification_result.get("suggested_new_zone") and form_data.get("auto_create_zones", True):
            new_zone_data = classification_result["suggested_new_zone"]
            
            # Valider que les données nécessaires sont présentes
            if not new_zone_data.get("name"):
                logger.error("Zone suggérée sans nom")
                return {"success": False, "error": "Zone suggérée sans nom"}
            
            # Créer la nouvelle zone
            new_zone_kwargs = {
                "title": new_zone_data.get("name", "Nouvelle zone"),
                "description": new_zone_data.get("description", "Zone créée automatiquement"),
                "auto_generated": True,
                "keywords": new_zone_data.get("keywords", []),
                "typical_skills": new_zone_data.get("typical_skills", []),
                "is_active": True
            }
            
            # Ajouter company_id seulement si elle existe
            if company_id:
                new_zone_kwargs["company_id_id"] = company_id
            
            try:
                new_zone = SkillZone.objects.create(**new_zone_kwargs)
                
                # Ajouter le CV à cette nouvelle zone
                SkillZoneCandidate.objects.create(
                    skill_zone_id=new_zone,
                    candidate_id=None,
                    reason="Import CV - Nouvelle zone créée",
                    confidence_score=0.8,  # Confiance par défaut pour les nouvelles zones
                    auto_classified=True,
                    source_tag='import',
                    classification_details={
                        "cv_file": cv_data['file_path'],
                        "original_filename": cv_data['original_filename'],
                        "analysis_date": timezone.now().isoformat(),
                        "extracted_skills": classification_result.get("extracted_skills", []),
                        "professional_level": classification_result.get("professional_level", "intermediate"),
                        "can_be_converted_to_candidate": True
                    }
                )
                
                logger.info(f"Nouvelle zone créée: {new_zone.title}")
                
                return {
                    "success": True,
                    "new_zone_created": True,
                    "zone_name": new_zone.title
                }
            except Exception as zone_error:
                logger.error(f"Erreur création zone: {str(zone_error)}")
                return {"success": False, "error": f"Erreur création zone: {str(zone_error)}"}
        
        # Gérer le cas où aucune zone n'est trouvée et qu'aucune n'est suggérée
        if not success and not classification_result.get("suggested_new_zone"):
            # Si auto-création activée, créer une zone basée sur le nom du fichier
            if form_data.get("auto_create_zones", True):
                filename = os.path.basename(cv_data['original_filename'])
                name_parts = os.path.splitext(filename)[0].split('_')
                
                # Essayer de deviner un nom de domaine à partir du nom de fichier
                domain_keywords = ["dev", "data", "marketing", "finance", "rh", "cyber", "web", "mobile"]
                domain = next((part for part in name_parts if any(kw in part.lower() for kw in domain_keywords)), None)
                
                if not domain:
                    domain = "Général"
                
                # Créer une zone générique
                new_zone_kwargs = {
                    "title": f"Zone {domain.capitalize()}",
                    "description": f"Zone créée automatiquement lors de l'import",
                    "auto_generated": True,
                    "keywords": [domain.lower()],
                    "is_active": True
                }
                
                if company_id:
                    new_zone_kwargs["company_id_id"] = company_id
                
                try:
                    new_zone = SkillZone.objects.create(**new_zone_kwargs)
                    
                    # Ajouter le CV à cette nouvelle zone
                    SkillZoneCandidate.objects.create(
                        skill_zone_id=new_zone,
                        candidate_id=None,
                        reason="Import CV - Création zone par défaut",
                        confidence_score=0.5,  # Confiance réduite
                        auto_classified=True,
                        source_tag='import',
                        classification_details={
                            "cv_file": cv_data['file_path'],
                            "original_filename": cv_data['original_filename'],
                            "analysis_date": timezone.now().isoformat(),
                            "can_be_converted_to_candidate": True
                        }
                    )
                    
                    logger.info(f"Zone par défaut créée: {new_zone.title}")
                    return {
                        "success": True,
                        "new_zone_created": True,
                        "zone_name": new_zone.title,
                        "fallback": True
                    }
                except Exception as zone_error:
                    logger.error(f"Erreur création zone par défaut: {str(zone_error)}")
                    return {"success": False, "error": f"Erreur création zone par défaut: {str(zone_error)}"}
            else:
                return {"success": False, "error": "Aucune zone de compétences appropriée trouvée"}
        
        return {"success": success}
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        error_message = str(e) if str(e) else "Erreur inconnue pendant la classification"
        logger.error(f"Erreur classification CV: {error_message}\nDétails:\n{error_details}")
        return {"success": False, "error": error_message}


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
        
        # Récupérer les 3 dernières erreurs
        last_errors = []
        if import_history.error_log:
            last_errors = import_history.error_log[-3:]
        
        return JsonResponse({
            'status': import_history.status,
            'progress': import_history.get_progress_percentage(),
            'processed': import_history.processed_cvs,
            'total': import_history.total_cvs,
            'successful': import_history.successful_classifications,
            'failed': import_history.failed_classifications,
            'new_zones': import_history.new_zones_created,
            'last_errors': last_errors
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