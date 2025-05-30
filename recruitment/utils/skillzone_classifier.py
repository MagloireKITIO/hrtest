# recruitment/utils/skillzone_classifier.py

import json
import logging
import asyncio
from typing import List, Dict, Optional, Tuple
from asgiref.sync import sync_to_async
from django.core.cache import cache
from django.utils import timezone
from django.db import transaction
import hashlib

logger = logging.getLogger(__name__)


class SkillZoneClassifier:
    """
    Gestionnaire pour la classification automatique des candidats dans les zones de compétences
    """
    
    def __init__(self, cv_analysis_manager):
        self.cv_analysis_manager = cv_analysis_manager
        self.CACHE_TIMEOUT = 60 * 60 * 24  # 24 heures
        logger.info("Initialisation du SkillZoneClassifier")
    
    def _generate_classification_cache_key(self, candidate_id: int, company_id: int) -> str:
        """Génère une clé de cache unique pour la classification"""
        key_string = f"skillzone_classification_{candidate_id}_{company_id}"
        return hashlib.sha256(key_string.encode()).hexdigest()
    
    @sync_to_async
    def _get_available_zones(self, company_id):
        """Récupère toutes les zones de compétences actives pour une entreprise"""
        from recruitment.models import SkillZone
        return list(SkillZone.objects.filter(
            company_id=company_id,
            is_active=True
        ).order_by('title'))
    
    @sync_to_async
    def _get_ai_config(self, company):
        """Récupère la configuration IA pour l'entreprise"""
        from recruitment.models import AIConfiguration
        return AIConfiguration.get_config_for_company(company)
    
    async def classify_candidate(self, candidate, source_tag='manual') -> Dict:
        """
        Classifie un candidat dans les zones de compétences appropriées
        
        Args:
            candidate: Instance de Candidate
            source_tag: Source de la classification ('manual', 'application', 'import', 'ai_suggestion')
            
        Returns:
            Dict avec les résultats de classification
        """
        try:
            logger.info(f"[SKILLZONE] Début classification candidat {candidate.id}")
            
            # Vérifier le cache
            company_id = await sync_to_async(lambda: candidate.recruitment_id.company_id.id)()
            cache_key = self._generate_classification_cache_key(candidate.id, company_id)
            cached_result = cache.get(cache_key)
            
            if cached_result and source_tag != 'import':  # Ne pas utiliser le cache pour les imports
                logger.info(f"[SKILLZONE] Résultat en cache pour candidat {candidate.id}")
                return cached_result
            
            # Récupérer la configuration et les zones disponibles
            company = await sync_to_async(lambda: candidate.recruitment_id.company_id)()
            ai_config = await self._get_ai_config(company)
            available_zones = await self._get_available_zones(company_id)
            
            if not ai_config:
                logger.error("[SKILLZONE] Aucune configuration IA disponible")
                return {"error": "No AI configuration found"}
            
            # Extraire le texte du CV
            cv_text = await self.cv_analysis_manager._extract_text_from_pdf(candidate.resume)
            
            # Préparer le prompt avec les zones disponibles
            prompt = ai_config.get_skillzone_prompt(available_zones)
            
            # Appeler l'IA pour la classification
            classification_result = await self._call_ai_for_classification(
                cv_text, prompt, ai_config
            )
            
            # Traiter et sauvegarder les résultats
            processed_result = await self._process_classification_result(
                candidate, classification_result, ai_config, available_zones, source_tag
            )
            
            # Mettre en cache
            cache.set(cache_key, processed_result, self.CACHE_TIMEOUT)
            
            logger.info(f"[SKILLZONE] Classification terminée pour candidat {candidate.id}")
            return processed_result
            
        except Exception as e:
            logger.error(f"[SKILLZONE] Erreur classification candidat {candidate.id}: {str(e)}")
            return {"error": str(e)}
    
    async def _call_ai_for_classification(self, cv_text: str, prompt: str, ai_config) -> dict:
        """Appelle l'API Together AI pour classifier le CV avec gestion améliorée des erreurs"""
        try:
            from together import Together
            import os
            import re
            import json
            
            os.environ['TOGETHER_API_KEY'] = ai_config.api_key
            client = Together()
            
            logger.info("[SKILLZONE] Appel API Together pour classification")
            
            # Limiter la taille du CV pour éviter les dépassements de tokens
            cv_text_limited = cv_text[:4000]
            
            response = client.chat.completions.create(
                model=ai_config.model_name,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": f"Analysez ce CV:\n\n{cv_text_limited}"}
                ],
                max_tokens=ai_config.max_tokens,
                temperature=0.3  # Plus déterministe pour la classification
            )
            
            raw_response = response.choices[0].message.content.strip()
            logger.info("[SKILLZONE] Réponse reçue de l'API Together")
            
            # Tenter d'extraire le JSON en utilisant des expressions régulières pour être plus robuste
            json_match = re.search(r'({[\s\S]*})', raw_response)
            
            if json_match:
                json_str = json_match.group(1)
                
                # Essayer plusieurs méthodes pour corriger et parser le JSON
                try:
                    # 1. Tenter de parser directement
                    return json.loads(json_str)
                except json.JSONDecodeError as e1:
                    logger.warning(f"Première tentative de parsing JSON échouée: {str(e1)}")
                    
                    try:
                        # 2. Essayer de corriger les problèmes courants dans le JSON
                        corrected_json = self._fix_json_structure(json_str)
                        return json.loads(corrected_json)
                    except json.JSONDecodeError as e2:
                        logger.error(f"Échec du parsing JSON après correction: {str(e2)}")
                        
                        # 3. Tenter une approche plus robuste avec un JSON minimal mais valide
                        return self._extract_minimal_json(json_str, raw_response)
            else:
                logger.error("Aucun JSON trouvé dans la réponse")
                # Créer un JSON minimal avec suggestion de zone basée sur le texte
                return self._create_fallback_json(raw_response, cv_text)
                    
        except Exception as e:
            logger.error(f"[SKILLZONE] Erreur appel IA: {str(e)}")
            # Retourner une structure minimale mais valide
            return {
                "matched_zones": [],
                "suggested_new_zone": {
                    "name": "Zone suggérée par défaut",
                    "description": "Créée suite à une erreur d'analyse",
                    "keywords": [],
                    "typical_skills": []
                },
                "error": str(e)
            }

    def _fix_json_structure(self, json_str):
        """Tente de corriger les problèmes courants dans les structures JSON"""
        import re
        
        # Corriger les accolades non fermées
        open_braces = json_str.count('{')
        close_braces = json_str.count('}')
        if open_braces > close_braces:
            json_str += '}' * (open_braces - close_braces)
        
        # Corriger les listes de compétences dupliquées (problème observé)
        # Regex pour trouver des structures comme "typical_skills": [...], "typical_skills": [...]
        duplicate_pattern = r'("typical_skills"\s*:\s*\[[^\]]*\]),\s*("typical_skills"\s*:)'
        json_str = re.sub(duplicate_pattern, r'\1,', json_str)
        
        # Corriger les virgules superflues à la fin des objets
        json_str = re.sub(r',\s*}', '}', json_str)
        
        # Remplacer les guillemets Unicode par des guillemets standards
        json_str = json_str.replace('\u201c', '"').replace('\u201d', '"')
        
        return json_str

    def _extract_minimal_json(self, json_str, raw_response):
        """Extrait les informations minimales nécessaires même d'un JSON corrompu"""
        import re
        
        result = {
            "matched_zones": [],
            "suggested_new_zone": None
        }
        
        # Extraire les zones correspondantes (même partiellement)
        zones_match = re.search(r'"matched_zones"\s*:\s*\[(.*?)\]', json_str, re.DOTALL)
        if zones_match:
            zones_text = zones_match.group(1)
            # Extraire chaque zone individuellement
            zone_pattern = r'{(.*?)}'
            zone_matches = re.finditer(zone_pattern, zones_text, re.DOTALL)
            
            for zone_match in zone_matches:
                zone_content = zone_match.group(1)
                
                # Extraire l'ID et le score
                zone_id_match = re.search(r'"zone_id"\s*:\s*"([^"]*)"', zone_content)
                confidence_match = re.search(r'"confidence"\s*:\s*([\d.]+)', zone_content)
                
                if zone_id_match and confidence_match:
                    result["matched_zones"].append({
                        "zone_id": zone_id_match.group(1),
                        "confidence": float(confidence_match.group(1)),
                        "reasons": []  # Simplifié pour robustesse
                    })
        
        # Extraire la zone suggérée (même partiellement)
        suggested_zone_match = re.search(r'"suggested_new_zone"\s*:\s*{(.*?)}', json_str, re.DOTALL)
        if suggested_zone_match:
            zone_content = suggested_zone_match.group(1)
            
            # Extraire les champs principaux
            name_match = re.search(r'"name"\s*:\s*"([^"]*)"', zone_content)
            desc_match = re.search(r'"description"\s*:\s*"([^"]*)"', zone_content)
            
            if name_match:
                result["suggested_new_zone"] = {
                    "name": name_match.group(1),
                    "description": desc_match.group(1) if desc_match else "Description non disponible",
                    "keywords": [],
                    "typical_skills": []
                }
                
                # Tenter d'extraire des mots-clés s'ils existent
                keywords_match = re.search(r'"keywords"\s*:\s*\[(.*?)\]', zone_content, re.DOTALL)
                if keywords_match:
                    keywords_text = keywords_match.group(1)
                    keywords = re.findall(r'"([^"]*)"', keywords_text)
                    result["suggested_new_zone"]["keywords"] = keywords
        
        # Si toujours pas de zones, tenter d'en extraire des noms du texte brut
        if not result["matched_zones"] and not result["suggested_new_zone"]:
            # Chercher des noms potentiels de zones dans la réponse
            potential_zones = re.findall(r'["\']([A-Za-z\s]+?)["\']', raw_response)
            if potential_zones:
                result["suggested_new_zone"] = {
                    "name": potential_zones[0],
                    "description": "Zone extraite du texte brut suite à une erreur",
                    "keywords": [],
                    "typical_skills": []
                }
        
        return result

    def _create_fallback_json(self, raw_response, cv_text):
        """Crée un JSON minimal avec une suggestion basée sur le texte du CV"""
        # Extraire les premiers mots du CV pour estimer un domaine
        first_words = cv_text.split()[:50]
        text_sample = " ".join(first_words)
        
        # Chercher des mots-clés communs dans les domaines de compétences
        domains = {
            "Développement": ["développeur", "programmeur", "code", "javascript", "python", "java", "web"],
            "Marketing": ["marketing", "communication", "digital", "seo", "publicité", "vente"],
            "Finance": ["finance", "comptable", "comptabilité", "audit", "financier", "trésorerie"],
            "Ressources Humaines": ["rh", "ressources humaines", "recrutement", "formation", "talent"],
            "Cybersécurité": ["cybersécurité", "sécurité", "audit", "pentest", "hacking", "firewall"],
            "Data Science": ["data", "données", "statistiques", "analyse", "machine learning", "ia"]
        }
        
        # Trouver le domaine le plus probable
        best_domain = None
        best_count = 0
        
        for domain, keywords in domains.items():
            count = sum(1 for keyword in keywords if keyword.lower() in text_sample.lower())
            if count > best_count:
                best_count = count
                best_domain = domain
        
        # Utiliser un domaine par défaut si aucun n'est trouvé
        if not best_domain or best_count == 0:
            best_domain = "Profil Généraliste"
        
        return {
            "matched_zones": [],
            "suggested_new_zone": {
                "name": best_domain,
                "description": f"Zone suggérée automatiquement basée sur l'analyse du CV",
                "keywords": [],
                "typical_skills": []
            }
        }
    
    @sync_to_async
    def _process_classification_result(
        self, candidate, result: Dict, ai_config, available_zones: List, source_tag: str
    ) -> Dict:
        """Traite et sauvegarde les résultats de classification"""
        from recruitment.models import SkillZone, SkillZoneCandidate
        
        processed_results = {
            "candidate_id": candidate.id,
            "classifications": [],
            "new_zone_created": None,
            "extracted_skills": result.get("extracted_skills", []),
            "professional_level": result.get("professional_level", "intermediate")
        }
        
        with transaction.atomic():
            # Traiter les zones correspondantes
            matched_zones = result.get("matched_zones", [])
            zones_to_classify = []
            
            # Filtrer selon le score de confiance minimum
            for match in matched_zones[:ai_config.max_zones_per_candidate]:
                if match["confidence"] >= ai_config.min_confidence_for_auto_classification:
                    zones_to_classify.append(match)
            
            # Si aucune zone ne correspond bien, créer une nouvelle zone si suggérée
            if not zones_to_classify and result.get("suggested_new_zone") and ai_config.enable_auto_skillzone_creation:
                new_zone_data = result["suggested_new_zone"]
                
                # Créer la nouvelle zone
                new_zone = SkillZone.objects.create(
                    title=new_zone_data["name"],
                    description=new_zone_data["description"],
                    company_id=candidate.recruitment_id.company_id,
                    auto_generated=True,
                    keywords=new_zone_data.get("keywords", []),
                    typical_skills=new_zone_data.get("typical_skills", [])
                )
                
                processed_results["new_zone_created"] = {
                    "id": new_zone.id,
                    "name": new_zone.title
                }
                
                # Ajouter cette nouvelle zone à classifier
                zones_to_classify = [{
                    "zone": new_zone,
                    "confidence": 0.8,  # Score par défaut pour nouvelle zone
                    "reasons": ["Zone créée spécifiquement pour ce profil"]
                }]
            
            # Classifier le candidat dans les zones sélectionnées
            for zone_data in zones_to_classify:
                # Trouver la zone par ID ou nom
                if isinstance(zone_data.get("zone"), str):
                    zone = next(
                        (z for z in available_zones if str(z.id) == zone_data["zone"] or z.title == zone_data["zone"]),
                        None
                    )
                else:
                    zone = zone_data.get("zone")
                
                if zone:
                    # Vérifier si la classification existe déjà
                    existing = SkillZoneCandidate.objects.filter(
                        skill_zone_id=zone,
                        candidate_id=candidate
                    ).first()
                    
                    if existing:
                        # Mettre à jour si nécessaire
                        if existing.confidence_score is None or existing.confidence_score < zone_data["confidence"]:
                            existing.confidence_score = zone_data["confidence"]
                            existing.auto_classified = True
                            existing.source_tag = source_tag
                            existing.classification_details = {
                                "reasons": zone_data.get("reasons", []),
                                "analysis_date": timezone.now().isoformat(),
                                "ai_model": ai_config.model_name
                            }
                            existing.save()
                    else:
                        # Créer nouvelle classification
                        SkillZoneCandidate.objects.create(
                            skill_zone_id=zone,
                            candidate_id=candidate,
                            reason=f"Classification automatique - Score: {zone_data['confidence']:.2f}",
                            confidence_score=zone_data["confidence"],
                            auto_classified=True,
                            source_tag=source_tag,
                            classification_details={
                                "reasons": zone_data.get("reasons", []),
                                "analysis_date": timezone.now().isoformat(),
                                "ai_model": ai_config.model_name
                            }
                        )
                    
                    processed_results["classifications"].append({
                        "zone_id": zone.id,
                        "zone_name": zone.title,
                        "confidence": zone_data["confidence"],
                        "reasons": zone_data.get("reasons", [])
                    })
        
        return processed_results
    
    async def bulk_classify_candidates(self, candidates: List, import_history=None) -> Dict:
        """
        Classifie plusieurs candidats en lot
        
        Args:
            candidates: Liste des candidats à classifier
            import_history: Instance de SkillZoneImportHistory pour le suivi
            
        Returns:
            Dict avec les statistiques de classification
        """
        results = {
            "total": len(candidates),
            "successful": 0,
            "failed": 0,
            "new_zones_created": 0,
            "classifications": []
        }
        
        for i, candidate in enumerate(candidates):
            try:
                # Mettre à jour le statut si historique fourni
                if import_history:
                    await sync_to_async(lambda: setattr(
                        import_history, 'processed_cvs', i + 1
                    ))()
                    await sync_to_async(import_history.save)()
                
                # Classifier le candidat
                result = await self.classify_candidate(candidate, source_tag='import')
                
                if "error" not in result:
                    results["successful"] += 1
                    results["classifications"].append(result)
                    
                    if result.get("new_zone_created"):
                        results["new_zones_created"] += 1
                else:
                    results["failed"] += 1
                    if import_history:
                        await sync_to_async(import_history.add_error)(
                            f"Candidate {candidate.id}",
                            result["error"]
                        )
                
                # Pause pour éviter la surcharge de l'API
                if i % 10 == 0 and i > 0:
                    await asyncio.sleep(1)
                    
            except Exception as e:
                logger.error(f"[SKILLZONE] Erreur bulk classify candidat {candidate.id}: {str(e)}")
                results["failed"] += 1
                if import_history:
                    await sync_to_async(import_history.add_error)(
                        f"Candidate {candidate.id}",
                        str(e)
                    )
        
        # Finaliser l'historique
        if import_history:
            await sync_to_async(lambda: setattr(
                import_history, 'successful_classifications', results["successful"]
            ))()
            await sync_to_async(lambda: setattr(
                import_history, 'failed_classifications', results["failed"]
            ))()
            await sync_to_async(lambda: setattr(
                import_history, 'new_zones_created', results["new_zones_created"]
            ))()
            await sync_to_async(lambda: setattr(
                import_history, 'status', 'completed'
            ))()
            await sync_to_async(import_history.save)()
        
        return results


# Singleton pour utilisation globale
skillzone_classifier = None

def get_skillzone_classifier():
    """Factory pour obtenir l'instance du classifier"""
    global skillzone_classifier
    if skillzone_classifier is None:
        from recruitment.utils.cv_analysis import cv_analysis_manager
        skillzone_classifier = SkillZoneClassifier(cv_analysis_manager)
    return skillzone_classifier