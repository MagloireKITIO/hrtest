"""
Configuration Google Calendar
"""
import os
from django.conf import settings

class GoogleSettings:
    @staticmethod
    def get_credentials():
        """Retourne les credentials Google selon l'environnement"""
        if 'WEBSITE_HOSTNAME' in os.environ:
            return {
                "web": {
                    "client_id": os.environ['GOOGLE_CLIENT_ID'],
                    "project_id": os.environ['GOOGLE_PROJECT_ID'],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                    "client_secret": os.environ['GOOGLE_CLIENT_SECRET'],
                    "redirect_uri": [os.environ['GOOGLE_REDIRECT_URI']]
                }
            }
        return {
            "web": {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "project_id": settings.GOOGLE_PROJECT_ID,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_REDIRECT_URIS
            }
        }

# Paramètres par défaut pour le développement
DEFAULT_SETTINGS = {
    'GOOGLE_CLIENT_ID': '981620828584-cpc1digkh0batp28bm530f4innrekai2.apps.googleusercontent.com',
    'GOOGLE_PROJECT_ID': 'activahr',
    'GOOGLE_CLIENT_SECRET': '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',
    'GOOGLE_REDIRECT_URIS': [
        "http://localhost:8000/oauth2callback/",
        "http://localhost:8080/oauth2callback/",
        "http://127.0.0.1:8000/oauth2callback/",
    ]
}