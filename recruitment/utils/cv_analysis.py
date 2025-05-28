# recruitment/utils/cv_analysis.py - Remplacer la classe CVAnalysisManager complète

import json
import logging
import asyncio
import nest_asyncio
import pdfplumber
from asgiref.sync import sync_to_async
from django.conf import settings
from django.core.cache import cache
from django.utils.timezone import now
import threading
import hashlib
import io
import os
from datetime import datetime, timedelta
from django.utils import timezone
from django.core.files.storage import default_storage

logger = logging.getLogger(__name__)
nest_asyncio.apply()
_event_loop = asyncio.new_event_loop()

class CVAnalysisManager:
    def __init__(self):
        logger.info("Initialisation du CVAnalysisManager avec Together AI")
        self._analysis_queue = asyncio.Queue()
        self._is_processing = False
        self.CACHE_TIMEOUT = 60 * 60 * 24  # 24 heures
        self.CV_REANALYSIS_DAYS = 30  # Durée avant réanalyse
        self._start_worker()

    def _start_worker(self):
        """Démarrage du thread de traitement"""
        threading.Thread(
            target=self._run_event_loop,
            daemon=True,
            name="CVAnalysisWorker"
        ).start()

    def _run_event_loop(self):
        """Exécution de la boucle d'événements"""
        asyncio.set_event_loop(_event_loop)
        _event_loop.run_until_complete(self._process_queue_continuously())

    def _generate_cache_key(self, candidate, config):
        """Génère une clé de cache unique basée sur le CV et la configuration"""
        if hasattr(settings, 'USE_AZURE_STORAGE') and settings.USE_AZURE_STORAGE:
            modified_time = default_storage.get_modified_time(candidate.resume.name).timestamp()
            key_string = f"{candidate.id}_{candidate.resume.name}_{modified_time}_{config.id if config else 'default'}"
        else:
            resume_path = candidate.resume.path
            modified_time = os.path.getmtime(resume_path)
            key_string = f"{candidate.id}_{resume_path}_{modified_time}_{config.id if config else 'default'}"
        
        return f"cv_analysis_{hashlib.sha256(key_string.encode()).hexdigest()}"

    def _get_pdf_cache_key(self, pdf_identifier):
        """Génère une clé de cache pour le contenu PDF"""
        if hasattr(settings, 'USE_AZURE_STORAGE') and settings.USE_AZURE_STORAGE:
            modified_time = default_storage.get_modified_time(pdf_identifier).timestamp()
        else:
            modified_time = os.path.getmtime(pdf_identifier)
            
        salt = settings.SECRET_KEY[:16]
        content = f'{pdf_identifier}_{modified_time}_{salt}'
        return f"pdf_content_{hashlib.sha256(content.encode()).hexdigest()}"

    @sync_to_async
    def _get_ai_configuration(self, candidate):
        """Récupère la configuration IA pour le candidat"""
        try:
            from recruitment.models import AIConfiguration
            
            company = candidate.recruitment_id.company_id
            config = AIConfiguration.get_config_for_company(company)
            
            if not config:
                # Créer une configuration par défaut avec Together AI
                config, created = AIConfiguration.objects.get_or_create(
                    name="Configuration Together AI par défaut",
                    defaults={
                        'api_key': 'a1c9fd0fa475a97cc06b7e32dc022682f4a186b4a642d0ca88a53e0ac1eea86b',
                        'model_name': 'deepseek-ai/DeepSeek-V3',
                        'is_default': True,
                        'analysis_prompt': """IMPORTANT: Répondez uniquement avec un JSON valide sans texte additionnel.
                        Vous êtes un expert RH qui analyse des CV pour évaluer l'adéquation avec un poste.
                        
                        Critères d'évaluation:
                        1. Pertinence du domaine (30%) - Si le domaine ne correspond PAS DU TOUT au poste, score=0
                        2. Expérience professionnelle (25%) - Durée, postes similaires, responsabilités
                        3. Formation/Éducation (20%) - Diplômes pertinents, niveau d'études
                        4. Compétences techniques (15%) - Adéquation avec les technologies requises
                        5. Certifications/Projets (10%) - Certifications spécifiques, projets pertinents
                        
                        Description du poste à analyser:
                        {}
                        
                        Format JSON requis (OBLIGATOIRE):
                        {{
                            "job_matching": {{
                                "is_relevant": true/false,
                                "reason": "Expliquer pourquoi le CV correspond ou non au poste"
                            }},
                            "score": 0-100,
                            "details": {{
                                "education": "Analyse de la formation",
                                "experience": "Analyse de l'expérience",
                                "technical_skills": "Analyse des compétences techniques",
                                "certifications": "Certifications et projets pertinents"
                            }},
                            "strengths": ["Point fort 1", "Point fort 2"],
                            "areas_for_improvement": ["Amélioration 1", "Amélioration 2"]
                        }}"""
                    }
                )
                
            return config
            
        except Exception as e:
            logger.error(f"Erreur récupération config IA: {str(e)}")
            return None

    async def _process_queue_continuously(self):
        """Traitement continu de la file"""
        while True:
            try:
                if not self._analysis_queue.empty():
                    await self._process_queue()
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.error(f"Erreur du worker: {str(e)}", exc_info=True)

    @sync_to_async
    def _extract_text_from_pdf(self, resume_field):
        """Extraction de texte avec cache"""
        if hasattr(settings, 'USE_AZURE_STORAGE') and settings.USE_AZURE_STORAGE:
            cache_key = self._get_pdf_cache_key(resume_field.name)
        else:
            cache_key = self._get_pdf_cache_key(resume_field.path)

        cached_text = cache.get(cache_key)
        if cached_text is not None:
            logger.info("Cache hit pour PDF")
            return cached_text

        try:
            if hasattr(settings, 'USE_AZURE_STORAGE') and settings.USE_AZURE_STORAGE:
                with default_storage.open(resume_field.name, 'rb') as pdf_file:
                    pdf_bytes = io.BytesIO(pdf_file.read())
                    with pdfplumber.open(pdf_bytes) as pdf:
                        text = []
                        for i, page in enumerate(pdf.pages):
                            try:
                                text.append(page.extract_text() or "")
                            except Exception as e:
                                logger.warning(f"Erreur page {i+1}: {str(e)}")
            else:
                with pdfplumber.open(resume_field.path) as pdf:
                    text = []
                    for i, page in enumerate(pdf.pages):
                        try:
                            text.append(page.extract_text() or "")
                        except Exception as e:
                            logger.warning(f"Erreur page {i+1}: {str(e)}")

            full_text = " ".join(text).strip()
            if len(full_text) < 50:
                raise ValueError("Texte PDF insuffisant")
            
            cache.set(cache_key, full_text, self.CACHE_TIMEOUT)
            return full_text
            
        except Exception as e:
            logger.error(f"Échec extraction PDF: {str(e)}")
            raise

    @sync_to_async
    def _get_job_description(self, candidate):
        """Récupération validée de la description"""
        desc = candidate.recruitment_id.description
        if not desc or len(desc) < 20:
            raise ValueError("Description de poste invalide")
        return desc.strip()

    async def analyze_cv(self, candidate):
        """Analyse d'un CV avec Together AI"""
        try:
            logger.info(f"[DÉBUT] Analyse CV Together AI - Candidat {candidate.id}")
            
            config = await self._get_ai_configuration(candidate)
            if not config:
                logger.error(f"Aucune configuration IA disponible pour {candidate.id}")
                await sync_to_async(candidate.mark_analysis_failed)()
                return
            
            # Vérification du cache
            cache_key = self._generate_cache_key(candidate, config)
            cached_results = cache.get(cache_key)
            if cached_results:
                logger.info(f"Résultats en cache trouvés pour {candidate.id}")
                await sync_to_async(candidate.update_ai_analysis)(
                    score=cached_results["score"],
                    details=cached_results
                )
                return

            # Extraction et analyse
            text = await self._extract_text_from_pdf(candidate.resume)
            job_description = await self._get_job_description(candidate)
            
            # Mise à jour statut
            await sync_to_async(candidate.start_ai_analysis)()

            # Analyse avec Together AI
            response = await self._make_together_api_call(text, job_description, config)

            # Sauvegarde
            cache.set(cache_key, response, self.CACHE_TIMEOUT)
            await sync_to_async(candidate.update_ai_analysis)(
                score=response["score"],
                details=response
            )
            logger.info(f"[SUCCÈS] Candidat {candidate.id} - Score: {response['score']}%")

        except Exception as e:
            logger.error(f"[ÉCHEC] Candidat {candidate.id} - {type(e).__name__}: {str(e)}")
            await sync_to_async(candidate.mark_analysis_failed)()

    async def _make_together_api_call(self, text, job_description, config, max_retries=2):
        """Appel API Together AI"""
        
        formatted_prompt = config.analysis_prompt.format(job_description)
        
        for attempt in range(max_retries):
            try:
                # Import Together AI
                from together import Together
                
                # Configuration de la clé API
                import os
                os.environ['TOGETHER_API_KEY'] = config.api_key
                
                client = Together()
                
                logger.info(f"Appel Together AI - tentative {attempt + 1}")
                
                response = client.chat.completions.create(
                    model=config.model_name,
                    messages=[
                        {"role": "system", "content": formatted_prompt},
                        {"role": "user", "content": f"Analysez ce CV:\n\n{text[:3000]}"}  # Limiter la taille
                    ],
                    max_tokens=config.max_tokens,
                    temperature=config.temperature
                )
                
                raw_response = response.choices[0].message.content.strip()
                logger.info("✅ Together AI - Réponse reçue")
                
                # Traitement de la réponse
                return self._process_together_response(raw_response)
                
            except Exception as e:
                logger.error(f"Together AI - Tentative {attempt + 1} échouée: {str(e)}")
                if attempt == max_retries - 1:
                    return self._generate_fallback_response(str(e))
                await asyncio.sleep(2 ** attempt)

        return self._generate_fallback_response("Toutes les tentatives ont échoué")

    def _process_together_response(self, raw_response):
        """Traite la réponse de Together AI"""
        try:
            # Extraction JSON
            json_start = raw_response.find('{')
            json_end = raw_response.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = raw_response[json_start:json_end]
                response = json.loads(json_str)
                
                if self._validate_response(response):
                    # Normalisation du score
                    if not response.get("job_matching", {}).get("is_relevant", True):
                        response["score"] = 0
                        if "details" not in response:
                            response["details"] = {}
                        response["details"]["warning"] = response["job_matching"]["reason"]
                    else:
                        response["score"] = max(0, min(100, int(response.get("score", 50))))
                    
                    return response
            
            raise ValueError("JSON non trouvé dans la réponse")
            
        except json.JSONDecodeError as e:
            logger.error(f"Erreur JSON: {e}")
            return self._generate_fallback_response(f"Erreur JSON: {str(e)}")

    def _validate_response(self, response):
        """Validation de la réponse"""
        required_keys = ["job_matching", "score", "details", "strengths", "areas_for_improvement"]
        if not all(key in response for key in required_keys):
            return False
        
        if "job_matching" in response and not all(key in response["job_matching"] for key in ["is_relevant", "reason"]):
            return False
            
        return True

    def _generate_fallback_response(self, error_msg):
        """Génère une réponse de fallback en cas d'erreur"""
        return {
            "job_matching": {
                "is_relevant": False,
                "reason": f"Erreur d'analyse: {error_msg}"
            },
            "score": 0,
            "details": {
                "error": error_msg,
                "education": "Analyse manuelle requise",
                "experience": "Analyse manuelle requise",
                "technical_skills": "Analyse manuelle requise",
                "certifications": "Analyse manuelle requise"
            },
            "strengths": [],
            "areas_for_improvement": ["Vérifier la configuration Together AI", "Réessayer l'analyse"]
        }

    async def add_to_queue(self, candidate):
        """Ajout à la file d'attente"""
        logger.info(f"Ajout candidat {candidate.id} à la file Together AI")
        await self._analysis_queue.put(candidate)

    async def _process_queue(self):
        """Traitement de la file"""
        try:
            candidate = await self._analysis_queue.get()
            await self.analyze_cv(candidate)
        except Exception as e:
            logger.error(f"Erreur traitement: {str(e)}")
        finally:
            self._analysis_queue.task_done()

cv_analysis_manager = CVAnalysisManager()