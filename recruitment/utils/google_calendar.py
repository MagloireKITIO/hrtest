import json
import logging
import os.path
import pickle
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect
from django.core.cache import cache
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from django.urls import reverse

logger = logging.getLogger(__name__)

SCOPES = [
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/calendar.events'
]

class FlowData:
    """Classe pour stocker les données essentielles du Flow"""
    def __init__(self, client_config, scopes, redirect_uri, state=None):
        self.client_config = client_config
        self.scopes = scopes
        self.redirect_uri = redirect_uri
        self.state = state

    def to_flow(self):
        """Recrée un objet Flow à partir des données stockées"""
        flow = Flow.from_client_config(
            self.client_config,
            self.scopes,
            redirect_uri=self.redirect_uri
        )
        if self.state:
            flow.state = self.state
        return flow

def get_callback_url(request):
    """Retourne l'URL de callback selon l'environnement"""
    if 'WEBSITE_HOSTNAME' in os.environ:
        return f"https://{os.environ['WEBSITE_HOSTNAME']}/oauth2callback/"
    return request.build_absolute_uri('/oauth2callback/')

def clear_invalid_token():
    """Supprime le token existant s'il est invalide"""
    token_path = os.path.join(settings.BASE_DIR, 'token.pickle')
    try:
        if os.path.exists(token_path):
            os.remove(token_path)
            logger.info("Token invalide supprimé")
    except Exception as e:
        logger.error(f"Erreur lors de la suppression du token: {e}")

def get_google_calendar_service(request=None):
    """
    Initialise et retourne le service Google Calendar.
    Gère l'authentification OAuth2 si nécessaire.
    """
    try:
        logger.info("Initialisation du service Google Calendar")
        creds = None
        token_path = os.path.join(settings.BASE_DIR, 'token.pickle')

        # Vérification des credentials
        if not hasattr(settings, 'GOOGLE_CALENDAR_CREDENTIALS'):
            raise ValueError("GOOGLE_CALENDAR_CREDENTIALS manquant dans settings")

        # Essai de chargement du token existant
        try:
            if os.path.exists(token_path):
                with open(token_path, 'rb') as token:
                    creds = pickle.load(token)
        except Exception as e:
            logger.warning(f"Token invalide ou corrompu: {e}")
            clear_invalid_token()
            creds = None

        # Vérification et utilisation du token
        if creds and creds.valid:
            try:
                service = build('calendar', 'v3', credentials=creds)
                service.calendarList().list().execute()  # Test du service
                return service
            except Exception as e:
                logger.warning(f"Test de service échoué: {e}")
                clear_invalid_token()
                creds = None

        # Rafraîchissement du token expiré
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                with open(token_path, 'wb') as token:
                    pickle.dump(creds, token)
                return build('calendar', 'v3', credentials=creds)
            except Exception as e:
                logger.warning(f"Échec du rafraîchissement: {e}")
                clear_invalid_token()
                creds = None

        # Initialisation du flow OAuth2
        if request:
            callback_url = get_callback_url(request)
            if 'WEBSITE_HOSTNAME' not in os.environ:  # En développement
                os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
            flow = Flow.from_client_config(
                settings.GOOGLE_CALENDAR_CREDENTIALS,
                SCOPES,
                redirect_uri=callback_url
            )

            auth_url, state = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true'
            )

            # Stocker les données du flow
            flow_data = FlowData(
                settings.GOOGLE_CALENDAR_CREDENTIALS,
                SCOPES,
                callback_url,
                state
            )
            
            # Stocker les données dans le cache
            cache.set(f'oauth_flow_{state}', pickle.dumps(flow_data.__dict__), 3600)
            
            if request.session.get('return_to'):
                cache.set(f'return_to_{state}', request.session['return_to'], 3600)

            return HttpResponse(f"""
                <script>
                    window.location.href = "{auth_url}";
                </script>
            """)
        
        raise ValueError("Request object required for OAuth2 flow")

    except Exception as e:
        logger.error(f"Erreur dans get_google_calendar_service: {e}")
        clear_invalid_token()
        raise

def create_calendar_event(service, event_details):
    """
    Crée un événement dans Google Calendar
    """
    try:
        if not service:
            raise ValueError("Service Google Calendar non initialisé")

        event = {
            'summary': event_details['summary'],
            'description': event_details['description'],
            'start': {
                'dateTime': event_details['start_time'],
                'timeZone': settings.TIME_ZONE,
            },
            'end': {
                'dateTime': event_details['end_time'],
                'timeZone': settings.TIME_ZONE,
            },
            'attendees': event_details['attendees'],
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'email', 'minutes': 24 * 60},
                    {'method': 'popup', 'minutes': 30},
                ],
            },
            'conferenceData': {
                'createRequest': {
                    'requestId': f"meet_{event_details['id']}",
                    'conferenceSolutionKey': {'type': 'hangoutsMeet'}
                }
            },
        }

        created_event = service.events().insert(
            calendarId='primary',
            body=event,
            conferenceDataVersion=1,
            sendUpdates='all'
        ).execute()
        
        logger.info(f"Événement créé: {created_event.get('id')}")
        return created_event

    except Exception as e:
        logger.error(f"Erreur création événement: {e}")
        return None

def handle_oauth2callback(request):
    """
    Gère le callback OAuth2 de Google
    """
    try:
        state = request.GET.get('state')
        if not state:
            raise ValueError("État OAuth manquant")

        # Récupérer les données du flow depuis le cache
        flow_data_pickle = cache.get(f'oauth_flow_{state}')
        if not flow_data_pickle:
            raise ValueError("Session OAuth expirée")

        # Recréer le flow
        flow_data_dict = pickle.loads(flow_data_pickle)
        flow_data = FlowData(**flow_data_dict)
        flow = flow_data.to_flow()

        # Récupérer l'URL de retour
        return_to = cache.get(f'return_to_{state}')

        flow.fetch_token(authorization_response=request.build_absolute_uri())
        creds = flow.credentials

        # Sauvegarder le token
        token_path = os.path.join(settings.BASE_DIR, 'token.pickle')
        with open(token_path, 'wb') as token:
            pickle.dump(creds, token)

        # Nettoyer le cache
        cache.delete(f'oauth_flow_{state}')
        cache.delete(f'return_to_{state}')

        logger.info("Authentification réussie")
        
        if return_to:
            return redirect(return_to)
        return redirect('pipeline')

    except Exception as e:
        logger.error(f"Erreur dans oauth2callback: {e}")
        messages.error(request, "Échec de l'authentification Google")
        return redirect('pipeline')