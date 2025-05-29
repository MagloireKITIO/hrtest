# recruitment/views/skillzone_search.py

import json
from django.shortcuts import render
from django.http import JsonResponse
from django.db.models import Q, Count, Avg, F
from django.utils.translation import gettext_lazy as _
from django.core.cache import cache
import logging

from horilla.decorators import login_required, permission_required, hx_request_required
from recruitment.models import SkillZone, SkillZoneCandidate, Candidate
from recruitment.utils.skillzone_classifier import get_skillzone_classifier
from recruitment.views.paginator_qry import paginator_qry

logger = logging.getLogger(__name__)


@login_required
@permission_required("recruitment.view_skillzone")
def skillzone_smart_search(request):
    """Vue principale pour la recherche intelligente dans les zones de compétences"""
    
    query = request.GET.get('q', '')
    search_type = request.GET.get('search_type', 'keyword')  # keyword, semantic, hybrid
    filter_by_zone = request.GET.get('zone_id')
    min_confidence = float(request.GET.get('min_confidence', 0.5))
    professional_level = request.GET.get('professional_level')
    
    company_id = request.user.employee_get.company_id
    
    # Cache key pour les résultats
    cache_key = f"skillzone_search_{company_id}_{query}_{search_type}_{filter_by_zone}"
    cached_results = cache.get(cache_key)
    
    if cached_results and not request.GET.get('force_refresh'):
        results = cached_results
    else:
        if search_type == 'semantic':
            results = semantic_search(query, company_id, filter_by_zone, min_confidence)
        elif search_type == 'hybrid':
            results = hybrid_search(query, company_id, filter_by_zone, min_confidence)
        else:
            results = keyword_search(query, company_id, filter_by_zone, min_confidence)
        
        # Filtrer par niveau professionnel si spécifié
        if professional_level and results['candidates']:
            results['candidates'] = [
                c for c in results['candidates'] 
                if c.get('professional_level') == professional_level
            ]
        
        # Mettre en cache pour 30 minutes
        cache.set(cache_key, results, 1800)
    
    # Pagination des résultats
    if request.GET.get('view_type') == 'candidates':
        # Vue détaillée des candidats
        candidates = results.get('candidates', [])
        paginated = paginator_qry(candidates, request.GET.get('page'))
        
        return render(request, 'skill_zone/search_results_candidates.html', {
            'results': paginated,
            'query': query,
            'total_count': len(candidates),
            'search_type': search_type
        })
    else:
        # Vue par zones
        zones = results.get('zones', [])
        paginated = paginator_qry(zones, request.GET.get('page'))
        
        return render(request, 'skill_zone/search_results_zones.html', {
            'results': paginated,
            'query': query,
            'total_count': results.get('total_candidates', 0),
            'search_type': search_type
        })


def keyword_search(query, company_id, filter_by_zone=None, min_confidence=0.5):
    """Recherche par mots-clés classique avec amélioration"""
    
    results = {
        'zones': [],
        'candidates': [],
        'total_candidates': 0
    }
    
    if not query:
        return results
    
    # Diviser la requête en mots-clés
    keywords = query.lower().split()
    
    # Recherche dans les zones
    zone_q = Q()
    for keyword in keywords:
        zone_q |= (
            Q(title__icontains=keyword) |
            Q(description__icontains=keyword) |
            Q(keywords__icontains=keyword) |
            Q(typical_skills__icontains=keyword)
        )
    
    zones = SkillZone.objects.filter(
        zone_q,
        company_id=company_id,
        is_active=True
    )
    
    if filter_by_zone:
        zones = zones.filter(id=filter_by_zone)
    
    # Annoter avec des statistiques
    zones = zones.annotate(
        candidate_count=Count('skillzonecandidate_set', filter=Q(skillzonecandidate_set__is_active=True)),
        avg_confidence=Avg('skillzonecandidate_set__confidence_score')
    ).order_by('-candidate_count')
    
    # Recherche dans les candidats
    candidate_q = Q()
    for keyword in keywords:
        candidate_q |= (
            Q(candidate_id__name__icontains=keyword) |
            Q(candidate_id__email__icontains=keyword) |
            Q(classification_details__extracted_skills__icontains=keyword) |
            Q(reason__icontains=keyword)
        )
    
    skillzone_candidates = SkillZoneCandidate.objects.filter(
        candidate_q,
        confidence_score__gte=min_confidence,
        is_active=True,
        skill_zone_id__company_id=company_id
    ).select_related('candidate_id', 'skill_zone_id')
    
    if filter_by_zone:
        skillzone_candidates = skillzone_candidates.filter(skill_zone_id=filter_by_zone)
    
    # Construire les résultats
    zone_data = []
    for zone in zones:
        zone_candidates = skillzone_candidates.filter(skill_zone_id=zone)
        zone_data.append({
            'zone': zone,
            'candidate_count': zone.candidate_count,
            'avg_confidence': zone.avg_confidence,
            'matching_candidates': zone_candidates[:5],  # Top 5
            'relevance_score': calculate_relevance_score(zone, keywords)
        })
    
    # Trier par score de pertinence
    zone_data.sort(key=lambda x: x['relevance_score'], reverse=True)
    
    # Préparer les données des candidats
    candidate_data = []
    for sz_candidate in skillzone_candidates:
        candidate_data.append({
            'candidate': sz_candidate.candidate_id,
            'zone': sz_candidate.skill_zone_id,
            'confidence': sz_candidate.confidence_score,
            'source': sz_candidate.source_tag,
            'skills': sz_candidate.classification_details.get('extracted_skills', []) if sz_candidate.classification_details else [],
            'professional_level': sz_candidate.classification_details.get('professional_level', 'unknown') if sz_candidate.classification_details else 'unknown'
        })
    
    results['zones'] = zone_data
    results['candidates'] = candidate_data
    results['total_candidates'] = len(candidate_data)
    
    return results


async def semantic_search(query, company_id, filter_by_zone=None, min_confidence=0.5):
    """Recherche sémantique utilisant les embeddings de l'IA"""
    
    results = {
        'zones': [],
        'candidates': [],
        'total_candidates': 0
    }
    
    if not query:
        return results
    
    try:
        classifier = get_skillzone_classifier()
        ai_config = await classifier._get_ai_config(company_id)
        
        if not ai_config:
            logger.error("Pas de configuration IA pour la recherche sémantique")
            return keyword_search(query, company_id, filter_by_zone, min_confidence)
        
        # Générer l'embedding de la requête
        query_embedding = await generate_query_embedding(query, ai_config)
        
        # Rechercher les zones avec embeddings similaires
        zones = await find_similar_zones(query_embedding, company_id, filter_by_zone)
        
        # Rechercher les candidats basés sur leurs compétences extraites
        candidates = await find_similar_candidates(query_embedding, company_id, filter_by_zone, min_confidence)
        
        results['zones'] = zones
        results['candidates'] = candidates
        results['total_candidates'] = len(candidates)
        
    except Exception as e:
        logger.error(f"Erreur recherche sémantique: {str(e)}")
        # Fallback sur recherche par mots-clés
        return keyword_search(query, company_id, filter_by_zone, min_confidence)
    
    return results


def hybrid_search(query, company_id, filter_by_zone=None, min_confidence=0.5):
    """Recherche hybride combinant mots-clés et sémantique"""
    
    # Obtenir les résultats des deux méthodes
    keyword_results = keyword_search(query, company_id, filter_by_zone, min_confidence)
    semantic_results = semantic_search(query, company_id, filter_by_zone, min_confidence)
    
    # Fusionner et pondérer les résultats
    combined_results = {
        'zones': [],
        'candidates': [],
        'total_candidates': 0
    }
    
    # Fusion des zones avec pondération
    zone_scores = {}
    
    # Scores des mots-clés (poids 0.4)
    for zone_data in keyword_results['zones']:
        zone_id = zone_data['zone'].id
        zone_scores[zone_id] = {
            'data': zone_data,
            'keyword_score': zone_data['relevance_score'] * 0.4,
            'semantic_score': 0
        }
    
    # Scores sémantiques (poids 0.6)
    for zone_data in semantic_results['zones']:
        zone_id = zone_data['zone'].id
        if zone_id in zone_scores:
            zone_scores[zone_id]['semantic_score'] = zone_data['relevance_score'] * 0.6
        else:
            zone_scores[zone_id] = {
                'data': zone_data,
                'keyword_score': 0,
                'semantic_score': zone_data['relevance_score'] * 0.6
            }
    
    # Calculer les scores finaux et trier
    final_zones = []
    for zone_id, scores in zone_scores.items():
        total_score = scores['keyword_score'] + scores['semantic_score']
        zone_data = scores['data']
        zone_data['relevance_score'] = total_score
        final_zones.append(zone_data)
    
    final_zones.sort(key=lambda x: x['relevance_score'], reverse=True)
    
    # Fusion des candidats (éliminer les doublons)
    seen_candidates = set()
    final_candidates = []
    
    for candidate in keyword_results['candidates'] + semantic_results['candidates']:
        candidate_id = candidate['candidate'].id
        if candidate_id not in seen_candidates:
            seen_candidates.add(candidate_id)
            final_candidates.append(candidate)
    
    combined_results['zones'] = final_zones
    combined_results['candidates'] = final_candidates
    combined_results['total_candidates'] = len(final_candidates)
    
    return combined_results


def calculate_relevance_score(zone, keywords):
    """Calcule un score de pertinence pour une zone par rapport aux mots-clés"""
    score = 0
    
    # Titre (poids élevé)
    for keyword in keywords:
        if keyword in zone.title.lower():
            score += 3
    
    # Description (poids moyen)
    if zone.description:
        for keyword in keywords:
            score += zone.description.lower().count(keyword) * 2
    
    # Mots-clés de la zone (poids élevé)
    if zone.keywords:
        zone_keywords_lower = [k.lower() for k in zone.keywords]
        for keyword in keywords:
            if keyword in zone_keywords_lower:
                score += 3
    
    # Compétences typiques (poids moyen)
    if zone.typical_skills:
        skills_lower = [s.lower() for s in zone.typical_skills]
        for keyword in keywords:
            if keyword in skills_lower:
                score += 2
    
    # Bonus pour le nombre de candidats
    score += min(zone.candidate_count * 0.1, 5)
    
    return score


@login_required
@hx_request_required
def skillzone_search_autocomplete(request):
    """Autocomplétion pour la recherche"""
    query = request.GET.get('q', '').lower()
    company_id = request.user.employee_get.company_id
    
    if len(query) < 2:
        return JsonResponse({'suggestions': []})
    
    suggestions = set()
    
    # Suggestions depuis les titres de zones
    zones = SkillZone.objects.filter(
        title__icontains=query,
        company_id=company_id,
        is_active=True
    ).values_list('title', flat=True)[:5]
    suggestions.update(zones)
    
    # Suggestions depuis les mots-clés
    keyword_zones = SkillZone.objects.filter(
        keywords__icontains=query,
        company_id=company_id,
        is_active=True
    )
    for zone in keyword_zones[:3]:
        if zone.keywords:
            matching_keywords = [k for k in zone.keywords if query in k.lower()]
            suggestions.update(matching_keywords[:2])
    
    # Suggestions depuis les compétences typiques
    skill_zones = SkillZone.objects.filter(
        typical_skills__icontains=query,
        company_id=company_id,
        is_active=True
    )
    for zone in skill_zones[:3]:
        if zone.typical_skills:
            matching_skills = [s for s in zone.typical_skills if query in s.lower()]
            suggestions.update(matching_skills[:2])
    
    return JsonResponse({
        'suggestions': list(suggestions)[:10]
    })


# Fonctions helper pour la recherche sémantique (à implémenter selon vos besoins)
async def generate_query_embedding(query, ai_config):
    """Génère un embedding pour la requête de recherche"""
    # TODO: Implémenter avec Together AI
    # Pour l'instant, retourner un embedding factice
    return [0.1] * 768


async def find_similar_zones(query_embedding, company_id, filter_by_zone):
    """Trouve les zones similaires basées sur les embeddings"""
    # TODO: Implémenter la similarité cosinus
    # Pour l'instant, retourner des résultats vides
    return []


async def find_similar_candidates(query_embedding, company_id, filter_by_zone, min_confidence):
    """Trouve les candidats similaires basés sur les embeddings"""
    # TODO: Implémenter la similarité cosinus
    # Pour l'instant, retourner des résultats vides
    return []