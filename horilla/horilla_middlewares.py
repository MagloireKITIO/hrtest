"""
horilla_middlewares.py

This module is used to register horilla's middlewares without affecting the horilla/settings.py
"""

import threading

from django.http import HttpResponseNotAllowed
from django.shortcuts import render

from horilla.settings import MIDDLEWARE

MIDDLEWARE.append("base.middleware.CompanyMiddleware")
MIDDLEWARE.append("horilla.horilla_middlewares.MethodNotAllowedMiddleware")
MIDDLEWARE.append("horilla.horilla_middlewares.ThreadLocalMiddleware")
MIDDLEWARE.append("accessibility.middlewares.AccessibilityMiddleware")
_thread_locals = threading.local()


_thread_locals = threading.local()

class ThreadLocalMiddleware:
    """
    Middleware pour gérer la requête dans thread_locals de manière sécurisée
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Sauvegarder la requête dans thread_locals
        _thread_locals.request = request
        
        try:
            # Exécuter la vue et obtenir la réponse
            response = self.get_response(request)
            return response
            
        finally:
            # Nettoyage systématique des thread_locals
            self._cleanup()
    
    def _cleanup(self):
        """
        Nettoie les données stockées dans thread_locals
        """
        if hasattr(_thread_locals, 'request'):
            del _thread_locals.request

    def process_exception(self, request, exception):
        """
        Assure le nettoyage même en cas d'exception
        """
        self._cleanup()
        return None

# Fonction utilitaire pour obtenir la requête actuelle
def get_current_request():
    """
    Récupère la requête actuelle de manière sécurisée
    """
    try:
        return getattr(_thread_locals, 'request', None)
    except AttributeError:
        return None


class MethodNotAllowedMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if isinstance(response, HttpResponseNotAllowed):
            return render(request, "405.html")
        return response
